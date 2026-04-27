"""Canned Xiaomi MiMo API responses for use in engine + unit tests."""

from __future__ import annotations

import base64
import io
import wave


def make_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 24_000) -> bytes:
    """Build a tiny silence WAV (24kHz mono int16) for tests."""
    n_samples = int(duration_seconds * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def synth_response_payload(audio_bytes: bytes) -> dict:  # type: ignore[type-arg]
    """Wrap raw audio in the Xiaomi MiMo /chat/completions JSON envelope."""
    return {
        "id": "test_completion_id",
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "content": "",
                    "role": "assistant",
                    "audio": {
                        "id": "test_audio_id",
                        "data": base64.b64encode(audio_bytes).decode("ascii"),
                    },
                },
            }
        ],
    }


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
