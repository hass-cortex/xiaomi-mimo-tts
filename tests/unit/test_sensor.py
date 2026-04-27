"""Tests for sensor.py."""

from __future__ import annotations

import pytest

from custom_components.xiaomi_mimo_tts.engine.models import TTSCallStats


def _ok_stats(text: str = "hello", audio_bytes: int = 24_000 * 2) -> TTSCallStats:
    return TTSCallStats(
        success=True,
        error_kind=None,
        duration_ms=400.0,
        audio_bytes=audio_bytes,
        audio_seconds=audio_bytes / (24_000 * 2),
        text=text,
        text_chars=len(text),
        streaming=False,
        ttft_ms=None,
        sentence_count=None,
    )


def _err_stats(kind: str = "api") -> TTSCallStats:
    return TTSCallStats(
        success=False,
        error_kind=kind,
        duration_ms=200.0,
        audio_bytes=0,
        audio_seconds=0.0,
        text="x",
        text_chars=1,
        streaming=False,
        ttft_ms=None,
        sentence_count=None,
    )


def test_requests_total_increments() -> None:
    from custom_components.xiaomi_mimo_tts.sensor import SENSOR_DESCRIPTIONS

    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "requests_total")
    assert desc.update_fn(None, _ok_stats()) == 1
    assert desc.update_fn(5, _ok_stats()) == 6
    assert desc.update_fn(5, _err_stats()) == 6  # increments on failure too


def test_requests_failed_only_on_error() -> None:
    from custom_components.xiaomi_mimo_tts.sensor import SENSOR_DESCRIPTIONS

    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "requests_failed")
    assert desc.update_fn(0, _ok_stats()) == 0
    assert desc.update_fn(0, _err_stats()) == 1


def test_total_audio_minutes_accumulates_only_on_success() -> None:
    from custom_components.xiaomi_mimo_tts.sensor import SENSOR_DESCRIPTIONS

    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_audio_minutes")
    s = _ok_stats(audio_bytes=24_000 * 2 * 60)  # 60 seconds of audio
    assert desc.update_fn(0.0, s) == pytest.approx(1.0, abs=0.01)
    assert desc.update_fn(1.0, _err_stats()) == 1.0


def test_last_text_truncates_long_state() -> None:
    from custom_components.xiaomi_mimo_tts.sensor import SENSOR_DESCRIPTIONS

    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "last_text")
    long_text = "x" * 500
    state, attrs = desc.update_fn_with_attrs(None, _ok_stats(text=long_text))
    assert len(state) <= 255
    assert state.endswith("...")
    assert attrs == {"full_text": long_text}


def test_last_result_classifies_kind() -> None:
    from custom_components.xiaomi_mimo_tts.sensor import SENSOR_DESCRIPTIONS

    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "last_result")
    assert desc.update_fn(None, _ok_stats()) == "success"
    assert desc.update_fn(None, _err_stats(kind="auth")) == "auth_error"
    assert desc.update_fn(None, _err_stats(kind="timeout")) == "timeout"
    assert desc.update_fn(None, _err_stats(kind="api")) == "api_error"


def test_sensor_descriptions_count() -> None:
    from custom_components.xiaomi_mimo_tts.sensor import SENSOR_DESCRIPTIONS

    assert len(SENSOR_DESCRIPTIONS) == 15
