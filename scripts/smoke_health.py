"""Smoke test a running service (local container or deployed app):
/health must report the pinned prompt, this repo's release and MCP version."""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fetch(url: str, wait: int) -> dict:
    deadline = time.time() + wait
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return json.loads(r.read().decode())
        except Exception as exc:
            if time.time() > deadline:
                raise SystemExit(f"SMOKE FAILED: {url} unreachable: {exc}")
            time.sleep(3)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000/health")
    p.add_argument("--wait", type=int, default=60, help="seconds to wait for startup")
    a = p.parse_args()
    h = fetch(a.url, a.wait)
    pin = json.loads((ROOT / "prompts" / "pin.json").read_text())
    checks = [
        ("status ok", h.get("status") == "ok"),
        ("release == VERSION", h.get("release") == (ROOT / "VERSION").read_text().strip()),
        ("prompt_version == pin", h.get("prompt_version") == pin["prompt_version"]),
        ("prompt_sha256 == pin", h.get("prompt_sha256") == pin["prompt_sha256"]),
        ("prompt_pinned", h.get("prompt_pinned") is True),
        ("mcp version == mcp_server/VERSION",
         h.get("mcp_server", {}).get("version")
         == (ROOT / "mcp_server" / "VERSION").read_text().strip()),
    ]
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    print(json.dumps(h, indent=2))
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
