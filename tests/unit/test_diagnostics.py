"""Tests for diagnostics.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_diagnostics_redacts_api_key(mock_hass, mock_config_entry) -> None:
    from custom_components.xiaomi_mimo_tts.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    mock_config_entry.data = {"api_key": "sk-supersecret"}
    mock_config_entry.options = {}
    mock_config_entry.subentries = {}
    mock_config_entry.runtime_data.available_models = frozenset({"mimo-v2.5-tts"})
    out = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
    assert "sk-supersecret" not in str(out)
    assert out["data"]["api_key"] == "**REDACTED**"


@pytest.mark.asyncio
async def test_diagnostics_redacts_voice_clone_sample(
    mock_hass, mock_config_entry
) -> None:
    from custom_components.xiaomi_mimo_tts.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    fake_subentry = MagicMock()
    fake_subentry.subentry_id = "se1"
    fake_subentry.title = "Alice"
    fake_subentry.data = {
        "type": "voice_clone",
        "voice_sample_id": "media-source://media_source/local/voice_samples/alice.mp3",
    }
    mock_config_entry.data = {"api_key": "x"}
    mock_config_entry.options = {}
    mock_config_entry.subentries = {"se1": fake_subentry}
    mock_config_entry.runtime_data.available_models = frozenset({"mimo-v2.5-tts"})

    out = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
    assert out["subentries"][0]["data"]["voice_sample_id"] == "**REDACTED**"
