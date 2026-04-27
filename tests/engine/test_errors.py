"""Tests for engine.errors module."""

from __future__ import annotations

from custom_components.xiaomi_mimo_tts.engine.errors import (
    XiaomiMimoApiError,
    XiaomiMimoAuthError,
    XiaomiMimoBadRequestError,
    XiaomiMimoConnectionError,
    XiaomiMimoError,
    XiaomiMimoQuotaExceededError,
    XiaomiMimoRateLimitError,
    XiaomiMimoServerError,
    XiaomiMimoTimeoutError,
)


def test_mimoerror_extends_exception_not_homeassistant_error() -> None:
    """Engine errors must NOT extend HomeAssistantError (boundary contract)."""
    assert issubclass(XiaomiMimoError, Exception)
    # Hard guarantee: nothing imports homeassistant in engine/
    import custom_components.xiaomi_mimo_tts.engine.errors as mod

    src = mod.__file__
    assert src is not None
    with open(src, encoding="utf-8") as fp:
        text = fp.read()
    assert "homeassistant" not in text


def test_connection_and_timeout_classes() -> None:
    assert issubclass(XiaomiMimoConnectionError, XiaomiMimoError)
    assert issubclass(XiaomiMimoTimeoutError, XiaomiMimoConnectionError)


def test_api_error_carries_metadata() -> None:
    err = XiaomiMimoApiError(
        status=400, error_code="invalid_input", error_message="bad text"
    )
    assert err.status == 400
    assert err.error_code == "invalid_input"
    assert err.error_message == "bad text"
    assert "bad text" in str(err)


def test_specific_api_error_subclasses() -> None:
    for cls in (
        XiaomiMimoAuthError,
        XiaomiMimoRateLimitError,
        XiaomiMimoQuotaExceededError,
        XiaomiMimoBadRequestError,
        XiaomiMimoServerError,
    ):
        assert issubclass(cls, XiaomiMimoApiError)


def test_rate_limit_carries_retry_after() -> None:
    err = XiaomiMimoRateLimitError(
        status=429, error_code=None, error_message="rate limited", retry_after=2.5
    )
    assert err.retry_after == 2.5
