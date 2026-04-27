"""Tests for selector.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.xiaomi_mimo_tts.selector import (
    list_existing_samples,
    save_uploaded_sample,
)


@pytest.mark.asyncio
async def test_list_existing_returns_content_ids(mock_hass, tmp_path) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    (voice_dir / "alice.mp3").write_bytes(b"\xff\xfb")
    (voice_dir / "bob.wav").write_bytes(b"RIFF")
    (voice_dir / "ignored.txt").write_bytes(b"x")

    samples = await list_existing_samples(mock_hass, dir_path=str(voice_dir))
    ids = {s["value"] for s in samples}
    assert any("alice.mp3" in i for i in ids)
    assert any("bob.wav" in i for i in ids)
    assert not any("ignored.txt" in i for i in ids)


@pytest.mark.asyncio
async def test_save_uploaded_writes_file_with_uuid_name(mock_hass, tmp_path) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    fake_audio = b"\xff\xfb" + b"\x00" * 1024  # ~1KB mp3-magic
    upload_src = tmp_path / "upload_src.bin"
    upload_src.write_bytes(fake_audio)
    with patch(
        "custom_components.xiaomi_mimo_tts.selector.process_uploaded_file"
    ) as mock_process:
        mock_process.return_value.__enter__.return_value = upload_src
        result = await save_uploaded_sample(
            mock_hass,
            file_id="upload-id-1",
            mime="audio/mpeg",
            voice_samples_dir=str(voice_dir),
        )
    assert result.startswith("media-source://media_source/local/voice_samples/clone_")
    written = list(voice_dir.glob("clone_*.mp3"))
    assert len(written) == 1
    assert written[0].read_bytes() == fake_audio


@pytest.mark.asyncio
async def test_save_uploaded_rejects_oversize(mock_hass, tmp_path) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    huge = b"\xff\xfb" + b"\x00" * (11 * 1024 * 1024)  # > 10 MB
    upload_src = tmp_path / "upload_huge.bin"
    upload_src.write_bytes(huge)
    with patch(
        "custom_components.xiaomi_mimo_tts.selector.process_uploaded_file"
    ) as mock_process:
        mock_process.return_value.__enter__.return_value = upload_src
        with pytest.raises(ValueError):
            await save_uploaded_sample(
                mock_hass,
                file_id="upload-id-2",
                mime="audio/mpeg",
                voice_samples_dir=str(voice_dir),
            )


@pytest.mark.asyncio
async def test_save_uploaded_rejects_bad_mime(mock_hass, tmp_path) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    with pytest.raises(ValueError):
        await save_uploaded_sample(
            mock_hass,
            file_id="upload-id-3",
            mime="audio/flac",
            voice_samples_dir=str(voice_dir),
        )


@pytest.mark.asyncio
async def test_save_uploaded_with_custom_save_as(mock_hass, tmp_path) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    fake_audio = b"\xff\xfb" + b"\x00" * 16
    upload_src = tmp_path / "upload.bin"
    upload_src.write_bytes(fake_audio)
    with patch(
        "custom_components.xiaomi_mimo_tts.selector.process_uploaded_file"
    ) as mock_process:
        mock_process.return_value.__enter__.return_value = upload_src
        result = await save_uploaded_sample(
            mock_hass,
            file_id="upload-x",
            mime="audio/mpeg",
            voice_samples_dir=str(voice_dir),
            save_as="alice",
        )
    assert result.endswith("/alice.mp3")
    assert (voice_dir / "alice.mp3").read_bytes() == fake_audio


@pytest.mark.asyncio
async def test_save_uploaded_save_as_replaces_wrong_extension(
    mock_hass, tmp_path
) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    fake_audio = b"RIFF\x00\x00\x00\x00WAVE"
    upload_src = tmp_path / "upload.bin"
    upload_src.write_bytes(fake_audio)
    with patch(
        "custom_components.xiaomi_mimo_tts.selector.process_uploaded_file"
    ) as mock_process:
        mock_process.return_value.__enter__.return_value = upload_src
        # User typed alice.mp3 but mime says wav → must coerce to alice.wav
        result = await save_uploaded_sample(
            mock_hass,
            file_id="upload-y",
            mime="audio/wav",
            voice_samples_dir=str(voice_dir),
            save_as="alice.mp3",
        )
    assert result.endswith("/alice.wav")


@pytest.mark.asyncio
async def test_save_uploaded_save_as_rejects_path_traversal(
    mock_hass, tmp_path
) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    with (
        patch("custom_components.xiaomi_mimo_tts.selector.process_uploaded_file"),
        pytest.raises(ValueError),
    ):
        await save_uploaded_sample(
            mock_hass,
            file_id="upload-bad",
            mime="audio/mpeg",
            voice_samples_dir=str(voice_dir),
            save_as="../escape",
        )


@pytest.mark.asyncio
async def test_save_uploaded_save_as_rejects_existing(mock_hass, tmp_path) -> None:
    voice_dir = tmp_path / "voice_samples"
    voice_dir.mkdir()
    (voice_dir / "alice.mp3").write_bytes(b"existing")
    upload_src = tmp_path / "upload.bin"
    upload_src.write_bytes(b"\xff\xfb")
    with patch(
        "custom_components.xiaomi_mimo_tts.selector.process_uploaded_file"
    ) as mock_process:
        mock_process.return_value.__enter__.return_value = upload_src
        with pytest.raises(ValueError):
            await save_uploaded_sample(
                mock_hass,
                file_id="upload-collide",
                mime="audio/mpeg",
                voice_samples_dir=str(voice_dir),
                save_as="alice",
            )
