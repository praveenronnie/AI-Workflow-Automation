"""TC-DOMAIN — registry: list, upload idempotency, dup create, manifests."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)
h, _ = _h.signup_login(c, "dom")

r = c.get("/domains/", headers=h)
domains = r.json()
_h.check("TC-DOMAIN-001 list (seeded)", r.status_code == 200 and len(domains) >= 1, str(len(domains)))
seeded = next((d for d in domains if d.get("name") == "pca_site_assessment"), None)
_h.check("TC-DOMAIN-001b pca_site_assessment present", seeded is not None)

# upload bundle (idempotent upsert)
bundle = {
    "domain_name": f"test_domain_{uuid.uuid4().hex[:6]}",
    "display_name": "Test Domain",
    "version": "1.0.0",
    "description": "created by domain_check",
    "sections": [{"name": "Sec", "aliases": [], "order": 0, "fields": [
        {"name": "FieldA", "aliases": ["a"], "intent": "text", "description": ""},
    ]}],
}
r1 = c.post("/domains/upload", headers=h, json=bundle)
_h.check("TC-DOMAIN-003 upload bundle -> 201", r1.status_code == 201, r1.text[:100])
r2 = c.post("/domains/upload", headers=h, json=bundle)
_h.check("TC-DOMAIN-004 re-upload idempotent -> 201", r2.status_code == 201)

r = c.post("/domains/", headers=h, json={"name": bundle["domain_name"]})
_h.check("TC-DOMAIN-005 duplicate create -> 400", r.status_code == 400, str(r.status_code))

did = r1.json().get("id") or (r2.json().get("id") if r2.status_code == 201 else None)
if did:
    r = c.get(f"/domains/{did}/manifests", headers=h)
    _h.check("TC-DOMAIN-006 manifests GET", r.status_code == 200, r.text[:100])
r = c.get(f"/domains/999999/manifests", headers=h)
_h.check("TC-DOMAIN-007 unknown manifests -> 404", r.status_code == 404)

sys.exit(_h.finish("DOMAIN"))
