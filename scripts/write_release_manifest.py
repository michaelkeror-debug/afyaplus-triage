"""Regenerate release.json from the repo's version files (run before tagging)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import runtime as rt  # noqa: E402

manifest = {
    'release': rt.RELEASE_VERSION,
    'git_tag': f'v{rt.RELEASE_VERSION}',
    'image': f'afyaplus-triage:{rt.RELEASE_VERSION}',
    'prompt_bundle': {
        'version': rt.PROMPT_VERSION,
        'file': f'prompts/triage_system_v{rt.PROMPT_VERSION}.txt',
        'sha256': rt.PROMPT_SHA256,
    },
    'config': {
        'version': rt.CONFIG['config_version'],
        'file': 'config/triage.yaml',
        'sha256': rt.CONFIG_SHA256,
    },
    'mcp_server': {'name': 'afyaplus-logistics', 'version': rt.MCP_VERSION},
}
(rt.ROOT / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
