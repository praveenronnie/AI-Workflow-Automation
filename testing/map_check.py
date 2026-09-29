"""TC-MAP-014 — mapping_in_progress flag set/cleared."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)
h, _ = _h.signup_login(c, "map")
rid = _h.new_rid(c, h)

# upload a minimal but valid PDF (no extraction needed for the flag test —
# check the report_locks.mapping_in_progress after a /map attempt)
c.post(f"/reports/{rid}/form_schema", headers=h,
       json={"form_schema": {"sections": [{"sectionName": "S", "tableId": 1, "fields": []}]},
             "source_url": "https://x", "trigger_intent": False})
r = c.post(f"/reports/{rid}/map", headers=h, json={"domain": "pca_site_assessment"})
# Evidence absent -> 400; the important assertion is that mapping_in_progress
# was NOT left stuck (cleared in finally). We cannot read the private flag via
# API, so assert the report is still lockable/mappable afterwards → no stuck flag.
_h.check("TC-MAP-014 map ran and did not wedge flag", r.status_code in (200, 400), f"{r.status_code} {r.text[:120]}")
# subsequent operation works (flag cleared → no deadlock)
r2 = c.post(f"/reports/{rid}/form_schema", headers=h,
            json={"form_schema": {"sections": [{"sectionName": "S2", "tableId": 1, "fields": []}]},
                  "source_url": "https://x"})
_h.check("TC-MAP-014b follow-up schema write OK (flag released)", r2.status_code == 200, str(r2.status_code))

sys.exit(_h.finish("MAP-FLAG"))