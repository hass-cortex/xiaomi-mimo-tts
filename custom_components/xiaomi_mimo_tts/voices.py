"""The voices of one config entry, and the devices they hang off.

An entry has one TTS entity whose voices are the built-in voices, by name, and
every voice profile (subentry), by subentry ID: a designed or cloned voice is
its profile, and a built-in profile is a built-in voice with a style prompt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import (
    BUILT_IN_VOICES,
    CONF_DEFAULT_VOICE,
    CONF_SUBENTRY_TYPE,
    DEFAULT_VOICE,
    DOMAIN,
    SUBENTRY_TYPE_BUILT_IN,
    SUBENTRY_TYPE_VOICE_CLONE,
    SUBENTRY_TYPE_VOICE_DESIGN,
)
from .engine.models import (
    MODEL_BUILT_IN,
    MODEL_VOICE_CLONE,
    MODEL_VOICE_DESIGN,
    ModelId,
)

if TYPE_CHECKING:
    from . import XiaomiMimoTTSConfigEntry

MANUFACTURER = "Xiaomi MiMo"


class _ProfileKind(NamedTuple):
    """What a subentry type means to the API and to the device registry."""

    model: ModelId
    device_label: str


PROFILE_KINDS: dict[str, _ProfileKind] = {
    SUBENTRY_TYPE_BUILT_IN: _ProfileKind(MODEL_BUILT_IN, "Xiaomi MiMo v2.5 (built-in)"),
    SUBENTRY_TYPE_VOICE_DESIGN: _ProfileKind(
        MODEL_VOICE_DESIGN, "Xiaomi MiMo v2.5 (voice design)"
    ),
    SUBENTRY_TYPE_VOICE_CLONE: _ProfileKind(
        MODEL_VOICE_CLONE, "Xiaomi MiMo v2.5 (voice clone)"
    ),
}


class VoiceChoice(NamedTuple):
    """The voice that speaks: a profile, or a built-in voice without one."""

    name: str
    """What the voice is called: the built-in name or the profile title."""
    profile: ConfigSubentry | None
    built_in: str | None
    """The built-in voice when no profile speaks."""


def entry_voices(entry: XiaomiMimoTTSConfigEntry) -> list[tuple[str, str]]:
    """The entry's voices as (voice ID, name): built-in ones, then the profiles."""
    return [(name, name) for name in BUILT_IN_VOICES] + [
        (subentry.subentry_id, subentry.title) for subentry in entry.subentries.values()
    ]


def default_voice(entry: XiaomiMimoTTSConfigEntry) -> str:
    """The voice that speaks when a call names none.

    A default naming a profile since deleted falls back to MiMo's own default,
    rather than failing every call that leaves the voice out.
    """
    voice = entry.options.get(CONF_DEFAULT_VOICE, DEFAULT_VOICE)
    if voice in BUILT_IN_VOICES or voice in entry.subentries:
        return voice
    return DEFAULT_VOICE


def resolve_voice(entry: XiaomiMimoTTSConfigEntry, voice: str | None) -> VoiceChoice:
    """The voice a call asked for, or the entry's default when it asked for none.

    Raises:
        KeyError: `voice` is neither a built-in voice nor a profile of the entry.
    """
    voice = voice or default_voice(entry)
    if voice in BUILT_IN_VOICES:
        return VoiceChoice(name=voice, profile=None, built_in=voice)
    profile = entry.subentries[voice]
    return VoiceChoice(name=profile.title, profile=profile, built_in=None)


def entry_device_info(entry: XiaomiMimoTTSConfigEntry) -> DeviceInfo:
    """The entry's device: the TTS entity and the sensors of every call."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model="Xiaomi MiMo v2.5",
        name=entry.title,
        entry_type=DeviceEntryType.SERVICE,
    )


def profile_device_info(
    entry: XiaomiMimoTTSConfigEntry, subentry: ConfigSubentry
) -> DeviceInfo:
    """A profile's device: the sensors of the calls its voice spoke."""
    kind = PROFILE_KINDS.get(subentry.data[CONF_SUBENTRY_TYPE])
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{subentry.subentry_id}")},
        manufacturer=MANUFACTURER,
        model=kind.device_label if kind else "Xiaomi MiMo v2.5",
        name=subentry.title,
        entry_type=DeviceEntryType.SERVICE,
        via_device=(DOMAIN, entry.entry_id),
    )
