"""Tests for config_flow.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.xiaomi_mimo_tts.engine.errors import (
    XiaomiMimoAuthError,
    XiaomiMimoConnectionError,
)
from custom_components.xiaomi_mimo_tts.engine.models import ValidationResult


@pytest.mark.asyncio
async def test_user_step_success_creates_entry(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSConfigFlow

    flow = XiaomiMimoTTSConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    with (
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.XiaomiMimoClient"
        ) as mock_client_cls,
    ):
        instance = mock_client_cls.return_value
        instance.validate = AsyncMock(
            return_value=ValidationResult(
                available_models=frozenset(
                    {
                        "mimo-v2.5-tts",
                        "mimo-v2.5-tts-voicedesign",
                        "mimo-v2.5-tts-voiceclone",
                    }
                ),
                missing_models=frozenset(),
            )
        )
        result = await flow.async_step_user({"api_key": "sk-test"})

    flow.async_create_entry.assert_called_once()
    assert result == {"type": "create_entry"}


@pytest.mark.asyncio
async def test_user_step_auth_error_returns_form_with_error(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSConfigFlow

    flow = XiaomiMimoTTSConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})

    with (
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.XiaomiMimoClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.validate = AsyncMock(
            side_effect=XiaomiMimoAuthError(401, "invalid_key", "bad")
        )
        await flow.async_step_user({"api_key": "sk-bad"})

    args, kwargs = flow.async_show_form.call_args
    assert kwargs.get("errors", {}).get("base") == "invalid_api_key"


@pytest.mark.asyncio
async def test_user_step_connection_error_aborts(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSConfigFlow

    flow = XiaomiMimoTTSConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})

    with (
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.XiaomiMimoClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.validate = AsyncMock(
            side_effect=XiaomiMimoConnectionError("DNS")
        )
        await flow.async_step_user({"api_key": "sk-test"})

    args, kwargs = flow.async_show_form.call_args
    assert kwargs.get("errors", {}).get("base") == "cannot_connect"


@pytest.mark.asyncio
async def test_built_in_subentry_creates_entry(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import BuiltInSubentryFlow

    flow = BuiltInSubentryFlow()
    flow.hass = mock_hass
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    result = await flow.async_step_user(
        {"name": "Chloe Voice", "voice": "Chloe", "default_style_prompt": ""}
    )

    flow.async_create_entry.assert_called_once()
    args, kwargs = flow.async_create_entry.call_args
    assert kwargs["title"] == "Chloe Voice"
    assert kwargs["data"]["type"] == "built_in"
    assert kwargs["data"]["voice"] == "Chloe"
    assert result == {"type": "create_entry"}


@pytest.mark.asyncio
async def test_voice_design_subentry_creates_entry(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import VoiceDesignSubentryFlow

    flow = VoiceDesignSubentryFlow()
    flow.hass = mock_hass
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    await flow.async_step_user(
        {
            "name": "Young Male",
            "voice_description": "Young male, warm tone, late-20s",
        }
    )

    args, kwargs = flow.async_create_entry.call_args
    assert kwargs["title"] == "Young Male"
    assert kwargs["data"]["type"] == "voice_design"
    assert kwargs["data"]["voice_description"].startswith("Young male")


@pytest.mark.asyncio
async def test_voice_clone_source_show_form(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import VoiceCloneSubentryFlow

    flow = VoiceCloneSubentryFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})

    result = await flow.async_step_user(None)
    assert result == {"type": "form"}


@pytest.mark.asyncio
async def test_voice_clone_pick_existing(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import VoiceCloneSubentryFlow

    flow = VoiceCloneSubentryFlow()
    flow.hass = mock_hass
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    flow._chosen_name = "Alice Clone"
    flow._get_entry = MagicMock(return_value=MagicMock(options={}))

    with patch(
        "custom_components.xiaomi_mimo_tts.config_flow.list_existing_samples",
        new=AsyncMock(
            return_value=[
                {
                    "label": "alice.mp3",
                    "value": "media-source://media_source/local/voice_samples/alice.mp3",
                }
            ]
        ),
    ):
        await flow.async_step_pick(
            {
                "voice_sample_id": "media-source://media_source/local/voice_samples/alice.mp3"
            }
        )

    args, kwargs = flow.async_create_entry.call_args
    assert kwargs["title"] == "Alice Clone"
    assert kwargs["data"]["type"] == "voice_clone"
    assert "alice.mp3" in kwargs["data"]["voice_sample_id"]


@pytest.mark.asyncio
async def test_reauth_step_updates_entry(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSConfigFlow
    from custom_components.xiaomi_mimo_tts.engine.models import ValidationResult

    flow = XiaomiMimoTTSConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock()
    flow.async_update_and_abort = MagicMock(return_value={"type": "abort"})
    flow._reauth_entry = MagicMock(entry_id="entry_test", data={"api_key": "old"})

    with (
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.XiaomiMimoClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.validate = AsyncMock(
            return_value=ValidationResult(
                available_models=frozenset({"mimo-v2.5-tts"}),
                missing_models=frozenset(),
            )
        )
        await flow.async_step_reauth_confirm({"api_key": "new-key"})

    flow.async_update_and_abort.assert_called_once()


@pytest.mark.asyncio
async def test_reauth_step_invalid_key_shows_error(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSConfigFlow

    flow = XiaomiMimoTTSConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow.async_update_and_abort = MagicMock()
    flow._reauth_entry = MagicMock(entry_id="entry_test", data={"api_key": "old"})

    with (
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.xiaomi_mimo_tts.config_flow.XiaomiMimoClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.validate = AsyncMock(
            side_effect=XiaomiMimoAuthError(401, "x", "bad")
        )
        await flow.async_step_reauth_confirm({"api_key": "still-bad"})

    args, kwargs = flow.async_show_form.call_args
    assert kwargs.get("errors", {}).get("base") == "invalid_api_key"


@pytest.mark.asyncio
async def test_reconfigure_step_renders_form(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSConfigFlow

    flow = XiaomiMimoTTSConfigFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow._get_reconfigure_entry = MagicMock(return_value=MagicMock(options={}))

    result = await flow.async_step_reconfigure(None)
    assert result == {"type": "form"}


@pytest.mark.asyncio
async def test_options_flow_keeps_options_it_does_not_show(
    mock_hass, mock_config_entry
) -> None:
    """Saving the options must not drop the base URL that reconfigure set."""
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSOptionsFlow

    mock_config_entry.options = {"base_url": "https://proxy.example/v1"}
    flow = XiaomiMimoTTSOptionsFlow()
    flow.hass = mock_hass
    flow.config_entry = mock_config_entry
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

    await flow.async_step_init(
        {
            "default_voice": "Chloe",
            "request_timeout": 90,
            "streaming_enabled": False,
            "voice_samples_dir": "/media/x",
        }
    )
    data = flow.async_create_entry.call_args.kwargs["data"]
    assert data["base_url"] == "https://proxy.example/v1"
    assert data["default_voice"] == "Chloe"


@pytest.mark.asyncio
async def test_options_flow_offers_profiles_as_the_default_voice(
    mock_hass, mock_config_entry
) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import XiaomiMimoTTSOptionsFlow

    profile = MagicMock(
        subentry_id="se_warm", title="Warm", data={"type": "voice_design"}
    )
    mock_config_entry.subentries = {"se_warm": profile}
    mock_config_entry.options = {"default_voice": "se_warm"}
    flow = XiaomiMimoTTSOptionsFlow()
    flow.hass = mock_hass
    flow.config_entry = mock_config_entry

    with patch(
        "custom_components.xiaomi_mimo_tts.config_flow.SelectSelectorConfig"
    ) as config:
        result = await flow.async_step_init(None)
    assert result["type"] == "form"
    options = config.call_args.kwargs["options"]
    assert {"value": "se_warm", "label": "Warm"} in options
    assert {"value": "冰糖", "label": "冰糖"} in options
    default = next(
        k.default() for k in result["data_schema"].schema if k == "default_voice"
    )
    assert default == "se_warm"


@pytest.mark.asyncio
async def test_built_in_subentry_reconfigure(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import BuiltInSubentryFlow

    flow = BuiltInSubentryFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow._get_reconfigure_subentry = MagicMock(
        return_value=MagicMock(
            title="Old Name",
            data={"voice": "Chloe", "default_style_prompt": ""},
        )
    )

    result = await flow.async_step_reconfigure(None)
    assert result == {"type": "form"}


@pytest.mark.asyncio
async def test_voice_clone_uses_the_configured_samples_dir(mock_hass) -> None:
    """The samples directory option must reach the listing and the upload."""
    from custom_components.xiaomi_mimo_tts.config_flow import VoiceCloneSubentryFlow

    flow = VoiceCloneSubentryFlow()
    flow.hass = mock_hass
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    flow._chosen_name = "Alice Clone"
    flow._get_entry = MagicMock(
        return_value=MagicMock(options={"voice_samples_dir": "/media/custom_dir"})
    )
    assert flow._samples_dir == "/media/custom_dir"

    lister = AsyncMock(return_value=[])
    with patch(
        "custom_components.xiaomi_mimo_tts.config_flow.list_existing_samples",
        new=lister,
    ):
        await flow.async_step_pick(None)
    assert lister.await_args.kwargs["dir_path"] == "/media/custom_dir"


@pytest.mark.asyncio
async def test_unnamed_built_in_profile_goes_by_its_voice(mock_hass) -> None:
    """A profile is a voice in the picker; a stock title would say nothing."""
    from custom_components.xiaomi_mimo_tts.config_flow import BuiltInSubentryFlow

    flow = BuiltInSubentryFlow()
    flow.hass = mock_hass
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    await flow.async_step_user(
        {"name": "  ", "voice": "茉莉", "default_style_prompt": ""}
    )
    assert flow.async_create_entry.call_args.kwargs["title"] == "茉莉"


@pytest.mark.asyncio
async def test_unnamed_clone_profile_goes_by_its_sample(mock_hass) -> None:
    from custom_components.xiaomi_mimo_tts.config_flow import VoiceCloneSubentryFlow

    flow = VoiceCloneSubentryFlow()
    flow.hass = mock_hass
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    flow._get_entry = MagicMock(return_value=MagicMock(options={}))
    sample = "media-source://media_source/local/voice_samples/灣灣小何.mp3"
    with patch(
        "custom_components.xiaomi_mimo_tts.config_flow.list_existing_samples",
        new=AsyncMock(return_value=[{"label": "灣灣小何.mp3", "value": sample}]),
    ):
        await flow.async_step_user({"name": "", "sample_source": "existing"})
        await flow.async_step_pick({"voice_sample_id": sample})
    assert flow.async_create_entry.call_args.kwargs["title"] == "灣灣小何"
