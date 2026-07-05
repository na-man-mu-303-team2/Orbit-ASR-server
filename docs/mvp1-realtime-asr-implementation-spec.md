# Orbit Realtime ASR Spike Spec

## Status
Spike implementation spec

## Date
2026-07-05

## Objective
이 작업의 목적은 Orbit 발표 코칭 서비스의 전체 MVP를 완성하는 것이 아니라, 실시간 한국어 ASR 파이프라인이 실제로 쓸 만한지 빠르게 검증하는 스파이크다.

검증할 핵심 질문은 세 가지다.

1. 브라우저 마이크 음성을 WebRTC로 서버에 안정적으로 보낼 수 있는가?
2. 서버가 받은 음성을 NVIDIA NIM Nemotron ASR Streaming Realtime API로 전달하고 partial/final transcript를 받을 수 있는가?
3. 프론트엔드에서 WebSocket으로 transcript와 latency 측정값을 받아 실시간 전사 체감 지연을 확인할 수 있는가?

완성형 런타임, cue graph, 자동 슬라이드 넘김, 장기 운영 구조는 이번 범위가 아니다. 이번 문서는 “한 명의 개발자가 빠르게 붙여 보고, 브라우저에서 말하면 전사가 뜨고, 각 구간 지연이 숫자로 보이는 상태”를 만드는 데 초점을 둔다.

## Spike Outcome
스파이크가 끝나면 다음을 확인할 수 있어야 한다.

- 브라우저에서 Start를 누르면 마이크 권한을 받고 WebRTC 연결이 열린다.
- 서버 로그에서 audio frame 수신과 NIM 전송 chunk를 볼 수 있다.
- NIM real mode 또는 mock mode에서 partial/final transcript가 WebSocket으로 브라우저에 도착한다.
- UI에서 partial transcript, final transcript, WebRTC state, WebSocket state, latency 숫자를 바로 볼 수 있다.
- Stop을 누르면 브라우저 media track, peer connection, WebSocket, 서버 session task가 종료된다.
- 측정 결과를 보고 다음 단계 투자 여부를 판단할 수 있다.

## Non-Goals
- production-ready WebRTC Gateway
- 여러 사용자 동시 처리 최적화
- TURN 서버 운영
- Kubernetes/Helm 배포
- persistent session 저장소
- 인증/권한/결제
- cue graph matcher
- 자동 강조/자동 슬라이드 넘김
- LLM 피드백 리포트
- 한국어 ASR fine-tuning
- Prometheus/Grafana 대시보드
- p50/p95 장기 통계

## Working Assumptions
- 오디오는 반드시 WebRTC로 서버에 보낸다.
- transcript, status, latency event는 WebSocket으로 브라우저에 보낸다.
- 단일 개발/검증 환경은 AWS EC2 `g6.xlarge` 한 대를 기준으로 한다.
- NIM은 같은 host의 `ws://localhost:9000/v1/realtime?intent=transcription`에 떠 있다고 가정한다.
- NIM이 없을 때 UI와 서버 흐름을 확인하기 위해 mock client를 둔다.
- mock mode는 smoke/integration 검증용이고, 스파이크의 최종 판단은 가능하면 real NIM mode로 한다.
- 현재 저장소에 앱 코드가 없으면 새 구조를 만들고, 기존 frontend가 생기면 그 안에 테스트 페이지를 붙인다.

## Fast Path Architecture

```text
[Browser Test Page]
  - getUserMedia({ audio: true })
  - RTCPeerConnection audio uplink
  - WebSocket transcript/status/latency downlink

[Realtime Gateway: FastAPI + aiortc]
  - POST /api/realtime/sessions
  - POST /api/realtime/sessions/{sessionId}/offer
  - WS /api/realtime/sessions/{sessionId}/events
  - incoming audio track receiver
  - 16kHz mono PCM16 conversion
  - 80ms audio chunking
  - NIM WebSocket client
  - lightweight per-session metrics

[NVIDIA NIM ASR]
  - nemotron-asr-streaming
  - language=ko-KR
  - ws://localhost:9000/v1/realtime?intent=transcription
```

## Minimal Tech Stack

Backend:
- Python 3.11+
- FastAPI
- Uvicorn
- aiortc
- PyAV audio resampling through aiortc/PyAV
- websockets
- Pydantic
- pytest only for focused smoke/unit tests

Frontend:
- Existing React/Next.js app if present
- Otherwise a minimal Vite React app is acceptable
- Native `getUserMedia`, `RTCPeerConnection`, and `WebSocket`

Deployment:
- Local mock mode for fast development
- Single `g6.xlarge` real mode for NIM verification

## Suggested File Layout

Keep the spike small. Do not build a broad service framework unless the repo already has one.

```text
services/realtime-gateway/
  app/
    main.py
    config.py
    models.py
    session.py
    audio.py
    nim_client.py
    mock_nim_client.py
    metrics.py
  tests/
    test_audio.py
    test_metrics.py
    test_stabilizer.py
    test_health.py
  pyproject.toml
  README.md

apps/web/
  src/
    features/
      realtime-asr-spike/
        RealtimeAsrSpikePage.tsx
        useRealtimeAsrSpike.ts

scripts/
  run_nim_nemotron_asr.sh
  run_realtime_gateway.sh

.env.example
docker-compose.realtime.yml
```

If an existing application structure appears later, preserve that structure and map these files into the existing conventions.

## Environment Variables

```dotenv
REALTIME_HOST=0.0.0.0
REALTIME_PORT=8080
NIM_CLIENT=mock
NIM_REALTIME_WS_URL=ws://localhost:9000/v1/realtime?intent=transcription
NIM_LANGUAGE_CODE=ko-KR
NIM_MODEL=nemotron-asr-streaming
NIM_SAMPLE_RATE=16000
NIM_NUM_CHANNELS=1
NIM_AUDIO_FORMAT=pcm16
NIM_AUDIO_CHUNK_MS=80
LOG_LEVEL=INFO
NGC_API_KEY=
```

Rules:
- `NIM_CLIENT=mock` must work without Docker, GPU, or NIM.
- `NIM_CLIENT=real` must attempt the real NIM WebSocket connection.
- `NIM_AUDIO_CHUNK_MS` defaults to `80`; acceptable spike range is `40..100`.
- `NGC_API_KEY` is never hardcoded.

## API Contract

### `GET /health`

Used to verify the gateway is alive.

```json
{
  "status": "ok",
  "service": "realtime-gateway",
  "nimClient": "mock"
}
```

### `POST /api/realtime/sessions`

Creates an in-memory spike session.

Response:

```json
{
  "sessionId": "rt_...",
  "status": "created",
  "eventsUrl": "/api/realtime/sessions/rt_.../events"
}
```

### `POST /api/realtime/sessions/{sessionId}/offer`

Receives the browser WebRTC offer and returns the server answer.

Request:

```json
{
  "type": "offer",
  "sdp": "v=0..."
}
```

Response:

```json
{
  "type": "answer",
  "sdp": "v=0..."
}
```

### `WS /api/realtime/sessions/{sessionId}/events`

Sends browser-facing events. This WebSocket is the main spike feedback loop.

Transcript event:

```json
{
  "sessionId": "rt_...",
  "kind": "transcript",
  "type": "partial",
  "text": "안녕하세요",
  "receivedAt": 1783241702222,
  "source": "nim",
  "latency": {
    "firstAudioToThisTranscriptMs": 430,
    "lastChunkSentToThisTranscriptMs": 190,
    "serverReceivedToBrowserSentMs": 8
  },
  "raw": {}
}
```

Status event:

```json
{
  "sessionId": "rt_...",
  "kind": "status",
  "state": "webrtc_connected",
  "receivedAt": 1783241701500
}
```

Metrics event:

```json
{
  "sessionId": "rt_...",
  "kind": "metrics",
  "receivedAt": 1783241703000,
  "metrics": {
    "webrtcConnectedAt": 1783241701500,
    "firstAudioFrameAt": 1783241701800,
    "firstChunkSentToNimAt": 1783241701900,
    "firstTranscriptAt": 1783241702230,
    "firstPartialLatencyMs": 430,
    "latestPartialLatencyMs": 190,
    "audioChunksSent": 24,
    "audioBytesSent": 61440,
    "audioChunkDropCount": 0,
    "nimReconnectCount": 0
  }
}
```

Error event:

```json
{
  "sessionId": "rt_...",
  "kind": "error",
  "message": "nim_ws_closed",
  "receivedAt": 1783241703000,
  "raw": {
    "code": 1006
  }
}
```

## Frontend Spike Page

Create a page named `/realtime-asr-spike` when the frontend router allows it.

Required controls:
- Start
- Stop
- Clear transcript

Required display:
- Session ID
- WebRTC connection state
- WebSocket state
- NIM client mode: `mock` or `real`
- Current partial transcript
- Final transcript log
- First partial latency
- Latest partial latency
- Audio chunks sent
- Error panel

Start flow:
1. Call `getUserMedia({ audio: true })`.
2. `POST /api/realtime/sessions`.
3. Open `WebSocket` using `eventsUrl`.
4. Create `RTCPeerConnection`.
5. Add microphone audio track.
6. Create offer and set local description.
7. Send offer to `/offer`.
8. Set remote answer.
9. Render incoming transcript/status/metrics/error events.

Stop flow:
1. Stop local media tracks.
2. Close `RTCPeerConnection`.
3. Close WebSocket.
4. Keep transcript and metrics visible for inspection.

The page should be utilitarian. It is a test console, not a product screen.

## Backend Spike Implementation

### Session Object
Keep one in-memory object per session:

```python
class RealtimeSpikeSession:
    session_id: str
    peer_connection: RTCPeerConnection | None
    events: set[WebSocket]
    nim_client: NimClientProtocol
    metrics: SessionMetrics
    tasks: set[asyncio.Task]
```

Required methods:
- `handle_offer(sdp, type) -> answer`
- `broadcast(event) -> None`
- `on_audio_track(track) -> None`
- `stop() -> None`

`stop()` must be idempotent.

### Audio Handling
For the spike, keep the audio pipeline as direct as possible.

- Read `await track.recv()` in one background task.
- Resample each frame to 16kHz mono PCM16.
- Buffer bytes until one chunk is ready.
- Default chunk size is 80ms.
- Send chunks to NIM client with a monotonic timestamp.
- Log every chunk or every N chunks if logs are too noisy.

Chunk math:

```text
16000 samples/sec * 2 bytes/sample * 0.08 sec = 2560 bytes
```

### NIM Client
Define a tiny interface:

```python
class NimClientProtocol(Protocol):
    async def connect(self) -> None: ...
    async def send_audio(self, pcm16: bytes, sent_at_ms: int) -> None: ...
    async def events(self) -> AsyncIterator[TranscriptEvent]: ...
    async def close(self) -> None: ...
```

Real client behavior:
- Connect to `NIM_REALTIME_WS_URL`.
- Send `transcription_session.update` after connect.
- Send base64 PCM16 chunks as `input_audio_buffer.append`.
- Send `input_audio_buffer.commit` on stop.
- Preserve raw NIM events in logs and browser error/debug payloads when useful.

Initial session update:

```json
{
  "type": "transcription_session.update",
  "session": {
    "modalities": ["text"],
    "input_audio_format": "pcm16",
    "input_audio_transcription": {
      "language": "ko-KR",
      "model": "nemotron-asr-streaming"
    },
    "input_audio_params": {
      "sample_rate_hz": 16000,
      "num_channels": 1
    },
    "recognition_config": {
      "enable_automatic_punctuation": true,
      "enable_verbatim_transcripts": true
    },
    "word_boosting": {
      "enabled": false,
      "terms": []
    }
  }
}
```

Append event:

```json
{
  "type": "input_audio_buffer.append",
  "audio": "base64-encoded-pcm16"
}
```

Mock client behavior:
- No network calls.
- After several audio chunks, emit deterministic Korean partial/final examples.
- Include artificial delay so latency rendering can be tested.

### Transcript Handling
Do not build a full stabilizer for the spike. Implement only enough to make UI readable:

- Normalize repeated whitespace.
- Show partial immediately.
- Append final transcript to a final transcript log.
- If the same partial repeats, set `stablePartial=true`.

## Latency Measurement

The spike must produce actionable latency numbers, even if they are approximate.

Record these timestamps in milliseconds:
- `sessionCreatedAt`
- `websocketConnectedAt`
- `webrtcConnectedAt`
- `firstAudioFrameAt`
- `firstChunkSentToNimAt`
- `lastChunkSentToNimAt`
- `firstTranscriptAt`
- `latestTranscriptAt`
- `browserEventReceivedAt`

Compute and show:
- `firstPartialLatencyMs = firstTranscriptAt - firstAudioFrameAt`
- `latestPartialLatencyMs = latestTranscriptAt - lastChunkSentToNimAt`
- `serverToBrowserEventLatencyMs = browserEventReceivedAt - event.receivedAt`

Notes:
- `firstPartialLatencyMs` is the most important spike number.
- `latestPartialLatencyMs` is useful for steady-state feel.
- Browser receive time is measured in the frontend when the WebSocket message arrives.
- Exact audio capture timestamp is not required for this spike.

## Logging

Use JSON logs so the spike can be debugged quickly.

Audio chunk log:

```json
{
  "sessionId": "rt_...",
  "event": "audio_chunk_sent_to_nim",
  "chunkMs": 80,
  "bytes": 2560,
  "audioChunksSent": 12,
  "timestamp": 1783241702000
}
```

Transcript log:

```json
{
  "sessionId": "rt_...",
  "event": "transcript_received",
  "type": "partial",
  "textLength": 16,
  "firstAudioToThisTranscriptMs": 430,
  "lastChunkSentToThisTranscriptMs": 190,
  "timestamp": 1783241702230
}
```

Connection log:

```json
{
  "sessionId": "rt_...",
  "event": "webrtc_connection_state",
  "state": "connected",
  "timestamp": 1783241701500
}
```

## Scripts

### `scripts/run_nim_nemotron_asr.sh`

```bash
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
```

### `scripts/run_realtime_gateway.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../services/realtime-gateway"
export NIM_CLIENT="${NIM_CLIENT:-mock}"
uvicorn app.main:app --host "${REALTIME_HOST:-0.0.0.0}" --port "${REALTIME_PORT:-8080}" --reload
```

## Commands

Backend setup:

```bash
cd services/realtime-gateway
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Backend mock server:

```bash
cd services/realtime-gateway
NIM_CLIENT=mock uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Backend real NIM server:

```bash
cd services/realtime-gateway
NIM_CLIENT=real uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Backend tests:

```bash
cd services/realtime-gateway
pytest
```

Frontend dev server, if a new Vite app is created:

```bash
cd apps/web
npm install
npm run dev
```

Real NIM run on `g6.xlarge`:

```bash
export NGC_API_KEY=...
scripts/run_nim_nemotron_asr.sh
```

## Testing Strategy

Keep tests focused on spike risks. Do not spend time building comprehensive coverage for future architecture.

Required automated tests:
- `GET /health` returns `200`.
- `POST /api/realtime/sessions` returns `sessionId` and `eventsUrl`.
- Audio chunk size is 2560 bytes for 80ms, 16kHz, mono, PCM16.
- PCM16 bytes are base64 encoded into the expected NIM append payload.
- Mock NIM emits at least one partial and one final transcript.
- Transcript normalization collapses repeated whitespace.
- Session cleanup can be called twice without throwing.

Manual spike verification:
- Start backend in `NIM_CLIENT=mock`.
- Open `/realtime-asr-spike`.
- Click Start and confirm WebRTC connects.
- Confirm mock transcript appears with latency numbers.
- Stop and confirm cleanup.
- Start NIM on `g6.xlarge`.
- Start backend in `NIM_CLIENT=real`.
- Repeat the browser test with real microphone input.
- Record first partial latency and subjective transcript quality.

## Implementation Order

1. Backend health and session creation
   - Goal: server boots and creates an in-memory session.
   - Verify: health/session API tests pass.

2. Browser spike page skeleton
   - Goal: Start/Stop buttons, state panel, transcript panels.
   - Verify: page loads and can call session API.

3. WebSocket event channel
   - Goal: server can push status/metrics events to the browser.
   - Verify: Start shows WebSocket connected and receives a status event.

4. WebRTC offer/answer
   - Goal: browser sends microphone track to server.
   - Verify: server logs WebRTC connected and first audio frame.

5. Audio chunking
   - Goal: server converts audio to 16kHz mono PCM16 and emits 80ms chunks.
   - Verify: logs show 2560-byte chunks.

6. Mock NIM client
   - Goal: prove end-to-end UI flow without NIM.
   - Verify: transcript and latency render in browser.

7. Real NIM client
   - Goal: send chunks to NIM and parse transcript events.
   - Verify: real transcript appears in browser.

8. Latency polish
   - Goal: show first partial and latest partial latency clearly.
   - Verify: metrics update during speech and remain visible after Stop.

9. Spike README
   - Goal: another developer can run mock mode and real NIM mode.
   - Verify: commands are copy-pasteable and mention required env vars.

## Spike Acceptance Criteria

The spike is successful when:
- A developer can run mock mode locally and see transcript events in the browser.
- On `g6.xlarge`, a developer can run NIM and switch the gateway to `NIM_CLIENT=real`.
- Browser microphone audio reaches the server through WebRTC.
- Server sends 16kHz mono PCM16 chunks to the NIM client.
- Browser receives transcript events over WebSocket.
- UI displays first partial latency and latest partial latency.
- Server logs include audio chunk and transcript timing events.
- Stop cleans up enough that Start can be tried again without restarting the browser.

The spike is not blocked by:
- Missing production auth.
- Missing TURN server.
- Lack of long-running metrics storage.
- Lack of polished UI.
- Lack of automatic slide/cue features.

## Decision Output

At the end of the spike, capture these notes in the README or a short follow-up doc:

- Real NIM first partial latency range observed.
- Whether Korean partial quality is acceptable for presentation coaching.
- Whether WebRTC audio ingestion was stable for a 3-5 minute speaking test.
- Any NIM event shape differences from the assumed parser.
- Recommended next step: continue with production MVP, change ASR provider/config, or run another focused spike.

## Boundaries

Always:
- Use WebRTC for browser audio upload.
- Use WebSocket for transcript/status/latency feedback.
- Keep mock mode runnable without NIM.
- Keep real mode easy to switch on with `NIM_CLIENT=real`.
- Keep timing data visible in UI and logs.
- Keep secrets out of the repository.

Ask first:
- Adding persistent storage.
- Adding authentication.
- Adding TURN or multi-instance routing.
- Replacing NIM with another ASR provider.
- Expanding the spike into product UI.

Never:
- Commit `NGC_API_KEY`, AWS credentials, or personal data.
- Require GPU/NIM for ordinary automated tests.
- Build cue graph, slide automation, or LLM report features in this spike.
- Hide unknown NIM events without logging enough raw context to debug them.
