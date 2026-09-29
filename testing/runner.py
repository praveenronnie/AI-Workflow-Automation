"""FormIQ test runner — executes the full battery in dependency order.

Usage: python testing/runner.py [base_url]
Requires: infra + api running (docker compose up -d). `pipeline_check`
additionally requires a live Celery worker + Modal.
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

# (script, description, needs_worker)
BATTERY = [
    ("tests/smoke_api.py", "Smoke (core API, 31 checks)", False),
    ("testing/auth_check.py", "Auth + report lifecycle", False),
    ("testing/lock_check.py", "Lock lifecycle", False),
    ("testing/schema_check.py", "Form schema", False),
    ("testing/domain_check.py", "Domain registry", False),
    ("testing/docs_check.py", "Document management", False),
    ("testing/ops_check.py", "Ops/SEC/privacy routines", False),
    ("tests/org_isolation_check.py", "Org isolation (privacy walls)", False),
    ("tests/domain_map_check.py", "Domain validation on /map", False),
    ("tests/maintenance_check.py", "Sweeper + heartbeat + request-id", False),
    ("testing/upload_check.py", "Upload edge (ZIP/count/handwritten)", False),
    ("testing/map_check.py", "Mapping flag (no wedge)", False),
    ("testing/nfr_check.py", "Concurrency (10 uploads)", False),
    ("tests/pipeline_check.py", "FULL pipeline (needs worker + Modal)", True),
]


def run(script: str) -> int:
    r = subprocess.run(
        [sys.executable, str(ROOT / script), BASE],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    tail = (r.stdout or "").strip().splitlines()[-3:]
    for line in tail:
        print(f"    {line}")
    return r.returncode


def reset_rate_limit():
    """Dev-only: clear login rate-limit keys between suites (10/5min/IP)."""
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, socket_connect_timeout=3)
        keys = list(r.scan_iter(match="ratelimit:login:*"))
        if keys:
            r.delete(*keys)
    except Exception as e:
        print(f"    (rate-limit reset skipped: {e})")


def main() -> int:
    print(f"FormIQ test battery -> {BASE}\n{'=' * 60}")
    results = []
    for script, desc, needs_worker in BATTERY:
        print(f"\n> {desc}  ({script})")
        t0 = time.time()
        code = run(script)
        reset_rate_limit()
        dt = time.time() - t0

        status = "PASS" if code == 0 else "FAIL"
        results.append((script, desc, status, dt))
        print(f"  => {status} ({dt:.1f}s)")

    print(f"\n{'=' * 60}\nBATTERY SUMMARY")
    total_fail = 0
    for script, desc, status, dt in results:
        print(f"  {status:4}  {desc}  [{dt:.1f}s]")
        if status == "FAIL":
            total_fail += 1
    print(f"\n{len(results) - total_fail}/{len(results)} suites passed")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())

