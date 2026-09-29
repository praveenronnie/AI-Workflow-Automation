"""Race + normalization check for POST /reports/link (report creation).

Two users fire simultaneous link requests for the same URL — both must
succeed, and exactly ONE report must exist for that URL with both users
linked. Also verifies URL normalization merges equivalent variants.
"""
import asyncio
import uuid

import httpx

B = "http://localhost:8000"
URL = f"https://example.com/reports/{uuid.uuid4().hex[:8]}"


async def client_for(email: str) -> httpx.AsyncClient:
    c = httpx.AsyncClient(base_url=B, timeout=30)
    r = await c.post(
        "/auth/register",
        json={"email": email, "password": "T#12345678", "name": "R"},
    )
    print("register:", r.status_code, r.text[:120])
    r = await c.post(
        "/auth/token", data={"username": email, "password": "T#12345678"}
    )
    print("token:", r.status_code, r.text[:120])
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return c


async def main() -> None:
    # NOTE: each user resolves to their OWN organization (privacy wall), so
    # two different users are EXPECTED to get separate reports for the same
    # URL. The true race is same-org concurrent creation — e.g. the same user
    # double-clicking "New Report" or a retried request racing the original.
    c1 = await client_for(f"raceA_{uuid.uuid4().hex[:6]}@t.local")
    fails = 0

    # --- race: same user, simultaneous same-URL link ---
    results = await asyncio.gather(
        c1.post("/reports/link", json={"source_url": URL, "source_domain": "openquire"}),
        c1.post("/reports/link", json={"source_url": URL, "source_domain": "openquire"}),
    )
    statuses = [r.status_code for r in results]
    print("race statuses:", statuses)
    if statuses != [200, 200]:
        print("FAIL: concurrent link returned non-200", [r.text[:150] for r in results])
        fails += 1

    reports = await c1.get("/reports/user")
    ids = {
        r["report_id"]
        for r in reports.json()
        if (r.get("report_url") or "").rstrip("/").lower() == URL.rstrip("/").lower()
    }
    print("reports for URL:", ids)
    if len(ids) != 1:
        print("FAIL: expected exactly 1 report for the URL, got", len(ids))
        fails += 1

    # --- normalization: URL variants must resolve to the SAME report ---
    rid = next(iter(ids), "")
    # trailing slash, fragment, host case, default port — all normalize equal
    variants = [
        URL + "/",
        URL + "#section",
        URL.replace("example.com", "EXAMPLE.COM"),
        URL.replace("example.com", "example.com:443"),
    ]
    for v in variants:
        r = await c1.post(
            "/reports/link", json={"source_url": v, "source_domain": "openquire"}
        )
        got = r.json().get("report_id") if r.status_code == 200 else r.status_code
        ok = got == rid
        print(f"variant {v!r} -> {got}", "OK" if ok else "FAIL")
        if not ok:
            fails += 1

    # --- cross-org: a DIFFERENT user must get a DIFFERENT report ---
    c2 = await client_for(f"raceB_{uuid.uuid4().hex[:6]}@t.local")
    r = await c2.post(
        "/reports/link", json={"source_url": URL, "source_domain": "openquire"}
    )
    other_id = r.json().get("report_id")
    ok = r.status_code == 200 and other_id and other_id != rid
    print("cross-org separate report:", "OK" if ok else f"FAIL ({other_id})")
    if not ok:
        fails += 1

    print(f"\n==== REPORT RACE/NORMALIZATION ==== fails={fails}")
    await c1.aclose()
    await c2.aclose()
    raise SystemExit(1 if fails else 0)


asyncio.run(main())
