"""Exit-code contract of scripts/mcp_health.py. Uses its own configs, so a change to
config/mcp_required.yaml is caught by the pipeline's MCP health job, not by these tests."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BASE = {
    "name": "afyaplus-logistics",
    "module": "mcp_server/logistics_mcp.py",
    "version_resource": "version://current",
    "expected_version_file": "mcp_server/VERSION",
    "allow_stub_fallback": True,
    "required_tools": ["check_stock", "list_low_stock"],
    "probes": [
        {"tool": "check_stock", "args": {"clinic_id": "C01", "item": "amoxicillin"},
         "expect": {"quantity": 40}},
        {"tool": "check_stock", "args": {"clinic_id": "C99", "item": "x"},
         "expect_error": True},
    ],
}


def run(server: dict | None, mode: str) -> tuple[int, dict | None, str]:
    with tempfile.TemporaryDirectory() as d:
        cfg, report = Path(d) / "cfg.yaml", Path(d) / "report.json"
        cfg.write_text(yaml.safe_dump({"servers": [server]} if server else {"x": 1}))
        proc = subprocess.run(
            [sys.executable, "scripts/mcp_health.py", "--config", str(cfg),
             "--mode", mode, "--report", str(report)],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
        data = json.loads(report.read_text()) if report.exists() else None
        return proc.returncode, data, proc.stdout


def test_stub_healthy_exits_0():
    code, report, out = run(BASE, "stub")
    assert code == 0, out
    assert report["healthy"] is True


def test_missing_required_tool_exits_1():
    code, _, out = run({**BASE, "required_tools": BASE["required_tools"] + ["route_order"]},
                       "stub")
    assert code == 1 and "missing ['route_order']" in out


def test_wrong_tool_result_exits_1():
    bad = {**BASE, "probes": [{"tool": "check_stock",
                              "args": {"clinic_id": "C01", "item": "amoxicillin"},
                              "expect": {"quantity": 999}}]}
    assert run(bad, "stub")[0] == 1


def test_unavailable_live_without_fallback_exits_1():
    code, report, _ = run({**BASE, "module": "mcp_server/does_not_exist.py"}, "live")
    assert code == 1
    assert report["servers"][0]["checks"][0]["check"] == "server reachable"


def test_auto_falls_back_to_stub_with_same_contract():
    # live if the MCP client works here, otherwise stub fallback; exit code is the same
    code, report, _ = run(BASE, "auto")
    assert code == 0
    assert report["servers"][0]["mode_used"] in ("live", "stub (fallback)")


def test_bad_config_exits_2():
    assert run(None, "stub")[0] == 2
