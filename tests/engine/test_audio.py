"""Tests for engine.audio module."""

from __future__ import annotations

from custom_components.xiaomi_mimo_tts.engine.audio import (
    STREAMING_WAV_HEADER,
    build_wav_header,
)


def test_streaming_wav_header_is_44_bytes() -> None:
    assert len(STREAMING_WAV_HEADER) == 44


def test_streaming_wav_header_format() -> None:
    h = STREAMING_WAV_HEADER
    assert h[0:4] == b"RIFF"
    assert h[4:8] == b"\xff\xff\xff\xff"  # sentinel
    assert h[8:12] == b"WAVE"
    assert h[12:16] == b"fmt "
    # Sample rate at offset 24-27 LE int32
    assert int.from_bytes(h[24:28], "little") == 24_000
    # Channels offset 22-23
    assert int.from_bytes(h[22:24], "little") == 1
    # Bits per sample offset 34-35
    assert int.from_bytes(h[34:36], "little") == 16
    # data chunk
    assert h[36:40] == b"data"
    assert h[40:44] == b"\xff\xff\xff\xff"


def test_build_wav_header_writes_real_sizes_when_known() -> None:
    header = build_wav_header(1000)
    assert len(header) == 44
    assert int.from_bytes(header[4:8], "little") == 1000 + 36
    assert int.from_bytes(header[40:44], "little") == 1000
