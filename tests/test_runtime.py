import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from app import runtime as rt

ROOT = Path(__file__).resolve().parent.parent


def test_prompt_matches_pin():
    pin = json.loads((ROOT / "prompts" / "pin.json").read_text())
    assert rt.PROMPT_VERSION == pin["prompt_version"]
    assert rt.PROMPT_SHA256 == pin["prompt_sha256"]
    assert rt.PIN_MATCH is True


def test_sha_is_of_exact_file_bytes():
    raw = (ROOT / "prompts" / f"triage_system_v{rt.PROMPT_VERSION}.txt").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == rt.PROMPT_SHA256


def test_health_payload_has_versions():
    h = rt.health_payload()
    for key in ("release", "prompt_version", "prompt_sha256", "config_version",
                "config_sha256", "image_tag", "git_sha"):
        assert h[key], key
    assert h["mcp_server"]["version"] == (ROOT / "mcp_server" / "VERSION").read_text().strip()


def test_config_prompt_version_matches_pin():
    assert rt.CONFIG["prompt_version"] == rt.PIN["prompt_version"]


def test_unpinned_prompt_refuses_to_start():
    env = {**os.environ, "PROMPT_VERSION": "1.3.0-candidate"}
    env.pop("ALLOW_UNPINNED_PROMPT", None)
    proc = subprocess.run([sys.executable, "-c", "import app.runtime"], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert "does not match pin" in proc.stderr


def test_release_gate_passes():
    proc = subprocess.run([sys.executable, "scripts/check_release.py"], cwd=ROOT,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout
