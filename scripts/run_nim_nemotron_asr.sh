#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "NGC_API_KEY is required" >&2
  exit 1
fi

export CONTAINER_ID=nemotron-asr-streaming
export NIM_TAGS_SELECTOR="name=nemotron-asr-streaming,type=multi,batch_size=32"

docker run -it --rm --name="${CONTAINER_ID}" \
  --runtime=nvidia \
  --gpus '"device=0"' \
  --shm-size=8GB \
  -e NGC_API_KEY \
  -e NIM_HTTP_API_PORT=9000 \
  -e NIM_GRPC_API_PORT=50051 \
  -p 9000:9000 \
  -p 50051:50051 \
  -e NIM_TAGS_SELECTOR \
  "nvcr.io/nim/nvidia/${CONTAINER_ID}:latest"
