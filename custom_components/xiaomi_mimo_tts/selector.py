"""Helpers for voice-sample picker + uploader."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import uuid
from pathlib import Path

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.core import HomeAssistant

from .const import (
    ALLOWED_SAMPLE_MIMES,
    DEFAULT_VOICE_SAMPLES_DIR,
    MAX_SAMPLE_BYTES,
)

VOICE_SAMPLES_MEDIA_PREFIX = "media-source://media_source/local/voice_samples/"

# Reject path separators, control chars, and parent-dir traversal in filenames.
_FILENAME_INVALID_RE = re.compile(r"[\x00-\x1f/\\:]")


def _sanitize_filename(name: str, *, ext: str) -> str:
    """Return a safe basename ending with ``ext`` (e.g. ``.wav``).

    - Rejects path separators, control chars, and parent-dir traversal.
    - Rejects empty result and ``.`` / leading ``..`` patterns.
    - Appends ``ext`` if missing; replaces wrong extension with ``ext``.
    """
    name = name.strip()
    if not name:
        raise ValueError("filename is empty")
    if name == "." or name.startswith(".."):
        raise ValueError(f"invalid filename: {name!r}")
    if _FILENAME_INVALID_RE.search(name):
        raise ValueError(f"invalid characters in filename: {name!r}")
    base = Path(name).stem
    if not base:
        raise ValueError(f"invalid filename: {name!r}")
    return f"{base}{ext}"


def _list_audio_files(dir_path: str) -> list[str]:
    """Sync helper for thread off-load: return sorted mp3/wav filenames."""
    if not os.path.isdir(dir_path):
        return []
    return [
        entry
        for entry in sorted(os.listdir(dir_path))
        if entry.lower().endswith((".mp3", ".wav"))
    ]


async def list_existing_samples(
    hass: HomeAssistant,
    *,
    dir_path: str = DEFAULT_VOICE_SAMPLES_DIR,
) -> list[dict[str, str]]:
    """Return [{label, value}] of mp3/wav files under dir_path.

    `value` is a media_content_id consumable by VoiceSampleResolver.
    """
    entries = await asyncio.to_thread(_list_audio_files, dir_path)
    return [
        {"label": entry, "value": f"{VOICE_SAMPLES_MEDIA_PREFIX}{entry}"}
        for entry in entries
    ]


def _process_uploaded_to_target(
    hass: HomeAssistant,
    file_id: str,
    target: Path,
    max_bytes: int,
) -> None:
    """Validate upload size via stat then atomically copy to target.

    Uses ``shutil.copy2`` instead of read-into-bytes to avoid materialising
    multi-MB uploads in Python memory. ``O_EXCL`` create defends against
    concurrent uploads racing to the same filename.
    """
    with process_uploaded_file(hass, file_id) as src_path:
        src = Path(src_path)
        if src.stat().st_size > max_bytes:
            raise ValueError(f"Sample exceeds {max_bytes // (1024 * 1024)} MB")
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise ValueError(f"file exists: {target.name}") from exc
        with os.fdopen(fd, "wb") as dst, src.open("rb") as src_fp:
            shutil.copyfileobj(src_fp, dst, length=64 * 1024)


async def save_uploaded_sample(
    hass: HomeAssistant,
    *,
    file_id: str,
    mime: str,
    voice_samples_dir: str = DEFAULT_VOICE_SAMPLES_DIR,
    save_as: str | None = None,
) -> str:
    """Persist an uploaded file into voice_samples_dir.

    Args:
        hass: HA instance.
        file_id: HA file_upload temp id.
        mime: Allowed MIME (audio/mpeg or audio/wav).
        voice_samples_dir: Target directory for the saved file.
        save_as: Optional user-supplied filename (without or with extension).
            Empty/None falls back to ``clone_<uuid>.<ext>``.

    Returns:
        media_content_id pointing at the persisted file.

    Raises:
        ValueError: bad mime, invalid filename, file already exists, or upload
            exceeds MAX_SAMPLE_BYTES.
    """
    if mime not in ALLOWED_SAMPLE_MIMES:
        raise ValueError(f"Unsupported sample mime: {mime}")

    ext = ".mp3" if mime == "audio/mpeg" else ".wav"
    if save_as:
        filename = _sanitize_filename(save_as, ext=ext)
    else:
        filename = f"clone_{uuid.uuid4().hex[:8]}{ext}"
    target = Path(voice_samples_dir) / filename
    await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(
        _process_uploaded_to_target, hass, file_id, target, MAX_SAMPLE_BYTES
    )
    return f"{VOICE_SAMPLES_MEDIA_PREFIX}{filename}"
