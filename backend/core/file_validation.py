"""Content-sniffing validation: reject files whose bytes don't match their
claimed type before they are persisted or enqueued for extraction."""

from fastapi import HTTPException

_MAGICS = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "bmp": [b"BM"],
    "gif": [b"GIF87a", b"GIF89a"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],  # also docx/xlsx
    "webp": [b"RIFF"],  # RIFF....WEBP
}


def _is_webp(head: bytes) -> bool:
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


def validate_upload(filename: str, content: bytes, expected: str) -> None:
    """Raise HTTPException 400 when the content doesn't sniff as ``expected``.

    ``expected``: "pdf" or "image" (png/jpg/bmp/gif/webp/zip).
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    signatures = []
    if expected == "pdf":
        signatures = _MAGICS["pdf"]
    else:
        if ext in _MAGICS:
            signatures = _MAGICS[ext]
        else:
            signatures = [
                sig
                for kinds in ("png", "jpg", "bmp", "gif", "zip", "webp")
                for sig in _MAGICS[kinds]
            ]
    head = content[:16]
    ok = any(head.startswith(sig) for sig in signatures)
    if expected == "image" and _is_webp(head):
        ok = True
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File content does not match its type "
                f"(expected {expected}): {filename}"
            ),
        )
