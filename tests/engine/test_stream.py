"""Tests for engine.stream module."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from custom_components.xiaomi_mimo_tts.engine.models import VoiceConfig
from custom_components.xiaomi_mimo_tts.engine.stream import (
    STREAMING_WAV_HEADER,
    synthesize_text_stream,
)


def test_streaming_wav_header_is_44_bytes() -> None:
    h = STREAMING_WAV_HEADER
    assert len(h) == 44


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


@pytest.mark.asyncio
async def test_synthesize_text_stream_zh_en_boundary() -> None:
    """Verify ZH (。) and EN (.) sentence boundaries split correctly."""

    captured_batches: list[str] = []

    class FakeClient:
        async def synthesize_stream(self, text, voice_config):
            captured_batches.append(text)
            yield b"\x01\x02"

    async def text_chunks() -> AsyncIterator[str]:
        yield "你好。"
        yield "Hello world."
        yield "再見"

    out: list[bytes] = []
    async for chunk in synthesize_text_stream(
        FakeClient(),
        text_chunks(),
        VoiceConfig.for_built_in("Chloe"),
        schedule=(1, 3),
    ):
        out.append(chunk)

    # Each batch yields b"\x01\x02"
    assert b"".join(out) == b"\x01\x02" * len(captured_batches)
    # Schedule [1, 3, ALL]: 3 sentences => batch1 = first 1; batch2 = up to 3 (but only 2 left)
    assert captured_batches[0] == "你好。"
    # batch 2 contains the remaining 2 sentences combined
    combined_after_first = " ".join(captured_batches[1:])
    assert "Hello world." in combined_after_first
    assert "再見" in combined_after_first


@pytest.mark.asyncio
async def test_synthesize_text_stream_empty_input() -> None:
    class FakeClient:
        async def synthesize_stream(self, text, voice_config):
            yield b""

    async def empty() -> AsyncIterator[str]:
        if False:
            yield ""

    out = [
        chunk
        async for chunk in synthesize_text_stream(
            FakeClient(),
            empty(),
            VoiceConfig.for_built_in("Chloe"),
        )
    ]
    assert out == []


@pytest.mark.asyncio
async def test_synthesize_text_stream_single_short_chunk() -> None:
    """A single chunk without sentence boundary still gets synthesized at finish()."""
    captured: list[str] = []

    class FakeClient:
        async def synthesize_stream(self, text, voice_config):
            captured.append(text)
            yield b"DATA"

    async def single() -> AsyncIterator[str]:
        yield "Hello"  # no boundary punctuation

    out = [
        chunk
        async for chunk in synthesize_text_stream(
            FakeClient(),
            single(),
            VoiceConfig.for_built_in("Chloe"),
        )
    ]
    assert out == [b"DATA"]
    assert captured == ["Hello"]
