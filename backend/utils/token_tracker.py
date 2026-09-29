"""
Global token usage tracker for LLM calls.
Provides thread-safe in-memory tracking with file persistence.
"""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Dict

from backend.core.config import get_settings

# Global token statistics (in-memory)
token_stats = {
    "calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}

# Thread lock for safe concurrent access
token_lock = Lock()


def _stats_file() -> Path:
    """Token stats live under the shared storage dir (api and worker agree).

    This used to be a CWD-relative "data/token_stats.json", which resolved to a
    different location per process and ended up in the container's writable
    layer instead of a volume.
    """
    try:
        return Path(get_settings().storage_dir) / "token_stats.json"
    except Exception:  # pragma: no cover - settings unavailable
        return Path("data") / "token_stats.json"


# File path for persistence
TOKEN_STATS_FILE = str(_stats_file())


def increment_tokens(prompt_tokens: int, completion_tokens: int) -> None:
    with token_lock:
        token_stats["calls"] += 1
        token_stats["prompt_tokens"] += prompt_tokens
        token_stats["completion_tokens"] += completion_tokens
        token_stats["total_tokens"] += prompt_tokens + completion_tokens


def get_token_stats() -> Dict[str, int]:
    with token_lock:
        return token_stats.copy()


def reset_token_stats() -> None:
    with token_lock:
        token_stats["calls"] = 0
        token_stats["prompt_tokens"] = 0
        token_stats["completion_tokens"] = 0
        token_stats["total_tokens"] = 0

    # Clear the file
    save_token_stats()


def save_token_stats() -> None:
    try:
        os.makedirs(os.path.dirname(TOKEN_STATS_FILE), exist_ok=True)
        with open(TOKEN_STATS_FILE, "w") as f:
            json.dump(get_token_stats(), f, indent=2)
    except Exception as e:
        print(f"Failed to save token stats: {e}")


def load_token_stats() -> Dict[str, int]:
    """
    Load token statistics from file.

    Returns:
        Loaded token statistics or zeroed stats if file doesn't exist
    """
    if not os.path.exists(TOKEN_STATS_FILE):
        return token_stats.copy()

    try:
        with open(TOKEN_STATS_FILE, "r") as f:
            loaded = json.load(f)
            # Validate and update in-memory stats
            with token_lock:
                token_stats["calls"] = loaded.get("calls", 0)
                token_stats["prompt_tokens"] = loaded.get("prompt_tokens", 0)
                token_stats["completion_tokens"] = loaded.get("completion_tokens", 0)
                token_stats["total_tokens"] = loaded.get("total_tokens", 0)
            return token_stats.copy()
    except Exception as e:
        print(f"Failed to load token stats: {e}")
        return token_stats.copy()
