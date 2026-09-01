
from .base_extractor import BaseExtractor
from .pdf_extractor import PDFExtractor
from .image_extractor import ImageExtractor
from .handwritten_extractor import HandwrittenExtractor
from .zip_extractor import ZipExtractor
from inspection_ai.services.llm_client import LLMClient
from inspection_ai.config import Settings
from inspection_ai.services.docling_processor import DoclingProcessor
from inspection_ai.services.inference.modal_executor import ModalExecutor

settings = Settings()


class ExtractorRegistry:
    def __init__(self, config=None, vector_store=None):
        self.vector_store = vector_store
        self.pdf = PDFExtractor(
            config=config,
            vector_store=vector_store,
            docling=DoclingProcessor(),
            modal_executor=ModalExecutor(),
        )

        self.image = ImageExtractor(
            config=config,
            vector_store=vector_store,
            llm_client=LLMClient(
                primary_model=settings.llm_image_primary,
                fallback_model=settings.llm_image_fallback,
            ),
        )

        self.handwritten = HandwrittenExtractor(
            config=config,
            vector_store=vector_store,
            llm_client=LLMClient(
                primary_model=settings.llm_pdf_primary,
                fallback_model=settings.llm_pdf_fallback,
            ),
        )
        self.zip = ZipExtractor(self.pdf, self.image)
        self.extractors = {
            "pdf": self.pdf,
            "image": self.image,
            "handwritten": self.handwritten,
            "zip": self.zip,
        }

    def get(self, input_type: str):
        if input_type not in self.extractors:
            raise ValueError("No extractor for {}".format(input_type))
        return self.extractors[input_type]

    def register(self, name: str, extractor: BaseExtractor):
        self.extractors[name] = extractor
