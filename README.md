# Orbit ASR Spike

Realtime Korean ASR spike using browser WebRTC audio upload, a FastAPI gateway, NVIDIA NIM Nemotron ASR, and a static React/nginx test console.

## g6.xlarge Real NIM Deployment

Prerequisites:

- NVIDIA driver and NVIDIA Container Toolkit installed on the `g6.xlarge` host.
- Docker Engine with Compose v2.
- NGC access for `nvcr.io/nim/nvidia/nemotron-asr-streaming:latest`.
- `NGC_API_KEY` exported as an environment variable. Do not commit it.

Run:

```bash
export NGC_API_KEY=...
docker compose -f docker-compose.realtime.yml --profile nim up --build
```

This builds:

- `orbit-realtime-gateway:latest` from `services/realtime-gateway/Dockerfile`
- `orbit-realtime-asr-web:latest` from `apps/web/Dockerfile`

And starts:

- `nim-asr` from `nvcr.io/nim/nvidia/nemotron-asr-streaming:latest`
- `realtime-gateway` with `NIM_CLIENT=real`
- `realtime-gateway` connected to `ws://nim-asr:9000/v1/realtime?intent=transcription`
- `web` as an nginx-served static Vite build

Open:

```text
http://<g6-public-hostname-or-ip>:5173/realtime-asr-spike
```

If port `5173` is already in use on the host, override only the published web port:

```bash
WEB_PORT=5174 docker compose -f docker-compose.realtime.yml --profile nim up --build
```

## Local Docker Mock Mode

```bash
NIM_CLIENT=mock docker compose -f docker-compose.realtime.yml up --build realtime-gateway web
```

This skips the NIM profile and uses deterministic Korean mock transcripts.

## Local Development

Backend:

```bash
cd services/realtime-gateway
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
NIM_CLIENT=mock uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

See `services/realtime-gateway/README.md` for API details, tests, and real-mode notes.
