"""Tests for repairs.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_create_voice_sample_missing_issue_calls_create(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.repairs import (
        create_voice_sample_missing_issue,
    )

    with patch(
        "custom_components.xiaomi_mimo_tts.repairs.ir.async_create_issue"
    ) as mock_create:
        create_voice_sample_missing_issue(
            mock_hass,
            entry_id="entry_test",
            subentry_id="se_clone1",
            profile_name="Alice",
            missing_path="/media/voice_samples/alice.mp3",
        )
    mock_create.assert_called_once()
    args, kwargs = mock_create.call_args
    assert kwargs["translation_key"] == "voice_sample_missing"
    assert kwargs["is_fixable"] is True


@pytest.mark.asyncio
async def test_model_unavailable_issue(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.repairs import (
        create_model_unavailable_issue,
    )

    with patch(
        "custom_components.xiaomi_mimo_tts.repairs.ir.async_create_issue"
    ) as mock_create:
        create_model_unavailable_issue(
            mock_hass,
            subentry_id="se",
            profile_name="X",
            model_id="mimo-v2.5-tts-voiceclone",
        )
    args, kwargs = mock_create.call_args
    assert kwargs["translation_key"] == "model_unavailable"
    assert kwargs["is_fixable"] is False


@pytest.mark.asyncio
async def test_quota_exceeded_issue(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.repairs import create_quota_exceeded_issue

    with patch(
        "custom_components.xiaomi_mimo_tts.repairs.ir.async_create_issue"
    ) as mock_create:
        create_quota_exceeded_issue(mock_hass)
    args, kwargs = mock_create.call_args
    assert kwargs["translation_key"] == "quota_exceeded"


@pytest.mark.asyncio
async def test_media_dir_unwritable_issue(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.repairs import (
        create_media_dir_unwritable_issue,
    )

    with patch(
        "custom_components.xiaomi_mimo_tts.repairs.ir.async_create_issue"
    ) as mock_create:
        create_media_dir_unwritable_issue(mock_hass, dir_path="/media/voice_samples")
    args, kwargs = mock_create.call_args
    assert kwargs["translation_key"] == "media_dir_unwritable"
    assert kwargs["is_fixable"] is True
