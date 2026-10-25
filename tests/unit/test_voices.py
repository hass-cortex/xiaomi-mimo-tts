"""Tests for voices.py: what the voice picker shows."""

from __future__ import annotations

from unittest.mock import MagicMock


def _profile(subentry_id: str, title: str, kind: str, **data: object) -> MagicMock:
    return MagicMock(subentry_id=subentry_id, title=title, data={"type": kind, **data})


def _names(entry) -> dict[str, str]:
    from custom_components.xiaomi_mimo_tts.voices import entry_voices

    return dict(entry_voices(entry))


def test_profiles_of_one_title_are_told_apart(mock_config_entry) -> None:
    """Two clones left with the stock title must not look alike in the picker."""
    sample = "media-source://media_source/local/voice_samples/{}.mp3"
    mock_config_entry.subentries = {
        "a": _profile(
            "a", "Cloned Voice", "voice_clone", voice_sample_id=sample.format("anna_su")
        ),
        "b": _profile(
            "b",
            "Cloned Voice",
            "voice_clone",
            voice_sample_id=sample.format("灣灣小何"),
        ),
        "c": _profile("c", "Warm", "voice_design", voice_description="warm"),
    }
    names = _names(mock_config_entry)
    assert names["a"] != names["b"]
    assert "anna_su" in names["a"]
    assert "灣灣小何" in names["b"]
    assert names["c"] == "Warm"


def test_profile_named_after_its_built_in_voice_is_told_apart(
    mock_config_entry,
) -> None:
    mock_config_entry.subentries = {
        "p": _profile(
            "p", "冰糖", "built_in", voice="冰糖", default_style_prompt="calm"
        ),
    }
    names = _names(mock_config_entry)
    assert names["冰糖"] == "冰糖"
    assert names["p"] != "冰糖"


def test_mimo_default_has_a_readable_name(mock_config_entry) -> None:
    assert _names(mock_config_entry)["mimo_default"] != "mimo_default"
