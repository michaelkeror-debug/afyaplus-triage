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
  "git_sha": "<short commit of v1.2.0, injected by docker build --build-arg GIT_SHA>",
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

---

# Deliverable 2: CI/CD pipeline

Workflow: `.github/workflows/ci.yml`. Four jobs; each runs only if the previous one passes.

| # | Job | What it gates |
|---|---|---|
| 1 | Lint and tests | `ruff check .`, `check_release.py`, `pytest` (runtime/pin, MCP tools, API, eval scorer) |
| 2 | Eval gate | `scripts/run_eval.py` on `evals/golden.jsonl` (8 triage cases). Fails if pass rate < 0.85 or any safety violation (dose, diagnosis, missing disclaimer) |
| 3 | MCP health | `scripts/mcp_health.py` starts the MCP server over stdio, checks `version://current` == `mcp_server/VERSION` == `release.json`, both tools listed, real calls against `clinic.json` |
| 4 | Build and deploy | Builds `afyaplus-triage:<VERSION>`, runs it, `/health` smoke test + pin check. On `main`: push to ACR, update Azure Container App, re-check live `/health`. On PRs (or without Azure secrets): deploy stub written to the job summary |

**Triggers:** `pull_request`, `push` to `main`, and `workflow_dispatch` (Actions → ci → Run workflow;
tick *deploy* to deploy). Use `workflow_dispatch` if your account is minute-limited.
`release.yml` runs only on `v*.*.*` tags.

## Eval modes
- `OPENAI_API_KEY` secret set → **live**: calls `gpt-4o-mini` with the pinned prompt and `config/triage.yaml` settings.
- No key → **offline**: scores `evals/recorded/triage_v<prompt>.jsonl`. Recordings store the prompt SHA and fail as stale if the prompt changes.
- The shipped recordings are hand-written seed placeholders (the eval prints a warning). Replace them with real model output:
  `OPENAI_API_KEY=sk-... python scripts/run_eval.py --mode live --record`
- `must_include` rules accept alternatives with `|`; every response must also contain a care disclaimer (`evals/eval_config.json`).

## One-time Azure setup
```bash
az login
RG=afyaplus-rg; LOC=westeurope; ACR=afyaplusacr$RANDOM; APP=afyaplus-triage
az group create -n $RG -l $LOC
az acr create -n $ACR -g $RG --sku Basic --admin-enabled true
az acr build -r $ACR -t afyaplus-triage:1.2.0 --build-arg IMAGE_TAG=afyaplus-triage:1.2.0 .
az containerapp env create -n afyaplus-env -g $RG -l $LOC
az containerapp create -n $APP -g $RG --environment afyaplus-env \
  --image $ACR.azurecr.io/afyaplus-triage:1.2.0 --registry-server $ACR.azurecr.io \
  --target-port 8000 --ingress external
az ad sp create-for-rbac --name afyaplus-gha --role contributor \
  --scopes $(az group show -n $RG --query id -o tsv) --json-auth
echo "ACR_NAME=$ACR"
```

## GitHub settings (Settings → Secrets and variables → Actions)
| Kind | Name | Value |
|---|---|---|
| Secret | `AZURE_CREDENTIALS` | full JSON printed by `create-for-rbac` |
| Secret | `OPENAI_API_KEY` | optional; enables live eval |
| Variable | `ACR_NAME` | e.g. `afyaplusacr12345` |
| Variable | `AZURE_RESOURCE_GROUP` | `afyaplus-rg` |
| Variable | `CONTAINERAPP_NAME` | `afyaplus-triage` |

## Run the same gates locally
```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && python scripts/check_release.py && pytest -q
python scripts/run_eval.py
python scripts/mcp_health.py
```
