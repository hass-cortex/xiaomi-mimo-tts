"""Audio format facts for Xiaomi MiMo output. Pure Python — no HA framework imports."""

from __future__ import annotations

from typing import Final

SAMPLE_RATE: Final = 24_000
CHANNELS: Final = 1
BITS_PER_SAMPLE: Final = 16
SAMPLE_WIDTH_BYTES: Final = BITS_PER_SAMPLE // 8
BYTES_PER_SECOND: Final = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH_BYTES
WAV_HEADER_SIZE: Final = 44


def build_wav_header(pcm_bytes: int | None = None) -> bytes:
    """Build the 44-byte WAV header for 24 kHz mono PCM16.

    Args:
        pcm_bytes: Byte length of the PCM payload that follows, or None when
            it is not known yet, which writes the 0xFFFFFFFF sentinel sizes
            players accept for an open-ended stream.

    Returns:
        The 44-byte RIFF/WAVE header.
    """
    block_align = CHANNELS * SAMPLE_WIDTH_BYTES
    riff_size = 0xFFFFFFFF if pcm_bytes is None else pcm_bytes + WAV_HEADER_SIZE - 8
    data_size = 0xFFFFFFFF if pcm_bytes is None else pcm_bytes
    return (
        b"RIFF"
        + riff_size.to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + CHANNELS.to_bytes(2, "little")
        + SAMPLE_RATE.to_bytes(4, "little")
        + BYTES_PER_SECOND.to_bytes(4, "little")
        + block_align.to_bytes(2, "little")
        + BITS_PER_SAMPLE.to_bytes(2, "little")
        + b"data"
        + data_size.to_bytes(4, "little")
    )


STREAMING_WAV_HEADER: Final[bytes] = build_wav_header()
