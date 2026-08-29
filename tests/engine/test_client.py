"""Tests for engine.client.XiaomiMimoClient."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.xiaomi_mimo_tts.engine.client import XiaomiMimoClient
from custom_components.xiaomi_mimo_tts.engine.errors import (
    XiaomiMimoAuthError,
    XiaomiMimoConnectionError,
)

if TYPE_CHECKING:
    import pytest_mock


@pytest.mark.asyncio
async def test_validate_returns_available_models(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    mock_http.get(
        "https://api.xiaomimimo.com/v1/models",
        status=200,
        payload={
            "object": "list",
            "data": [
                {"id": "mimo-v2.5-tts", "object": "model", "owned_by": "xiaomi"},
                {
                    "id": "mimo-v2.5-tts-voicedesign",
                    "object": "model",
                    "owned_by": "xiaomi",
                },
                {
                    "id": "mimo-v2.5-tts-voiceclone",
                    "object": "model",
                    "owned_by": "xiaomi",
                },
                {"id": "mimo-v2-flash", "object": "model", "owned_by": "xiaomi"},
            ],
        },
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    result = await client.validate()
    assert result.all_models_available is True
    assert "mimo-v2.5-tts" in result.available_models
    assert "mimo-v2-flash" in result.available_models
    assert not result.missing_models


@pytest.mark.asyncio
async def test_validate_reports_missing_models(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    mock_http.get(
        "https://api.xiaomimimo.com/v1/models",
        status=200,
        payload={
            "object": "list",
            "data": [{"id": "mimo-v2.5-tts", "object": "model", "owned_by": "xiaomi"}],
        },
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    result = await client.validate()
    assert result.all_models_available is False
    assert "mimo-v2.5-tts-voicedesign" in result.missing_models
    assert "mimo-v2.5-tts-voiceclone" in result.missing_models


@pytest.mark.asyncio
async def test_validate_401_raises_auth_error(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    mock_http.get(
        "https://api.xiaomimimo.com/v1/models",
        status=401,
        payload={
            "error": {
                "message": "Invalid API Key",
                "code": "401",
                "type": "invalid_key",
            }
        },
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-bad")
    with pytest.raises(XiaomiMimoAuthError):
        await client.validate()


@pytest.mark.asyncio
async def test_validate_connection_error(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    mock_http.get(
        "https://api.xiaomimimo.com/v1/models",
        exception=aiohttp.ClientConnectionError("DNS failure"),
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    with pytest.raises(XiaomiMimoConnectionError):
        await client.validate()


@pytest.mark.asyncio
async def test_client_repr_redacts_api_key(
    aiohttp_session: aiohttp.ClientSession,
) -> None:
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-supersecret-1234567890")
    text = repr(client)
    assert "sk-supersecret" not in text
    assert "***" in text or "<redacted>" in text


# ---------------------------------------------------------------------------
# synthesize() tests
# ---------------------------------------------------------------------------

from custom_components.xiaomi_mimo_tts.engine.errors import (  # noqa: E402
    XiaomiMimoBadRequestError,
    XiaomiMimoQuotaExceededError,
    XiaomiMimoRateLimitError,
    XiaomiMimoServerError,
)
from custom_components.xiaomi_mimo_tts.engine.models import VoiceConfig  # noqa: E402
from tests.fixtures.mimo_responses import (  # noqa: E402
    make_pcm_bytes,
    make_wav_bytes,
    synth_sse_body,
)


def _mock_synth_ok(mock_http: aioresponses, pcm: bytes) -> None:
    """Queue one successful synthesis response (SSE, as synthesize() reads it)."""
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=200,
        body=synth_sse_body([pcm]),
        headers={"Content-Type": "text/event-stream"},
    )


@pytest.mark.asyncio
async def test_synthesize_built_in_returns_wav_bytes(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    _mock_synth_ok(mock_http, make_pcm_bytes())
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe", style="Cheerful")
    result = await client.synthesize("Hello", vc, audio_format="wav")
    # Byte-identical to what the stdlib wave module writes for the same PCM.
    assert result.audio_bytes == make_wav_bytes()
    assert result.audio_format == "wav"
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_synthesize_sends_correct_body(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    _mock_synth_ok(mock_http, make_pcm_bytes())
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe", style="Cheerful")
    await client.synthesize("Hello", vc, audio_format="wav")
    # Inspect last call
    last = list(mock_http.requests.items())[-1]
    request_kwargs = last[1][0].kwargs
    body = request_kwargs["json"]
    assert body["model"] == "mimo-v2.5-tts"
    assert body["audio"]["format"] == "pcm16"
    assert body["audio"]["voice"] == "Chloe"
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "Cheerful"
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][1]["content"] == "Hello"
    assert body["stream"] is True


@pytest.mark.asyncio
async def test_synthesize_design_omits_voice_field(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    _mock_synth_ok(mock_http, make_pcm_bytes())
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_design("Young male, warm")
    await client.synthesize("Hi.", vc)
    last = list(mock_http.requests.items())[-1]
    body = last[1][0].kwargs["json"]
    assert body["model"] == "mimo-v2.5-tts-voicedesign"
    assert "voice" not in body["audio"]
    assert body["messages"][0]["content"] == "Young male, warm"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,err_class",
    [
        (400, XiaomiMimoBadRequestError),
        (401, XiaomiMimoAuthError),
        (402, XiaomiMimoQuotaExceededError),
    ],
)
async def test_synthesize_status_to_error_class(
    aiohttp_session: aiohttp.ClientSession,
    mock_http: aioresponses,
    status: int,
    err_class: type[Exception],
) -> None:
    """Non-retried error codes: single mock is enough."""
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=status,
        payload={
            "error": {"message": f"http {status}", "code": str(status), "type": "x"}
        },
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    with pytest.raises(err_class):
        await client.synthesize("Hi", vc)


@pytest.mark.asyncio
async def test_synthesize_5xx_propagates_after_retry(
    aiohttp_session: aiohttp.ClientSession,
    mock_http: aioresponses,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """5xx retries once; if second attempt also fails, XiaomiMimoServerError propagates."""
    mocker.patch("asyncio.sleep")
    for _ in range(2):
        mock_http.post(
            "https://api.xiaomimimo.com/v1/chat/completions",
            status=500,
            payload={"error": {"message": "http 500", "code": "500", "type": "x"}},
        )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    with pytest.raises(XiaomiMimoServerError):
        await client.synthesize("Hi", vc)


@pytest.mark.asyncio
async def test_synthesize_429_carries_retry_after(
    aiohttp_session: aiohttp.ClientSession,
    mock_http: aioresponses,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """429 retries once; if second attempt also rate-limits, error propagates with retry_after."""
    mocker.patch("asyncio.sleep")
    for _ in range(2):
        mock_http.post(
            "https://api.xiaomimimo.com/v1/chat/completions",
            status=429,
            payload={"error": {"message": "rate limited", "code": "429", "type": "x"}},
            headers={"Retry-After": "3"},
        )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    with pytest.raises(XiaomiMimoRateLimitError) as exc_info:
        await client.synthesize("Hi", vc)
    assert exc_info.value.retry_after == 3.0


@pytest.mark.asyncio
async def test_synthesize_retries_429_once_with_retry_after(
    aiohttp_session: aiohttp.ClientSession,
    mock_http: aioresponses,
    mocker: pytest_mock.MockerFixture,
) -> None:
    """First call: 429 with Retry-After: 1 → wait → second call: 200."""
    mocker.patch("asyncio.sleep")
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=429,
        payload={"error": {"message": "rate", "code": "429", "type": "x"}},
        headers={"Retry-After": "1"},
    )
    _mock_synth_ok(mock_http, make_pcm_bytes())
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    result = await client.synthesize("Hi", vc)
    assert result.audio_bytes == make_wav_bytes()


@pytest.mark.asyncio
async def test_synthesize_retries_5xx_once(
    aiohttp_session: aiohttp.ClientSession,
    mock_http: aioresponses,
    mocker: pytest_mock.MockerFixture,
) -> None:
    mocker.patch("asyncio.sleep")
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=503,
        payload={"error": {"message": "down", "code": "503", "type": "x"}},
    )
    _mock_synth_ok(mock_http, make_pcm_bytes())
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    result = await client.synthesize("Hi", vc)
    assert result.audio_bytes == make_wav_bytes()


@pytest.mark.asyncio
async def test_synthesize_does_not_retry_401(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    """401 must NOT retry — it surfaces to ConfigEntryAuthFailed."""
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=401,
        payload={"error": {"message": "bad key", "code": "401", "type": "invalid_key"}},
    )
    # If retry were on, mock_http would need a second call queued. Single is enough.
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-bad")
    vc = VoiceConfig.for_built_in("Chloe")
    with pytest.raises(XiaomiMimoAuthError):
        await client.synthesize("Hi", vc)


@pytest.mark.asyncio
async def test_synthesize_does_not_retry_400(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=400,
        payload={"error": {"message": "text too long", "code": "400", "type": "x"}},
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    with pytest.raises(XiaomiMimoBadRequestError):
        await client.synthesize("Hi", vc)


# ---------------------------------------------------------------------------
# synthesize_stream() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_stream_yields_pcm_bytes(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    pcm_chunks = [b"\x01\x02" * 100, b"\x03\x04" * 100]
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=200,
        body=synth_sse_body(pcm_chunks),
        headers={"Content-Type": "text/event-stream"},
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    out: list[bytes] = []
    async for chunk in client.synthesize_stream("Hello", vc):
        out.append(chunk)
    assert b"".join(out) == b"".join(pcm_chunks)


@pytest.mark.asyncio
async def test_synthesize_stream_does_not_retry(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=503,
        payload={"error": {"message": "down", "code": "503", "type": "x"}},
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    vc = VoiceConfig.for_built_in("Chloe")
    with pytest.raises(XiaomiMimoServerError):
        async for _ in client.synthesize_stream("Hi", vc):
            pass


@pytest.mark.asyncio
async def test_synthesize_pcm16_returns_bare_pcm(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    """pcm16 callers get the raw payload with no RIFF header prepended."""
    pcm = make_pcm_bytes(0.1)
    _mock_synth_ok(mock_http, pcm)
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    result = await client.synthesize(
        "Hi", VoiceConfig.for_built_in("Chloe"), audio_format="pcm16"
    )
    assert result.audio_bytes == pcm
    assert result.audio_format == "pcm16"


@pytest.mark.asyncio
async def test_synthesize_stream_reassembles_across_read_chunks(
    aiohttp_session: aiohttp.ClientSession, mock_http: aioresponses
) -> None:
    """Events must survive separators that straddle a 64 KiB read boundary."""
    # Sizes chosen so the "\n\n" separators land at varied offsets well past
    # the first read chunk, including inside one.
    pcm_chunks = [bytes([i % 251]) * (40_000 + i * 997) for i in range(6)]
    mock_http.post(
        "https://api.xiaomimimo.com/v1/chat/completions",
        status=200,
        body=synth_sse_body(pcm_chunks),
        headers={"Content-Type": "text/event-stream"},
    )
    client = XiaomiMimoClient(aiohttp_session, api_key="sk-test")
    out = [
        chunk
        async for chunk in client.synthesize_stream(
            "Hi", VoiceConfig.for_built_in("Chloe")
        )
    ]
    assert out == pcm_chunks
