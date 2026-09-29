"""AfyaPlus logistics MCP server. Semver lives in mcp_server/VERSION (single source)."""
import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
MCP_VERSION = (HERE / 'VERSION').read_text(encoding='utf-8').strip()

logging.basicConfig(filename=str(HERE / 'mcp_server.log'), level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logging.info('afyaplus-logistics MCP starting, version %s', MCP_VERSION)

mcp = FastMCP('afyaplus-logistics')  # version exposed via version://current

with open(HERE / 'clinic.json', encoding='utf-8') as f:
    CLINICS = {c['id']: c for c in json.load(f)['clinics']}


@mcp.resource('version://current')
def version_current() -> str:
    """Semver of this MCP server. Agents and CI should read this."""
    return MCP_VERSION


@mcp.tool()
def check_stock(clinic_id: str, item: str) -> dict:
    """Check stock of a medical item at one clinic. Schema unchanged since 1.0.0."""
    clinic = CLINICS.get(clinic_id)
    if clinic is None:
        return {'error': f'Unknown clinic_id {clinic_id!r}'}
    qty = clinic['stock'].get(item.lower().strip())
    if qty is None:
        return {'error': f'Item {item!r} not tracked'}
    return {'clinic': clinic['name'], 'item': item, 'quantity': qty,
            'reorder_needed': qty < clinic['reorder_level']}


@mcp.tool()
def list_low_stock(clinic_id: str) -> dict:
    """List items below reorder_level. Additive in 1.1.0 (MINOR), no old schemas changed."""
    clinic = CLINICS.get(clinic_id)
    if clinic is None:
        return {'error': f'Unknown clinic_id {clinic_id!r}'}
    low = [{'item': k, 'quantity': v}
           for k, v in clinic['stock'].items()
           if v < clinic['reorder_level']]
    return {'clinic': clinic['name'], 'low_stock': low, 'mcp_version': MCP_VERSION}


if __name__ == '__main__':
    mcp.run(transport='stdio')
