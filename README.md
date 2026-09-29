# AfyaPlus Triage — Deliverable 1: Versioned Prompts, Config and MCP

## 1. Versioned artefacts (semver + explicit version files)

| Artefact | Version source | Current |
|---|---|---|
| Release / image | `VERSION` | `1.2.0` |
| Prompt bundle | `prompts/triage_system_v<semver>.txt` + `prompts/pin.json` | `1.2.0` (sha `28b5f129…d4ff`) |
| Config | `config/triage.yaml` → `config_version`, `prompt_version` | `1.0.0`, prompt `1.2.0` |
| MCP server | `mcp_server/VERSION` → `MCP_VERSION`, resource `version://current` | `1.1.0` |

Changelogs: `prompts/CHANGELOG.md`, `mcp_server/CHANGELOG.md`.
The `1.3.0-candidate` prompt is kept in the repo but is **not pinned**: the service
refuses to start with it unless `ALLOW_UNPINNED_PROMPT=1` (canary testing only).

## 2. Aligned release tag

One git tag binds the image tag, prompt bundle, config and MCP version, recorded in `release.json`:

```
v1.2.0  ->  image afyaplus-triage:1.2.0
        ->  prompt bundle 1.2.0  sha256 28b5f129a4bd3650b5765d74681c63df803ea241a0dd749dc7c99d4b0bd4d4ff
        ->  config 1.0.0         sha256 bf6fa48582b8092f7c72ea93b6054fc40187b4a5415a36dc54eff155f934ecaf
        ->  MCP afyaplus-logistics 1.1.0
```

Components keep independent semver (MCP stays `1.1.0` because nothing in it changed;
bumping it just to match would break semver). Alignment is enforced, not assumed:

- `scripts/release.sh` regenerates `release.json`, runs the gate, creates the annotated tag, builds the image with the same tag.
- `scripts/check_release.py --tag vX.Y.Z` fails if tag, `VERSION`, image, prompt SHA, pin, config or MCP version disagree.
- `Dockerfile` runs the gate at build time; `.github/workflows/release.yml` runs it on every tag and PR, then boots the image and runs `check_prompt_pin.py` against live `/health`.

Evidence (tag cut in this repo):

```
$ git tag -n1
v1.2.0   AfyaPlus v1.2.0: image afyaplus-triage:1.2.0, prompt 1.2.0, mcp 1.1.0

$ python scripts/check_release.py --tag v1.2.0
PASS VERSION is semver
PASS mcp VERSION is semver
PASS prompt version is semver
PASS release.json == VERSION
PASS image == afyaplus-triage:VERSION
PASS config prompt_version == pin
PASS prompt file sha == pin
PASS prompt sha == release.json
PASS prompt version == release.json
PASS config sha == release.json
PASS mcp version == release.json
PASS git tag v1.2.0 == v1.2.0

$ python scripts/check_release.py --tag v1.3.0      # negative test
FAIL git tag v1.3.0 == v1.2.0
```

## 3. `/health` exposes prompt SHA and runtime versions

```
$ curl -s localhost:8000/health
{
  "status": "ok",
  "release": "1.2.0",
  "image_tag": "afyaplus-triage:1.2.0",
  "git_sha": "db5d07b",
  "prompt_version": "1.2.0",
  "prompt_sha256": "28b5f129a4bd3650b5765d74681c63df803ea241a0dd749dc7c99d4b0bd4d4ff",
  "prompt_pinned": true,
  "config_version": "1.0.0",
  "config_sha256": "bf6fa48582b8092f7c72ea93b6054fc40187b4a5415a36dc54eff155f934ecaf",
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "mcp_server": {"name": "afyaplus-logistics", "version": "1.1.0"}
}

$ python scripts/check_prompt_pin.py
prompt pin OK 1.2.0 28b5f129a4bd...
```

Unpinned prompt is blocked at startup:

```
$ PROMPT_VERSION=1.3.0-candidate uvicorn app.prompt_app:app
RuntimeError: Prompt 1.3.0-candidate sha 00d808e2e3b7 does not match pin 1.2.0 sha 28b5f129a4bd.
Set ALLOW_UNPINNED_PROMPT=1 only for candidate testing.
```

## Run

```bash
pip install -r requirements.txt
uvicorn app.prompt_app:app --port 8000        # API + /health
python mcp_server/logistics_mcp.py            # MCP (stdio); read version://current
./scripts/release.sh                          # cut aligned tag + image
```

## Layout

```
VERSION  release.json  Dockerfile  requirements.txt
prompts/     triage_system_v1.2.0.txt  triage_system_v1.3.0-candidate.txt  pin.json  CHANGELOG.md
config/      triage.yaml
mcp_server/  logistics_mcp.py  VERSION  clinic.json (sample data)  CHANGELOG.md
app/         runtime.py (version resolution)  prompt_app.py (FastAPI)
scripts/     check_release.py  check_prompt_pin.py  write_release_manifest.py  release.sh
.github/workflows/release.yml
```
