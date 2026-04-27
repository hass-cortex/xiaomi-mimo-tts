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
