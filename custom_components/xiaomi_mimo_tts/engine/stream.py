"""Streaming TTS pipeline. Pure Python — no HA framework imports."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Final, Protocol

from sentence_stream import SentenceBoundaryDetector

from .models import VoiceConfig

SAMPLE_RATE: Final = 24_000
CHANNELS: Final = 1
BITS_PER_SAMPLE: Final = 16
SAMPLE_WIDTH_BYTES: Final = BITS_PER_SAMPLE // 8
BYTES_PER_SECOND: Final = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH_BYTES
WAV_HEADER_SIZE: Final = 44


class _StreamingClient(Protocol):
    def synthesize_stream(
        self, text: str, voice_config: VoiceConfig
    ) -> AsyncIterator[bytes]: ...


def _build_streaming_wav_header() -> bytes:
    block_align = CHANNELS * SAMPLE_WIDTH_BYTES
    return (
        b"RIFF"
        + (0xFFFFFFFF).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + CHANNELS.to_bytes(2, "little")
        + SAMPLE_RATE.to_bytes(4, "little")
        + BYTES_PER_SECOND.to_bytes(4, "little")
        + block_align.to_bytes(2, "little")
        + BITS_PER_SAMPLE.to_bytes(2, "little")
        + b"data"
        + (0xFFFFFFFF).to_bytes(4, "little")
    )


# 44-byte WAV header for streaming (sentinel sizes 0xFFFFFFFF for unknown length).
STREAMING_WAV_HEADER: Final[bytes] = _build_streaming_wav_header()


async def synthesize_text_stream(
    client: _StreamingClient,
    text_chunks: AsyncIterator[str],
    voice_config: VoiceConfig,
    schedule: tuple[int, ...] = (1, 3),
    on_batch: Callable[[int], None] | None = None,
) -> AsyncIterator[bytes]:
    """Yield PCM bytes for a streaming text input.

    Splits text into sentences using `sentence-stream` (CJK-aware), groups
    them into batches per `schedule` (e.g. [1, 3] then ALL), and calls the
    client's synthesize_stream once per batch. Output bytes are yielded in
    sentence order.

    ``on_batch`` is invoked with the sentence count of each batch right
    before its first byte is yielded — used by callers to track progress.
    """
    boundary = SentenceBoundaryDetector()
    sentences: list[str] = []
    sentences_ready = asyncio.Event()
    sentences_complete = False

    async def feed() -> None:
        nonlocal sentences_complete
        try:
            async for chunk in text_chunks:
                for s in boundary.add_chunk(chunk):
                    s = s.strip()
                    if s:
                        sentences.append(s)
                if sentences:
                    sentences_ready.set()
            tail = boundary.finish()
            if tail and tail.strip():
                sentences.append(tail.strip())
        finally:
            sentences_complete = True
            sentences_ready.set()

    feed_task = asyncio.create_task(feed(), name="mimo_sentence_feed")
    pending_schedule = list(schedule)
    try:
        while True:
            await sentences_ready.wait()
            if not sentences_complete:
                sentences_ready.clear()
            if not sentences:
                if sentences_complete:
                    break
                continue
            new = sentences[:]
            sentences.clear()
            while new:
                if pending_schedule:
                    n = pending_schedule.pop(0)
                    batch, new = new[:n], new[n:]
                else:
                    batch, new = new[:], []
                text = " ".join(batch).strip()
                if not text:
                    continue
                if on_batch is not None:
                    on_batch(len(batch))
                async for chunk in client.synthesize_stream(text, voice_config):
                    yield chunk
    finally:
        if not feed_task.done():
            feed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await feed_task
