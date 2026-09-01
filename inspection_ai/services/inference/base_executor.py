from abc import ABC, abstractmethod


class InferenceExecutor(ABC):
    @abstractmethod
    async def execute_docling(
        self,
        pdf_path: str,
        report_id: str,
        file_id: str,
        file_name: str,
        file_hash: str,
        user_id: str,
    ): ...

    @abstractmethod
    async def extract_raw_text(self, pdf_path: str) -> str: ...

    @abstractmethod
    async def execute_modal_embedding(self, texts): ...
