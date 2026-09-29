"""Verify: (1) maintenance heartbeat + sweep functions work and flip /ready;
(2) X-Request-ID middleware."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio

import httpx

from backend.tasks.maintenance import _sweep, _write_heartbeat

_write_heartbeat()
failed = asyncio.run(_sweep())
print("sweep result:", failed)

r = httpx.Client(transport=httpx.HTTPTransport(retries=3)).get(
    "http://localhost:8000/ready", timeout=30
)
body = r.json()
print("worker_alive:", body.get("worker_alive"))
print("request id header:", r.headers.get("X-Request-ID"))
assert body.get("worker_alive") is True, "heartbeat not visible"
assert r.headers.get("X-Request-ID"), "missing X-Request-ID"
print("PASS")

