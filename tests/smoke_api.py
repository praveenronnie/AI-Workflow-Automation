"""
End-to-end API smoke test (analysis-only audit).

Requires a live server. Usage:
    python tests/smoke_api.py [base_url]

Default base_url: http://127.0.0.1:8123
External providers (Modal/LLM) are exercised only where reachable; failures
are REPORTED, never swallowed.
"""

import io
import json
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123"

RESULTS = []  # (name, PASS/FAIL, detail)


def record(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('--- ' + detail) if detail else ''}")


def minimal_pdf() -> bytes:
    """A structurally valid single-page PDF with text."""
    content = b"BT /F1 12 Tf 72 720 Td (Site Assessment Report) Tj ET"
    stream = f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        stream,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objects, 1):
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for i in range(1, len(objects) + 1):
        out.write(f"{i:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF".encode()
    )
    return out.getvalue()


def main():
    client = httpx.Client(base_url=BASE, timeout=120, transport=httpx.HTTPTransport(retries=3))
    stamp = uuid.uuid4().hex[:8]
    email = f"smoke_{stamp}@test.local"
    password = "S3cure-Passw0rd!"

    # ---- health ----
    r = client.get("/health")
    record("GET /health", r.status_code == 200, f"{r.status_code} {r.text[:100]}")

    r = client.get("/ready")
    body = r.json()
    record(
        "GET /ready (all services)",
        r.status_code == 200 and body.get("ready") is True,
        json.dumps(body.get("services", {})),
    )

    # ---- auth ----
    r = client.post("/auth/register", json={"email": email, "password": password, "name": "Smoke"})
    record("POST /auth/register", r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}")

    r = client.post("/auth/register", json={"email": email, "password": password})
    record("POST /auth/register duplicate -> conflict (400/409)", r.status_code in (400, 409), f"{r.status_code} {r.text[:150]}")

    r = client.post("/auth/token", data={"username": email, "password": "wrong-password"})
    record("POST /auth/token wrong password -> 401", r.status_code == 401, f"{r.status_code} {r.text[:150]}")

    r = client.post("/auth/token", data={"username": email, "password": password})
    ok = r.status_code == 200 and "access_token" in r.text
    record("POST /auth/token login", ok, f"{r.status_code} {r.text[:120]}")
    token = r.json().get("access_token", "") if ok else ""
    refresh_token = r.json().get("refresh_token", "") if ok else ""
    headers = {"Authorization": f"Bearer {token}"}

    # ---- refresh rotation + logout revocation ----
    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    ok = r.status_code == 200 and "access_token" in r.text
    record("POST /auth/refresh rotates", ok, f"{r.status_code} {r.text[:120]}")
    new_refresh = r.json().get("refresh_token", "") if ok else ""

    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    record("reused refresh token revoked -> 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")

    r = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    record("fresh refresh token still valid", r.status_code == 200, f"{r.status_code}")

    r = client.post("/auth/logout", headers=headers)
    record("POST /auth/logout", r.status_code == 200, f"{r.status_code}")

    r = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    record("refresh after logout revoked -> 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")

    # re-login for the rest of the flow
    r = client.post("/auth/token", data={"username": email, "password": password})
    token = r.json().get("access_token", "")
    headers = {"Authorization": f"Bearer {token}"}

    # ---- unauthenticated access ----
    r = client.get("/reports/user")
    record("GET /reports/user without token -> 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")

    # ---- reports ----
    r = client.post(
        "/reports/link",
        headers=headers,
        json={"source_url": f"https://app.openquire.com/reports/{stamp}", "source_domain": "openquire"},
    )
    ok = r.status_code == 200
    record("POST /reports/link (create)", ok, f"{r.status_code} {r.text[:200]}")
    report_id = r.json().get("report_id") if ok else ""
    record("report_id returned", bool(report_id), str(report_id))

    r = client.get("/reports/user", headers=headers)
    ok = r.status_code == 200 and any(rep.get("report_id") == report_id for rep in r.json())
    record("GET /reports/user lists report", ok,
           f"{r.status_code} count={len(r.json()) if r.status_code == 200 else '?'}")

    # second user isolation
    email2 = f"smoke2_{stamp}@test.local"
    client.post("/auth/register", json={"email": email2, "password": password})
    tok2 = client.post("/auth/token", data={"username": email2, "password": password}).json().get("access_token", "")
    r = client.get(f"/reports/{report_id}", headers={"Authorization": f"Bearer {tok2}"})

    # second user isolation
    email2 = f"smoke2_{stamp}@test.local"
    client.post("/auth/register", json={"email": email2, "password": password})
    tok2 = client.post("/auth/token", data={"username": email2, "password": password}).json().get("access_token", "")
    r = client.get(f"/reports/{report_id}", headers={"Authorization": f"Bearer {tok2}"})
    record("cross-user report access denied", r.status_code in (403, 404), f"{r.status_code} {r.text[:150]}")

    r = client.get(f"/reports/{report_id}", headers=headers)
    record("GET /reports/{id} owner access", r.status_code == 200, f"{r.status_code} {r.text[:150]}")

    r = client.get(f"/reports/{uuid.uuid4().hex}", headers=headers)
    record("GET unknown report -> 404", r.status_code == 404, f"{r.status_code} {r.text[:150]}")

    return client, headers, report_id, stamp



def uploads_and_mapping(client, headers, report_id, stamp):
    # ---- lock (required before uploads/map) ----
    r = client.post(f"/reports/{report_id}/lock", headers=headers)
    record("POST /lock acquire", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    pdf = minimal_pdf()
    r = client.post(
        f"/reports/{report_id}/upload/pdf",
        headers=headers,
        files=[("files", ("site.pdf", pdf, "application/pdf"))],
        data={"doc_types": json.dumps(["scanned"])},
    )
    record("POST upload/pdf", r.status_code == 200, f"{r.status_code} {r.text[:300]}")

    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc00000030101"
        "00c9fe92ef0000000049454e44ae426082"
    )
    r = client.post(
        f"/reports/{report_id}/upload/image",
        headers=headers,
        files=[("files", ("photo.png", png, "image/png"))],
    )
    record("POST upload/image", r.status_code == 200, f"{r.status_code} {r.text[:300]}")

    r = client.post(
        f"/reports/{report_id}/upload/pdf",
        headers=headers,
        files=[("files", ("bad.pdf", b"not a real pdf", "application/pdf"))],
        data={"doc_types": json.dumps(["scanned"])},
    )
    record("POST upload/pdf invalid content rejected 400", r.status_code == 400, f"{r.status_code} {r.text[:200]}")

    r = client.post(
        f"/reports/{report_id}/upload/image",
        headers=headers,
        files=[("files", ("fake.png", b"this is not a png", "image/png"))],
    )
    record("POST upload/image invalid content rejected 400", r.status_code == 400, f"{r.status_code} {r.text[:200]}")

    r = client.post(
        f"/reports/{uuid.uuid4().hex}/upload/pdf",
        headers=headers,
        files=[("files", ("x.pdf", pdf, "application/pdf"))],
        data={"doc_types": "[]"},
    )
    record("POST upload/pdf unknown report -> 4xx", 400 <= r.status_code < 500, f"{r.status_code}")

    # ---- form schema ----
    schema = {
        "sections": [
            {
                "sectionName": "Site Details",
                "tableId": 1,
                "fields": [
                    {"field_id": "f1", "field_name": "Property Address", "field_type": "text"},
                    {"field_id": "f2", "field_name": "Foundation Type", "field_type": "select",
                     "options": {"opt1": "Slab", "opt2": "Pier & Beam"}},
                ],
            }
        ]
    }
    r = client.post(
        f"/reports/{report_id}/form_schema",
        headers=headers,
        json={"form_schema": schema, "source_url": "https://app.openquire.com/reports/x", "trigger_intent": False},
    )
    record("POST form_schema", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    r = client.post(f"/reports/{report_id}/form_schema", headers=headers, json={"form_schema": "not-an-object"})
    record("POST form_schema invalid payload -> 4xx", 400 <= r.status_code < 500, f"{r.status_code} {r.text[:150]}")

    # ---- status / mapping / domains ----
    r = client.get(f"/reports/{report_id}/form_schema", headers=headers)
    record("GET form_schema", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    r = client.post(f"/reports/{report_id}/map", headers=headers, json={"domain_id": 1})
    # TC-MAP-005: this smoke report has no extracted evidence (minimal PDF),
    # so 400 "No evidence found" is the documented expected outcome; 200 means
    # a live worker fully processed it.
    expected_map = r.status_code == 200 or (
        r.status_code == 400 and "No evidence found" in r.text
    )
    record("POST /map (evidence-guard, TC-MAP-005)", expected_map, f"{r.status_code} {r.text[:150]}")

    r = client.get(f"/reports/{report_id}/mapping", headers=headers)
    record("GET /mapping", r.status_code == 200, f"{r.status_code} {r.text[:300]}")

    r = client.get("/domains/", headers=headers)
    record("GET /domains/", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    r = client.post(f"/reports/{report_id}/unlock", headers=headers, json={"lock_token": "smoke"})
    # TC-LOCK-007: wrong token must NOT unlock — 403 is the documented contract.
    record("POST /unlock wrong token -> 403 (TC-LOCK-007)", r.status_code == 403, f"{r.status_code} {r.text[:120]}")


if __name__ == "__main__":
    c, h, rid, st = main()
    uploads_and_mapping(c, h, rid, st)
    print("\n==== SUMMARY ====")
    fails = [x for x in RESULTS if x[1] == "FAIL"]
    print(f"total={len(RESULTS)} pass={len(RESULTS) - len(fails)} fail={len(fails)}")
    for name, status, detail in fails:
        print(f"  FAIL: {name} --- {detail}")
    sys.exit(1 if fails else 0)


