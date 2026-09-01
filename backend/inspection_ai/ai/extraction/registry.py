
from .base_extractor import BaseExtractor
from .pdf_extractor import PDFExtractor
from .image_extractor import ImageExtractor
from .handwritten_extractor import HandwrittenExtractor
from .zip_extractor import ZipExtractor
from inspection_ai.ai.providers.llm_client import LLMClient


class ExtractorRegistry:
    def __init__(
        self,
        config=None,
        vector_store=None,
        llm: LLMClient = None,
        modal_executor=None,
    ):
        self.vector_store = vector_store
        self.llm = llm
        self.modal_executor = modal_executor
        self.pdf = PDFExtractor(
            config=config,
            vector_store=vector_store,
            llm_client=llm,
            modal_executor=modal_executor,
        )
        self.image = ImageExtractor(
            config=config,
            vector_store=vector_store,
            llm_client=llm,
        )
        self.handwritten = HandwrittenExtractor(
            config=config,
            vector_store=vector_store,
            llm_client=llm,
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
