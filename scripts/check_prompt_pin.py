"""CI gate: the running /health must match the committed prompt pin."""
import argparse
import json
import urllib.request


def load_pin(path: str = 'prompts/pin.json') -> dict:
    with open(path) as f:
        return json.load(f)


def fetch_health(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:8000/health')
    p.add_argument('--pin', default='prompts/pin.json')
    args = p.parse_args()

    pin = load_pin(args.pin)
    try:
        health = fetch_health(args.url)
    except Exception as exc:
        print('PROMPT PIN CHECK FAILED: /health unreachable:', exc)
        return 1
    ok = (health.get('prompt_version') == pin['prompt_version']
          and health.get('prompt_sha256') == pin['prompt_sha256'])
    if ok:
        print('prompt pin OK', pin['prompt_version'], pin['prompt_sha256'][:12] + '...')
        return 0
    print('PROMPT PIN MISMATCH')
    print('  expected:', pin)
    print('  health:  ', {k: health.get(k) for k in ('prompt_version', 'prompt_sha256')})
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
