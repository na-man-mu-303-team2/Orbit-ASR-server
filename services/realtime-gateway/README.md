# Orbit Realtime Gateway

FastAPI + aiortc gateway for the MVP1 realtime Korean ASR spike.

## What It Does

- Accepts browser microphone audio through WebRTC.
- Converts incoming audio to 16kHz mono PCM16 chunks.
- Sends 80ms audio chunks to either mock NIM or real NVIDIA NIM Nemotron ASR.
- Sends status, transcript, error, and latency metrics to the browser through WebSocket.
- Keeps all sessions in memory for spike validation only.

## Backend Setup

```bash
cd services/realtime-gateway
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Mock Mode

Mock mode requires no Docker, GPU, or NIM service.

```bash
cd services/realtime-gateway
NIM_CLIENT=mock uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Or from the repository root:

```bash
NIM_CLIENT=mock scripts/run_realtime_gateway.sh
```

## Real NIM Mode

Start NIM on the target GPU host:

```bash
export NGC_API_KEY=...
scripts/run_nim_nemotron_asr.sh
```

Then start the gateway against the local NIM WebSocket:

```bash
cd services/realtime-gateway
NIM_CLIENT=real \
NIM_REALTIME_WS_URL="ws://localhost:9000/v1/realtime?intent=transcription" \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

`NGC_API_KEY` must stay in the environment and must not be committed.

## Frontend Console

```bash
cd apps/web
npm install
npm run dev
```

Open:

```text
http://localhost:5173/realtime-asr-spike
```

The Vite dev server proxies `/api` and `/health` to `http://localhost:8080`. For a different gateway URL:

```bash
VITE_REALTIME_API_BASE=http://YOUR_GATEWAY:8080 npm run dev
```

## Tests

```bash
cd services/realtime-gateway
pytest
```

Required spike checks currently covered:

- `GET /health` returns gateway status.
- `POST /api/realtime/sessions` returns `sessionId` and `eventsUrl`.
- WebSocket receives initial status and metrics events.
- Stop endpoint cleans up an in-memory session.
- WebRTC offer endpoint returns an answer.
- 80ms 16kHz mono PCM16 chunk size is 2560 bytes.
- PyAV converter emits PCM16 bytes.
- NIM append payload base64 encodes PCM16 bytes.
- Mock NIM emits deterministic Korean partial and final transcript events.
- Transcript normalization collapses repeated whitespace.
- Session cleanup is idempotent.

## Manual Spike Verification

1. Start backend in mock mode.
2. Start the web console.
3. Open `/realtime-asr-spike`.
4. Click Start and approve microphone access.
5. Confirm WebRTC state reaches connected.
6. Confirm mock partial/final transcript appears.
7. Confirm first/latest partial latency and audio chunk counts update.
8. Click Stop and confirm the session can be started again without reloading.
9. Repeat with `NIM_CLIENT=real` on `g6.xlarge` after NIM starts.

## Decision Notes

Record these after a real NIM speaking test:

- Real NIM first partial latency range observed:
- Korean partial quality for presentation coaching:
- WebRTC stability over 3-5 minutes:
- NIM event shape differences from the parser assumptions:
- Recommended next step:
