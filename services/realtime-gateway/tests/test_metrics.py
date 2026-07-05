from app.metrics import SessionMetrics


def test_metrics_record_first_and_latest_partial_latency() -> None:
    metrics = SessionMetrics(sessionCreatedAt=1000)

    metrics.record_audio_frame(1100)
    metrics.record_chunk_sent(byte_count=2560, timestamp_ms=1200)
    metrics.record_transcript(timestamp_ms=1500, is_partial=True)

    assert metrics.firstPartialLatencyMs == 400
    assert metrics.latestPartialLatencyMs == 300
    assert metrics.audioChunksSent == 1
    assert metrics.audioBytesSent == 2560
