"""MCP health gate: start the server over stdio (as the agent does), then check
version://current, the tool list, and one real call per tool against clinic.json."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "logistics_mcp.py"
EXPECTED_VERSION = (ROOT / "mcp_server" / "VERSION").read_text().strip()
RELEASE_MCP = json.loads((ROOT / "release.json").read_text())["mcp_server"]["version"]
EXPECTED_TOOLS = {"check_stock", "list_low_stock"}


def tool_json(result) -> dict:
    if getattr(result, "isError", False):
        raise AssertionError(f"tool returned error: {result.content}")
    return json.loads(result.content[0].text)


async def run() -> list[tuple[str, bool, str]]:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)],
                                   cwd=str(ROOT))
    checks = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()

            res = await s.read_resource(AnyUrl("version://current"))
            version = res.contents[0].text.strip()
            checks.append(("version://current == mcp_server/VERSION",
                           version == EXPECTED_VERSION, version))
            checks.append(("version == release.json", version == RELEASE_MCP, RELEASE_MCP))

            names = {t.name for t in (await s.list_tools()).tools}
            checks.append(("tools exposed", EXPECTED_TOOLS <= names, sorted(names)))

            stock = tool_json(await s.call_tool(
                "check_stock", {"clinic_id": "C01", "item": "amoxicillin"}))
            checks.append(("check_stock C01 amoxicillin == 40",
                           stock.get("quantity") == 40, stock))

            low = tool_json(await s.call_tool("list_low_stock", {"clinic_id": "C04"}))
            low_items = {x["item"] for x in low.get("low_stock", [])}
            checks.append(("list_low_stock C04 has amoxicillin + ors_sachets",
                           {"amoxicillin", "ors_sachets"} <= low_items, sorted(low_items)))

            bad = tool_json(await s.call_tool(
                "check_stock", {"clinic_id": "C99", "item": "amoxicillin"}))
            checks.append(("unknown clinic returns error, not a guess",
                           "error" in bad, bad))
    return checks


def main() -> int:
    try:
        checks = asyncio.run(asyncio.wait_for(run(), timeout=60))
    except Exception as exc:
        print(f"MCP HEALTH FAILED: {type(exc).__name__}: {exc}")
        return 1
    for name, ok, detail in checks:
        print(("PASS " if ok else "FAIL ") + f"{name}  [{detail}]")
    ok = all(c[1] for c in checks)
    print("MCP HEALTH OK" if ok else "MCP HEALTH FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
