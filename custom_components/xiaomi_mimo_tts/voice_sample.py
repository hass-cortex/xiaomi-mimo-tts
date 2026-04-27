"""Resolve voice-sample media_content_id to base64 data URI for Xiaomi MiMo voice clone."""

from __future__ import annotations

import asyncio
import base64
import os
from collections import OrderedDict
from pathlib import Path

from homeassistant.components.media_source import async_resolve_media
from homeassistant.core import HomeAssistant

from .const import ALLOWED_SAMPLE_MIMES, MAX_SAMPLE_BYTES

# Cache entry: (data_uri, mtime, path) — path stored so cache hits skip re-resolve.
_CacheEntry = tuple[str, float, str]
VOICE_SAMPLE_CACHE_MAXSIZE = 8


class VoiceSampleError(Exception):
    """Raised when sample resolution / read / size validation fails."""


class VoiceSampleResolver:
    """Resolve + base64-encode voice samples with mtime-based caching.

    Cache entries are keyed by ``media_content_id`` and store
    ``(data_uri, mtime, path)``. On a cache hit the file mtime is checked
    directly (no round-trip through ``async_resolve_media``), so repeated
    calls for the same unchanged file never re-read from disk. The cache is
    a bounded LRU (``VOICE_SAMPLE_CACHE_MAXSIZE`` entries) so renamed or
    re-uploaded samples don't accumulate base64 strings indefinitely.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        cache: OrderedDict[str, _CacheEntry],
    ) -> None:
        self._hass = hass
        self._cache = cache

    async def resolve(self, media_content_id: str) -> str:
        """Resolve a media_content_id to a ``data:...;base64,...`` URI."""
        cached = self._cache.get(media_content_id)

        if cached is not None:
            cached_uri, cached_mtime, cached_path = cached
            current_mtime = await asyncio.to_thread(_safe_getmtime, cached_path)
            if current_mtime == cached_mtime:
                self._cache.move_to_end(media_content_id)
                return cached_uri

        try:
            resolved = await async_resolve_media(
                self._hass, media_content_id, target_media_player=None
            )
        except Exception as exc:
            raise VoiceSampleError(
                f"Cannot resolve voice sample: {media_content_id}"
            ) from exc

        path = getattr(resolved, "path", None) or getattr(resolved, "url", None)
        if not path:
            raise VoiceSampleError(
                f"Resolved media has no path or URL: {media_content_id}"
            )

        try:
            mtime, size, data = await asyncio.to_thread(_read_sample, path)
        except OSError as exc:
            raise VoiceSampleError(f"Sample file unavailable: {path}") from exc

        if size > MAX_SAMPLE_BYTES:
            raise VoiceSampleError(
                f"Voice sample exceeds {MAX_SAMPLE_BYTES // (1024 * 1024)} MB: {size} bytes"
            )

        mime = _guess_mime(path, data)
        if mime not in ALLOWED_SAMPLE_MIMES:
            raise VoiceSampleError(f"Unsupported sample mime: {mime}")

        b64 = base64.b64encode(data).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"
        self._cache[media_content_id] = (data_uri, mtime, str(path))
        self._cache.move_to_end(media_content_id)
        while len(self._cache) > VOICE_SAMPLE_CACHE_MAXSIZE:
            self._cache.popitem(last=False)
        return data_uri


def _safe_getmtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _read_sample(path: str | Path) -> tuple[float, int, bytes]:
    """Single-syscall stat + read; raises ``OSError`` if the file is gone."""
    p = Path(path)
    st = p.stat()
    return st.st_mtime, st.st_size, p.read_bytes()


def _guess_mime(path: str | Path, data: bytes) -> str:
    """Guess MIME from file extension and magic bytes."""
    lower = str(path).lower()
    if lower.endswith(".wav"):
        return "audio/wav"
    if (
        lower.endswith(".mp3")
        or data.startswith(b"\xff\xfb")
        or data.startswith(b"ID3")
    ):
        return "audio/mpeg"
    return "application/octet-stream"
