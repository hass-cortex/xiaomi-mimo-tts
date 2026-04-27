"""Repair issue helpers for Xiaomi MiMo TTS."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def create_voice_sample_missing_issue(
    hass: HomeAssistant,
    *,
    entry_id: str,
    subentry_id: str,
    profile_name: str,
    missing_path: str,
) -> None:
    """Sample file referenced by a voice_clone profile is unreachable."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"voice_sample_missing_{subentry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="voice_sample_missing",
        translation_placeholders={
            "profile_name": profile_name,
            "missing_path": missing_path,
        },
    )


def create_model_unavailable_issue(
    hass: HomeAssistant,
    *,
    subentry_id: str,
    profile_name: str,
    model_id: str,
) -> None:
    """User's Xiaomi MiMo account does not have access to the required model."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"model_unavailable_{subentry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="model_unavailable",
        translation_placeholders={
            "profile_name": profile_name,
            "model_id": model_id,
        },
        learn_more_url="https://platform.xiaomimimo.com",
    )


def create_quota_exceeded_issue(hass: HomeAssistant) -> None:
    """Xiaomi MiMo billing quota exhausted (HTTP 402)."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "quota_exceeded",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="quota_exceeded",
        learn_more_url="https://platform.xiaomimimo.com",
    )


def create_media_dir_unwritable_issue(
    hass: HomeAssistant,
    *,
    dir_path: str,
) -> None:
    """Voice samples directory cannot be created or written."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "media_dir_unwritable",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="media_dir_unwritable",
        translation_placeholders={"dir_path": dir_path},
    )
