"""Shared helpers for FormIQ test scripts (testing/ folder)."""

import io
import sys
import uuid

import httpx

FAILS: list = []


def check(name: str, ok: bool, detail: str = ""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('--- ' + detail) if detail else ''}")
    if not ok:
        FAILS.append(name)


def client(base: str) -> httpx.Client:
    return httpx.Client(
        base_url=base, timeout=120,
        transport=httpx.HTTPTransport(retries=3),
    )


def signup_login(c: httpx.Client, tag: str = "t") -> dict:
    """Register + login; returns auth headers."""
    email = f"{tag}_{uuid.uuid4().hex[:8]}@test.local"
    c.post("/auth/register", json={"email": email, "password": "S3cure-Passw0rd!"})
    tok = c.post(
        "/auth/token", data={"username": email, "password": "S3cure-Passw0rd!"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, email


def finish(module: str) -> int:
    print(f"\n==== {module} ====")
    print(f"fails={len(FAILS)}")
    return 1 if FAILS else 0


def new_rid(c, h) -> str:
    """Create a report + acquire lock; returns report id."""
    import uuid as _uuid
    rid = c.post("/reports/link", headers=h,
                 json={"source_url": f"https://x/{_uuid.uuid4().hex}"}).json()["report_id"]
    c.post(f"/reports/{rid}/lock", headers=h)
    return rid


def pdf(text: str = "Site Assessment Report", size: str = "small") -> bytes:
    """Structurally valid PDF. size='rich' embeds multiple text lines."""
    lines = [text]
    if size == "rich":
        lines += [
            "Property Address: 1247 Willow Creek Road, Springfield, IL 62704",
            "FOUNDATION: The foundation is a poured concrete slab-on-grade.",
            "ROOF: Asphalt shingle roof, some lifting near chimney flashing.",
            "ELECTRICAL: 200-amp panel, two GFCI outlets failed testing.",
        ]
    content = b"BT /F1 11 Tf 72 720 Td 14 TL\n"
    for ln in lines:
        safe = ln.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content += f"({safe}) Tj T*\n".encode()
    content += b"ET"
    stream = f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        stream,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objects, 1):
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    out.write(b"trailer\n<< /Size 6 /Root 1 0 R >>\n%%EOF")
    return out.getvalue()


def png() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc00000030101"
        "00c9fe92ef0000000049454e44ae426082"
    )
