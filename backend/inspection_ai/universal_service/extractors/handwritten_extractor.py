import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import List

import fitz
from PIL import Image

from inspection_ai.config import get_report_storage_path, get_settings
from inspection_ai.prompts.image_inspection.image_inspect_prompt import (
    handwritten_pdf_extraction_prompt,
)
from inspection_ai.services.aggregators.pdf_aggregator import aggregate_pdf_data
from inspection_ai.services.llm_client import LLMClient
from inspection_ai.universal_service.models.evidence import Evidence

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

MAX_LLM_WORKERS = 3


def _call_llm_with_retry(operation, description):
    """Call an LLM operation with bounded retries and exponential backoff."""
    for attempt in range(3):
        try:
            result = operation()
            if result:
                return result
            logger.warning(
                "llm returned empty for %s attempt=%s", description, attempt + 1
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "llm call failed for %s attempt=%s error=%s",
                description,
                attempt + 1,
                e,
            )
        if attempt == 2:
            break
        time.sleep(2**attempt)
    return {}


_TAGGED_LEAF_KEYS = {"value", "source", "page_number", "confidence"}


def _flatten_node(obj, prefix, out):
    """Recursively flatten an aggregated dict/list tree into (field_name, leaf) pairs.

    A "leaf" is any dict whose keys are all within ``_TAGGED_LEAF_KEYS`` and that
    contains a ``value`` key, or any scalar.
    """
    if isinstance(obj, dict):
        if obj and set(obj.keys()).issubset(_TAGGED_LEAF_KEYS) and "value" in obj:
            out.append((prefix, obj))
            return
        for k, v in obj.items():
            nxt = "{}.{}".format(prefix, k) if prefix else str(k)
            _flatten_node(v, nxt, out)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            nxt = "{}.{}".format(prefix, i) if prefix else str(i)
            _flatten_node(item, nxt, out)
    else:
        out.append((prefix, {"value": obj}))


class HandwrittenExtractor(BaseExtractor):
    def __init__(self, llm_client=None, config=None, vector_store=None):
        super().__init__(llm_client or LLMClient(), config)
        self.vector_store = vector_store

    def extract(
        self,
        file_id,
        pdf_bytes: bytes,
        report_id: str,
        session_id: str,
        batch_id: str,
        filename: str = "document.pdf",
        user_id: str = None,
        document_id: str = None,
    ) -> List[Evidence]:
        document_hash = hashlib.sha256(pdf_bytes).hexdigest()
        logger.info(
            "[PDF/HANDWRITTEN] extract started: file_id=%s report_id=%s filename=%s size_bytes=%d user_id=%s",
            file_id,
            report_id,
            filename,
            len(pdf_bytes),
            user_id,
        )
        try:
            aggregated = self.process_handwritten_pdf(
                pdf_bytes=pdf_bytes,
                report_id=report_id,
                filename=filename,
                file_id=file_id,
            )
            logger.info(
                "[PDF/HANDWRITTEN] Aggregation complete: file_id=%s report_id=%s",
                file_id,
                report_id,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                "[PDF/HANDWRITTEN] extract FAILED: file_id=%s report_id=%s error=%s",
                file_id,
                report_id,
                e,
                exc_info=True,
            )
            return []
        evidence = self._aggregated_to_evidence(
            aggregated,
            file_id,
            report_id,
            session_id,
            batch_id,
            user_id,
            document_hash,
            filename,
            document_id=document_id,
        )
        logger.info(
            "[PDF/HANDWRITTEN] extract complete: file_id=%s report_id=%s evidence=%d",
            file_id,
            report_id,
            len(evidence),
        )
        return evidence

    # ------------------------------------------------------------------
    # PDF -> images -> LLM -> aggregation
    # ------------------------------------------------------------------
    def process_handwritten_pdf(
        self, pdf_bytes: bytes, report_id: str, filename: str, file_id: str
    ) -> dict:
        storage = get_report_storage_path(report_id)
        for key in ("original", "processed", "json"):
            os.makedirs(storage[key], exist_ok=True)

        original_path = os.path.join(storage["original"], filename)
        with open(original_path, "wb") as f:
            f.write(pdf_bytes)

        image_paths = self.convert_pdf_to_images(original_path, storage["processed"])
        logger.info(
            "converted %s pages for handwritten pdf %s",
            len(image_paths),
            original_path,
        )

        extracted_data = self.process_images_batch(image_paths)
        with open(
            os.path.join(storage["json"], "handwritten_extracted.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(extracted_data, f, indent=2)

        aggregated = aggregate_pdf_data(pca_responses=extracted_data)
        with open(
            os.path.join(storage["json"], "pdf_aggregated.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(aggregated, f, indent=2)

        return aggregated

    def convert_pdf_to_images(self, pdf_path: str, output_dir: str) -> list:
        os.makedirs(output_dir, exist_ok=True)
        doc = fitz.open(pdf_path)
        image_paths = []
        try:
            for i, page in enumerate(doc):
                image_paths.append(self._save_page_as_image(page, i, output_dir))
        finally:
            doc.close()
        return image_paths

    def _save_page_as_image(self, page, index: int, output_dir: str) -> str:
        pix = page.get_pixmap(dpi=300)
        path = os.path.join(output_dir, "page_{}.png".format(index + 1))
        pix.save(path)
        return path

    def get_worker_count(self, total_batches: int) -> int:
        if total_batches <= 2:
            return 2
        return min(MAX_LLM_WORKERS, total_batches)

    def process_images_batch(self, image_paths: list) -> list:
        """Process every rendered page in parallel.

        Each page is submitted to a thread pool bounded by
        ``settings.max_concurrent_llm_calls`` so the VLM provider isn't
        hammered, while page-level parallelism replaces the previous
        sequential per-batch loop.  Page rendering stays at ``dpi=300``
        (see ``_save_page_as_image``).  Results keep 1-based page order.
        """
        if not image_paths:
            return []
        max_workers = max(
            1,
            min(get_settings().max_concurrent_llm_calls, len(image_paths)),
        )
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._process_single_image, idx + 1, path): idx
                for idx, path in enumerate(image_paths)
            }
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        results.append(res)
                except Exception as e:  # noqa: BLE001
                    logger.error("image processing failed error=%s", e)
        results.sort(key=lambda item: item["image_id"])
        return results

    def _process_single_image(self, image_id: int, image_path: str) -> dict:
        try:
            image = Image.open(image_path)
            response = self.process_image_with_llm(image)
        except Exception as e:  # noqa: BLE001
            logger.error("image processing failed for %s error=%s", image_path, e)
            response = {}
        return {"image_id": image_id, "image_data": response}

    def process_image_batch(self, image_paths: list, start_index: int) -> list:
        """Compatibility shim; per-page work is done by _process_single_image."""
        extracted = []
        for offset, image_path in enumerate(image_paths):
            extracted.append(
                self._process_single_image(start_index + offset + 1, image_path)
            )
        return extracted

    def process_image_with_llm(self, image: Image.Image) -> dict:
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        image_b64 = base64.b64encode(buffer.getvalue()).decode()
        payload = [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,{}".format(image_b64)},
            },
            {"type": "text", "text": handwritten_pdf_extraction_prompt()},
        ]
        return _call_llm_with_retry(
            lambda: self.llm.process_llm_request(payload, max_tokens=4096),
            "handwritten page",
        )

    # ------------------------------------------------------------------
    # Aggregated dict -> Evidence (+ Qdrant chunks)
    # ------------------------------------------------------------------
    def _aggregated_to_evidence(
        self,
        aggregated: dict,
        file_id,
        report_id: str,
        session_id: str,
        batch_id: str,
        user_id: str,
        document_hash: str,
        filename: str,
        document_id: str = None,
    ) -> List[Evidence]:
        if not aggregated:
            return []

        leaves = []
        _flatten_node(aggregated, "", leaves)

        evidence = []
        chunks = []
        for field_name, leaf in leaves:
            value = leaf.get("value")
            if value is None or (isinstance(value, str) and value.strip() == ""):
                continue
            source_ref = leaf.get("page_number") or leaf.get("source") or "handwritten"
            try:
                confidence = float(leaf.get("confidence") or 0.8)
            except (TypeError, ValueError):
                confidence = 0.8

            ev = self.build_evidence(
                field_name=field_name,
                value=value,
                source_type="handwritten_pdf",
                source_ref=str(source_ref),
                report_id=report_id,
                session_id=session_id,
                batch_id=batch_id,
                confidence=confidence,
                raw_text=(
                    json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                )[:500],
                document_hash=document_hash,
                file_id=file_id,
                document_id=document_id,
                tags=["handwritten", "pdf"],
                extraction_model="handwritten_vlm",
                category="handwritten",
                user_id=user_id,
            )
            evidence.append(ev)
            chunks.append(
                {
                    "id": ev.id,
                    "content": "{}: {}".format(field_name, ev.raw_text),
                    "metadata": {
                        "user_id": user_id,
                        "report_id": report_id,
                        "file_id": file_id,
                        "document_id": document_id,
                        "file_name": filename,
                        "source_type": "handwritten_pdf",
                        "source_ref": str(source_ref),
                        "field_name": field_name,
                        "value": value,
                        "confidence": confidence,
                    },
                }
            )

        if chunks and self.vector_store is not None:
            try:
                # _aggregated_to_evidence runs in a worker thread (no event loop),
                # so asyncio.run is safe here.  This actually persists the
                # embeddings (previously the async call was never awaited).
                asyncio.run(
                    self.vector_store.encode_and_store(report_id, user_id, chunks)
                )
                logger.info(
                    "[PDF/HANDWRITTEN] Embeddings stored: file_id=%s report_id=%s chunks=%d",
                    file_id,
                    report_id,
                    len(chunks),
                )
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[PDF/HANDWRITTEN] Failed to embed/store handwritten chunks: file_id=%s report_id=%s error=%s",
                    file_id,
                    report_id,
                    e,
                )

        return evidence
