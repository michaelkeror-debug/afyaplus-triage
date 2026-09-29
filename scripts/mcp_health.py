"""MCP health probe for CI.

Probes every server in config/mcp_required.yaml: version resource, required tools,
and tool calls with expected results.

Modes:
  live  - start the server over stdio with the MCP client (same path as the agent)
  stub  - import the server module in-process and call its tools directly
  auto  - live; if the server is unavailable (cannot start/connect), fall back to stub
          when the server allows it

Exit-code contract (identical in every mode):
  0 = all required servers and tools healthy
  1 = a probe failed, a tool is missing, or a server is unavailable with no fallback
  2 = invalid or missing config
"""
import argparse
import asyncio
import contextlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EXIT_OK, EXIT_FAILED, EXIT_CONFIG = 0, 1, 2
CONNECT_TIMEOUT = 20
CALL_TIMEOUT = 20


class Unavailable(Exception):
    """Server could not be started or reached (eligible for stub fallback)."""


# ---------- expectations ----------
def check_result(probe: dict, result: dict) -> tuple[bool, str]:
    if probe.get("expect_error"):
        return ("error" in result, f"error returned: {result.get('error', '<none>')}")
    if "error" in result:
        return False, f"tool error: {result['error']}"
    for key, want in probe.get("expect", {}).items():
        if result.get(key) != want:
            return False, f"{key}={result.get(key)!r}, expected {want!r}"
    rule = probe.get("expect_list_contains")
    if rule:
        items = {x.get(rule["key"]) for x in result.get(rule["field"], [])}
        missing = sorted(set(rule["values"]) - items)
        if missing:
            return False, f"{rule['field']} missing {missing}"
    return True, "ok"


async def run_checks(server: dict, read_version, list_tools, call_tool) -> list[dict]:
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "detail": str(detail)})

    expected = (ROOT / server["expected_version_file"]).read_text().strip()
    try:
        version = await read_version(server["version_resource"])
        add(f"{server['version_resource']} == {server['expected_version_file']}",
            version == expected, f"got {version}, expected {expected}")
    except Exception as exc:
        add(f"read {server['version_resource']}", False, f"{type(exc).__name__}: {exc}")

    try:
        names = set(await list_tools())
        missing = sorted(set(server["required_tools"]) - names)
        add("required tools exposed", not missing,
            f"missing {missing}" if missing else sorted(names))
    except Exception as exc:
        names = set()
        add("list tools", False, f"{type(exc).__name__}: {exc}")

    for probe in server.get("probes", []):
        label = f"{probe['tool']}({json.dumps(probe.get('args', {}), sort_keys=True)})"
        if probe["tool"] not in names:
            add(label, False, "tool not exposed")
            continue
        try:
            result = await call_tool(probe["tool"], probe.get("args", {}))
            ok, detail = check_result(probe, result)
            add(label, ok, detail)
        except Exception as exc:
            add(label, False, f"{type(exc).__name__}: {exc}")
    return checks


# ---------- live: stdio MCP client ----------
async def probe_live(server: dict) -> list[dict]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from pydantic import AnyUrl
    except ImportError as exc:
        raise Unavailable(f"MCP client library not installed: {exc}") from exc

    if not (ROOT / server["module"]).is_file():
        raise Unavailable(f"server module not found: {server['module']}")
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / server["module"])], cwd=str(ROOT))
    async with contextlib.AsyncExitStack() as stack:
        try:
            read, write = await asyncio.wait_for(
                stack.enter_async_context(stdio_client(params)), CONNECT_TIMEOUT)
            session = await stack.enter_async_context(ClientSession(read, write))
            await asyncio.wait_for(session.initialize(), CONNECT_TIMEOUT)
        except Exception as exc:
            raise Unavailable(f"{type(exc).__name__}: {exc}") from exc

        async def read_version(uri):
            res = await asyncio.wait_for(session.read_resource(AnyUrl(uri)), CALL_TIMEOUT)
            return res.contents[0].text.strip()

        async def list_tools():
            res = await asyncio.wait_for(session.list_tools(), CALL_TIMEOUT)
            return [t.name for t in res.tools]

        async def call_tool(name, args):
            res = await asyncio.wait_for(session.call_tool(name, args), CALL_TIMEOUT)
            if getattr(res, "isError", False):
                return {"error": str(res.content)}
            return json.loads(res.content[0].text)

        return await run_checks(server, read_version, list_tools, call_tool)


# ---------- stub: import the module in-process ----------
class _RecordingFastMCP:
    """Stand-in for FastMCP that records decorated tools and resources."""

    def __init__(self, name, *args, **kwargs):
        self.name, self.tools, self.resources = name, {}, {}

    def tool(self, *args, **kwargs):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco

    def resource(self, uri, *args, **kwargs):
        def deco(fn):
            self.resources[uri] = fn
            return fn
        return deco

    def run(self, *args, **kwargs):
        pass


def load_stub(server: dict) -> _RecordingFastMCP:
    shim = types.ModuleType("mcp.server.fastmcp")
    shim.FastMCP = _RecordingFastMCP
    names = ("mcp", "mcp.server", "mcp.server.fastmcp")
    saved = {n: sys.modules.get(n) for n in names}
    sys.modules.update({"mcp": types.ModuleType("mcp"),
                        "mcp.server": types.ModuleType("mcp.server"),
                        "mcp.server.fastmcp": shim})
    try:
        path = ROOT / server["module"]
        spec = importlib.util.spec_from_file_location(f"_stub_{server['name']}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for n, mod in saved.items():
            if mod is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = mod
    instances = [v for v in vars(module).values() if isinstance(v, _RecordingFastMCP)]
    if not instances:
        raise RuntimeError("no FastMCP server object found in module")
    return instances[0]


async def probe_stub(server: dict) -> list[dict]:
    try:
        srv = load_stub(server)
    except Exception as exc:
        return [{"check": "stub import", "passed": False,
                 "detail": f"{type(exc).__name__}: {exc}"}]

    async def read_version(uri):
        if uri not in srv.resources:
            raise KeyError(f"resource {uri} not defined")
        return str(srv.resources[uri]()).strip()

    async def list_tools():
        return list(srv.tools)

    async def call_tool(name, args):
        return srv.tools[name](**args)

    return await run_checks(server, read_version, list_tools, call_tool)


# ---------- orchestration ----------
async def probe_server(server: dict, mode: str) -> dict:
    report = {"name": server["name"], "mode_requested": mode, "mode_used": mode,
              "fallback_reason": None}
    if mode == "stub":
        report["checks"] = await probe_stub(server)
    else:
        try:
            report["checks"] = await probe_live(server)
            report["mode_used"] = "live"
        except Unavailable as exc:
            if mode == "auto" and server.get("allow_stub_fallback", False):
                report["mode_used"] = "stub (fallback)"
                report["fallback_reason"] = str(exc)
                report["checks"] = await probe_stub(server)
            else:
                report["mode_used"] = "live"
                report["checks"] = [{"check": "server reachable", "passed": False,
                                     "detail": str(exc)}]
    report["healthy"] = all(c["passed"] for c in report["checks"])
    return report


def load_config(path: Path) -> list[dict]:
    try:
        cfg = yaml.safe_load(path.read_text())
        servers = cfg["servers"]
        for s in servers:
            for key in ("name", "module", "version_resource", "expected_version_file",
                        "required_tools"):
                if key not in s:
                    raise KeyError(f"server {s.get('name', '?')} missing '{key}'")
        if not servers:
            raise ValueError("no servers listed")
        return servers
    except Exception as exc:
        print(f"MCP HEALTH CONFIG ERROR: {type(exc).__name__}: {exc}")
        sys.exit(EXIT_CONFIG)


def write_summary(reports: list[dict]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["### MCP health", "", "| Server | Mode | Check | Result |", "|---|---|---|---|"]
    for r in reports:
        for c in r["checks"]:
            lines.append(f"| {r['name']} | {r['mode_used']} | `{c['check']}` | "
                         f"{'PASS' if c['passed'] else 'FAIL: ' + c['detail']} |")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "config" / "mcp_required.yaml"))
    p.add_argument("--mode", choices=["auto", "live", "stub"], default="auto")
    p.add_argument("--report", default="mcp_health_report.json")
    a = p.parse_args()

    servers = load_config(Path(a.config))
    reports = [asyncio.run(probe_server(s, a.mode)) for s in servers]
    healthy = all(r["healthy"] for r in reports)

    for r in reports:
        print(f"== {r['name']}  mode={r['mode_used']}")
        if r["fallback_reason"]:
            print(f"   WARNING live unavailable, used stub: {r['fallback_reason']}")
        for c in r["checks"]:
            print(("   PASS " if c["passed"] else "   FAIL ") + f"{c['check']}  [{c['detail']}]")
    Path(a.report).write_text(json.dumps({"healthy": healthy, "servers": reports}, indent=2))
    write_summary(reports)
    print("MCP HEALTH OK" if healthy else "MCP HEALTH FAILED")
    return EXIT_OK if healthy else EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
