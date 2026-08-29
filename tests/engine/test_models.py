"""Tests for engine.models module."""

from __future__ import annotations

import dataclasses

import pytest

from custom_components.xiaomi_mimo_tts.engine.models import (
    SynthesisResult,
    TTSCallStats,
    ValidationResult,
    VoiceConfig,
)


def test_voiceconfig_for_built_in() -> None:
    vc = VoiceConfig.for_built_in("Chloe", style="Cheerful")
    assert vc.model == "mimo-v2.5-tts"
    assert vc.voice == "Chloe"
    assert vc.style_prompt == "Cheerful"


def test_voiceconfig_for_built_in_default_style() -> None:
    vc = VoiceConfig.for_built_in("Mia")
    assert vc.style_prompt == ""


def test_voiceconfig_for_design_requires_description() -> None:
    vc = VoiceConfig.for_design("Young male, warm tone")
    assert vc.model == "mimo-v2.5-tts-voicedesign"
    assert vc.voice is None
    assert vc.style_prompt == "Young male, warm tone"


def test_voiceconfig_for_clone_uses_data_uri() -> None:
    data_uri = "data:audio/mpeg;base64,SGVsbG8="
    vc = VoiceConfig.for_clone(data_uri, style="happy")
    assert vc.model == "mimo-v2.5-tts-voiceclone"
    assert vc.voice == data_uri
    assert vc.style_prompt == "happy"


def test_voiceconfig_is_frozen() -> None:
    vc = VoiceConfig.for_built_in("Chloe")
    with pytest.raises(dataclasses.FrozenInstanceError):
        vc.voice = "Mia"  # type: ignore[misc]


def test_validation_result_has_missing_models() -> None:
    vr = ValidationResult(
        available_models=frozenset({"mimo-v2.5-tts"}),
        missing_models=frozenset({"mimo-v2.5-tts-voicedesign"}),
    )
    assert vr.all_models_available is False
    assert "mimo-v2.5-tts-voicedesign" in vr.missing_models


def test_validation_result_all_available() -> None:
    vr = ValidationResult(
        available_models=frozenset(
            {"mimo-v2.5-tts", "mimo-v2.5-tts-voicedesign", "mimo-v2.5-tts-voiceclone"}
        ),
        missing_models=frozenset(),
    )
    assert vr.all_models_available is True


def test_synthesis_result_carries_audio_metadata() -> None:
    sr = SynthesisResult(
        audio_bytes=b"RIFF\x00\x00\x00\x00WAVE",
        audio_format="wav",
        duration_ms=1234.5,
        pcm_bytes=0,
    )
    assert sr.audio_bytes.startswith(b"RIFF")
    assert sr.audio_format == "wav"
    assert sr.duration_ms == 1234.5


def test_ttscallstats_streaming_has_ttft() -> None:
    stats = TTSCallStats(
        success=True,
        error_kind=None,
        duration_ms=1500.0,
        audio_bytes=240_000,
        audio_seconds=5.0,
        text="hello world",
        text_chars=11,
        streaming=True,
        ttft_ms=200.0,
    )
    assert stats.success
    assert stats.ttft_ms == 200.0
