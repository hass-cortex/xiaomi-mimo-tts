"""Xiaomi MiMo TTS custom integration entry point."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_REQUEST_TIMEOUT,
    DEFAULT_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
)
from .engine.client import XiaomiMimoClient
from .runtime import XiaomiMimoTTSRuntimeData

PLATFORMS: list[Platform] = [Platform.TTS, Platform.SENSOR]

type XiaomiMimoTTSConfigEntry = ConfigEntry[XiaomiMimoTTSRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: XiaomiMimoTTSConfigEntry
) -> bool:
    """Set up Xiaomi MiMo TTS from a config entry."""
    session = async_get_clientsession(hass)
    client = XiaomiMimoClient(
        session,
        api_key=entry.data[CONF_API_KEY],
        base_url=entry.options.get(CONF_BASE_URL, DEFAULT_BASE_URL),
        timeout=entry.options.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
    )
    entry.runtime_data = XiaomiMimoTTSRuntimeData(client=client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: XiaomiMimoTTSConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: XiaomiMimoTTSConfigEntry
) -> None:
    """Reload entry on options or subentry changes so new voice profiles materialise."""
    await hass.config_entries.async_reload(entry.entry_id)
