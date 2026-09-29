"""Resolves every version the running service uses. Stdlib + PyYAML only,
so CI and the README evidence script can import it without FastAPI."""
import hashlib
import json
import os
from pathlib import Path

import yaml

ROOT = Path(os.environ.get('APP_ROOT', Path(__file__).resolve().parent.parent))
PROMPTS_DIR = ROOT / 'prompts'
CONFIG_PATH = ROOT / 'config' / 'triage.yaml'
PIN_PATH = PROMPTS_DIR / 'pin.json'


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8').strip()


CONFIG_BYTES = CONFIG_PATH.read_bytes()
CONFIG = yaml.safe_load(CONFIG_BYTES)
CONFIG_SHA256 = sha256_bytes(CONFIG_BYTES)

RELEASE_VERSION = read_text(ROOT / 'VERSION')
MCP_VERSION = read_text(ROOT / 'mcp_server' / 'VERSION')
IMAGE_TAG = os.environ.get('IMAGE_TAG', f'afyaplus-triage:{RELEASE_VERSION}')
GIT_SHA = os.environ.get('GIT_SHA', 'unknown')

# Config is the source of truth; env var only for canary/candidate testing.
PROMPT_VERSION = os.environ.get('PROMPT_VERSION', CONFIG['prompt_version'])


def load_prompt(version: str) -> str:
    path = PROMPTS_DIR / f'triage_system_v{version}.txt'
    if not path.is_file():
        raise FileNotFoundError(f'No prompt for version {version!r}: {path}')
    return path.read_text(encoding='utf-8')


SYSTEM_PROMPT = load_prompt(PROMPT_VERSION)
PROMPT_SHA256 = sha256_bytes(SYSTEM_PROMPT.encode('utf-8'))

PIN = json.loads(PIN_PATH.read_text(encoding='utf-8'))
PIN_MATCH = (PIN['prompt_version'] == PROMPT_VERSION
             and PIN['prompt_sha256'] == PROMPT_SHA256)

# Fail fast: never serve an unpinned prompt unless explicitly allowed (canary).
if not PIN_MATCH and os.environ.get('ALLOW_UNPINNED_PROMPT') != '1':
    raise RuntimeError(
        f'Prompt {PROMPT_VERSION} sha {PROMPT_SHA256[:12]} does not match '
        f'pin {PIN["prompt_version"]} sha {PIN["prompt_sha256"][:12]}. '
        'Set ALLOW_UNPINNED_PROMPT=1 only for candidate testing.')


def health_payload() -> dict:
    return {
        'status': 'ok',
        'release': RELEASE_VERSION,
        'image_tag': IMAGE_TAG,
        'git_sha': GIT_SHA,
        'prompt_version': PROMPT_VERSION,
        'prompt_sha256': PROMPT_SHA256,
        'prompt_pinned': PIN_MATCH,
        'config_version': CONFIG['config_version'],
        'config_sha256': CONFIG_SHA256,
        'model': CONFIG['model'],
        'temperature': CONFIG['temperature'],
        'mcp_server': {'name': 'afyaplus-logistics', 'version': MCP_VERSION},
    }


if __name__ == '__main__':
    print(json.dumps(health_payload(), indent=2))
