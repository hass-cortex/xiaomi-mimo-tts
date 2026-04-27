"""Diagnostics for Xiaomi MiMo TTS — redacts api_key + voice sample IDs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import XiaomiMimoTTSConfigEntry

REDACT_KEYS = {"api_key", "voice_sample_id", "voice"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: XiaomiMimoTTSConfigEntry
) -> dict[str, Any]:
    return {
        "data": async_redact_data(dict(entry.data), REDACT_KEYS),
        "options": dict(entry.options),
        "subentries": [
            {
                "id": se.subentry_id,
                "title": se.title,
                "data": async_redact_data(dict(se.data), REDACT_KEYS),
            }
            for se in entry.subentries.values()
        ],
        "available_models": sorted(entry.runtime_data.available_models),
    }
