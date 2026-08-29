"""Xiaomi MiMo TTS API client.

Pure Python — accepts an injected aiohttp.ClientSession. Boundary contract:
must NOT import the HA framework.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Final, Literal

import aiohttp

from .audio import build_wav_header
from .errors import (
    XiaomiMimoApiError,
    XiaomiMimoAuthError,
    XiaomiMimoBadRequestError,
    XiaomiMimoConnectionError,
    XiaomiMimoQuotaExceededError,
    XiaomiMimoRateLimitError,
    XiaomiMimoServerError,
    XiaomiMimoTimeoutError,
)
from .models import REQUIRED_MODELS, SynthesisResult, ValidationResult, VoiceConfig

__all__ = ["DEFAULT_BASE_URL", "REQUIRED_MODELS", "XiaomiMimoClient"]

_LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final = "https://api.xiaomimimo.com/v1"
VALIDATE_TIMEOUT_S: Final = 5.0


class XiaomiMimoClient:
    """Async HTTP client for the Xiaomi MiMo TTS API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        audio_format: Literal["wav", "pcm16"] = "wav",
    ) -> SynthesisResult:
        """Public synthesize with single retry on 429 / 5xx / connection errors."""
        return await self._with_retry(
            lambda: self._do_synthesize(text, voice_config, audio_format)
        )

    async def _do_synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        audio_format: Literal["wav", "pcm16"],
    ) -> SynthesisResult:
        """Single attempt — collect the whole stream into one clip.

        Streams even though the caller wants every byte: the server emits
        audio while it is still inferring, so draining the stream completes
        sooner than waiting on the one-shot response. Retrying this stays safe
        precisely because nothing reaches the caller until the last byte has
        arrived — unlike `synthesize_stream`, which cannot be replayed.
        """
        start = time.monotonic()
        pcm = bytearray()
        async for chunk in self.synthesize_stream(text, voice_config):
            pcm.extend(chunk)
        duration_ms = (time.monotonic() - start) * 1000.0

        pcm_bytes = len(pcm)
        audio_bytes = bytes(pcm)
        if audio_format == "wav":
            audio_bytes = build_wav_header(pcm_bytes) + audio_bytes
        return SynthesisResult(
            audio_bytes=audio_bytes,
            audio_format=audio_format,
            duration_ms=duration_ms,
            pcm_bytes=pcm_bytes,
        )

    async def synthesize_stream(
        self, text: str, voice_config: VoiceConfig
    ) -> AsyncIterator[bytes]:
        """Stream PCM bytes from Xiaomi MiMo with stream=true. NO retry — bytes are
        already being yielded; restart not possible without restarting audio.

        Uses chunked reading + manual SSE event parsing because the
        compatibility-mode models emit the whole clip as one ``data:`` line
        (multi-MB), which exceeds aiohttp's default 128 KiB readline limit.
        """
        url = f"{self._base_url}/chat/completions"
        body = self._build_body(text, voice_config)
        try:
            async with self._session.post(
                url,
                headers=self._headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    await self._raise_for_status(resp)
                async for chunk in self._iter_sse_audio(resp):
                    yield chunk
        except TimeoutError as exc:
            raise XiaomiMimoTimeoutError("synthesize_stream timed out") from exc
        except aiohttp.ClientConnectionError as exc:
            raise XiaomiMimoConnectionError(str(exc)) from exc

    async def _iter_sse_audio(
        self, resp: aiohttp.ClientResponse
    ) -> AsyncIterator[bytes]:
        """Read response in 64 KiB chunks, split SSE events on ``\\n\\n``,
        decode ``data: {audio.data}`` payloads, and yield raw PCM bytes.

        Tolerates arbitrarily large ``data:`` lines (well beyond aiohttp's
        readline limit) by buffering raw bytes instead of lines.
        """
        buffer = bytearray()
        scanned = 0
        async for chunk in resp.content.iter_chunked(64 * 1024):
            buffer.extend(chunk)
            # Process complete SSE events. Each event ends with "\n\n".
            while True:
                sep = buffer.find(b"\n\n", scanned)
                if sep == -1:
                    # Keep one byte back so a separator split across two
                    # chunks is still found.
                    scanned = max(0, len(buffer) - 1)
                    break
                event_bytes = bytes(memoryview(buffer)[:sep])
                del buffer[: sep + 2]
                scanned = 0
                for pcm in self._decode_sse_event(event_bytes):
                    yield pcm
        # Trailing event without final blank line
        if buffer.strip():
            for pcm in self._decode_sse_event(bytes(buffer)):
                yield pcm

    def _decode_sse_event(self, event: bytes) -> Iterator[bytes]:
        """Decode one SSE event's ``data:`` lines into PCM bytes."""
        for line in event.split(b"\n"):
            line = line.strip()
            if not line.startswith(b"data: "):
                continue
            payload = line[6:]
            if payload == b"[DONE]":
                return
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            audio = delta.get("audio")
            if not audio:
                continue
            b64 = audio.get("data")
            if not b64:
                continue
            yield base64.b64decode(b64)

    async def validate(self) -> ValidationResult:
        """Probe GET /v1/models. Free, ~0.4 s, validates auth + lists models."""
        url = f"{self._base_url}/models"
        try:
            async with self._session.get(
                url,
                headers={"api-key": self._api_key},
                timeout=aiohttp.ClientTimeout(total=VALIDATE_TIMEOUT_S),
            ) as resp:
                if resp.status == 401:
                    raise XiaomiMimoAuthError(
                        status=401,
                        error_code="invalid_key",
                        error_message="Invalid API key",
                    )
                if resp.status >= 400:
                    body = await _safe_read_json(resp)
                    err = (body or {}).get("error", {})
                    raise XiaomiMimoApiError(
                        status=resp.status,
                        error_code=err.get("code"),
                        error_message=err.get("message", f"HTTP {resp.status}"),
                    )
                body = await resp.json()
        except TimeoutError as exc:
            raise XiaomiMimoTimeoutError("Validate timed out") from exc
        except aiohttp.ClientConnectionError as exc:
            raise XiaomiMimoConnectionError(str(exc)) from exc

        available = frozenset(m["id"] for m in body.get("data", []))
        return ValidationResult(
            available_models=available,
            missing_models=REQUIRED_MODELS - available,
        )

    def __repr__(self) -> str:
        return f"XiaomiMimoClient(base_url={self._base_url!r}, api_key=<redacted>)"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def _build_body(self, text: str, vc: VoiceConfig) -> dict:  # type: ignore[type-arg]
        """Build the request body. Always streaming, and streaming implies pcm16."""
        audio: dict[str, str] = {"format": "pcm16"}
        if vc.voice is not None:
            audio["voice"] = vc.voice
        return {
            "model": vc.model,
            "messages": [
                {"role": "user", "content": vc.style_prompt},
                {"role": "assistant", "content": text},
            ],
            "audio": audio,
            "stream": True,
        }

    async def _raise_for_status(self, resp: aiohttp.ClientResponse) -> None:
        body = await _safe_read_json(resp)
        err = (body or {}).get("error", {}) if isinstance(body, dict) else {}
        code = err.get("code")
        message = err.get("message", f"HTTP {resp.status}")
        if resp.status in (401, 403):
            raise XiaomiMimoAuthError(
                status=resp.status, error_code=code, error_message=message
            )
        if resp.status == 402:
            raise XiaomiMimoQuotaExceededError(
                status=resp.status, error_code=code, error_message=message
            )
        if resp.status == 429:
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            raise XiaomiMimoRateLimitError(
                status=resp.status,
                error_code=code,
                error_message=message,
                retry_after=retry_after,
            )
        if resp.status == 400:
            raise XiaomiMimoBadRequestError(
                status=resp.status, error_code=code, error_message=message
            )
        if 500 <= resp.status < 600:
            raise XiaomiMimoServerError(
                status=resp.status, error_code=code, error_message=message
            )
        raise XiaomiMimoApiError(
            status=resp.status, error_code=code, error_message=message
        )

    async def _with_retry(
        self, op: Callable[[], Awaitable[SynthesisResult]]
    ) -> SynthesisResult:
        """Retry once on 429 (Retry-After or 1s), 5xx, or connection error."""
        try:
            return await op()
        except XiaomiMimoRateLimitError as exc:
            wait = min(exc.retry_after or 1.0, 5.0)
            _LOGGER.debug("Rate limited; retrying after %.1fs", wait)
            await asyncio.sleep(wait)
            return await op()
        except XiaomiMimoServerError:
            _LOGGER.debug("Server error; retrying after 1s")
            await asyncio.sleep(1.0)
            return await op()
        except XiaomiMimoConnectionError:
            _LOGGER.debug("Connection error; retrying after 1s")
            await asyncio.sleep(1.0)
            return await op()


async def _safe_read_json(resp: aiohttp.ClientResponse) -> dict | None:  # type: ignore[type-arg]
    """Read JSON body without raising; used for error response decoding."""
    try:
        return await resp.json()  # type: ignore[no-any-return]
    except aiohttp.ContentTypeError, ValueError:
        return None


def _parse_retry_after(value: str | None) -> float | None:
    """Parse Retry-After header value to seconds as float."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
