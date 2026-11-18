#!/bin/sh
# Inert until explicitly invoked. No login, publication, cleanup or host service changes.
set -eu
command -v docker >/dev/null || { echo 'BLOCKED: Docker CLI is unavailable'; exit 1; }
docker info >/dev/null
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
: "${PAYMESH_CONTAINER_ENV_FILE:?Set external container environment file path}"
# Conservative available-space gate: build sizes cannot be measured before first build.
free_kb=$(df -Pk "$repo" | awk 'END {print $4}')
[ "$free_kb" -ge 16777216 ] || { echo 'BLOCKED: reserve at least 16 GiB free before building'; exit 1; }
: "${LLAMA_CPP_SOURCE_DIR:?Set reviewed local llama.cpp source directory}"
[ "$(git -C "$LLAMA_CPP_SOURCE_DIR" rev-parse HEAD)" = ec7f3ac9ab33e46b136eb5ab6a76c4d81f57c7f1 ] || { echo 'BLOCKED: llama.cpp commit differs'; exit 1; }
[ -z "$(git -C "$LLAMA_CPP_SOURCE_DIR" status --porcelain --untracked-files=no)" ] || { echo 'BLOCKED: llama.cpp source has tracked changes'; exit 1; }
docker compose --env-file "$PAYMESH_CONTAINER_ENV_FILE" -f "$repo/deploy/compose.yaml" config --quiet
COMPOSE_PARALLEL_LIMIT=1 docker compose --env-file "$PAYMESH_CONTAINER_ENV_FILE" -f "$repo/deploy/compose.yaml" build java python frontend llama
