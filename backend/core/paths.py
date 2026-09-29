"""Filesystem storage locations shared across features."""

from pathlib import Path

# Anchor to the repository root (backend/core/paths.py -> parents[2]) so the
# API, the Celery worker and the beat process all resolve the SAME absolute
# path regardless of their current working directory.  A relative path here
# ("./storage/uploads") made uploads land in <cwd>/storage, and the worker
# (started from a different directory) failed with FileNotFoundError when it
# tried to open the file paths handed over in the Celery payload.
#
# In Docker the code lives at /app, so this resolves to /app/storage/uploads
# for both the api and worker containers (both mount .:/app).
REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = REPO_ROOT / "storage" / "uploads"


def to_transport_path(path: Path | str) -> str:
    """Portable path string for Celery payloads and DB ``storage_path`` rows.

    Returns a repo-relative, forward-slash string (e.g.
    ``storage/uploads/jobs/<id>/file.jpg``).  Such a reference resolves on
    EVERY host: a Windows API anchors it at REPO_ROOT (``D:\\...\\storage``)
    while a Linux worker container anchors it at its own repo root
    (``/app/storage``).  Absolute Windows paths (``D:\\...``) are meaningless
    inside Linux containers, so the hybrid native-API + Docker-worker setup
    only works when payloads carry this portable form.
    """
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        # Outside the repo: fall back to an absolute, forward-slash reference.
        return p.as_posix()


def resolve_transport_path(path_str: str) -> Path:
    """Inverse of :func:`to_transport_path` — anchor relative refs at REPO_ROOT.

    Absolute strings are returned unchanged (after normalizing Windows
    separators), so legacy DB rows written before this change still resolve
    on the host that owns those absolute paths.
    """
    p = Path(str(path_str).replace("\\", "/"))
    if p.is_absolute():
        return p
    return REPO_ROOT / p