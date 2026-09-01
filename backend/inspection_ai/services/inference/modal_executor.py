import asyncio
import logging

from inspection_ai.services.inference.base_executor import InferenceExecutor
import modal

logger = logging.getLogger(__name__)

MAX_CONCURRENT_PDFS = 3
MAX_RETRIES = 3


async def call_modal_with_retry(operation, description):
    for attempt in range(MAX_RETRIES):
        try:
            return await operation()
        except Exception as e:
            logger.warning(
                "retry attempt %s/%s for %s failed error=%s",
                attempt + 1,
                MAX_RETRIES,
                description,
                e,
            )
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2**attempt)


class ModalExecutor(InferenceExecutor):
    def __init__(self):
        docling_cls = modal.Cls.from_name("docling-inference", "DoclingInference")
        embedding_class = modal.Cls.from_name("embedding-service", "EmbeddingService")

        self.docling_instance = docling_cls()
        self.modal_embedding = embedding_class()

        logger.info(
            "ModalExecutor initialized — Docling instance ready, Embedding instance ready"
        )

    async def execute_modal_embedding(self, texts):
        return await self.modal_embedding.encode_batch.remote.aio(texts)

    async def execute_docling(
        self,
        pdf_bytes: bytes,
        report_id: str,
        file_id: str,
        file_name: str,
        file_hash: str,
        user_id: str,
    ) -> dict:
        logger.info(
            "execute_docling delegating to Modal — File name=%s, report_id=%s, file_id=%s",
            file_name,
            report_id,
            file_id,
        )

        async def operation():
            return await self.docling_instance.process_pdf.remote.aio(
                pdf_bytes=pdf_bytes,
                report_id=report_id,
                file_id=file_id,
                file_name=file_name,
                file_hash=file_hash,
                user_id=user_id,
            )

        return await call_modal_with_retry(
            operation, f"docling report_id={report_id} file_id={file_id}"
        )

    async def extract_raw_text(self, pdf_path: str) -> str:
        logger.info("extract_raw_text delegating to Modal — path=%s", pdf_path)

        async def operation():
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            return await self.docling_instance.extract_raw_text.remote.aio(pdf_bytes)

        return await call_modal_with_retry(operation, "docling raw text")
