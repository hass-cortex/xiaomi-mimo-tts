"""Runtime data attached to ConfigEntry.runtime_data."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .engine.client import XiaomiMimoClient


@dataclass(slots=True)
class XiaomiMimoTTSRuntimeData:
    """In-memory state shared across entities and platforms for one config entry."""

    client: XiaomiMimoClient
    available_models: frozenset[str] = field(default_factory=frozenset)
    voice_sample_cache: OrderedDict[str, tuple[str, float, str]] = field(
        default_factory=OrderedDict
    )
    """LRU map: media_content_id → (base64_data_uri, mtime, resolved_path_str)."""
    sensors_by_subentry: dict[str, list[Any]] = field(default_factory=dict)
    """subentry_id → list of XiaomiMimoSensor (registered after async_added_to_hass)."""
