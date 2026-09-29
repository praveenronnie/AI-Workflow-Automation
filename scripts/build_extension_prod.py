"""Package the Chrome extension for production (Chrome Web Store / enterprise).

Dev keeps `http://localhost:8000` so `Load unpacked` works against a local API.
This script copies `extension/` to a staging dir, rewrites the API base and the
manifest host permissions to the deployed domain, sanity-checks that no local
defaults survive, and writes a zip into `dist/`.

Usage:
    python scripts/build_extension_prod.py --api-domain api.formiq.app
    python scripts/build_extension_prod.py --api-domain api.formiq.app --version 1.1.0

The API domain may also come from `API_DOMAIN` in `.env` (never the
`api.example.com` placeholder). Requires the UI bundle to be built first:
    cd frontend/web && npm run build      # -> extension/ui/dist
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXT_DIR = REPO_ROOT / "extension"
UI_DIST = EXT_DIR / "ui" / "dist"
ENV_FILE = REPO_ROOT / ".env"

SKIP_DIRS = {"__pycache__", "node_modules", ".git", "screenshots"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}

API_BASE_RE = re.compile(r'const\s+DEFAULT_API_BASE\s*=\s*"[^"]*"\s*;')
PLACEHOLDER = "api.example.com"


def resolve_domain(arg: str | None) -> str:
    domain = (arg or "").strip()
    if not domain and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("API_DOMAIN="):
                domain = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    domain = domain.replace("https://", "").replace("http://", "").strip("/")
    if not domain or domain == PLACEHOLDER:
        sys.exit(
            "ERROR: set --api-domain (or API_DOMAIN in .env) to the deployed API "
            "hostname, e.g. api.formiq.app"
        )
    return domain


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the production extension zip")
    parser.add_argument("--api-domain", help="deployed API hostname, e.g. api.formiq.app")
    parser.add_argument("--version", help="override the manifest version")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "dist"))
    args = parser.parse_args()

    domain = resolve_domain(args.api_domain)
    if not (UI_DIST / "index.html").is_file():
        sys.exit(
            "ERROR: extension/ui/dist/index.html is missing - build the side-panel "
            "UI first:  cd frontend/web && npm install && npm run build"
        )

    api_base = f"https://{domain}"
    manifest_src = EXT_DIR / "manifest.json"
    if not manifest_src.is_file():
        sys.exit(f"ERROR: {manifest_src} not found")

    staging = Path(tempfile.mkdtemp(prefix="formiq-ext-"))
    work = staging / "extension"
    try:
        shutil.copytree(
            EXT_DIR,
            work,
            ignore=lambda _d, names: [
                n for n in names if n in SKIP_DIRS or n in SKIP_FILES
            ],
        )

        # 1) API base in the service worker (all backend traffic goes through it)
        bg = work / "background" / "background.js"
        bg_text = bg.read_text(encoding="utf-8")
        if not API_BASE_RE.search(bg_text):
            sys.exit("ERROR: DEFAULT_API_BASE not found in background.js - update the script")
        bg_text = API_BASE_RE.sub(f'const DEFAULT_API_BASE = "{api_base}";', bg_text, count=1)
        bg.write_text(bg_text, encoding="utf-8")

        # 2) Manifest: same host permissions, minus the dev-only loopback entry,
        #    plus the deployed API origin. The form-platform hosts must stay:
        #    the extension injects its content scripts into those pages.
        def prod_hosts(hosts: list[str]) -> list[str]:
            kept = [
                h
                for h in hosts
                if "localhost" not in h and "127.0.0.1" not in h
            ]
            api_origin = f"https://{domain}/*"
            if api_origin not in kept:
                kept.append(api_origin)
            return kept

        manifest = json.loads(manifest_src.read_text(encoding="utf-8"))
        manifest["host_permissions"] = prod_hosts(manifest.get("host_permissions", []))
        for entry in manifest.get("web_accessible_resources", []):
            entry["matches"] = prod_hosts(entry.get("matches", []))
        if args.version:
            manifest["version"] = args.version
        (work / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # 3) Fail loudly if a dev-only reference survived anywhere in the bundle.
        #    (`app.openquire.com` is the form platform the extension targets, so
        #    it legitimately appears in adapters/background — reported, not fatal.)
        leftovers: list[str] = []
        platform_refs = 0
        for path in work.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".js", ".json", ".html", ".css"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "localhost:8000" in text or "127.0.0.1:8000" in text:
                leftovers.append(str(path.relative_to(work)))
            if "app.openquire.com" in text:
                platform_refs += 1
        if leftovers:
            sys.exit("ERROR: dev-only API references still present: " + ", ".join(leftovers))

        # 4) Zip (manifest.json must sit at the archive root)
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        version = manifest["version"]
        out_zip = out_dir / f"formiq-extension-{version}.zip"
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(work.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(work).as_posix())
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    files = sum(1 for _ in zipfile.ZipFile(out_zip).namelist())
    print(f"Production extension built: {out_zip}")
    print(f"  version        : {version}")
    print(f"  api base       : {api_base}")
    print(f"  host perms     : {', '.join(manifest['host_permissions'])}")
    print(f"  files in zip   : {files}")
    print(
        f"  platform refs  : {platform_refs} file(s) still target app.openquire.com "
        "(expected: adapters/background)"
    )
    print("Next: upload to the Chrome Web Store, or distribute the .zip for unpacked load.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
