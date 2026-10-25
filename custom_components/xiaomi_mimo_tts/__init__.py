"""Xiaomi MiMo TTS custom integration entry point."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_DEFAULT_VOICE,
    CONF_REQUEST_TIMEOUT,
    CONF_SUBENTRY_TYPE,
    DEFAULT_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    SUBENTRY_TYPE_BUILT_IN,
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


async def async_migrate_entry(
    hass: HomeAssistant, entry: XiaomiMimoTTSConfigEntry
) -> bool:
    """Bring an entry up to the current version.

    1.1 → 1.2: each voice profile was a TTS entity of its own; now the entry
    has one, whose voices are the profiles. The profiles' TTS entities go, and
    the default voice becomes the first built-in profile (else the first
    profile), so the new entity speaks as the one a pipeline most likely used.
    Their devices and sensors stay.
    """
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity.domain == Platform.TTS and entity.unique_id != entry.entry_id:
                registry.async_remove(entity.entity_id)
        profiles = sorted(
            entry.subentries.values(),
            key=lambda se: se.data.get(CONF_SUBENTRY_TYPE) != SUBENTRY_TYPE_BUILT_IN,
        )
        options = dict(entry.options)
        if profiles and CONF_DEFAULT_VOICE not in options:
            options[CONF_DEFAULT_VOICE] = profiles[0].subentry_id
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
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
