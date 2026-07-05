import { useRealtimeAsrSpike } from "./useRealtimeAsrSpike";

function formatMetric(value: number | null | undefined, suffix = "ms") {
  return value == null ? "n/a" : `${value}${suffix}`;
}

function MetricCell({
  label,
  value,
  suffix
}: {
  label: string;
  value: number | null | undefined;
  suffix?: string;
}) {
  return (
    <div className="metric-cell">
      <dt>{label}</dt>
      <dd>{formatMetric(value, suffix)}</dd>
    </div>
  );
}

export function RealtimeAsrSpikePage() {
  const spike = useRealtimeAsrSpike();

  return (
    <main className="page-shell">
      <header className="topbar">
        <div>
          <h1>Realtime ASR Spike</h1>
          <p>WebRTC microphone uplink, WebSocket transcript downlink, live latency console.</p>
        </div>
        <div className="actions" aria-label="Realtime ASR controls">
          <button type="button" onClick={() => void spike.start()} disabled={spike.isStarting}>
            {spike.isStarting ? "Starting" : "Start"}
          </button>
          <button type="button" className="secondary" onClick={() => void spike.stop()}>
            Stop
          </button>
          <button type="button" className="secondary" onClick={spike.clearTranscript}>
            Clear transcript
          </button>
        </div>
      </header>

      <section className="status-grid" aria-label="Session state">
        <div>
          <span>Session ID</span>
          <strong>{spike.sessionId || "not started"}</strong>
        </div>
        <div>
          <span>WebRTC</span>
          <strong>{spike.webRtcState}</strong>
        </div>
        <div>
          <span>WebSocket</span>
          <strong>{spike.webSocketState}</strong>
        </div>
        <div>
          <span>NIM client</span>
          <strong>{spike.nimClient}</strong>
        </div>
      </section>

      <section className="metric-grid" aria-label="Latency and audio metrics">
        <MetricCell label="First partial latency" value={spike.metrics.firstPartialLatencyMs} />
        <MetricCell label="Latest partial latency" value={spike.metrics.latestPartialLatencyMs} />
        <MetricCell
          label="Server to browser"
          value={spike.lastServerToBrowserEventLatencyMs}
        />
        <MetricCell label="Audio chunks sent" value={spike.metrics.audioChunksSent} suffix="" />
        <MetricCell label="Audio bytes sent" value={spike.metrics.audioBytesSent} suffix=" bytes" />
        <MetricCell label="Chunk drops" value={spike.metrics.audioChunkDropCount} suffix="" />
      </section>

      <div className="transcript-layout">
        <section className="panel" aria-label="Current partial transcript">
          <h2>Partial</h2>
          <p className="partial-text">{spike.partialTranscript || "Waiting for speech..."}</p>
        </section>

        <section className="panel" aria-label="Final transcript log">
          <h2>Final transcript</h2>
          {spike.finalTranscriptLog.length === 0 ? (
            <p className="empty">No final transcript yet.</p>
          ) : (
            <ol className="final-log">
              {spike.finalTranscriptLog.map((text, index) => (
                <li key={`${text}-${index}`}>{text}</li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section className="panel error-panel" aria-label="Errors">
        <h2>Errors</h2>
        {spike.errors.length === 0 ? (
          <p className="empty">No errors.</p>
        ) : (
          <ul>
            {spike.errors.map((error, index) => (
              <li key={`${error}-${index}`}>{error}</li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
