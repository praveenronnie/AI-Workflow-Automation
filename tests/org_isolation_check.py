"""Phase 0 privacy-wall test: cross-org document dedup must NOT resolve.

Two users (each auto-provisioned into their own organization) upload the SAME
file. Expected: the second org gets a NEW document (extraction enqueued),
never a link to the first org's document. Also verifies org 1's report is
invisible to org 2.
"""

import io
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123"
client = httpx.Client(base_url=BASE, timeout=120, transport=httpx.HTTPTransport(retries=3))
fails = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
    if not ok:
        fails.append(name)


def signup_and_login() -> dict:
    email = f"iso_{uuid.uuid4().hex[:8]}@test.local"
    client.post("/auth/register", json={"email": email, "password": "S3cure-Passw0rd!"})
    tok = client.post("/auth/token", data={"username": email, "password": "S3cure-Passw0rd!"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def minimal_pdf() -> bytes:
    content = b"BT /F1 12 Tf 72 720 Td (Org isolation test) Tj ET"
    stream = f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        stream,
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objects, 1):
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    out.write(b"trailer\n<< /Size 5 /Root 1 0 R >>\n%%EOF")
    return out.getvalue()


pdf = minimal_pdf()

# --- Org A ---
hA = signup_and_login()
rA = client.post("/reports/link", headers=hA, json={"source_url": f"https://x/{uuid.uuid4().hex}"})
ridA = rA.json()["report_id"]
client.post(f"/reports/{ridA}/lock", headers=hA)
uA = client.post(
    f"/reports/{ridA}/upload/pdf", headers=hA,
    files=[("files", ("shared.pdf", pdf, "application/pdf"))],
    data={"doc_types": '["scanned"]'},
)
print("org A upload:", uA.status_code, uA.json().get("status"))
check("org A first upload creates document (processing)", uA.json().get("status") == "processing")

# --- Org B: same file ---
hB = signup_and_login()
rB = client.post("/reports/link", headers=hB, json={"source_url": f"https://x/{uuid.uuid4().hex}"})
ridB = rB.json()["report_id"]
client.post(f"/reports/{ridB}/lock", headers=hB)
uB = client.post(
    f"/reports/{ridB}/upload/pdf", headers=hB,
    files=[("files", ("shared.pdf", pdf, "application/pdf"))],
    data={"doc_types": '["scanned"]'},
)
print("org B upload:", uB.status_code, uB.json().get("status"))
check(
    "org B same-hash upload does NOT link across orgs (new doc, not 'linked')",
    uB.json().get("status") != "linked",
    f"status={uB.json().get('status')}",
)

# --- cross-org report invisibility ---
r = client.get(f"/reports/{ridA}", headers=hB)
check("org B cannot read org A report", r.status_code == 404, str(r.status_code))

print("\n==== ORG ISOLATION ====")
print(f"fails={len(fails)}")
sys.exit(1 if fails else 0)

