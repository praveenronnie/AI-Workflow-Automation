"""TC-SCHEMA — form schema store/get/PUT + variants."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)
h, _ = _h.signup_login(c, "sc")
rid = c.post("/reports/link", headers=h, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]
c.post(f"/reports/{rid}/lock", headers=h)

schema = {"sections": [{"sectionName": "S1", "tableId": 1, "fields": [
    {"field_id": "fa", "field_name": "Address", "field_type": "text"},
]}]}
r = c.post(f"/reports/{rid}/form_schema", headers=h,
           json={"form_schema": schema, "source_url": "https://x", "trigger_intent": False})
_h.check("TC-SCHEMA-001 store", r.status_code == 200, r.text[:100])

r = c.post(f"/reports/{rid}/form_schema", headers=h,
           json={"form_schema": schema})
_h.check("TC-SCHEMA-002 missing source_url -> 422", r.status_code == 422)

rid2 = c.post("/reports/link", headers=h, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]
r = c.post(f"/reports/{rid2}/form_schema", headers=h,
           json={"form_schema": schema, "source_url": "https://x"})
_h.check("TC-SCHEMA-003 requires lock -> 409", r.status_code == 409, str(r.status_code))

r = c.get(f"/reports/{rid}/form_schema", headers=h)
got = r.json().get("form_schema") or {}
_h.check("TC-SCHEMA-004 get stored", r.status_code == 200 and got.get("sections"))

put_schema = {"sections": [{"sectionName": "S1", "tableId": 1, "fields": [
    {"field_id": "fb", "field_name": "Roof", "field_type": "text"},
]}]}
r = c.put(f"/reports/{rid}/form_schema", headers=h,
          json={"form_schema": put_schema, "source_url": "https://x"})
_h.check("TC-SCHEMA-005 PUT replaces", r.status_code == 200, r.text[:100])

r = c.get(f"/reports/{rid}/form_schema", headers=h)
ids = [f.get("field_id") for f in r.json().get("form_schema", {}).get("sections", [{}])[0].get("fields", [])]
_h.check("TC-SCHEMA-006 field_id keys preserved", ids == ["fb"], str(ids))

sys.exit(_h.finish("SCHEMA"))
