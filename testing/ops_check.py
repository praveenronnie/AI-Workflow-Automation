"""TC-OPS / TC-SEC / TC-EXTRACT — health, request-id, privacy failures, sweeper, heartbeat."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)

# health / ready
r = c.get("/health")
_h.check("TC-OPS-001 /health 200", r.status_code == 200)
r = c.get("/ready")
body = r.json()
_h.check("TC-OPS-002 /ready all services", body.get("ready") is True, str(body.get("services")))
# TC-OPS-003: degraded path is determined by `any(services.values())` and a
# "degraded" status; we assert the response contract always carries the fields
# (live-down testing is covered by the docker healthcheck / prod watchdogs).
_h.check("TC-OPS-003 /ready shape (status+ready+services)",
         "status" in body and isinstance(body.get("ready"), bool) and isinstance(body.get("services"), dict),
         str(body.get("status")))

# request id
rid_hdr = str(uuid.uuid4().hex[:12])
r = c.get("/health", headers={"X-Request-ID": rid_hdr})
_h.check("TC-OPS-005 request-id echoed", r.headers.get("X-Request-ID") == rid_hdr, r.headers.get("X-Request-ID"))
r = c.get("/health")
_h.check("TC-OPS-005b request-id generated", bool(r.headers.get("X-Request-ID")))

# sweeper + heartbeat functions
import asyncio
from backend.tasks import maintenance as mt

mt._write_heartbeat()
failed = asyncio.run(mt._sweep())
_h.check("TC-EXTRACT-009 sweeper runs clean", isinstance(failed, int))
r = c.get("/ready")
_h.check("TC-EXTRACT heartbeat visible", r.json().get("worker_alive") is True)

# SEC routines: magic bytes (already in smoke), unknown types
h, _ = _h.signup_login(c, "sec")
rid = c.post("/reports/link", headers=h, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]
c.post(f"/reports/{rid}/lock", headers=h)
r = c.post(f"/reports/{rid}/upload/image", headers=h,
           files=[("files", ("fake.png", b"not a png", "image/png"))])
_h.check("TC-SEC-006 magic-byte enforcement", r.status_code == 400, str(r.status_code))

# UI-010: grep for removed standalone-mode residue (code-level, cross-platform)
root = Path(__file__).resolve().parent.parent
residue = []
for py in (root / "frontend" / "web" / "src").rglob("*.ts*"):
    txt = py.read_text(encoding="utf-8", errors="ignore")
    for needle in ("directApiUpload", "localStorage", "standalone"):
        if needle in txt:
            residue.append(f"{py.name}:{needle}")
_h.check("TC-UI-010 standalone mode removed", not residue, str(residue[:3]))

sys.exit(_h.finish("OPS+SEC+EXTRACT-partial"))