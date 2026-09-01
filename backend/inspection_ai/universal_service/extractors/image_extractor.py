import base64
import hashlib
import io
import logging
from typing import List
from uuid import uuid4

from inspection_ai.prompts.image_inspection.image_inspect_prompt import (
    visual_updated_prompt,
)
from inspection_ai.services.llm_client import LLMClient
from inspection_ai.universal_service.models.evidence import Evidence
from PIL import Image

from .base_extractor import BaseExtractor, categorize_field

logger = logging.getLogger(__name__)


class ImageExtractor(BaseExtractor):

    def __init__(self, llm_client: LLMClient = None, config=None, vector_store=None):
        super().__init__(llm_client or LLMClient(), config)
        self.batch_size = (config.image_batch_size if config else None) or 10
        self.max_dim = (config.max_image_dim if config else None) or 768
        self.vector_store = vector_store

    def extract(self, image_items: List[tuple]) -> List[dict]:
        logger.info(
            "[IMAGE] extract started: images=%d batch_size=%d",
            len(image_items),
            self.batch_size,
        )
        results: List[dict] = []
        if not image_items:
            return results

        total_batches = (len(image_items) + self.batch_size - 1) // self.batch_size
        for i in range(0, len(image_items), self.batch_size):
            batch = image_items[i : i + self.batch_size]
            batch_no = i // self.batch_size + 1
            logger.info(
                "[IMAGE-BATCH] Processing batch %d/%d: images=%d",
                batch_no,
                total_batches,
                len(batch),
            )
            results.extend(self.process_batch(batch))
            logger.info(
                "[IMAGE-BATCH] Batch %d complete: results=%d",
                batch_no,
                len(results),
            )

        logger.info("[IMAGE] extract finished: results=%d", len(results))
        return results

    def resize_image(self, image_content: bytes, max_dim: int = None) -> bytes:
        max_dim = max_dim or self.max_dim
        resample = getattr(Image, "Resampling", Image).LANCZOS
        try:
            with Image.open(io.BytesIO(image_content)) as image:
                w, h = image.size
                if max(w, h) <= max_dim:
                    return image_content
                scale = max_dim / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                resized = image.resize(new_size, resample)
                buffer = io.BytesIO()
                resized.save(buffer, format="JPEG")
                return buffer.getvalue()
        except Exception as e:  # noqa: BLE001
            logger.warning("[IMAGE] resize_image failed (using original): %s", e)
            return image_content

    def process_batch(self, batch: List[tuple]) -> List[dict]:
        payload = []
        for filename, content in batch:
            if isinstance(content, str):
                content = content.encode("utf-8")
            content = self.resize_image(content)
            image_b64 = base64.b64encode(content).decode()
            payload.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                }
            )
        payload.append({"type": "text", "text": visual_updated_prompt()})

        try:
            response = self.llm.process_llm_request(
                payload, flow_type="image_extraction"
            )
            logger.info(
                "[IMAGE-BATCH] LLM extraction OK: batch_images=%d",
                len(batch),
            )
        except Exception as e:  # noqa: BLE001
            response = {}
            logger.error(
                "[IMAGE-BATCH] LLM extraction FAILED: batch_images=%d error=%s",
                len(batch),
                e,
            )

        items = response.get("results") if isinstance(response, dict) else response
        if not isinstance(items, list):
            items = []

        results = []
        for idx, (filename, content) in enumerate(batch):
            item = (
                items[idx] if idx < len(items) and isinstance(items[idx], dict) else {}
            )
            results.append(
                {
                    "image_id": uuid4().hex,
                    "filename": filename,
                    "content_hash": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                    "observations": self.extract_observations(item),
                }
            )
        return results

    def extract_observations(self, item: dict) -> List[dict]:
        observations = []
        image_id = item.get("image_id")
        building_area = item.get("building_area", "")
        domains = (
            item.get("domains", []) if isinstance(item.get("domains"), list) else []
        )
        for domain_obj in domains:
            domain = domain_obj.get("domain", "")
            for obs in domain_obj.get("observations", []):
                observations.append(
                    {
                        "field_name": obs.get("visual_object", "observation"),
                        "value": obs.get("description", ""),
                        "confidence": obs.get("confidence", 0.7),
                        "category": categorize_field(domain),
                        "tags": [
                            "image",
                            f"image_id:{image_id}",
                            f"area:{building_area}",
                            f"domain:{domain}",
                        ],
                        "raw_text": obs.get("description", ""),
                    }
                )
        return observations

    def to_evidence(
        self,
        results: List[dict],
        file_id,
        report_id: str,
        session_id: str,
        batch_id: str,
        user_id: str = None,
        document_ids: dict = None,
    ) -> List[Evidence]:
        """document_ids: filename -> knowledge-base document id."""
        document_ids = document_ids or {}
        evidence = []
        for res in results:
            # Traceable source ref: uploaded filename + short image id, so a
            # mapped value points back at the actual uploaded image.
            source_ref = "{}#{}".format(
                res.get("filename") or "image", (res.get("image_id") or "")[:8]
            )
            document_id = document_ids.get(res.get("filename"))
            for obs in res.get("observations", []):
                if not obs.get("value"):
                    continue
                content_hash = hashlib.sha256(str(obs["value"]).encode()).hexdigest()
                evidence.append(
                    self.build_evidence(
                        field_name=obs.get("field_name", "observation"),
                        value=obs["value"],
                        source_type="image",
                        source_ref=source_ref,
                        report_id=report_id,
                        session_id=session_id,
                        batch_id=batch_id,
                        user_id=user_id,
                        confidence=obs.get("confidence", 0.7),
                        raw_text=obs.get("raw_text"),
                        content_hash=content_hash,
                        category=obs.get("category"),
                        tags=obs.get("tags", ["image"]),
                        extraction_model=(
                            self.config.llm_model if self.config else "vlm"
                        ),
                        file_id=file_id,
                        document_id=document_id,
                    )
                )
        return evidence

    def build_chunks(
        self, results: List[dict], report_id, user_id=None, document_ids: dict = None
    ) -> List[dict]:
        document_ids = document_ids or {}
        chunks = []
        for res in results:
            document_id = document_ids.get(res.get("filename"))
            for obs in res.get("observations", []):
                if not obs.get("value"):
                    continue
                c_hash = hashlib.sha256(str(obs["value"]).encode()).hexdigest()
                chunks.append(
                    {
                        "id": f"img-{res['image_id']}-{c_hash[:8]}",
                        "content": f"{obs.get('field_name', 'observation')}: {obs['value']}",
                        "metadata": {
                            "user_id": user_id,
                            "report_id": report_id,
                            "document_id": document_id,
                            "file_name": res.get("filename"),
                            "image_id": res.get("image_id"),
                            "source_type": "image",
                            "confidence": obs.get("confidence", 0.7),
                            "field_name": obs.get("field_name", "observation"),
                            "value": obs["value"],
                        },
                    }
                )
        return chunks

    async def save_embeddings(
        self, results: List[dict], report_id, user_id=None, document_ids: dict = None
    ) -> None:
        if self.vector_store is None:
            return
        chunks = self.build_chunks(results, report_id, user_id, document_ids)
        if not chunks:
            return
        try:
            await self.vector_store.encode_and_store(report_id, user_id, chunks)
            logger.info(
                "[IMAGE] Embeddings stored: report_id=%s chunks=%d",
                report_id,
                len(chunks),
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                "[IMAGE] Failed to store embeddings: report_id=%s error=%s",
                report_id,
                e,
            )
