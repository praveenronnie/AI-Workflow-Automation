"""Verify /map rejects unknown/missing domains with a clear 400 (plan item 5)."""
import sys
import time
import uuid

import httpx

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = httpx.Client(base_url=B, timeout=60, transport=httpx.HTTPTransport(retries=3))


def req(fn, *args, **kwargs):
    """Retry wrapper: Windows Docker port-proxy intermittently refuses new
    connections under rapid connect/close cycles — retry with backoff."""
    last = None
    for attempt in range(4):
        try:
            return fn(*args, **kwargs)
        except httpx.ConnectError as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last

email = f"dom_{uuid.uuid4().hex[:6]}@test.local"
req(c.post, "/auth/register", json={"email": email, "password": "S3cure-Passw0rd!"})
tok = req(c.post, "/auth/token", data={"username": email, "password": "S3cure-Passw0rd!"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
rid = req(c.post, "/reports/link", headers=h, json={"source_url": f"https://x/{uuid.uuid4().hex}"}).json()["report_id"]
req(c.post, f"/reports/{rid}/lock", headers=h)
r = req(c.post, 
    f"/reports/{rid}/form_schema",
    headers=h,
    json={"form_schema": {"sections": [{"sectionName": "S", "tableId": 1, "fields": []}]},
          "source_url": "https://x", "trigger_intent": False},
)
print("form_schema:", r.status_code)

r = req(c.post, f"/reports/{rid}/map", headers=h, json={"domain": "no_such_domain"})
print("unknown domain ->", r.status_code, r.json()["detail"])
r = req(c.post, f"/reports/{rid}/map", headers=h, json={})
print("missing domain ->", r.status_code, r.json()["detail"])
r = req(c.post, f"/reports/{rid}/map", headers=h, json={"domain": "pca_site_assessment"})
print("valid domain ->", r.status_code, r.json().get("detail", r.json().get("status")))




