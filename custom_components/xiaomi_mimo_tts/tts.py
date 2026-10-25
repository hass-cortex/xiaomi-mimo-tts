"""Xiaomi MiMo TTS entity (non-streaming and streaming)."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, NoReturn

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
    Voice,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEFAULT_STYLE_PROMPT,
    CONF_STREAMING_ENABLED,
    CONF_SUBENTRY_TYPE,
    CONF_VOICE,
    CONF_VOICE_DESCRIPTION,
    CONF_VOICE_SAMPLE_ID,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_STREAMING_ENABLED,
    SUBENTRY_TYPE_BUILT_IN,
    SUBENTRY_TYPE_VOICE_CLONE,
    SUBENTRY_TYPE_VOICE_DESIGN,
)
from .engine.audio import BYTES_PER_SECOND, STREAMING_WAV_HEADER
from .engine.errors import (
    XiaomiMimoAuthError,
    XiaomiMimoBadRequestError,
    XiaomiMimoError,
)
from .engine.models import (
    SynthesisResult,
    TTSCallStats,
    VoiceConfig,
    supports_low_latency_stream,
)
from .repairs import create_voice_sample_missing_issue
from .voice_sample import VoiceSampleError, VoiceSampleResolver
from .voices import VoiceChoice, entry_device_info, entry_voices, resolve_voice

if TYPE_CHECKING:
    from . import XiaomiMimoTTSConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 6


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiMimoTTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the entry's one TTS entity, which speaks in every voice it has."""
    async_add_entities([XiaomiMimoTTSEntity(entry)])


class XiaomiMimoTTSEntity(TextToSpeechEntity):
    """One TTS entity per entry; the voice option picks a built-in voice or a profile."""

    # Home Assistant refuses audio from a TTS entity whose name is None, which
    # is what has_entity_name with no name of its own would give.
    _attr_has_entity_name = False
    _attr_supported_languages = ["zh-CN", "zh-TW", "en-US"]
    _attr_default_language = "zh-CN"

    def __init__(self, entry: XiaomiMimoTTSConfigEntry) -> None:
        self._entry = entry
        self._client = entry.runtime_data.client
        self._sample_resolver: VoiceSampleResolver | None = None
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._attr_device_info = entry_device_info(entry)

    @property
    def supported_options(self) -> list[str]:
        return [ATTR_VOICE]

    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Every voice of the entry; each speaks all the supported languages."""
        return [Voice(voice_id, name) for voice_id, name in entry_voices(self._entry)]

    def _voice(self, options: dict[str, Any]) -> VoiceChoice:
        """The voice `options` asks for, else the entry's default.

        Raises:
            HomeAssistantError: `options` names a voice the entry does not have.
        """
        voice = options.get(ATTR_VOICE)
        try:
            return resolve_voice(self._entry, voice)
        except KeyError:
            raise HomeAssistantError(
                f"{self._entry.title} has no voice {voice!r}; its voices are the "
                "built-in ones and its voice profiles"
            ) from None

    async def _voice_config_async(self, voice: VoiceChoice) -> VoiceConfig:
        """Async to allow voice_clone to resolve sample at call time."""
        if voice.profile is None:
            assert voice.built_in is not None
            return VoiceConfig.for_built_in(voice_name=voice.built_in)
        data = voice.profile.data
        kind = data[CONF_SUBENTRY_TYPE]
        if kind == SUBENTRY_TYPE_BUILT_IN:
            return VoiceConfig.for_built_in(
                voice_name=data[CONF_VOICE],
                style=data.get(CONF_DEFAULT_STYLE_PROMPT, ""),
            )
        if kind == SUBENTRY_TYPE_VOICE_DESIGN:
            return VoiceConfig.for_design(data[CONF_VOICE_DESCRIPTION])
        if kind == SUBENTRY_TYPE_VOICE_CLONE:
            resolver = self._sample_resolver
            if resolver is None:
                resolver = VoiceSampleResolver(
                    self.hass, cache=self._entry.runtime_data.voice_sample_cache
                )
                self._sample_resolver = resolver
            data_uri = await resolver.resolve(data[CONF_VOICE_SAMPLE_ID])
            return VoiceConfig.for_clone(data_uri)
        raise NotImplementedError(f"Unknown subentry type {kind}")

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tuple[str, bytes]:
        start = time.monotonic()
        success = False
        error_kind: str | None = None
        result: SynthesisResult | None = None
        voice: VoiceChoice | None = None
        try:
            voice = self._voice(options)
            try:
                voice_config = await self._voice_config_async(voice)
            except VoiceSampleError as exc:
                error_kind = "api"
                assert voice.profile is not None
                self._raise_voice_sample_error(voice.profile, exc)
            try:
                result = await self._client.synthesize(
                    message, voice_config, audio_format=DEFAULT_AUDIO_FORMAT
                )
                success = True
            except XiaomiMimoError as exc:
                error_kind = "auth" if isinstance(exc, XiaomiMimoAuthError) else "api"
                self._raise_api_error(exc)
            assert result is not None
            return result.audio_format, result.audio_bytes
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            # PCM only, so the figure means the same on both paths.
            pcm_bytes = result.pcm_bytes if result else 0
            self._push_stats(
                voice,
                TTSCallStats(
                    success=success,
                    error_kind=error_kind,
                    duration_ms=duration_ms,
                    audio_bytes=pcm_bytes,
                    audio_seconds=pcm_bytes / BYTES_PER_SECOND,
                    text=message,
                    text_chars=len(message),
                    streaming=False,
                    # Nothing can play until the whole clip is back, so the
                    # wait before audio starts is the whole call.
                    ttft_ms=duration_ms if success else None,
                    voice=voice.name if voice else "",
                ),
            )

    def _raise_api_error(self, exc: XiaomiMimoError) -> NoReturn:
        """Translate an engine error at the HA boundary."""
        if isinstance(exc, XiaomiMimoAuthError):
            self._entry.async_start_reauth(self.hass)
            raise ConfigEntryAuthFailed("invalid_api_key") from exc
        if isinstance(exc, XiaomiMimoBadRequestError):
            raise HomeAssistantError(
                f"Xiaomi MiMo rejected the request: {exc.error_message}"
            ) from exc
        raise HomeAssistantError(f"Xiaomi MiMo TTS error: {exc}") from exc

    def _raise_voice_sample_error(
        self, profile: ConfigSubentry, exc: VoiceSampleError
    ) -> NoReturn:
        create_voice_sample_missing_issue(
            self.hass,
            entry_id=self._entry.entry_id,
            subentry_id=profile.subentry_id,
            profile_name=profile.title,
            missing_path=profile.data.get(CONF_VOICE_SAMPLE_ID, "(unknown)"),
        )
        raise HomeAssistantError(f"Voice sample missing or invalid: {exc}") from exc

    def _push_stats(self, voice: VoiceChoice | None, stats: TTSCallStats) -> None:
        """Count the call on the entry, and on the profile whose voice spoke."""
        by_device = self._entry.runtime_data.sensors_by_device
        sensors = list(by_device.get(self._entry.entry_id, []))
        if voice is not None and voice.profile is not None:
            sensors += by_device.get(voice.profile.subentry_id, [])
        for sensor in sensors:
            try:
                sensor.handle_call(stats)
            except Exception:
                _LOGGER.exception("Sensor push failed")

    def async_supports_streaming_input(self) -> bool:
        """Follow the entry-level switch.

        The base class infers support from the mere presence of an
        `async_stream_tts_audio` override. Whether the audio then streams out
        depends on the voice, which only the call names; see `_stream`.
        """
        return bool(
            self._entry.options.get(CONF_STREAMING_ENABLED, DEFAULT_STREAMING_ENABLED)
        )

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Return a streaming TTS response with a WAV header followed by PCM chunks."""
        return TTSAudioResponse(DEFAULT_AUDIO_FORMAT, self._stream(request))

    async def _stream(self, request: TTSAudioRequest) -> AsyncGenerator[bytes]:
        """Relay the voice's PCM as it arrives.

        A model in compatibility mode sends the whole clip in one piece after
        inference, so its call goes through `synthesize`, which may retry,
        and the clip follows the header in one chunk.
        """
        yield STREAMING_WAV_HEADER
        start = time.monotonic()
        ttft_ms: float | None = None
        text = ""
        pcm_bytes_total = 0
        success = False
        streaming = False
        error_kind: str | None = None
        voice: VoiceChoice | None = None
        try:
            voice = self._voice(request.options)
            try:
                voice_config = await self._voice_config_async(voice)
            except VoiceSampleError as exc:
                error_kind = "api"
                assert voice.profile is not None
                self._raise_voice_sample_error(voice.profile, exc)
            streaming = supports_low_latency_stream(voice_config.model)

            # The API takes no incremental input, so the reply has to be whole
            # before the request can go out.
            text = "".join([chunk async for chunk in request.message_gen])

            try:
                if streaming:
                    async for chunk in self._client.synthesize_stream(
                        text, voice_config
                    ):
                        if ttft_ms is None:
                            ttft_ms = (time.monotonic() - start) * 1000.0
                        pcm_bytes_total += len(chunk)
                        yield chunk
                else:
                    result = await self._client.synthesize(
                        text, voice_config, audio_format="pcm16"
                    )
                    ttft_ms = (time.monotonic() - start) * 1000.0
                    pcm_bytes_total = result.pcm_bytes
                    yield result.audio_bytes
                success = True
            except XiaomiMimoError as exc:
                error_kind = "auth" if isinstance(exc, XiaomiMimoAuthError) else "api"
                self._raise_api_error(exc)
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            self._push_stats(
                voice,
                TTSCallStats(
                    success=success,
                    error_kind=error_kind,
                    duration_ms=duration_ms,
                    audio_bytes=pcm_bytes_total,
                    audio_seconds=pcm_bytes_total / BYTES_PER_SECOND,
                    text=text,
                    text_chars=len(text),
                    streaming=streaming,
                    ttft_ms=ttft_ms,
                    voice=voice.name if voice else "",
                ),
            )
