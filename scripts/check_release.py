"""CI gate: git tag, image tag, prompt bundle, config and MCP version must all agree
with release.json. Usage: python scripts/check_release.py [--tag v1.2.0]"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import runtime as rt  # noqa: E402

SEMVER = re.compile(r'^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$')


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--tag', help='git tag being released, e.g. v1.2.0')
    p.add_argument('--image', help='image tag being pushed, e.g. afyaplus-triage:1.2.0')
    a = p.parse_args()
    m = json.loads((rt.ROOT / 'release.json').read_text())
    checks = [
        ('VERSION is semver', bool(SEMVER.match(rt.RELEASE_VERSION))),
        ('mcp VERSION is semver', bool(SEMVER.match(rt.MCP_VERSION))),
        ('prompt version is semver', bool(SEMVER.match(rt.PROMPT_VERSION))),
        ('release.json == VERSION', m['release'] == rt.RELEASE_VERSION),
        ('image == afyaplus-triage:VERSION', m['image'] == f'afyaplus-triage:{rt.RELEASE_VERSION}'),
        ('config prompt_version == pin', rt.CONFIG['prompt_version'] == rt.PIN['prompt_version']),
        ('prompt file sha == pin', rt.PIN_MATCH),
        ('prompt sha == release.json', m['prompt_bundle']['sha256'] == rt.PROMPT_SHA256),
        ('prompt version == release.json', m['prompt_bundle']['version'] == rt.PROMPT_VERSION),
        ('config sha == release.json', m['config']['sha256'] == rt.CONFIG_SHA256),
        ('mcp version == release.json', m['mcp_server']['version'] == rt.MCP_VERSION),
    ]
    if a.tag:
        checks.append((f'git tag {a.tag} == v{rt.RELEASE_VERSION}', a.tag == m['git_tag']))
    if a.image:
        checks.append((f'image {a.image} == release.json', a.image.endswith(m['image'])))
    for name, ok in checks:
        print(('PASS ' if ok else 'FAIL ') + name)
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
