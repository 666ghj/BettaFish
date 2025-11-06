#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-bettafish}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bettafish}"

cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker CLI not found on PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker daemon is not reachable. Is Docker running?" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo ".env not found. Creating it from .env.example for convenience."
  cp .env.example .env
fi

# Negotiate an available port and keep .env in sync with the choice.
if ! PORT_OUTPUT="$(python -m utils.port_utils)"; then
  exit $?
fi

HOST="$(printf '%s\n' "$PORT_OUTPUT" | sed -n '1p')"
PORT="$(printf '%s\n' "$PORT_OUTPUT" | sed -n '2p')"
PORT_CHANGED="$(printf '%s\n' "$PORT_OUTPUT" | sed -n '3p')"
PORT_CHANGED="${PORT_CHANGED:-0}"

if [[ -z "${PORT}" ]]; then
  echo "Error: 未能解析可用端口。" >&2
  exit 1
fi

if [[ "${PORT_CHANGED}" == "1" ]]; then
  echo "PORT 已调整为 ${PORT} 并写入 .env。"
else
  echo "PORT 使用 ${PORT}。"
fi

export PORT

# Ensure bind-mounted directories exist to avoid root-owned folders being created later.
for dir in logs final_reports insight_engine_streamlit_reports media_engine_streamlit_reports query_engine_streamlit_reports; do
  mkdir -p "${dir}"
done

echo "Building Docker image ${IMAGE_NAME}:${IMAGE_TAG}..."
docker build --tag "${IMAGE_NAME}:${IMAGE_TAG}" -f Dockerfile .

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Error: Docker Compose plugin or docker-compose binary not found." >&2
  exit 1
fi

echo "Starting services with ${COMPOSE_CMD[*]}..."
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --project-name "${COMPOSE_PROJECT_NAME}" up --build "$@"
