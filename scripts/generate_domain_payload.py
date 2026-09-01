"""Generate the ``POST /domains/upload`` payload for a bundled domain catalog.

Usage:
    python scripts/generate_domain_payload.py pca_site_assessment

Writes ``scripts/seed_data/<slug>_payload.json`` — paste its contents into
Swagger for ``POST /domains/upload``.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from backend.inspection_ai.domain_catalog import build_upload_payload  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/generate_domain_payload.py <domain_slug>")
        raise SystemExit(1)
    slug = sys.argv[1]
    payload = build_upload_payload(slug)
    out_dir = Path(__file__).resolve().parent / "seed_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}_payload.json"
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {out_path}")
    print(
        f"sections={len(payload['sections'])} "
        f"fields={sum(len(s.get('fields', [])) for s in payload['sections'])}"
    )


if __name__ == "__main__":
    main()
