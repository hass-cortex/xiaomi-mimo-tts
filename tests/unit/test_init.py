"""Tests for __init__.py async_setup_entry / async_unload_entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_setup_entry_creates_runtime_data(mock_hass, mock_config_entry) -> None:
    from custom_components.xiaomi_mimo_tts import async_setup_entry
    from custom_components.xiaomi_mimo_tts.runtime import XiaomiMimoTTSRuntimeData

    mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    with patch(
        "custom_components.xiaomi_mimo_tts.async_get_clientsession",
        return_value=MagicMock(),
    ):
        result = await async_setup_entry(mock_hass, mock_config_entry)
    assert result is True
    assert isinstance(mock_config_entry.runtime_data, XiaomiMimoTTSRuntimeData)


@pytest.mark.asyncio
async def test_unload_entry(mock_hass, mock_config_entry) -> None:
    from custom_components.xiaomi_mimo_tts import async_unload_entry

    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    mock_config_entry.runtime_data = MagicMock()
    result = await async_unload_entry(mock_hass, mock_config_entry)
    assert result is True


def _registry_entry(entity_id: str, unique_id: str):
    return MagicMock(
        entity_id=entity_id, unique_id=unique_id, domain=entity_id.split(".")[0]
    )


@pytest.mark.asyncio
async def test_migration_drops_profile_tts_entities_and_keeps_their_voice(
    mock_hass, mock_config_entry
) -> None:
    """1.1 had a TTS entity per profile; the built-in one becomes the default voice."""
    from custom_components.xiaomi_mimo_tts import async_migrate_entry

    mock_config_entry.version = 1
    mock_config_entry.minor_version = 1
    mock_config_entry.subentries = {
        "se_warm": MagicMock(subentry_id="se_warm", data={"type": "voice_design"}),
        "se_chloe": MagicMock(subentry_id="se_chloe", data={"type": "built_in"}),
    }
    registry = MagicMock()
    entities = [
        _registry_entry("tts.xiaomi_mimo_built_in", "entry_test_se_chloe"),
        _registry_entry("tts.xiaomi_mimo_designed_voice", "entry_test_se_warm"),
        _registry_entry(
            "sensor.warm_requests_total", "entry_test_se_warm_requests_total"
        ),
    ]
    with (
        patch("custom_components.xiaomi_mimo_tts.er.async_get", return_value=registry),
        patch(
            "custom_components.xiaomi_mimo_tts.er.async_entries_for_config_entry",
            return_value=entities,
        ),
    ):
        assert await async_migrate_entry(mock_hass, mock_config_entry) is True

    removed = {c.args[0] for c in registry.async_remove.call_args_list}
    assert removed == {"tts.xiaomi_mimo_built_in", "tts.xiaomi_mimo_designed_voice"}
    update = mock_hass.config_entries.async_update_entry.call_args.kwargs
    assert update["options"]["default_voice"] == "se_chloe"
    assert update["minor_version"] == 2


@pytest.mark.asyncio
async def test_migration_keeps_a_chosen_default_voice(
    mock_hass, mock_config_entry
) -> None:
    from custom_components.xiaomi_mimo_tts import async_migrate_entry

    mock_config_entry.version = 1
    mock_config_entry.minor_version = 1
    mock_config_entry.options = {"default_voice": "茉莉"}
    mock_config_entry.subentries = {
        "se_chloe": MagicMock(subentry_id="se_chloe", data={"type": "built_in"}),
    }
    with (
        patch("custom_components.xiaomi_mimo_tts.er.async_get"),
        patch(
            "custom_components.xiaomi_mimo_tts.er.async_entries_for_config_entry",
            return_value=[],
        ),
    ):
        await async_migrate_entry(mock_hass, mock_config_entry)
    update = mock_hass.config_entries.async_update_entry.call_args.kwargs
    assert update["options"]["default_voice"] == "茉莉"
