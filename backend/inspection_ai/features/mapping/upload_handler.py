import io
import zipfile
from enum import Enum
from pathlib import Path
from typing import List, Tuple

from fastapi import HTTPException, UploadFile

try:
    import magic
except ImportError:
    magic = None

from inspection_ai.ai.models.extraction_config import ExtractionConfig


class InputType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    ZIP = "zip"


class UploadedFile:
    def __init__(self, filename: str, content: bytes, content_type: str):
        self.filename = filename
        self.content = content
        self.content_type = content_type
        self.size_mb = len(content) / (1024 * 1024)


class UniversalUploadHandler:
    MAX_FILE_SIZE_MB = 100
    MAX_FILES_PER_REQUEST = 20

    ALLOWED_EXTENSIONS = {
        "pdf": [".pdf"],
        "image": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"],
        "zip": [".zip"],
    }

    ALLOWED_MIME_TYPES = {
        "pdf": ["application/pdf"],
        "image": [
            "image/jpeg",
            "image/png",
            "image/bmp",
            "image/gif",
            "image/tiff",
            "image/webp",
        ],
        "zip": ["application/zip", "application/x-zip-compressed"],
    }

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}

    def __init__(self, config: ExtractionConfig = None):
        self.config = config or ExtractionConfig()

    def validate_and_route(
        self, files: List[UploadFile]
    ) -> Tuple[InputType, List[UploadedFile]]:
        if len(files) > self.MAX_FILES_PER_REQUEST:
            raise HTTPException(
                status_code=400,
                detail="Max " + str(self.MAX_FILES_PER_REQUEST) + " files per request",
            )

        validated_files: List[UploadedFile] = []
        input_type: InputType = None

        for file in files:
            content = file.file.read()

            size_mb = len(content) / (1024 * 1024)
            if size_mb > self.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail="File "
                    + file.filename
                    + " too large: "
                    + str(round(size_mb, 1))
                    + "MB",
                )

            ext = Path(file.filename).suffix.lower()
            if ext not in [".pdf", ".zip"] + list(self.IMAGE_EXTENSIONS):
                raise HTTPException(status_code=400, detail="Invalid extension: " + ext)

            content_type = self.detect_mime(content, ext)
            if ext == ".pdf" and content_type != "application/pdf":
                raise HTTPException(
                    status_code=400, detail="Invalid PDF: " + file.filename
                )
            elif ext in list(self.IMAGE_EXTENSIONS):
                if not content_type.startswith("image/"):
                    raise HTTPException(
                        status_code=400, detail="Invalid image: " + file.filename
                    )
            elif ext == ".zip" and content_type not in self.ALLOWED_MIME_TYPES["zip"]:
                raise HTTPException(
                    status_code=400, detail="Invalid ZIP: " + file.filename
                )

            if input_type is None:
                if ext == ".pdf":
                    input_type = InputType.PDF
                elif ext == ".zip":
                    input_type = InputType.ZIP
                else:
                    input_type = InputType.IMAGE

            validated_files.append(UploadedFile(file.filename, content, content_type))

        if input_type is None:
            input_type = InputType.PDF

        return input_type, validated_files

    def detect_mime(self, content: bytes, ext: str) -> str:
        if magic is not None:
            try:
                return magic.from_buffer(content[:1024], mime=True)
            except Exception:
                pass
        ext_map = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".bmp": "image/bmp",
            ".gif": "image/gif",
            ".tiff": "image/tiff",
            ".webp": "image/webp",
            ".zip": "application/zip",
        }
        return ext_map.get(ext, "application/octet-stream")

    def extract_zip_entries(self, zip_bytes: bytes) -> List[Tuple[str, bytes]]:
        entries = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zip_ref:
            for zip_info in zip_ref.namelist():
                ext = Path(zip_info).suffix.lower()
                if ext == ".pdf" or ext in self.IMAGE_EXTENSIONS:
                    entries.append((zip_info, zip_ref.read(zip_info)))
        return entries
