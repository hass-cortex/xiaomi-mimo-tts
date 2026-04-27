"""Pure-Python dataclasses used by the Xiaomi MiMo engine.

Boundary contract: this module must NOT import the HA framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

MODEL_BUILT_IN: Final = "mimo-v2.5-tts"
MODEL_VOICE_DESIGN: Final = "mimo-v2.5-tts-voicedesign"
MODEL_VOICE_CLONE: Final = "mimo-v2.5-tts-voiceclone"

REQUIRED_MODELS: Final[frozenset[str]] = frozenset(
    {MODEL_BUILT_IN, MODEL_VOICE_DESIGN, MODEL_VOICE_CLONE}
)

ModelId = Literal[
    "mimo-v2.5-tts",
    "mimo-v2.5-tts-voicedesign",
    "mimo-v2.5-tts-voiceclone",
]


@dataclass(frozen=True, slots=True)
class VoiceConfig:
    """How to synthesize speech for a single TTS call.

    Construct via class methods: for_built_in / for_design / for_clone.
    """

    model: ModelId
    voice: str | None
    """Built-in voice name, base64 data URI for clone, or None for design."""
    style_prompt: str
    """User-message content. Required for voice_design; optional otherwise."""

    @classmethod
    def for_built_in(cls, voice_name: str, style: str = "") -> VoiceConfig:
        return cls(model=MODEL_BUILT_IN, voice=voice_name, style_prompt=style)

    @classmethod
    def for_design(cls, description: str) -> VoiceConfig:
        return cls(
            model=MODEL_VOICE_DESIGN,
            voice=None,
            style_prompt=description,
        )

    @classmethod
    def for_clone(cls, sample_data_uri: str, style: str = "") -> VoiceConfig:
        return cls(
            model=MODEL_VOICE_CLONE,
            voice=sample_data_uri,
            style_prompt=style,
        )


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of XiaomiMimoClient.validate(). Lists which required models are reachable."""

    available_models: frozenset[str]
    missing_models: frozenset[str]

    @property
    def all_models_available(self) -> bool:
        return not self.missing_models


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    """Result of a non-streaming synthesize() call."""

    audio_bytes: bytes
    audio_format: Literal["wav", "pcm16"]
    duration_ms: float


@dataclass(frozen=True, slots=True)
class TTSCallStats:
    """Per-call statistics pushed to HA sensors after each TTS request.

    Lives in the engine so the engine's own benchmarking / CLI can produce them
    without depending on HA. The HA sensor module consumes them.
    """

    success: bool
    error_kind: str | None
    """One of: "auth", "timeout", "rate_limit", "api", "unknown" — or None on success."""
    duration_ms: float
    audio_bytes: int
    audio_seconds: float
    text: str
    text_chars: int
    streaming: bool
    ttft_ms: float | None
    sentence_count: int | None
