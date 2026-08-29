"""Constants for the Xiaomi MiMo TTS integration."""

from __future__ import annotations

from typing import Final

from .engine.client import DEFAULT_BASE_URL

__all__ = [
    "ALLOWED_SAMPLE_MIMES",
    "BUILT_IN_VOICES",
    "CONF_API_KEY",
    "CONF_BASE_URL",
    "CONF_DEFAULT_STYLE_PROMPT",
    "CONF_REQUEST_TIMEOUT",
    "CONF_STREAMING_ENABLED",
    "CONF_SUBENTRY_TYPE",
    "CONF_VOICE",
    "CONF_VOICE_DESCRIPTION",
    "CONF_VOICE_SAMPLE_ID",
    "CONF_VOICE_SAMPLES_DIR",
    "DEFAULT_AUDIO_FORMAT",
    "DEFAULT_BASE_URL",
    "DEFAULT_REQUEST_TIMEOUT",
    "DEFAULT_STREAMING_ENABLED",
    "DEFAULT_VOICE_SAMPLES_DIR",
    "DOMAIN",
    "MAX_SAMPLE_BYTES",
    "SUBENTRY_TYPES",
    "SUBENTRY_TYPE_BUILT_IN",
    "SUBENTRY_TYPE_VOICE_CLONE",
    "SUBENTRY_TYPE_VOICE_DESIGN",
]

DOMAIN: Final = "xiaomi_mimo_tts"

# Config entry data keys
CONF_API_KEY: Final = "api_key"

# Options keys (entry-level)
CONF_BASE_URL: Final = "base_url"
CONF_REQUEST_TIMEOUT: Final = "request_timeout"
CONF_STREAMING_ENABLED: Final = "streaming_enabled"
CONF_VOICE_SAMPLES_DIR: Final = "voice_samples_dir"

DEFAULT_REQUEST_TIMEOUT: Final = 60
DEFAULT_STREAMING_ENABLED: Final = True
DEFAULT_VOICE_SAMPLES_DIR: Final = "/media/voice_samples"
DEFAULT_AUDIO_FORMAT: Final = "wav"

# Subentry types
SUBENTRY_TYPE_BUILT_IN: Final = "built_in"
SUBENTRY_TYPE_VOICE_DESIGN: Final = "voice_design"
SUBENTRY_TYPE_VOICE_CLONE: Final = "voice_clone"

SUBENTRY_TYPES: Final = (
    SUBENTRY_TYPE_BUILT_IN,
    SUBENTRY_TYPE_VOICE_DESIGN,
    SUBENTRY_TYPE_VOICE_CLONE,
)

# Subentry data keys
CONF_SUBENTRY_TYPE: Final = "type"
CONF_VOICE: Final = "voice"
CONF_DEFAULT_STYLE_PROMPT: Final = "default_style_prompt"
CONF_VOICE_DESCRIPTION: Final = "voice_description"
CONF_VOICE_SAMPLE_ID: Final = "voice_sample_id"

# Built-in voices
BUILT_IN_VOICES: Final = (
    "mimo_default",
    "Chloe",
    "Mia",
    "Milo",
    "Dean",
    "冰糖",
    "茉莉",
    "苏打",
    "白桦",
)

# Voice clone sample limits
MAX_SAMPLE_BYTES: Final = 10 * 1024 * 1024  # 10 MB
ALLOWED_SAMPLE_MIMES: Final = ("audio/mpeg", "audio/wav")
