from app.audio import Pcm16Chunker, pcm16_chunk_size_bytes


def test_audio_chunk_size_is_2560_bytes_for_default_spike_settings() -> None:
    assert pcm16_chunk_size_bytes(sample_rate=16000, num_channels=1, chunk_ms=80) == 2560


def test_pcm16_chunker_buffers_until_full_chunks_are_available() -> None:
    chunker = Pcm16Chunker(chunk_size=4)

    assert chunker.append(b"ab") == []
    assert chunker.append(b"cdefghi") == [b"abcd", b"efgh"]
    assert chunker.flush() == b"i"
