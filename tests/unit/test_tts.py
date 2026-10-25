"""Tests for XiaomiMimoTTSEntity."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.xiaomi_mimo_tts.const import CONF_STREAMING_ENABLED
from custom_components.xiaomi_mimo_tts.engine.audio import (
    BYTES_PER_SECOND,
    STREAMING_WAV_HEADER,
)
from custom_components.xiaomi_mimo_tts.engine.errors import (
    XiaomiMimoApiError,
    XiaomiMimoAuthError,
)
from custom_components.xiaomi_mimo_tts.engine.models import (
    MODEL_BUILT_IN,
    MODEL_VOICE_DESIGN,
    SynthesisResult,
)


def make_subentry(subentry_id: str, kind: str, title: str, **data: object) -> MagicMock:
    se = MagicMock()
    se.subentry_id = subentry_id
    se.title = title
    se.data = {"type": kind, **data}
    return se


@pytest.fixture
def profiles(mock_config_entry) -> dict[str, MagicMock]:
    """One profile of each kind in the entry, by subentry ID."""
    subentries = [
        make_subentry(
            "se_chloe",
            "built_in",
            "Calm Chloe",
            voice="Chloe",
            default_style_prompt="calm",
        ),
        make_subentry("se_warm", "voice_design", "Warm", voice_description="warm"),
        make_subentry(
            "se_mum", "voice_clone", "Mum", voice_sample_id="media-source://mum"
        ),
    ]
    mock_config_entry.subentries = {se.subentry_id: se for se in subentries}
    return mock_config_entry.subentries


def _ok(pcm_bytes: int = 6) -> SynthesisResult:
    return SynthesisResult(
        audio_bytes=b"RIFF...WAV",
        audio_format="wav",
        duration_ms=1.0,
        pcm_bytes=pcm_bytes,
    )


def _entity(entry, *, result: SynthesisResult | None = None, error=None):
    """The entry's entity with a client whose one-shot call returns or raises."""
    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(entry)
    entity.hass = MagicMock()
    entity._client = MagicMock()
    entity._client.synthesize = AsyncMock(
        return_value=result or _ok(), side_effect=error
    )
    return entity


def _sent(entity):
    """The VoiceConfig of the last one-shot call."""
    return entity._client.synthesize.call_args.args[1]


def _record_calls(entry, *scopes: str) -> dict[str, list]:
    """Sensors on each scope (entry ID or subentry ID) that record their calls."""
    received: dict[str, list] = {scope: [] for scope in scopes}

    class FakeSensor:
        def __init__(self, scope: str) -> None:
            self.scope = scope

        def handle_call(self, stats):
            received[self.scope].append(stats)

    entry.runtime_data.sensors_by_device = {s: [FakeSensor(s)] for s in scopes}
    return received


async def _drain(entity, text: str, options: dict) -> list[bytes]:
    async def text_gen() -> AsyncIterator[str]:
        for word in text.split(" "):
            yield word + " "

    request = MagicMock()
    request.message_gen = text_gen()
    request.options = options
    request.language = "en-US"
    response = await entity.async_stream_tts_audio(request)
    return [chunk async for chunk in response.data_gen]


@pytest.mark.asyncio
async def test_one_shot_call_returns_wav(mock_config_entry) -> None:
    entity = _entity(mock_config_entry)
    fmt, data = await entity.async_get_tts_audio("Hello", "en", {})
    assert (fmt, data) == ("wav", b"RIFF...WAV")


@pytest.mark.asyncio
async def test_auth_error_translates_to_config_entry_auth_failed(
    mock_config_entry,
) -> None:
    from homeassistant.exceptions import ConfigEntryAuthFailed

    entity = _entity(mock_config_entry, error=XiaomiMimoAuthError(401, "k", "bad"))
    with pytest.raises(ConfigEntryAuthFailed):
        await entity.async_get_tts_audio("Hello", "en", {})
    mock_config_entry.async_start_reauth.assert_called_once_with(entity.hass)


@pytest.mark.asyncio
async def test_generic_api_error_translates_to_homeassistant_error(
    mock_config_entry,
) -> None:
    from homeassistant.exceptions import HomeAssistantError

    entity = _entity(mock_config_entry, error=XiaomiMimoApiError(500, "x", "boom"))
    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("Hello", "en", {})


def test_voices_are_the_built_in_ones_and_every_profile(
    mock_config_entry, profiles
) -> None:
    """Profiles of every kind are voices of the one entity, under their titles."""
    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    entity = XiaomiMimoTTSEntity(mock_config_entry)
    assert "voice" in entity.supported_options
    for language in entity._attr_supported_languages:
        voices = {
            (v.voice_id, v.name) for v in entity.async_get_supported_voices(language)
        }
        assert {("Chloe", "Chloe"), ("冰糖", "冰糖")} <= voices, language
        assert {
            ("se_chloe", "Calm Chloe"),
            ("se_warm", "Warm"),
            ("se_mum", "Mum"),
        } <= voices


@pytest.mark.asyncio
async def test_built_in_voice_speaks_without_a_style(
    mock_config_entry, profiles
) -> None:
    entity = _entity(mock_config_entry)
    await entity.async_get_tts_audio("Hi", "zh-TW", {"voice": "茉莉"})
    sent = _sent(entity)
    assert (sent.model, sent.voice, sent.style_prompt) == (MODEL_BUILT_IN, "茉莉", "")


@pytest.mark.asyncio
async def test_built_in_profile_speaks_with_its_style(
    mock_config_entry, profiles
) -> None:
    entity = _entity(mock_config_entry)
    await entity.async_get_tts_audio("Hi", "zh-TW", {"voice": "se_chloe"})
    sent = _sent(entity)
    assert (sent.voice, sent.style_prompt) == ("Chloe", "calm")


@pytest.mark.asyncio
async def test_design_profile_speaks_its_description(
    mock_config_entry, profiles
) -> None:
    entity = _entity(mock_config_entry)
    await entity.async_get_tts_audio("Hi", "zh-TW", {"voice": "se_warm"})
    sent = _sent(entity)
    assert (sent.model, sent.style_prompt) == (MODEL_VOICE_DESIGN, "warm")


@pytest.mark.asyncio
async def test_clone_profile_resolves_its_sample(mock_config_entry, profiles) -> None:
    entity = _entity(mock_config_entry)
    entity._sample_resolver = MagicMock()
    entity._sample_resolver.resolve = AsyncMock(return_value="data:audio/wav;base64,")
    await entity.async_get_tts_audio("Hi", "zh-TW", {"voice": "se_mum"})
    entity._sample_resolver.resolve.assert_awaited_once_with("media-source://mum")


@pytest.mark.asyncio
async def test_without_a_voice_the_default_voice_speaks(
    mock_config_entry, profiles
) -> None:
    mock_config_entry.options = {"default_voice": "se_warm"}
    entity = _entity(mock_config_entry)
    await entity.async_get_tts_audio("Hi", "zh-TW", {})
    assert _sent(entity).style_prompt == "warm"


@pytest.mark.asyncio
async def test_default_naming_a_deleted_profile_falls_back_to_mimo_default(
    mock_config_entry, profiles
) -> None:
    """Deleting the default profile must not break every call that names no voice."""
    mock_config_entry.options = {"default_voice": "se_gone"}
    entity = _entity(mock_config_entry)
    await entity.async_get_tts_audio("Hi", "zh-TW", {})
    assert _sent(entity).voice == "mimo_default"


@pytest.mark.asyncio
async def test_unknown_voice_is_refused_before_the_api_is_called(
    mock_config_entry, profiles
) -> None:
    """A voice of another engine (an Edge name left in a caller's settings)."""
    from homeassistant.exceptions import HomeAssistantError

    entity = _entity(mock_config_entry)
    with pytest.raises(HomeAssistantError, match="zh-TW-HsiaoChenNeural"):
        await entity.async_get_tts_audio(
            "Hi", "zh-TW", {"voice": "zh-TW-HsiaoChenNeural"}
        )
    entity._client.synthesize.assert_not_called()


@pytest.mark.asyncio
async def test_missing_clone_sample_is_reported_against_its_profile(
    mock_config_entry, profiles, monkeypatch
) -> None:
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.xiaomi_mimo_tts import tts
    from custom_components.xiaomi_mimo_tts.voice_sample import VoiceSampleError

    issue = MagicMock()
    monkeypatch.setattr(tts, "create_voice_sample_missing_issue", issue)
    entity = _entity(mock_config_entry)
    entity._sample_resolver = MagicMock()
    entity._sample_resolver.resolve = AsyncMock(side_effect=VoiceSampleError("gone"))
    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("Hi", "zh-TW", {"voice": "se_mum"})
    assert issue.call_args.kwargs["subentry_id"] == "se_mum"
    assert issue.call_args.kwargs["missing_path"] == "media-source://mum"


@pytest.mark.asyncio
async def test_call_is_counted_on_the_entry_and_the_profile_that_spoke(
    mock_config_entry, profiles
) -> None:
    entity = _entity(mock_config_entry)
    received = _record_calls(mock_config_entry, "entry_test", "se_warm", "se_chloe")
    await entity.async_get_tts_audio("Hi", "zh-TW", {"voice": "se_warm"})
    assert [s.voice for s in received["entry_test"]] == ["Warm"]
    assert [s.text for s in received["se_warm"]] == ["Hi"]
    assert received["se_chloe"] == []


@pytest.mark.asyncio
async def test_built_in_voice_call_is_counted_on_the_entry_only(
    mock_config_entry, profiles
) -> None:
    entity = _entity(mock_config_entry)
    received = _record_calls(mock_config_entry, "entry_test", "se_chloe")
    await entity.async_get_tts_audio("Hi", "zh-TW", {"voice": "Chloe"})
    assert [s.voice for s in received["entry_test"]] == ["Chloe"]
    assert received["se_chloe"] == []


@pytest.mark.asyncio
async def test_failed_call_is_counted_as_failed(mock_config_entry) -> None:
    from homeassistant.exceptions import HomeAssistantError

    entity = _entity(mock_config_entry, error=XiaomiMimoApiError(500, "x", "boom"))
    received = _record_calls(mock_config_entry, "entry_test")
    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("Hi", "en", {})
    [stats] = received["entry_test"]
    assert (stats.success, stats.error_kind) == (False, "api")


@pytest.mark.asyncio
async def test_non_streaming_call_reports_the_wait_before_audio(
    mock_config_entry,
) -> None:
    """A one-shot synthesis has no audio until it returns, so that is its TTFT."""
    entity = _entity(mock_config_entry, result=_ok(pcm_bytes=BYTES_PER_SECOND))
    received = _record_calls(mock_config_entry, "entry_test")
    await entity.async_get_tts_audio("Hi", "en", {})
    [stats] = received["entry_test"]
    assert stats.streaming is False
    assert stats.ttft_ms == stats.duration_ms
    # PCM only — the streaming path reports the same way.
    assert stats.audio_bytes == BYTES_PER_SECOND


def test_streaming_input_follows_the_entry_switch(mock_config_entry) -> None:
    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    assert XiaomiMimoTTSEntity(mock_config_entry).async_supports_streaming_input()
    mock_config_entry.options = {CONF_STREAMING_ENABLED: False}
    assert not XiaomiMimoTTSEntity(mock_config_entry).async_supports_streaming_input()


@pytest.mark.asyncio
async def test_built_in_voice_streams_the_whole_reply_in_one_request(
    mock_config_entry,
) -> None:
    entity = _entity(mock_config_entry)
    calls: list[tuple[str, str]] = []

    async def fake_stream(text, vc):
        calls.append((text, vc.voice))
        yield b"PCM_PART_1"
        yield b"PCM_PART_2"

    entity._client.synthesize_stream = fake_stream
    received = _record_calls(mock_config_entry, "entry_test")
    out = await _drain(entity, "First sentence. Second one.", {"voice": "Dean"})

    assert out == [STREAMING_WAV_HEADER, b"PCM_PART_1", b"PCM_PART_2"]
    # One request carrying the whole reply — the API takes no partial input.
    assert calls == [("First sentence. Second one. ", "Dean")]
    assert received["entry_test"][0].streaming is True


@pytest.mark.asyncio
async def test_compat_mode_voice_on_the_stream_path_arrives_in_one_piece(
    mock_config_entry, profiles
) -> None:
    """A designed voice has nothing to stream; its call may retry, and says it did not stream."""
    entity = _entity(
        mock_config_entry,
        result=SynthesisResult(
            audio_bytes=b"PCM_WHOLE", audio_format="pcm16", duration_ms=1.0, pcm_bytes=9
        ),
    )
    entity._client.synthesize_stream = MagicMock()
    received = _record_calls(mock_config_entry, "entry_test")
    out = await _drain(entity, "Hi", {"voice": "se_warm"})

    assert out == [STREAMING_WAV_HEADER, b"PCM_WHOLE"]
    entity._client.synthesize_stream.assert_not_called()
    assert entity._client.synthesize.call_args.kwargs["audio_format"] == "pcm16"
    [stats] = received["entry_test"]
    assert (stats.streaming, stats.audio_bytes) == (False, 9)


def test_entity_has_a_name(mock_config_entry) -> None:
    """Home Assistant refuses audio from a TTS entity whose name is None."""
    from custom_components.xiaomi_mimo_tts.tts import XiaomiMimoTTSEntity

    mock_config_entry.title = "Xiaomi MiMo TTS"
    entity = XiaomiMimoTTSEntity(mock_config_entry)
    assert not entity._attr_has_entity_name
    assert entity._attr_name == "Xiaomi MiMo TTS"
