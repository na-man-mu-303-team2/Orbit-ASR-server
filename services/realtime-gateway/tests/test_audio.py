import av

from app.audio import AudioFrameConverter, Pcm16Chunker, pcm16_chunk_size_bytes


def test_audio_chunk_size_is_2560_bytes_for_default_spike_settings() -> None:
    assert pcm16_chunk_size_bytes(sample_rate=16000, num_channels=1, chunk_ms=80) == 2560


def test_pcm16_chunker_buffers_until_full_chunks_are_available() -> None:
    chunker = Pcm16Chunker(chunk_size=4)

    assert chunker.append(b"ab") == []
    assert chunker.append(b"cdefghi") == [b"abcd", b"efgh"]
    assert chunker.flush() == b"i"


def test_audio_frame_converter_outputs_16khz_mono_pcm16_bytes() -> None:
    frame = av.AudioFrame(format="s16", layout="mono", samples=160)
    frame.sample_rate = 16000
    frame.planes[0].update(b"\x01\x02" * 160)
    converter = AudioFrameConverter(sample_rate=16000)

    pcm16 = converter.to_pcm16(frame)

    assert pcm16 == b"\x01\x02" * 160
