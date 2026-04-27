"""Tests for XiaomiMimoTTSEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.xiaomi_mimo_tts.engine.errors import (
    XiaomiMimoApiError,
    XiaomiMimoAuthError,
)
from custom_components.xiaomi_mimo_tts.engine.models import SynthesisResult


@pytest.fixture
def mock_subentry_built_in() -> MagicMock:
    se = MagicMock()
    se.subentry_id = "se_built_in"
    se.title = "Chloe"
    se.data = {
        "type": "built_in",
        "voice": "Chloe",
        "default_style_prompt": "",
    }
    return se


@pytest.mark.asyncio
async def test_async_get_tts_audio_built_in_returns_wav(
    mock_config_entry, mock_subentry_built_in
) -> None:
    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(mock_config_entry, mock_subentry_built_in)
    entity._client = MagicMock()
    entity._client.synthesize = AsyncMock(
        return_value=SynthesisResult(
            audio_bytes=b"RIFF...WAV",
            audio_format="wav",
            duration_ms=300.0,
        )
    )
    fmt, data = await entity.async_get_tts_audio("Hello", "en", {})
    assert fmt == "wav"
    assert data == b"RIFF...WAV"


@pytest.mark.asyncio
async def test_auth_error_translates_to_config_entry_auth_failed(
    mock_hass, mock_config_entry, mock_subentry_built_in
) -> None:
    from homeassistant.exceptions import ConfigEntryAuthFailed

    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(mock_config_entry, mock_subentry_built_in)
    entity.hass = mock_hass
    entity._client = MagicMock()
    entity._client.synthesize = AsyncMock(
        side_effect=XiaomiMimoAuthError(401, "invalid_key", "bad")
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await entity.async_get_tts_audio("Hello", "en", {})
    mock_config_entry.async_start_reauth.assert_called_once_with(mock_hass)


@pytest.mark.asyncio
async def test_generic_api_error_translates_to_homeassistant_error(
    mock_config_entry, mock_subentry_built_in
) -> None:
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(mock_config_entry, mock_subentry_built_in)
    entity._client = MagicMock()
    entity._client.synthesize = AsyncMock(
        side_effect=XiaomiMimoApiError(500, "x", "boom")
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("Hello", "en", {})


from collections.abc import AsyncIterator


@pytest.mark.asyncio
async def test_async_stream_tts_audio_yields_header_then_pcm(
    mock_config_entry, mock_subentry_built_in
) -> None:
    from custom_components.xiaomi_mimo_tts.engine.stream import STREAMING_WAV_HEADER
    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(mock_config_entry, mock_subentry_built_in)

    async def fake_stream(text, vc):
        yield b"PCM_PART_1"
        yield b"PCM_PART_2"

    entity._client = MagicMock()
    entity._client.synthesize_stream = fake_stream

    async def text_gen() -> AsyncIterator[str]:
        yield "Hello world."

    request = MagicMock()
    request.message_gen = text_gen()
    request.options = {}
    request.language = "en-US"

    response = await entity.async_stream_tts_audio(request)
    out: list[bytes] = []
    async for chunk in response.data_gen:
        out.append(chunk)

    assert response.extension == "wav"
    assert out[0] == STREAMING_WAV_HEADER
    combined = b"".join(out)
    assert b"PCM_PART_1" in combined
    assert b"PCM_PART_2" in combined


@pytest.mark.asyncio
async def test_tts_pushes_stats_after_call(
    mock_config_entry, mock_subentry_built_in
) -> None:
    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(mock_config_entry, mock_subentry_built_in)
    entity._client = MagicMock()
    entity._client.synthesize = AsyncMock(
        return_value=SynthesisResult(
            audio_bytes=b"\x00" * 24_000 * 2,  # 1 second of PCM
            audio_format="wav",
            duration_ms=400.0,
        )
    )
    received: list = []

    class FakeSensor:
        def handle_call(self, stats):
            received.append(stats)

    mock_config_entry.runtime_data.sensors_by_subentry = {
        mock_subentry_built_in.subentry_id: [FakeSensor()]
    }
    await entity.async_get_tts_audio("Hi", "en", {})
    assert len(received) == 1
    assert received[0].success is True
    assert received[0].text == "Hi"
    assert received[0].streaming is False


@pytest.mark.asyncio
async def test_tts_pushes_stats_on_error(
    mock_config_entry, mock_subentry_built_in
) -> None:
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(mock_config_entry, mock_subentry_built_in)
    entity._client = MagicMock()
    entity._client.synthesize = AsyncMock(
        side_effect=XiaomiMimoApiError(500, "x", "boom")
    )
    received: list = []

    class FakeSensor:
        def handle_call(self, stats):
            received.append(stats)

    mock_config_entry.runtime_data.sensors_by_subentry = {
        mock_subentry_built_in.subentry_id: [FakeSensor()]
    }
    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("Hi", "en", {})
    assert len(received) == 1
    assert received[0].success is False
    assert received[0].error_kind == "api"
