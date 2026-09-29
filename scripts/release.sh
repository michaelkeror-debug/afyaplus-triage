#!/usr/bin/env bash
# Cut an aligned release: one tag -> one image -> one prompt bundle -> one MCP version.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(cat VERSION)
TAG="v${VERSION}"
python scripts/write_release_manifest.py > /dev/null
python scripts/check_release.py --tag "$TAG"
git add release.json
git diff --cached --quiet || git commit -m "release: ${TAG} manifest"
MCP=$(cat mcp_server/VERSION)
PROMPT=$(python -c "import json;print(json.load(open('prompts/pin.json'))['prompt_version'])")
git tag -a "$TAG" -m "AfyaPlus ${TAG}: image afyaplus-triage:${VERSION}, prompt ${PROMPT}, mcp ${MCP}"
if [[ "${SKIP_DOCKER:-0}" != "1" ]]; then
  docker build \
    --build-arg IMAGE_TAG="afyaplus-triage:${VERSION}" \
    --build-arg GIT_SHA="$(git rev-parse --short HEAD)" \
    -t "afyaplus-triage:${VERSION}" .
fi
echo "Tagged ${TAG}. Push with: git push origin ${TAG} && docker push afyaplus-triage:${VERSION}"
