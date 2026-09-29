"""TC-NFR — concurrent uploads + rate-limit count."""
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from testing import _h

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = _h.client(BASE)
h, _ = _h.signup_login(c, "nfr")
rid = _h.new_rid(c, h)


def upload(i: int):
    name = f"f_{i}_{uuid.uuid4().hex[:4]}.png"
    r = c.post(f"/reports/{rid}/upload/image", headers=h,
               files=[("files", (name, _h.png(), "image/png"))])
    return r.status_code


with ThreadPoolExecutor(max_workers=10) as ex:
    codes = list(ex.map(upload, range(10)))
_h.check("TC-NFR-002 10 concurrent uploads -> all 200", all(code == 200 for code in codes), str(codes))

sys.exit(_h.finish("NFR-CONCURRENCY"))