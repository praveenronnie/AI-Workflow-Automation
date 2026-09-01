"""
Modal GPU inference for Docling.
DocumentConverter loaded once during container startup. Delegates extraction to
DoclingProcessor (shared business logic). Only Modal-specific lifecycle and
temporary file handling lives here.
"""

import logging
import modal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = modal.App("docling-inference")

image = (
    modal.Image.debian_slim()
    .apt_install(
        "libgl1",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender1",
        "poppler-utils",
    )
    .pip_install(
        "docling==2.51.0",
        "easyocr",
    )
    .add_local_file(
        local_path="inspection_ai/services/inference/modal_executor.py",
        remote_path="/root/inspection_ai/services/inference/modal_executor.py",
    )
    .add_local_file(
        local_path="inspection_ai/services/docling_processor.py",
        remote_path="/root/inspection_ai/services/docling_processor.py",
    )
)

GPU = "L4"
MODAL_TIMEOUT = 600


@app.cls(
    image=image,
    gpu=GPU,
    timeout=MODAL_TIMEOUT,
    scaledown_window=300,
    secrets=[modal.Secret.from_name("openquire-env")],
)
class DoclingInference:
    """Docling inference container. DocumentConverter loaded once at container start."""

    @modal.enter()
    def __enter__(self):
        from inspection_ai.services.docling_processor import (
            DoclingProcessor,
        )

        logger.info("Loading DoclingProcessor on container start")
        self.processor = DoclingProcessor()
        logger.info("DoclingProcessor loaded successfully")

    @modal.method()
    def process_pdf(
        self,
        pdf_bytes: bytes,
        report_id: str,
        file_id: str,
        file_name: str,
        file_hash: str,
        user_id: str,
    ) -> dict:
        import os
        import tempfile

        logger.info(
            "DoclingInference.process_pdf called — %d bytes, report_id=%s, file_id=%s",
            len(pdf_bytes),
            report_id,
            file_id,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            result = self.processor.extract_raw_texts(
                tmp_path,
                report_id=report_id,
                file_id=file_id,
                file_name=file_name,
                file_hash=file_hash,
                user_id=user_id,
            )
            logger.info(
                "DoclingInference.process_pdf completed — report_id=%s, file_id=%s",
                report_id,
                file_id,
            )
            return result
        except Exception as e:
            logger.error(
                "DoclingInference.process_pdf failed — report_id=%s, file_id=%s, error=%s",
                report_id,
                file_id,
                e,
            )
            raise
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                logger.debug("Temp file cleaned up — path=%s", tmp_path)

    @modal.method()
    def extract_raw_text(self, pdf_bytes: bytes) -> str:
        import os
        import tempfile

        logger.info(
            "DoclingInference.extract_raw_text called — %d bytes",
            len(pdf_bytes),
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            result = self.processor.extract_raw_texts(tmp_path)
            logger.info("DoclingInference.extract_raw_text completed")
            # Extract text from chunks
            if isinstance(result, dict) and "chunks" in result:
                chunks = result["chunks"]
                return "\n\n".join(chunk.get("content", "") for chunk in chunks)
            return str(result)
        except Exception as e:
            logger.error(
                "DoclingInference.extract_raw_text failed — error=%s",
                e,
            )
            raise
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                logger.debug("Temp file cleaned up — path=%s", tmp_path)


@app.function(image=image)
def warmup():
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    print("Docling initialized successfully.")


@app.function(image=image)
def test_run(
    pdf_path: str,
    report_id: str = "local-test",
):
    from inspection_ai.services.docling_processor import (
        DoclingProcessor,
    )

    processor = DoclingProcessor()
    result = processor.extract_raw_text(pdf_path)
    result["report_id"] = report_id
    return result
