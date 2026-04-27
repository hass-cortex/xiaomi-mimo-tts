"""Xiaomi MiMo TTS engine error hierarchy.

Pure Python — no HA framework imports.
Boundary contract: errors must extend Exception, not HA-side error classes.
The HA shell layer translates these to platform exceptions.
"""

from __future__ import annotations


class XiaomiMimoError(Exception):
    """Base class for all Xiaomi MiMo engine errors."""


class XiaomiMimoConnectionError(XiaomiMimoError):
    """Network-level failure: DNS, connect refused, socket reset."""


class XiaomiMimoTimeoutError(XiaomiMimoConnectionError):
    """Total request timeout exceeded."""


class XiaomiMimoApiError(XiaomiMimoError):
    """HTTP non-2xx response from Xiaomi MiMo API.

    Args:
        status: HTTP status code.
        error_code: Vendor-specific code from response body, if any.
        error_message: Human-readable message; safe to surface to user.
    """

    def __init__(self, status: int, error_code: str | None, error_message: str) -> None:
        super().__init__(error_message)
        self.status = status
        self.error_code = error_code
        self.error_message = error_message


class XiaomiMimoAuthError(XiaomiMimoApiError):
    """401 / 403 — invalid or revoked API key."""


class XiaomiMimoRateLimitError(XiaomiMimoApiError):
    """429 — request throttled.

    Args:
        retry_after: Seconds to wait before retry, parsed from `Retry-After` header.
    """

    def __init__(
        self,
        status: int,
        error_code: str | None,
        error_message: str,
        retry_after: float | None,
    ) -> None:
        super().__init__(status, error_code, error_message)
        self.retry_after = retry_after


class XiaomiMimoQuotaExceededError(XiaomiMimoApiError):
    """402 — billing / quota exhausted."""


class XiaomiMimoBadRequestError(XiaomiMimoApiError):
    """400 — invalid request (e.g. text too long, unsupported voice)."""


class XiaomiMimoServerError(XiaomiMimoApiError):
    """5xx — Xiaomi MiMo backend failure."""
