import hashlib
import logging
from typing import List

from inspection_ai.ai.providers.llm_client import LLMClient
from inspection_ai.ai.models.evidence import Evidence
from inspection_ai.ai.providers.docling_processor import DoclingProcessor
from inspection_ai.ai.providers.inference.modal_executor import ModalExecutor

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class PDFExtractor(BaseExtractor):
    def __init__(
        self,
        llm_client: LLMClient = None,
        config=None,
        docling=None,
        vector_store=None,
        modal_executor=None,
    ):
        super().__init__(llm_client or LLMClient(), config)
        self.docling = docling
        self.vector_store = vector_store
        self.modal_executor = modal_executor

    @property
    def docling(self):
        if self._docling is None:
            self._docling = DoclingProcessor()
        return self._docling

    @property
    def get_modal_executor(self) -> ModalExecutor:
        if self.modal_executor is None:
            self.modal_executor = ModalExecutor()
        return self.modal_executor

    @docling.setter
    def docling(self, value):
        self._docling = value

    async def extract(
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
            "[PDF] extract started: file_id=%s report_id=%s filename=%s size_bytes=%d file_hash=%s user_id=%s",
            file_id,
            report_id,
            filename,
            len(pdf_bytes),
            document_hash[:12],
            user_id,
        )
        evidence = []

        try:
            docling_result = await self.get_modal_executor.execute_docling(
                pdf_bytes=pdf_bytes,
                report_id=report_id,
                file_id=file_id,
                file_name=filename,
                file_hash=document_hash,
                user_id=user_id,
            )
            logger.info(
                "[PDF] Docling result received: file_id=%s report_id=%s user_id=%s chunks=%d",
                file_id,
                report_id,
                user_id,
                len(docling_result["chunks"])
                if isinstance(docling_result, dict)
                else 0,
            )

            chunks = []
            for chunk in docling_result["chunks"]:
                content = chunk.get("content", "")
                if not content:
                    continue

                page_no = chunk.get("page_no")
                if isinstance(page_no, list):
                    page_no = page_no[0] if page_no else "unknown"
                # Traceable source ref: pdf filename + page, so a mapped value
                # points at the exact document and page (reports may have many PDFs).
                source_ref = f"{filename}#page-{page_no}" if page_no else f"{filename}#page-unknown"
                content_hash = chunk.get("chunk_content_hash")

                ev = self.build_evidence(
                    field_name="chunk",
                    value=content,
                    source_type="pdf",
                    source_ref=source_ref,
                    report_id=report_id,
                    session_id=session_id,
                    batch_id=batch_id,
                    file_id=file_id,
                    document_id=document_id,
                    user_id=user_id,
                    confidence=1.0,
                    raw_text=content,
                    document_hash=document_hash,
                    content_hash=content_hash,
                    extraction_model="docling_raw",
                    category="raw_chunk",
                    tags=["raw", "unprocessed", "pdf"],
                )
                evidence.append(ev)
                chunks.append(
                    {
                        "id": ev.id,
                        "content": content,
                        "metadata": {
                            "user_id": user_id,
                            "report_id": report_id,
                            "file_id": file_id,
                            "document_id": document_id,
                            "file_name": filename,
                            "page_no": str(page_no),
                            "section": chunk.get("section"),
                            "source_type": "pdf",
                            "source_ref": source_ref,
                            "content_hash": content_hash,
                            "field_name": "chunk",
                            "value": content,
                        },
                    }
                )

            if chunks and self.vector_store is not None:
                try:
                    # encode_and_store is async -> await it directly (the old
                    # run_in_executor call merely returned a coroutine and never
                    # actually persisted the embeddings).
                    await self.vector_store.encode_and_store(report_id, user_id, chunks)
                    logger.info(
                        "[PDF] Embeddings stored: file_id=%s report_id=%s chunks=%d",
                        file_id,
                        report_id,
                        len(chunks),
                    )
                except Exception as e:
                    logger.error(
                        "[PDF] Failed to embed/store pdf chunks: file_id=%s report_id=%s error=%s",
                        file_id,
                        report_id,
                        e,
                    )

            logger.info(
                "[PDF] extract complete: file_id=%s report_id=%s evidence=%d",
                file_id,
                report_id,
                len(evidence),
            )
            return evidence

        except Exception as e:
            logger.error(
                "[PDF] extract FAILED: file_id=%s report_id=%s error=%s",
                file_id,
                report_id,
                e,
                exc_info=True,
            )
            return evidence
