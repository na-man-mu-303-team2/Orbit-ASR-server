from __future__ import annotations

from collections.abc import Iterable


def pcm16_chunk_size_bytes(
    sample_rate: int = 16000,
    num_channels: int = 1,
    chunk_ms: int = 80,
    bytes_per_sample: int = 2,
) -> int:
    return int(sample_rate * num_channels * bytes_per_sample * (chunk_ms / 1000))


class Pcm16Chunker:
    def __init__(self, chunk_size: int) -> None:
        self.chunk_size = chunk_size
        self._buffer = bytearray()

    def append(self, pcm16: bytes) -> list[bytes]:
        self._buffer.extend(pcm16)
        chunks: list[bytes] = []
        while len(self._buffer) >= self.chunk_size:
            chunks.append(bytes(self._buffer[: self.chunk_size]))
            del self._buffer[: self.chunk_size]
        return chunks

    def flush(self) -> bytes:
        remaining = bytes(self._buffer)
        self._buffer.clear()
        return remaining


class AudioFrameConverter:
    def __init__(self, sample_rate: int = 16000) -> None:
        import av

        self._resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)

    def to_pcm16(self, frame: object) -> bytes:
        frames = self._resampler.resample(frame)
        return b"".join(_frame_to_pcm16(frame) for frame in frames)


def _frame_to_pcm16(frame: object) -> bytes:
    to_ndarray = getattr(frame, "to_ndarray", None)
    if callable(to_ndarray):
        array = to_ndarray()
        return array.astype("<i2", copy=False).tobytes()

    planes: Iterable[object] = getattr(frame, "planes", [])
    return b"".join(bytes(plane) for plane in planes)
