"""Unit-test fixtures. HA module mocks are injected by tests/conftest.py (root level)
and are available here via sys.modules before any import of custom_components.*."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_hass() -> MagicMock:
    """Return a mock HomeAssistant instance with common attributes."""
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=lambda: None)
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Return a mock ConfigEntry with sensible defaults."""
    entry = MagicMock()
    entry.entry_id = "entry_test"
    entry.unique_id = "abcdef0123456789"
    entry.data = {"api_key": "sk-test"}
    entry.options = {}
    entry.subentries = {}
    entry.runtime_data = MagicMock()
    entry.runtime_data.sensors_by_subentry = {}
    entry.runtime_data.voice_sample_cache = {}
    return entry
