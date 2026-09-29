"""TC-LOCK — lock lifecycle checks (short-TTL expiry simulated via heartbeat)."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)

h1, _ = _h.signup_login(c, "la")
h2, _ = _h.signup_login(c, "lb")
rid = c.post("/reports/link", headers=h1, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]

r = c.post(f"/reports/{rid}/lock", headers=h1)
body = r.json()
token = body.get("lock_token")
_h.check("TC-LOCK-001 acquire", r.status_code == 200 and token and body.get("expires_at"))

r = c.post(f"/reports/{rid}/lock", headers=h2)
# h2 is a DIFFERENT org -> report is invisible (privacy wall) rather than 409.
_h.check("TC-LOCK-002 cross-org acquire -> 404 (scoped)", r.status_code == 404, str(r.status_code))

r = c.post(f"/reports/{rid}/lock", headers=h1)
_h.check("TC-LOCK-003 re-acquire same user -> 200", r.status_code == 200)
token = r.json().get("lock_token", token)

r = c.post(f"/reports/{rid}/lock/heartbeat", headers=h1, json={"lock_token": token})
_h.check("TC-LOCK-004 heartbeat -> 200", r.status_code == 200, r.text[:80])

r = c.post(f"/reports/{rid}/lock/heartbeat", headers=h2, json={"lock_token": "bogus"})
_h.check("TC-LOCK-005 heartbeat wrong token -> 4xx", 400 <= r.status_code < 500, str(r.status_code))

r = c.post(f"/reports/{rid}/unlock", headers=h1)
_h.check("TC-LOCK-006 unlock no body -> 422", r.status_code == 422)

r = c.post(f"/reports/{rid}/unlock", headers=h1, json={"lock_token": "bogus"})
_h.check("TC-LOCK-007 unlock wrong token -> 403", r.status_code == 403, str(r.status_code))

r = c.post(f"/reports/{rid}/unlock", headers=h1, json={"lock_token": token})
_h.check("TC-LOCK-008 unlock -> 200", r.status_code == 200)
r = c.post(f"/reports/{rid}/lock", headers=h1)
_h.check("TC-LOCK-008b re-acquire after unlock", r.status_code == 200)

# TC-LOCK-009 — expired lock takeover (force-expire via direct repo with short TTL)
import asyncio
from sqlalchemy import select, update
from datetime import datetime, timedelta
from backend.database.base import AsyncSessionLocal
from backend.database.models.documents import ReportLock

async def _force_expire(rid: str):
    async with AsyncSessionLocal() as db_:
        await db_.execute(
            update(ReportLock).where(ReportLock.report_id == rid).values(
                expires_at=datetime.utcnow() - timedelta(seconds=60)
            )
        )
        await db_.commit()

asyncio.run(_force_expire(rid))
# Takeover after expiry: same-user re-acquire (cross-org would 404 by privacy wall)
r = c.post(f"/reports/{rid}/lock", headers=h1)
_h.check("TC-LOCK-009 expired lock takeover -> 200", r.status_code == 200, str(r.status_code))

# mutation without lock
rid2 = c.post("/reports/link", headers=h1, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]
r = c.post(
    f"/reports/{rid2}/upload/pdf", headers=h1,
    files=[("files", ("a.pdf", _h.pdf(), "application/pdf"))],
    data={"doc_types": '["scanned"]'},
)
_h.check("TC-LOCK-010 mutation without lock -> 409", r.status_code == 409, str(r.status_code))

sys.exit(_h.finish("LOCK"))
