"""Root test fixtures. Mocks the entire homeassistant.* hierarchy via sys.modules
injection so all tests run without the HA framework installed.

This conftest runs first for every test regardless of subdirectory. Engine tests
(tests/engine/) remain HA-decoupled — they never reference HA symbols — but they
still need the package __init__.py to import cleanly.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass as _dataclass
from types import ModuleType
from unittest.mock import MagicMock

# ── Build module stubs ────────────────────────────────────────────────────────

_ha = ModuleType("homeassistant")
_ha_core = ModuleType("homeassistant.core")
_ha_config_entries = ModuleType("homeassistant.config_entries")
_ha_data_entry_flow = ModuleType("homeassistant.data_entry_flow")
_ha_const = ModuleType("homeassistant.const")
_ha_exceptions = ModuleType("homeassistant.exceptions")
_ha_helpers = ModuleType("homeassistant.helpers")
_ha_helpers_aiohttp = ModuleType("homeassistant.helpers.aiohttp_client")
_ha_helpers_cv = ModuleType("homeassistant.helpers.config_validation")
_ha_helpers_dr = ModuleType("homeassistant.helpers.device_registry")
_ha_helpers_ep = ModuleType("homeassistant.helpers.entity_platform")
_ha_helpers_er = ModuleType("homeassistant.helpers.entity_registry")
_ha_helpers_ar = ModuleType("homeassistant.helpers.area_registry")
_ha_helpers_fr = ModuleType("homeassistant.helpers.floor_registry")
_ha_helpers_ir = ModuleType("homeassistant.helpers.issue_registry")
_ha_helpers_ms = ModuleType("homeassistant.helpers.media_source")
_ha_helpers_rs = ModuleType("homeassistant.helpers.restore_state")
_ha_helpers_sel = ModuleType("homeassistant.helpers.selector")
_ha_helpers_storage = ModuleType("homeassistant.helpers.storage")
_ha_helpers_uc = ModuleType("homeassistant.helpers.update_coordinator")
_ha_components = ModuleType("homeassistant.components")
_ha_components_ha = ModuleType("homeassistant.components.homeassistant")
_ha_components_ha_exposed = ModuleType(
    "homeassistant.components.homeassistant.exposed_entities"
)
_ha_components_diagnostics = ModuleType("homeassistant.components.diagnostics")
_ha_components_file_upload = ModuleType("homeassistant.components.file_upload")
_ha_components_media_player = ModuleType("homeassistant.components.media_player")
_ha_components_media_source = ModuleType("homeassistant.components.media_source")
_ha_components_sensor = ModuleType("homeassistant.components.sensor")
_ha_components_tts = ModuleType("homeassistant.components.tts")

# ── homeassistant.core ────────────────────────────────────────────────────────

_ha_core.HomeAssistant = MagicMock
_ha_core.callback = lambda f: f
_ha_core.Event = MagicMock
_ha_core.ServiceCall = MagicMock
_ha_core.SupportsResponse = MagicMock()
_ha_core.SupportsResponse.ONLY = "only"
_ha_core.SupportsResponse.OPTIONAL = "optional"
_ha_core.SupportsResponse.NONE = "none"
_ha_core.ServiceResponse = dict

# ── homeassistant.exceptions ─────────────────────────────────────────────────

_ha_exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
_ha_exceptions.ConfigEntryAuthFailed = type(
    "ConfigEntryAuthFailed", (_ha_exceptions.HomeAssistantError,), {}
)
_ha_exceptions.ConfigEntryError = type(
    "ConfigEntryError", (_ha_exceptions.HomeAssistantError,), {}
)
_ha_exceptions.ConfigEntryNotReady = type(
    "ConfigEntryNotReady", (_ha_exceptions.HomeAssistantError,), {}
)
_ha_exceptions.ServiceValidationError = type(
    "ServiceValidationError",
    (_ha_exceptions.HomeAssistantError,),
    {"__init__": lambda self, *a, **kw: Exception.__init__(self, *a)},
)

# ── homeassistant.const ───────────────────────────────────────────────────────

_ha_const.Platform = MagicMock(TTS="tts", SENSOR="sensor")
_ha_const.CONF_API_KEY = "api_key"
_ha_const.CONF_NAME = "name"
_ha_const.EntityCategory = MagicMock()
_ha_const.EntityCategory.DIAGNOSTIC = "diagnostic"
_ha_const.UnitOfInformation = MagicMock()
_ha_const.UnitOfInformation.BYTES = "B"
_ha_const.UnitOfTime = MagicMock()
_ha_const.UnitOfTime.MILLISECONDS = "ms"
_ha_const.UnitOfTime.MINUTES = "min"
_ha_const.UnitOfTime.SECONDS = "s"

# ── homeassistant.config_entries ─────────────────────────────────────────────


class _MockConfigFlow:
    """Mock ConfigFlow base class providing real method stubs for subclass testing."""

    VERSION = 1
    hass = None
    _reconfigure_entry_id = None

    def __init__(self) -> None:
        self.context: dict = {}

    def __init_subclass__(cls, *, domain: str | None = None, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

    def async_show_form(self, **kwargs: object) -> dict:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: object) -> dict:
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs: object) -> dict:
        return {"type": "abort", **kwargs}

    async def async_set_unique_id(self, unique_id: str) -> None:
        self.context["unique_id"] = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        pass

    def async_update_reload_and_abort(self, entry: object, **kwargs: object) -> dict:
        return {
            "type": "abort",
            "reason": kwargs.get("reason", "reconfigure_successful"),
        }

    def _get_reconfigure_entry(self) -> MagicMock:
        entry = MagicMock()
        entry.data = {}
        entry.entry_id = "existing_entry"
        return entry

    @staticmethod
    def async_get_options_flow(config_entry: object) -> None:
        raise NotImplementedError


class _MockOptionsFlow:
    """Mock OptionsFlow base class."""

    hass = None
    config_entry = None

    def async_show_form(self, **kwargs: object) -> dict:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: object) -> dict:
        return {"type": "create_entry", **kwargs}

    @staticmethod
    def add_suggested_values_to_schema(
        schema: object, suggested_values: object
    ) -> object:
        return schema


class _MockSection:
    """Mock section for data entry flows."""

    def __init__(self, schema: object, options: dict | None = None) -> None:
        self.schema = schema
        self.options = options or {}

    def __call__(self, value: object) -> object:
        return self.schema(value)  # type: ignore[operator]


_ha_data_entry_flow.section = _MockSection


class _MockConfigSubentryFlow:
    """Mock ConfigSubentryFlow base class for subentry flow testing."""

    hass = None

    def async_show_form(self, **kwargs: object) -> dict:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: object) -> dict:
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs: object) -> dict:
        return {"type": "abort", **kwargs}

    def _get_reconfigure_subentry(self) -> MagicMock:
        subentry = MagicMock()
        subentry.title = "Old Title"
        subentry.data = {}
        return subentry

    def async_update_and_abort(self, subentry: object, **kwargs: object) -> dict:
        return {
            "type": "abort",
            "reason": kwargs.get("reason", "reconfigure_successful"),
        }


_ha_config_entries.ConfigEntry = MagicMock
_ha_config_entries.ConfigFlow = _MockConfigFlow
_ha_config_entries.ConfigSubentry = MagicMock
_ha_config_entries.ConfigSubentryFlow = _MockConfigSubentryFlow
_ha_config_entries.ConfigFlowResult = dict
_ha_config_entries.SubentryFlowResult = dict
_ha_config_entries.OptionsFlow = _MockOptionsFlow
_ha_config_entries.ConfigEntryAuthFailed = _ha_exceptions.ConfigEntryAuthFailed
_ha_config_entries.ConfigEntryNotReady = _ha_exceptions.ConfigEntryNotReady

# ── homeassistant.helpers.entity_registry ────────────────────────────────────

_ha_helpers_er.async_get = MagicMock()
_ha_helpers_er.EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"

# ── homeassistant.helpers.area_registry ──────────────────────────────────────

_ha_helpers_ar.async_get = MagicMock()
_ha_helpers_ar.EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"

# ── homeassistant.helpers.device_registry ────────────────────────────────────

_ha_helpers_dr.async_get = MagicMock()
_ha_helpers_dr.EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
_ha_helpers_dr.DeviceInfo = dict


class _DeviceEntryType:
    SERVICE = "service"


_ha_helpers_dr.DeviceEntryType = _DeviceEntryType

# ── homeassistant.helpers.floor_registry ─────────────────────────────────────

_ha_helpers_fr.async_get = MagicMock()
_ha_helpers_fr.EVENT_FLOOR_REGISTRY_UPDATED = "floor_registry_updated"

# ── homeassistant.helpers.issue_registry ─────────────────────────────────────

_ha_helpers_ir.async_get = MagicMock()
_ha_helpers_ir.async_create_issue = MagicMock()


class _IssueSeverity:
    ERROR = "error"
    WARNING = "warning"


_ha_helpers_ir.IssueSeverity = _IssueSeverity

# ── homeassistant.helpers.entity_platform ────────────────────────────────────

_ha_helpers_ep.AddConfigEntryEntitiesCallback = MagicMock

# ── homeassistant.helpers.config_validation ──────────────────────────────────

_ha_helpers_cv.config_entry_only_config_schema = lambda domain: {}

# ── homeassistant.helpers.aiohttp_client ─────────────────────────────────────

_ha_helpers_aiohttp.async_get_clientsession = MagicMock()

# ── homeassistant.helpers.storage ────────────────────────────────────────────


class _MockStore:
    """Mock HA Store that keeps data in memory."""

    def __init__(self, hass: object, version: int, key: str) -> None:
        self._data: dict | None = None

    async def async_load(self) -> dict | None:
        return self._data

    async def async_save(self, data: dict) -> None:
        self._data = data


_ha_helpers_storage.Store = _MockStore

# ── homeassistant.helpers.selector ───────────────────────────────────────────

_ha_helpers_sel.TextSelector = MagicMock()
_ha_helpers_sel.TextSelectorConfig = MagicMock()
_ha_helpers_sel.SelectSelector = MagicMock()
_ha_helpers_sel.SelectSelectorConfig = MagicMock()
_ha_helpers_sel.SelectSelectorMode = MagicMock(DROPDOWN="dropdown", LIST="list")
_ha_helpers_sel.SelectOptionDict = dict
_ha_helpers_sel.FileSelector = MagicMock()
_ha_helpers_sel.FileSelectorConfig = MagicMock()

# ── homeassistant.helpers.media_source ───────────────────────────────────────

_ha_helpers_ms.async_resolve_media = MagicMock()

# ── homeassistant.helpers.restore_state ──────────────────────────────────────

_ha_helpers_rs.RestoreEntity = type(
    "RestoreEntity",
    (),
    {"async_get_last_state": lambda self: None},
)

# ── homeassistant.helpers.update_coordinator ─────────────────────────────────

_ha_helpers_uc.DataUpdateCoordinator = MagicMock
_ha_helpers_uc.UpdateFailed = type("UpdateFailed", (Exception,), {})

# ── homeassistant.components.homeassistant.exposed_entities ──────────────────

_ha_components_ha_exposed.async_should_expose = MagicMock(return_value=True)

# ── homeassistant.components.sensor ──────────────────────────────────────────

_ha_components_sensor.SensorEntity = type(
    "SensorEntity", (), {"_attr_device_info": None, "_attr_unique_id": None}
)


class _MockRestoreSensor:
    """Mock RestoreSensor with state restore support."""

    _attr_device_info = None
    _attr_unique_id = None
    _attr_native_value = None
    _attr_should_poll = True
    hass = None

    async def async_get_last_sensor_data(self) -> None:
        return None

    def async_write_ha_state(self) -> None:
        pass

    async def async_added_to_hass(self) -> None:
        pass


_ha_components_sensor.RestoreSensor = _MockRestoreSensor


@_dataclass(frozen=True, kw_only=True)
class _MockSensorEntityDescription:
    """Mock SensorEntityDescription with commonly used fields."""

    key: str = ""
    translation_key: str | None = None
    name: str | None = None
    icon: str | None = None
    device_class: object = None
    state_class: object = None
    entity_category: object = None
    entity_registry_enabled_default: bool = True
    native_unit_of_measurement: str | None = None
    suggested_display_precision: int | None = None
    options: list | None = None


_ha_components_sensor.SensorEntityDescription = _MockSensorEntityDescription
_ha_components_sensor.SensorDeviceClass = MagicMock()
_ha_components_sensor.SensorDeviceClass.ENUM = "enum"
_ha_components_sensor.SensorStateClass = MagicMock()
_ha_components_sensor.SensorStateClass.TOTAL_INCREASING = "total_increasing"

# ── homeassistant.components.tts ─────────────────────────────────────────────

_ha_components_tts.TextToSpeechEntity = type(
    "TextToSpeechEntity",
    (),
    {
        "_attr_device_info": None,
        "_attr_unique_id": None,
        "async_write_ha_state": lambda self: None,
    },
)
_ha_components_tts.TtsAudioType = MagicMock
_ha_components_tts.SampleRate = MagicMock()
_ha_components_tts.SampleRate.SAMPLERATE_24000 = 24000


@_dataclass
class _MockTTSAudioResponse:
    extension: str
    data_gen: object


_ha_components_tts.TTSAudioResponse = _MockTTSAudioResponse
_ha_components_tts.TTSAudioRequest = MagicMock

# ── homeassistant.components.media_player ────────────────────────────────────

_ha_components_media_player.MediaPlayerEntity = MagicMock

# ── homeassistant.components.media_source ────────────────────────────────────

_ha_components_media_source.BrowseMediaSource = MagicMock
_ha_components_media_source.MediaSource = MagicMock
_ha_components_media_source.MediaSourceItem = MagicMock
_ha_components_media_source.PlayMedia = MagicMock
_ha_components_media_source.async_resolve_media = MagicMock()

# ── homeassistant.components.diagnostics ─────────────────────────────────────

_ha_components_diagnostics.async_redact_data = lambda d, keys: {
    k: ("**REDACTED**" if k in keys else v) for k, v in d.items()
}

# ── homeassistant.components.file_upload ─────────────────────────────────────

_ha_components_file_upload.process_wrong_handler = MagicMock
_ha_components_file_upload.process_uploaded_file = MagicMock()

# ── Register all mocked modules ───────────────────────────────────────────────

for _mod_name, _mod in [
    ("homeassistant", _ha),
    ("homeassistant.core", _ha_core),
    ("homeassistant.config_entries", _ha_config_entries),
    ("homeassistant.data_entry_flow", _ha_data_entry_flow),
    ("homeassistant.const", _ha_const),
    ("homeassistant.exceptions", _ha_exceptions),
    ("homeassistant.helpers", _ha_helpers),
    ("homeassistant.helpers.aiohttp_client", _ha_helpers_aiohttp),
    ("homeassistant.helpers.config_validation", _ha_helpers_cv),
    ("homeassistant.helpers.device_registry", _ha_helpers_dr),
    ("homeassistant.helpers.entity_platform", _ha_helpers_ep),
    ("homeassistant.helpers.entity_registry", _ha_helpers_er),
    ("homeassistant.helpers.area_registry", _ha_helpers_ar),
    ("homeassistant.helpers.floor_registry", _ha_helpers_fr),
    ("homeassistant.helpers.issue_registry", _ha_helpers_ir),
    ("homeassistant.helpers.media_source", _ha_helpers_ms),
    ("homeassistant.helpers.restore_state", _ha_helpers_rs),
    ("homeassistant.helpers.selector", _ha_helpers_sel),
    ("homeassistant.helpers.storage", _ha_helpers_storage),
    ("homeassistant.helpers.update_coordinator", _ha_helpers_uc),
    ("homeassistant.components", _ha_components),
    ("homeassistant.components.homeassistant", _ha_components_ha),
    (
        "homeassistant.components.homeassistant.exposed_entities",
        _ha_components_ha_exposed,
    ),
    ("homeassistant.components.diagnostics", _ha_components_diagnostics),
    ("homeassistant.components.file_upload", _ha_components_file_upload),
    ("homeassistant.components.media_player", _ha_components_media_player),
    ("homeassistant.components.media_source", _ha_components_media_source),
    ("homeassistant.components.sensor", _ha_components_sensor),
    ("homeassistant.components.tts", _ha_components_tts),
]:
    sys.modules[_mod_name] = _mod

# voluptuous is in the test dependency group, but guard in case environment differs
try:
    import voluptuous as _vol  # noqa: F401
except ImportError:
    _vol_mock = MagicMock()
    sys.modules["voluptuous"] = _vol_mock
