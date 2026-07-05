#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../services/realtime-gateway"
export NIM_CLIENT="${NIM_CLIENT:-mock}"
uvicorn app.main:app --host "${REALTIME_HOST:-0.0.0.0}" --port "${REALTIME_PORT:-8080}" --reload
