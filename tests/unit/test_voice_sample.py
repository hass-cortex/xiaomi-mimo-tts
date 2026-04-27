"""Tests for voice_sample.py."""

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.xiaomi_mimo_tts.voice_sample import (
    VoiceSampleError,
    VoiceSampleResolver,
)


@pytest.mark.asyncio
async def test_resolve_returns_data_uri(mock_hass, tmp_path) -> None:
    sample = tmp_path / "alice.mp3"
    sample.write_bytes(b"\xff\xfb\x90\x00fake-mp3")  # mp3 magic
    cache: OrderedDict = OrderedDict()
    resolver = VoiceSampleResolver(mock_hass, cache=cache)

    with patch(
        "custom_components.xiaomi_mimo_tts.voice_sample.async_resolve_media",
        new=AsyncMock(return_value=MagicMock(url=None, path=str(sample))),
    ):
        data_uri = await resolver.resolve(
            "media-source://media_source/local/voice_samples/alice.mp3"
        )
    assert data_uri.startswith("data:audio/mpeg;base64,")


@pytest.mark.asyncio
async def test_cache_hit_skips_disk_read(mock_hass, tmp_path) -> None:
    sample = tmp_path / "a.mp3"
    sample.write_bytes(b"\xff\xfb\x00\x00")
    cache: OrderedDict = OrderedDict()
    resolver = VoiceSampleResolver(mock_hass, cache=cache)
    content_id = "media-source://media_source/local/voice_samples/a.mp3"

    with patch(
        "custom_components.xiaomi_mimo_tts.voice_sample.async_resolve_media",
        new=AsyncMock(return_value=MagicMock(url=None, path=str(sample))),
    ) as resolve_mock:
        first = await resolver.resolve(content_id)
        second = await resolver.resolve(content_id)

    assert first == second
    # Second resolve must not have hit async_resolve_media a second time
    assert resolve_mock.call_count == 1


@pytest.mark.asyncio
async def test_oversize_sample_rejected(mock_hass, tmp_path) -> None:
    sample = tmp_path / "huge.mp3"
    sample.write_bytes(b"\x00" * (11 * 1024 * 1024))
    cache: OrderedDict = OrderedDict()
    resolver = VoiceSampleResolver(mock_hass, cache=cache)

    with (
        patch(
            "custom_components.xiaomi_mimo_tts.voice_sample.async_resolve_media",
            new=AsyncMock(return_value=MagicMock(url=None, path=str(sample))),
        ),
        pytest.raises(VoiceSampleError),
    ):
        await resolver.resolve(
            "media-source://media_source/local/voice_samples/huge.mp3"
        )


@pytest.mark.asyncio
async def test_resolve_fail_raises_voice_sample_error(mock_hass) -> None:
    cache: OrderedDict = OrderedDict()
    resolver = VoiceSampleResolver(mock_hass, cache=cache)

    with (
        patch(
            "custom_components.xiaomi_mimo_tts.voice_sample.async_resolve_media",
            new=AsyncMock(side_effect=Exception("not found")),
        ),
        pytest.raises(VoiceSampleError),
    ):
        await resolver.resolve("media-source://nope")
