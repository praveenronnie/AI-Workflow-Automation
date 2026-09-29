"""Export the OpenAPI schema as the frontend contract artifact.

Usage: python scripts/export_openapi.py [out_path]
Writes docs/openapi.json (committed); frontend types are generated from it so
backend contract changes are diffable in code review.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app import app  # noqa: E402


def main() -> None:
    out = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    paths = len(schema.get("paths", {}))
    print(f"OpenAPI schema written: {out} ({paths} paths)")


if __name__ == "__main__":
    main()
