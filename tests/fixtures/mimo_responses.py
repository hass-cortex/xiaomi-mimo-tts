"""Canned Xiaomi MiMo API responses for use in engine + unit tests."""

from __future__ import annotations

import base64
import io
import wave


def make_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 24_000) -> bytes:
    """Build a tiny silence WAV (24kHz mono int16) for tests."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(make_pcm_bytes(duration_seconds, sample_rate))
    return buf.getvalue()


# Sample SSE chunks for streaming tests (each line is one delta event)
def synth_sse_chunks(pcm_chunks: list[bytes]) -> list[bytes]:
    """Build SSE event lines emitting delta.audio.data."""
    out: list[bytes] = []
    for chunk in pcm_chunks:
        b64 = base64.b64encode(chunk).decode("ascii")
        line = (
            f'data: {{"choices":[{{"delta":{{"audio":{{"data":"{b64}"}}}},'
            f'"index":0}}]}}\n\n'
        )
        out.append(line.encode("ascii"))
    out.append(b"data: [DONE]\n\n")
    return out


def make_pcm_bytes(duration_seconds: float = 1.0, sample_rate: int = 24_000) -> bytes:
    """Raw 24kHz mono int16 silence — the payload `make_wav_bytes` wraps."""
    return b"\x00\x00" * int(duration_seconds * sample_rate)


def synth_sse_body(pcm_chunks: list[bytes]) -> bytes:
    """Join `synth_sse_chunks` into a single SSE response body."""
    return b"".join(synth_sse_chunks(pcm_chunks))
