"""TC-DOCS — document listing/deletion per report."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)
h, _ = _h.signup_login(c, "doc")
rid = c.post("/reports/link", headers=h, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]
c.post(f"/reports/{rid}/lock", headers=h)

png = _h.png()
r = c.post(f"/reports/{rid}/upload/image", headers=h,
           files=[("files", ("img.png", png, "image/png"))])
_h.check("TC-DOCS-001 upload for docs list", r.status_code == 200, r.text[:100])

r = c.get(f"/reports/{rid}", headers=h)
docs = r.json().get("documents", [])
_h.check("TC-DOCS-001b server-authored docs listed", len(docs) >= 1 and docs[0].get("document_id"), str(len(docs)))
doc_id = docs[0]["document_id"] if docs else ""

r = c.delete(f"/reports/{rid}/documents/{doc_id}", headers=h)
_h.check("TC-DOCS-002 delete document", r.status_code == 200, str(r.status_code))
r = c.get(f"/reports/{rid}", headers=h)
docs_after = r.json().get("documents", [])
_h.check("TC-DOCS-002b removed from list", all(d["document_id"] != doc_id for d in docs_after))

r = c.delete(f"/reports/{rid}/documents/{uuid.uuid4().hex}", headers=h)
_h.check("TC-DOCS-003 unknown doc -> 404", r.status_code == 404, str(r.status_code))

rid2 = c.post("/reports/link", headers=h, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]
r = c.delete(f"/reports/{rid2}/documents/{doc_id}", headers=h)
_h.check("TC-DOCS-004 delete without lock -> 409", r.status_code == 409, str(r.status_code))

sys.exit(_h.finish("DOCS"))
