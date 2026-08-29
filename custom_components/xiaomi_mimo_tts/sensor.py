"""Xiaomi MiMo TTS diagnostic sensors (14 per voice profile)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_SUBENTRY_TYPE,
    CONF_VOICE,
    CONF_VOICE_SAMPLE_ID,
    DOMAIN,
    SUBENTRY_TYPE_BUILT_IN,
    SUBENTRY_TYPE_VOICE_CLONE,
)
from .engine.models import TTSCallStats

if TYPE_CHECKING:
    from . import XiaomiMimoTTSConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class XiaomiMimoSensorDescription(SensorEntityDescription):
    """A Xiaomi MiMo sensor description carrying its push-update function.

    ``update_fn`` receives ``(current_value, stats)`` and returns the new value;
    ``stateful_update_fn`` receives the sensor itself for entries that need
    per-instance state (e.g. the rolling average). Mutually exclusive.
    """

    update_fn: Callable[[Any, TTSCallStats], Any] = lambda cur, s: cur
    stateful_update_fn: Callable[[XiaomiMimoSensor, TTSCallStats], Any] | None = None
    update_fn_with_attrs: (
        Callable[[Any, TTSCallStats], tuple[Any, dict[str, Any]]] | None
    ) = None


def _classify_result(stats: TTSCallStats) -> str:
    if stats.success:
        return "success"
    return {
        "auth": "auth_error",
        "timeout": "timeout",
    }.get(stats.error_kind or "", "api_error")


def _truncate_state_with_attrs(
    cur: Any, stats: TTSCallStats
) -> tuple[str, dict[str, Any]]:
    text = stats.text
    if len(text) <= 252:
        return text, {"full_text": text}
    return text[:252] + "...", {"full_text": text}


def _avg_duration(sensor: XiaomiMimoSensor, stats: TTSCallStats) -> Any:
    if not stats.success:
        return sensor._attr_native_value
    history = sensor.duration_history
    history.append(stats.duration_ms)
    return round(sum(history) / len(history), 1)


SENSOR_DESCRIPTIONS: tuple[XiaomiMimoSensorDescription, ...] = (
    XiaomiMimoSensorDescription(
        key="requests_total",
        translation_key="requests_total",
        name="Requests total",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: int(cur or 0) + 1,
    ),
    XiaomiMimoSensorDescription(
        key="requests_success",
        translation_key="requests_success",
        name="Requests success",
        icon="mdi:check-circle",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        update_fn=lambda cur, s: int(cur or 0) + (1 if s.success else 0),
    ),
    XiaomiMimoSensorDescription(
        key="requests_failed",
        translation_key="requests_failed",
        name="Requests failed",
        icon="mdi:alert-circle",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: int(cur or 0) + (0 if s.success else 1),
    ),
    XiaomiMimoSensorDescription(
        key="last_duration",
        translation_key="last_duration",
        name="Last duration",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: round(s.duration_ms, 1),
    ),
    XiaomiMimoSensorDescription(
        key="average_duration",
        translation_key="average_duration",
        name="Average duration",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        stateful_update_fn=_avg_duration,
    ),
    XiaomiMimoSensorDescription(
        key="last_audio_size",
        translation_key="last_audio_size",
        name="Last audio size",
        icon="mdi:file-music",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        update_fn=lambda cur, s: round(s.audio_bytes / 1024, 1) if s.success else cur,
    ),
    XiaomiMimoSensorDescription(
        key="last_audio_seconds",
        translation_key="last_audio_seconds",
        name="Last audio seconds",
        icon="mdi:clock-fast",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=1,
        update_fn=lambda cur, s: round(s.audio_seconds, 1) if s.success else cur,
    ),
    XiaomiMimoSensorDescription(
        key="total_audio_minutes",
        translation_key="total_audio_minutes",
        name="Total audio minutes",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: round(
            float(cur or 0) + (s.audio_seconds / 60 if s.success else 0), 2
        ),
    ),
    XiaomiMimoSensorDescription(
        key="last_text_chars",
        translation_key="last_text_chars",
        name="Last text characters",
        icon="mdi:format-letter-case",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        update_fn=lambda cur, s: s.text_chars,
    ),
    XiaomiMimoSensorDescription(
        key="total_chars_synthesized",
        translation_key="total_chars_synthesized",
        name="Total characters synthesized",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: int(cur or 0) + (s.text_chars if s.success else 0),
    ),
    XiaomiMimoSensorDescription(
        key="last_result",
        translation_key="last_result",
        name="Last result",
        icon="mdi:check-decagram",
        device_class=SensorDeviceClass.ENUM,
        options=["success", "api_error", "auth_error", "timeout"],
        update_fn=lambda cur, s: _classify_result(s),
    ),
    XiaomiMimoSensorDescription(
        key="last_text",
        translation_key="last_text",
        name="Last text",
        icon="mdi:text",
        update_fn_with_attrs=_truncate_state_with_attrs,
    ),
    XiaomiMimoSensorDescription(
        key="last_ttft",
        translation_key="last_ttft",
        name="Last time to first audio",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        # How long before audio starts, whichever path the call took. Clears
        # on failure rather than keeping a stale reading.
        update_fn=lambda cur, s: round(s.ttft_ms, 1) if s.ttft_ms is not None else None,
    ),
    XiaomiMimoSensorDescription(
        key="last_streaming",
        translation_key="last_streaming",
        name="Last call streaming",
        icon="mdi:transit-connection-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: bool(s.streaming),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiMimoTTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry in entry.subentries.values():
        entities: list[Any] = [
            XiaomiMimoSensor(entry, subentry, desc) for desc in SENSOR_DESCRIPTIONS
        ]
        if subentry.data.get(CONF_SUBENTRY_TYPE) in (
            SUBENTRY_TYPE_BUILT_IN,
            SUBENTRY_TYPE_VOICE_CLONE,
        ):
            entities.append(XiaomiMimoVoiceSensor(entry, subentry))
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)


class XiaomiMimoSensor(RestoreSensor):
    """RestoreSensor that handles per-call stats pushes."""

    has_entity_name = True
    entity_description: XiaomiMimoSensorDescription
    _attr_should_poll = False

    def __init__(
        self,
        entry: XiaomiMimoTTSConfigEntry,
        subentry: ConfigSubentry,
        description: XiaomiMimoSensorDescription,
    ) -> None:
        self.entity_description = description
        self._entry = entry
        self._subentry = subentry
        self._attr_unique_id = (
            f"{entry.entry_id}_{subentry.subentry_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{subentry.subentry_id}")},
        )
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self.duration_history: deque[float] = deque(maxlen=10)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value
        self._entry.runtime_data.sensors_by_subentry.setdefault(
            self._subentry.subentry_id, []
        ).append(self)

    async def async_will_remove_from_hass(self) -> None:
        registered = self._entry.runtime_data.sensors_by_subentry.get(
            self._subentry.subentry_id
        )
        if registered is not None and self in registered:
            registered.remove(self)

    def handle_call(self, stats: TTSCallStats) -> None:
        desc = self.entity_description
        if desc.update_fn_with_attrs is not None:
            new_value, attrs = desc.update_fn_with_attrs(self._attr_native_value, stats)
            self._attr_extra_state_attributes = attrs
        elif desc.stateful_update_fn is not None:
            new_value = desc.stateful_update_fn(self, stats)
        else:
            new_value = desc.update_fn(self._attr_native_value, stats)
        if new_value != self._attr_native_value:
            self._attr_native_value = new_value
            self.async_write_ha_state()


class XiaomiMimoVoiceSensor(SensorEntity):
    """Config-driven sensor exposing the voice this subentry is bound to.

    Only registered for built-in and voice-clone subentries — voice-design
    profiles use a free-text description that already lives in the subentry
    title. The integration reloads on subentry change, so the sensor reads
    its value once at init.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "voice_in_use"
    _attr_icon = "mdi:account-voice"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, entry: XiaomiMimoTTSConfigEntry, subentry: ConfigSubentry
    ) -> None:
        self._entry = entry
        self._subentry = subentry
        self._attr_unique_id = f"{entry.entry_id}_{subentry.subentry_id}_voice_in_use"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{subentry.subentry_id}")},
        )
        self._attr_native_value = self._compute_value()

    def _compute_value(self) -> str | None:
        sub_type = self._subentry.data.get(CONF_SUBENTRY_TYPE)
        if sub_type == SUBENTRY_TYPE_BUILT_IN:
            return self._subentry.data.get(CONF_VOICE)
        if sub_type == SUBENTRY_TYPE_VOICE_CLONE:
            sample_id = self._subentry.data.get(CONF_VOICE_SAMPLE_ID, "")
            # Strip media-source prefix so the value is just the file name.
            return sample_id.rsplit("/", 1)[-1] if sample_id else None
        return None
