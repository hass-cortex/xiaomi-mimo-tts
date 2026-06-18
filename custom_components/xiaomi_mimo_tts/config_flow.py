"""Config flow for Xiaomi MiMo TTS."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    BUILT_IN_VOICES,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_DEFAULT_AUDIO_FORMAT,
    CONF_DEFAULT_STYLE_PROMPT,
    CONF_REQUEST_TIMEOUT,
    CONF_STREAMING_ENABLED,
    CONF_SUBENTRY_TYPE,
    CONF_VOICE,
    CONF_VOICE_DESCRIPTION,
    CONF_VOICE_SAMPLE_ID,
    CONF_VOICE_SAMPLES_DIR,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_STREAMING_ENABLED,
    DEFAULT_VOICE_SAMPLES_DIR,
    DOMAIN,
    SUBENTRY_TYPE_BUILT_IN,
    SUBENTRY_TYPE_VOICE_CLONE,
    SUBENTRY_TYPE_VOICE_DESIGN,
)
from .engine.client import XiaomiMimoClient
from .engine.errors import (
    XiaomiMimoAuthError,
    XiaomiMimoConnectionError,
    XiaomiMimoError,
)
from .selector import list_existing_samples, save_uploaded_sample

_LOGGER = logging.getLogger(__name__)

DEFAULT_ENTRY_TITLE = "Xiaomi MiMo TTS"

USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): str,
        vol.Required(CONF_API_KEY): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})

_VOICE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(BUILT_IN_VOICES),
        translation_key="voice",
        mode=SelectSelectorMode.DROPDOWN,
    )
)


async def _validate_api_key(
    hass: HomeAssistant, api_key: str, base_url: str = DEFAULT_BASE_URL
) -> str | None:
    """Validate ``api_key`` against the Xiaomi MiMo API.

    Returns the ``errors["base"]`` key on failure, or None on success. Logs
    missing-model warnings as a side effect on success.
    """
    session = async_get_clientsession(hass)
    client = XiaomiMimoClient(session, api_key=api_key, base_url=base_url)
    try:
        result = await client.validate()
    except XiaomiMimoAuthError:
        return "invalid_api_key"
    except XiaomiMimoConnectionError:
        return "cannot_connect"
    except XiaomiMimoError:
        return "unknown"
    if not result.all_models_available:
        _LOGGER.warning(
            "Some Xiaomi MiMo TTS models unavailable: %s", result.missing_models
        )
    return None


BUILT_IN_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Xiaomi MiMo Built-in"): str,
        vol.Required(CONF_VOICE, default="冰糖"): _VOICE_SELECTOR,
        vol.Optional(CONF_DEFAULT_STYLE_PROMPT, default=""): str,
    }
)


class BuiltInSubentryFlow(ConfigSubentryFlow):
    """Subentry flow for built-in voice profile."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=BUILT_IN_SCHEMA)
        return self.async_create_entry(
            title=user_input["name"],
            data={
                CONF_SUBENTRY_TYPE: SUBENTRY_TYPE_BUILT_IN,
                CONF_VOICE: user_input[CONF_VOICE],
                CONF_DEFAULT_STYLE_PROMPT: user_input.get(
                    CONF_DEFAULT_STYLE_PROMPT, ""
                ),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is None:
            # Use description.suggested_value (not default=) for Optional fields:
            # default= acts as fallback when key omitted, so a cleared field would
            # silently restore the old value.
            schema = vol.Schema(
                {
                    vol.Required("name", default=subentry.title): str,
                    vol.Required(
                        CONF_VOICE,
                        default=subentry.data.get(CONF_VOICE, "冰糖"),
                    ): _VOICE_SELECTOR,
                    vol.Optional(
                        CONF_DEFAULT_STYLE_PROMPT,
                        description={
                            "suggested_value": subentry.data.get(
                                CONF_DEFAULT_STYLE_PROMPT, ""
                            )
                        },
                    ): str,
                }
            )
            return self.async_show_form(step_id="reconfigure", data_schema=schema)
        return self.async_update_and_abort(
            self._get_entry(),
            subentry,
            title=user_input["name"],
            data={
                CONF_SUBENTRY_TYPE: SUBENTRY_TYPE_BUILT_IN,
                CONF_VOICE: user_input[CONF_VOICE],
                CONF_DEFAULT_STYLE_PROMPT: user_input.get(
                    CONF_DEFAULT_STYLE_PROMPT, ""
                ),
            },
        )


VOICE_DESIGN_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Xiaomi MiMo Designed Voice"): str,
        vol.Required(CONF_VOICE_DESCRIPTION): str,
    }
)


class VoiceDesignSubentryFlow(ConfigSubentryFlow):
    """Subentry flow for voice-design profile (text-described voice)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=VOICE_DESIGN_SCHEMA)
        return self.async_create_entry(
            title=user_input["name"],
            data={
                CONF_SUBENTRY_TYPE: SUBENTRY_TYPE_VOICE_DESIGN,
                CONF_VOICE_DESCRIPTION: user_input[CONF_VOICE_DESCRIPTION],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("name", default=subentry.title): str,
                    vol.Required(
                        CONF_VOICE_DESCRIPTION,
                        default=subentry.data.get(CONF_VOICE_DESCRIPTION, ""),
                    ): str,
                }
            )
            return self.async_show_form(step_id="reconfigure", data_schema=schema)
        return self.async_update_and_abort(
            self._get_entry(),
            subentry,
            title=user_input["name"],
            data={
                CONF_SUBENTRY_TYPE: SUBENTRY_TYPE_VOICE_DESIGN,
                CONF_VOICE_DESCRIPTION: user_input[CONF_VOICE_DESCRIPTION],
            },
        )


VOICE_CLONE_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Xiaomi MiMo Cloned Voice"): str,
        vol.Required("sample_source", default="upload"): vol.In(["upload", "existing"]),
    }
)


def _voice_clone_upload_schema() -> vol.Schema:
    from homeassistant.helpers.selector import (
        FileSelector,
        FileSelectorConfig,
    )

    return vol.Schema(
        {
            vol.Required("audio_file"): FileSelector(
                FileSelectorConfig(accept="audio/mpeg,audio/wav")
            ),
            vol.Optional("save_as", default=""): str,
        }
    )


def _voice_clone_pick_schema(
    samples: list[dict[str, str]], *, default: str | None = None
) -> vol.Schema:
    label_by_value = {s["value"]: s["label"] for s in samples}
    if default and default in label_by_value:
        marker = vol.Required(CONF_VOICE_SAMPLE_ID, default=default)
    else:
        marker = vol.Required(CONF_VOICE_SAMPLE_ID)
    return vol.Schema({marker: vol.In(label_by_value)})


class VoiceCloneSubentryFlow(ConfigSubentryFlow):
    """Subentry flow for voice-clone profile (audio sample → cloned voice)."""

    def __init__(self) -> None:
        self._chosen_name: str = ""
        self._reconfigure_subentry: ConfigSubentry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=VOICE_CLONE_SOURCE_SCHEMA
            )
        self._chosen_name = user_input["name"]
        if user_input["sample_source"] == "upload":
            return await self.async_step_upload()
        return await self.async_step_pick()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("name", default=subentry.title): str,
                    vol.Required("sample_source", default="existing"): vol.In(
                        ["upload", "existing"]
                    ),
                }
            )
            return self.async_show_form(step_id="reconfigure", data_schema=schema)
        self._chosen_name = user_input["name"]
        self._reconfigure_subentry = subentry
        if user_input["sample_source"] == "upload":
            return await self.async_step_upload()
        return await self.async_step_pick()

    async def async_step_upload(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="upload", data_schema=_voice_clone_upload_schema()
            )
        save_as = (user_input.get("save_as") or "").strip() or None
        try:
            cid = await save_uploaded_sample(
                self.hass,
                file_id=user_input["audio_file"],
                mime="audio/mpeg",
                voice_samples_dir=DEFAULT_VOICE_SAMPLES_DIR,
                save_as=save_as,
            )
        except ValueError:
            return self.async_show_form(
                step_id="upload",
                data_schema=_voice_clone_upload_schema(),
                errors={"base": "invalid_sample"},
            )
        return self._finish_clone(cid)

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        samples = await list_existing_samples(self.hass)
        if not samples:
            return self.async_abort(reason="no_samples_found")
        if user_input is None:
            current = (
                self._reconfigure_subentry.data.get(CONF_VOICE_SAMPLE_ID)
                if self._reconfigure_subentry is not None
                else None
            )
            return self.async_show_form(
                step_id="pick",
                data_schema=_voice_clone_pick_schema(samples, default=current),
            )
        return self._finish_clone(user_input[CONF_VOICE_SAMPLE_ID])

    def _finish_clone(self, voice_sample_id: str) -> SubentryFlowResult:
        """Create or update the voice_clone subentry with the resolved sample id."""
        entry_data = {
            CONF_SUBENTRY_TYPE: SUBENTRY_TYPE_VOICE_CLONE,
            CONF_VOICE_SAMPLE_ID: voice_sample_id,
        }
        if self._reconfigure_subentry is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                self._reconfigure_subentry,
                title=self._chosen_name,
                data=entry_data,
            )
        return self.async_create_entry(title=self._chosen_name, data=entry_data)


class XiaomiMimoTTSConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Main config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(_config_entry: Any) -> XiaomiMimoTTSOptionsFlow:
        return XiaomiMimoTTSOptionsFlow()

    @classmethod
    def async_get_supported_subentry_types(
        cls, _config_entry: Any
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {
            SUBENTRY_TYPE_BUILT_IN: BuiltInSubentryFlow,
            SUBENTRY_TYPE_VOICE_DESIGN: VoiceDesignSubentryFlow,
            SUBENTRY_TYPE_VOICE_CLONE: VoiceCloneSubentryFlow,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

        api_key = user_input[CONF_API_KEY]
        unique_id = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        error = await _validate_api_key(self.hass, api_key)
        if error is None:
            title = (user_input.get(CONF_NAME) or "").strip() or DEFAULT_ENTRY_TITLE
            return self.async_create_entry(
                title=title,
                data={CONF_API_KEY: api_key},
                options={},
            )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors={"base": error}
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=REAUTH_SCHEMA
            )
        api_key = user_input[CONF_API_KEY]
        error = await _validate_api_key(self.hass, api_key)
        if error is None:
            # Non-auto-reload variant: the entry's update listener
            # (_async_update_listener) fires on data change and reloads. Keeping
            # the listener as the single reload source avoids a redundant
            # double-scheduled reload and is also required for subentry edits.
            return self.async_update_and_abort(
                self._reauth_entry, data={CONF_API_KEY: api_key}
            )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors={"base": error},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        description={"suggested_value": entry.title},
                    ): str,
                    vol.Required(
                        CONF_BASE_URL,
                        default=entry.options.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                    ): str,
                    vol.Required(
                        CONF_REQUEST_TIMEOUT,
                        default=entry.options.get(
                            CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
                        ),
                    ): int,
                }
            )
            return self.async_show_form(step_id="reconfigure", data_schema=schema)
        new_title = (user_input.pop(CONF_NAME, None) or "").strip() or entry.title
        # Non-auto-reload variant: the entry's update listener handles the
        # reload when data/options change (single reload source; also covers
        # subentry edits, which async_update_and_abort does not auto-reload).
        return self.async_update_and_abort(
            entry,
            title=new_title,
            options={**entry.options, **user_input},
        )


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REQUEST_TIMEOUT, default=DEFAULT_REQUEST_TIMEOUT): int,
        vol.Required(CONF_STREAMING_ENABLED, default=DEFAULT_STREAMING_ENABLED): bool,
        vol.Required(CONF_VOICE_SAMPLES_DIR, default=DEFAULT_VOICE_SAMPLES_DIR): str,
        vol.Required(CONF_DEFAULT_AUDIO_FORMAT, default=DEFAULT_AUDIO_FORMAT): vol.In(
            ["wav", "pcm16"]
        ),
    }
)


class XiaomiMimoTTSOptionsFlow(OptionsFlow):
    """Options flow for Xiaomi MiMo TTS."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=OPTIONS_SCHEMA)
