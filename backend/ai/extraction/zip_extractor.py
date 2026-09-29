import hashlib
import io
import zipfile
from pathlib import Path
from typing import List

from .pdf_extractor import PDFExtractor
from .image_extractor import ImageExtractor

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


class ZipExtractor:
    def __init__(self, pdf_extractor: PDFExtractor = None, image_extractor: ImageExtractor = None):
        self.pdf_extractor = pdf_extractor or PDFExtractor()
        self.image_extractor = image_extractor or ImageExtractor()

    async def extract(
        self, zip_bytes: bytes, report_id: str, session_id: str, batch_id: str, user_id: str = None
    ) -> List:
        evidence = []
        pdf_files = []
        image_files = []

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zip_ref:
            for zip_info in zip_ref.namelist():
                suffix = Path(zip_info).suffix.lower()
                if suffix == ".pdf":
                    pdf_files.append((zip_info, zip_ref.read(zip_info)))
                elif suffix in IMAGE_EXTENSIONS:
                    image_files.append((zip_info, zip_ref.read(zip_info)))

        for name, content in pdf_files:
            file_id = "zip-" + hashlib.sha256(zip_bytes).hexdigest()[:12] + "-" + Path(name).stem
            evidence.extend(
                await self.pdf_extractor.extract(
                    file_id, content, report_id, session_id, batch_id,
                    filename=Path(name).name, user_id=user_id,
                )
            )

        if image_files:
            image_contents = [(content, Path(name).name) for name, content in image_files]
            file_id = "zip-img-" + hashlib.sha256(zip_bytes).hexdigest()[:12]
            evidence.extend(
                await self.image_extractor.extract(
                    file_id, image_contents, report_id, session_id, batch_id, user_id=user_id,
                )
            )

        return evidence