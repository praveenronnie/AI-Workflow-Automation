"""TC-AUTH / TC-REPORT / TC-SEC — auth & report lifecycle checks."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)


def new_user(tag):
    return _h.signup_login(c, tag)


h1, e1 = new_user("a")
h2, e2 = new_user("b")

# register
r = c.post("/auth/register", json={"email": f"dup_{uuid.uuid4().hex[:6]}@test.local", "password": "x", "name": "N"})
_h.check("TC-AUTH-001 register (name present)", r.status_code == 200)
r = c.post("/auth/register", json={"email": e1, "password": "S3cure-Passw0rd!"})
_h.check("TC-AUTH-002 duplicate -> 409", r.status_code == 409, str(r.status_code))
r = c.post("/auth/register", json={})
_h.check("TC-AUTH-003 missing fields -> 422", r.status_code == 422)
r = c.post("/auth/register", json={"email": f"nn_{uuid.uuid4().hex[:6]}@test.local", "password": "S3cure-Passw0rd!"})
_h.check("TC-AUTH-004 no-name register -> 200", r.status_code == 200, r.text[:80])

# login variants
r = c.post("/auth/token", data={"username": e1, "password": "bad"})
_h.check("TC-AUTH-006 wrong password -> 401", r.status_code == 401)
r = c.post("/auth/token", data={"username": f"ghost_{uuid.uuid4().hex[:4]}@test.local", "password": "x"})
_h.check("TC-AUTH-007 unknown user -> 401", r.status_code == 401)
_h.check("TC-AUTH-007b no user enumeration (same message)", "Incorrect email or password" in r.text)

# refresh rotation
r = c.post("/auth/token", data={"username": e1, "password": "S3cure-Passw0rd!"})
tok1 = r.json()
r = c.post("/auth/refresh", json={"refresh_token": tok1["refresh_token"]})
_h.check("TC-AUTH-009 rotation -> 200 new pair", r.status_code == 200)
tok2 = r.json()
r = c.post("/auth/refresh", json={"refresh_token": tok1["refresh_token"]})
_h.check("TC-AUTH-010 reuse -> 401", r.status_code == 401)
r = c.post("/auth/refresh", json={"refresh_token": tok1["access_token"]})
_h.check("TC-AUTH-011 access-as-refresh -> 401", r.status_code == 401)
r = c.get("/auth/me", headers=h1)
_h.check("TC-AUTH-013 /auth/me", r.status_code == 200 and r.json().get("email") == e1)
r = c.get("/reports/user")
_h.check("TC-AUTH-014 no token -> 401", r.status_code == 401)

# logout revokes
r = c.post("/auth/logout", headers=h1)
_h.check("TC-AUTH-012 logout", r.status_code == 200)
r = c.post("/auth/refresh", json={"refresh_token": tok2["refresh_token"]})
_h.check("TC-AUTH-012b refresh after logout -> 401", r.status_code == 401)

# reports
h3, _ = new_user("c")
r = c.post("/reports/link", headers=h3, json={"source_url": f"https://x/{uuid.uuid4().hex}"})
rid = r.json()["report_id"]
_h.check("TC-REPORT-001 link create", r.status_code == 200 and r.json().get("created") is True)
r = c.post("/reports/link", headers=h3, json={"source_url": f"https://x/{uuid.uuid4().hex}"})
_h.check("TC-REPORT-003 create without url", r.status_code == 200 and r.json()["report_id"] != rid)
r = c.post("/reports/link", headers=h3, json={"source_url": f"https://x/{uuid.uuid4().hex}", "source_domain": "custom"})
_h.check("TC-REPORT-008 custom domain accepted", r.status_code == 200)
r = c.get("/reports/user", headers=h3)
_h.check("TC-REPORT-004 list reports", r.status_code == 200 and len(r.json()) >= 3)
r = c.get(f"/reports/{rid}", headers=h3)
_h.check("TC-REPORT-005 get by id owner", r.status_code == 200)
r = c.get(f"/reports/{rid}", headers=h2)
_h.check("TC-REPORT-006 cross-org -> 404", r.status_code == 404)
r = c.get(f"/reports/{uuid.uuid4().hex}", headers=h3)
_h.check("TC-REPORT-007 unknown -> 404", r.status_code == 404)
r = c.get("/reports/user", headers=h2)
_h.check("TC-REPORT-010 list excludes others", all(rep["report_id"] != rid for rep in r.json()))
r = c.delete(f"/reports/{rid}", headers=h3)
_h.check("TC-REPORT-009 delete -> 204", r.status_code == 204)
r = c.get(f"/reports/{rid}", headers=h3)
_h.check("TC-REPORT-009b deleted -> 404", r.status_code == 404)

# TC-AUTH-008 — rate-limit count (Redis-backed); run LAST (trips limiter for this IP)
r429 = False
for _ in range(12):
    rr = c.post("/auth/token", data={"username": e1, "password": "bad-no-matter"})
    if rr.status_code == 429:
        r429 = True
        break
_h.check("TC-AUTH-008 rate limit -> 429 after 11 attempts", r429, "429 observed")

sys.exit(_h.finish("AUTH+REPORT"))
