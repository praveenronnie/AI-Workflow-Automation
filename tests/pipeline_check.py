"""Full pipeline E2E against a deployment with a live Celery worker:
upload text PDF -> wait for extraction -> map -> mappings returned.

Usage: python tests/pipeline_check.py [base_url]
"""

import io
import sys
import time
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
client = httpx.Client(base_url=BASE, timeout=180)
fails = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
    if not ok:
        fails.append(name)


def rich_pdf() -> bytes:
    """Multi-paragraph text PDF so Docling produces real chunks."""
    lines = [
        "Site Assessment Report - Property Inspection Summary",
        "Property Address: 1247 Willow Creek Road, Springfield, IL 62704",
        "Inspection Date: March 14, 2026",
        "Inspector: J. Martinez, License PI-448210",
        "",
        "FOUNDATION: The foundation is a poured concrete slab-on-grade,",
        "constructed in 1998. No visible cracking, settlement, or heaving",
        "was observed at the perimeter. Slab levelness within tolerance.",
        "",
        "ROOF: Asphalt composition shingle roof, approximately 12 years old.",
        "Several lifted shingles noted on the south slope near the chimney",
        "flashing. Recommend sealing and replacement of 6-8 shingles.",
        "",
        "ELECTRICAL: 200-amp main panel, copper wiring throughout. Two",
        "GFCI outlets in the kitchen failed to trip during testing and",
        "require replacement. Panel labeling incomplete.",
        "",
        "PLUMBING: CPVC supply lines, water heater manufactured 2019, 50",
        "gallon. Water pressure measured at 58 PSI. Minor corrosion at",
        "the laundry standpipe connection; recommend resealing.",
        "",
        "HVAC: Gas furnace, 14 years old, functional at time of inspection.",
        "AC condenser unit 8 years old, cooling differential within range.",
        "Recommend annual service and filter replacement.",
    ]
    content = b"BT /F1 11 Tf 72 720 Td 14 TL\n"
    for ln in lines:
        safe = ln.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content += f"({safe}) Tj T*\n".encode()
    content += b"ET"
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
    out.write(b"trailer\n<< /Size 6 /Root 1 0 R >>\n%%EOF")
    return out.getvalue()


stamp = uuid.uuid4().hex[:8]
email = f"pipe_{stamp}@test.local"
client.post("/auth/register", json={"email": email, "password": "S3cure-Passw0rd!"})
tok = client.post("/auth/token", data={"username": email, "password": "S3cure-Passw0rd!"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

rid = client.post("/reports/link", headers=h, json={"source_url": f"https://app.openquire.com/reports/{stamp}"}).json()["report_id"]
check("report created", bool(rid), rid)
client.post(f"/reports/{rid}/lock", headers=h)

r = client.post(
    f"/reports/{rid}/upload/pdf", headers=h,
    files=[("files", ("site-report.pdf", rich_pdf(), "application/pdf"))],
    data={"doc_types": '["scanned"]'},
)
print("upload:", r.status_code, r.text[:150])
check("upload accepted", r.status_code == 200, r.text[:120])
job_id = r.json().get("job_id")

# Wait for extraction + embedding (worker + Modal + LLM; generous timeout)
print("waiting for extraction (up to 5 min)...")
deadline = time.time() + 300
extracted = False
while time.time() < deadline:
    time.sleep(10)
    jr = client.get(f"/reports/jobs/{job_id}", headers=h)
    status = jr.json().get("status") if jr.status_code == 200 else "?"
    print("  job:", status)
    if status in ("completed", "failed"):
        extracted = status == "completed"
        break
check("extraction job completed", extracted, f"last status={status}")

r = client.get(f"/reports/{rid}/mapping", headers=h)
proc = r.json().get("processing", {})
check("extraction_completed flag", proc.get("extraction_completed") is True, str(proc))

schema = {
    "sections": [{
        "sectionName": "Site Details",
        "tableId": 1,
        "fields": [
            {"field_id": "f_addr", "field_name": "Property Address", "field_type": "text"},
            {"field_id": "f_found", "field_name": "Foundation Type", "field_type": "select",
             "options": {"o1": "Slab", "o2": "Pier & Beam", "o3": "Crawlspace"}},
            {"field_id": "f_roof", "field_name": "Roof Condition Notes", "field_type": "text"},
        ],
    }]
}
r = client.post(
    f"/reports/{rid}/form_schema", headers=h,
    json={"form_schema": schema, "source_url": f"https://app.openquire.com/reports/{stamp}", "trigger_intent": False},
)
check("form_schema stored", r.status_code == 200, r.text[:120])

r = client.post(f"/reports/{rid}/map", headers=h, json={"domain": "pca_site_assessment"})
print("map:", r.status_code, r.text[:200])
check("/map accepted (evidence found)", r.status_code == 200, r.text[:150])

r = client.get(f"/reports/{rid}/mapping", headers=h)
mappings = r.json().get("mappings", [])
check("mappings returned", len(mappings) > 0, f"count={len(mappings)}")
for m in mappings[:5]:
    print(f"   {m.get('field_id')}: {str(m.get('value'))[:60]} (conf={m.get('confidence')}, method={m.get('mapping_method')})")

print("\n==== PIPELINE ====")
print(f"fails={len(fails)}")
sys.exit(1 if fails else 0)

