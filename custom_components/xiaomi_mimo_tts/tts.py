"""Xiaomi MiMo TTS entity (non-streaming and streaming)."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator
from typing import TYPE_CHECKING, Any, NoReturn

from homeassistant.components.tts import (
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEFAULT_STYLE_PROMPT,
    CONF_SUBENTRY_TYPE,
    CONF_VOICE,
    CONF_VOICE_DESCRIPTION,
    CONF_VOICE_SAMPLE_ID,
    DEFAULT_AUDIO_FORMAT,
    DOMAIN,
    SUBENTRY_TYPE_BUILT_IN,
    SUBENTRY_TYPE_VOICE_CLONE,
    SUBENTRY_TYPE_VOICE_DESIGN,
)
from .engine.errors import (
    XiaomiMimoAuthError,
    XiaomiMimoBadRequestError,
    XiaomiMimoError,
)
from .engine.models import SynthesisResult, TTSCallStats, VoiceConfig
from .engine.stream import (
    BYTES_PER_SECOND,
    STREAMING_WAV_HEADER,
    WAV_HEADER_SIZE,
    synthesize_text_stream,
)
from .repairs import create_voice_sample_missing_issue
from .voice_sample import VoiceSampleError, VoiceSampleResolver

if TYPE_CHECKING:
    from . import XiaomiMimoTTSConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 6


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiMimoTTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one TTS entity per voice subentry."""
    for subentry in entry.subentries.values():
        async_add_entities(
            [XiaomiMimoTTSEntity(entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class XiaomiMimoTTSEntity(TextToSpeechEntity):
    """One TTS entity per voice profile (subentry)."""

    _attr_has_entity_name = False
    _attr_supported_languages = ["zh-CN", "zh-TW", "en-US"]
    _attr_default_language = "zh-CN"

    def __init__(
        self, entry: XiaomiMimoTTSConfigEntry, subentry: ConfigSubentry
    ) -> None:
        self._entry = entry
        self._subentry = subentry
        self._client = entry.runtime_data.client
        self._sample_resolver: VoiceSampleResolver | None = None
        self._attr_unique_id = f"{entry.entry_id}_{subentry.subentry_id}"
        self._attr_name = subentry.title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{subentry.subentry_id}")},
            manufacturer="Xiaomi MiMo",
            model=self._model_label(),
            name=subentry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    def _model_label(self) -> str:
        return {
            SUBENTRY_TYPE_BUILT_IN: "Xiaomi MiMo v2.5 (built-in)",
            SUBENTRY_TYPE_VOICE_DESIGN: "Xiaomi MiMo v2.5 (voice design)",
            SUBENTRY_TYPE_VOICE_CLONE: "Xiaomi MiMo v2.5 (voice clone)",
        }.get(self._subentry.data[CONF_SUBENTRY_TYPE], "Xiaomi MiMo v2.5")

    async def _voice_config_async(self) -> VoiceConfig:
        """Async to allow voice_clone to resolve sample at call time."""
        data = self._subentry.data
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
        try:
            try:
                voice_config = await self._voice_config_async()
            except VoiceSampleError as exc:
                error_kind = "api"
                self._raise_voice_sample_error(exc)
            try:
                result = await self._client.synthesize(
                    message, voice_config, audio_format=DEFAULT_AUDIO_FORMAT
                )
                success = True
            except XiaomiMimoAuthError as exc:
                error_kind = "auth"
                self._entry.async_start_reauth(self.hass)
                raise ConfigEntryAuthFailed("invalid_api_key") from exc
            except XiaomiMimoBadRequestError as exc:
                error_kind = "api"
                raise HomeAssistantError(
                    f"Xiaomi MiMo rejected the request: {exc.error_message}"
                ) from exc
            except XiaomiMimoError as exc:
                error_kind = "api"
                raise HomeAssistantError(f"Xiaomi MiMo TTS error: {exc}") from exc
            assert result is not None
            return result.audio_format, result.audio_bytes
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            audio_bytes = len(result.audio_bytes) if result else 0
            pcm_bytes = max(0, audio_bytes - WAV_HEADER_SIZE)
            audio_seconds = pcm_bytes / BYTES_PER_SECOND if pcm_bytes else 0.0
            self._push_stats(
                TTSCallStats(
                    success=success,
                    error_kind=error_kind,
                    duration_ms=duration_ms,
                    audio_bytes=audio_bytes,
                    audio_seconds=audio_seconds,
                    text=message,
                    text_chars=len(message),
                    streaming=False,
                    ttft_ms=None,
                    sentence_count=None,
                )
            )

    def _raise_voice_sample_error(self, exc: VoiceSampleError) -> NoReturn:
        create_voice_sample_missing_issue(
            self.hass,
            entry_id=self._entry.entry_id,
            subentry_id=self._subentry.subentry_id,
            profile_name=self._subentry.title,
            missing_path=self._subentry.data.get(CONF_VOICE_SAMPLE_ID, "(unknown)"),
        )
        raise HomeAssistantError(f"Voice sample missing or invalid: {exc}") from exc

    def _push_stats(self, stats: TTSCallStats) -> None:
        sensors = self._entry.runtime_data.sensors_by_subentry.get(
            self._subentry.subentry_id, []
        )
        for sensor in sensors:
            try:
                sensor.handle_call(stats)
            except Exception:
                _LOGGER.exception("Sensor push failed")

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Return a streaming TTS response with a WAV header followed by PCM chunks."""
        return TTSAudioResponse(DEFAULT_AUDIO_FORMAT, self._stream(request))

    async def _stream(self, request: TTSAudioRequest) -> AsyncGenerator[bytes]:
        yield STREAMING_WAV_HEADER
        start = time.monotonic()
        ttft_ms: float | None = None
        text_buffer: list[str] = []
        sentence_count = 0
        pcm_bytes_total = 0
        success = False
        error_kind: str | None = None

        def on_batch(_batch_size: int) -> None:
            nonlocal sentence_count
            sentence_count += 1

        try:
            try:
                voice_config = await self._voice_config_async()
            except VoiceSampleError as exc:
                error_kind = "api"
                self._raise_voice_sample_error(exc)

            async def _wrapped_msgs() -> AsyncIterator[str]:
                async for chunk in request.message_gen:
                    text_buffer.append(chunk)
                    yield chunk

            try:
                async for chunk in synthesize_text_stream(
                    self._client,
                    _wrapped_msgs(),
                    voice_config,
                    on_batch=on_batch,
                ):
                    if ttft_ms is None:
                        ttft_ms = (time.monotonic() - start) * 1000.0
                    pcm_bytes_total += len(chunk)
                    yield chunk
                success = True
            except XiaomiMimoAuthError as exc:
                error_kind = "auth"
                self._entry.async_start_reauth(self.hass)
                raise ConfigEntryAuthFailed("invalid_api_key") from exc
            except XiaomiMimoError as exc:
                error_kind = "api"
                raise HomeAssistantError(
                    f"Xiaomi MiMo TTS streaming error: {exc}"
                ) from exc
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            text = "".join(text_buffer)
            audio_seconds = pcm_bytes_total / BYTES_PER_SECOND
            self._push_stats(
                TTSCallStats(
                    success=success,
                    error_kind=error_kind,
                    duration_ms=duration_ms,
                    audio_bytes=pcm_bytes_total,
                    audio_seconds=audio_seconds,
                    text=text,
                    text_chars=len(text),
                    streaming=True,
                    ttft_ms=ttft_ms,
                    sentence_count=sentence_count or None,
                )
            )
