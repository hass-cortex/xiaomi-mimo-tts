# Contributing to Xiaomi MiMo TTS

Thank you for considering contributing to this project. This guide covers the development setup, testing, and submission process.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- A Home Assistant instance (for integration testing)

## Development Setup

```bash
git clone https://github.com/hass-cortex/xiaomi-mimo-tts.git
cd xiaomi-mimo-tts
uv sync --group dev --group test
```

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage report
uv run pytest tests/ --cov=custom_components --cov-report=term-missing

# Run a specific test file
uv run pytest tests/engine/test_client.py -v
```

## Code Style

This project enforces consistent code style via automated tooling:

- **Linting**: `uv run ruff check .`
- **Formatting**: `uv run ruff format .`
- **Type checking**: `uv run pyright`
- Follow Google-style docstrings for all public functions and classes

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use case |
|--------|----------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `chore:` | Maintenance / tooling |
| `refactor:` | Code restructure without behavior change |
| `test:` | Adding or updating tests |

Example: `feat: add support for voice design style preview`

## Submitting Changes

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes with appropriate tests
4. Ensure all checks pass (`ruff check`, `ruff format --check`, `pytest`)
5. Submit a pull request with a clear description of the change

## Project Structure

The codebase follows a strict **engine / HA-shell split**:

- `engine/` — HA-decoupled core (no `homeassistant.*` imports). Covers the Xiaomi MiMo API client, voice models, audio format facts, and error hierarchy. Testable with plain pytest — no `sys.modules` mocking needed.
- HA-shell — the surrounding integration files (`tts.py`, `sensor.py`, `config_flow.py`, etc.) that wire the engine into Home Assistant.

```
xiaomi-mimo-tts/
  custom_components/xiaomi_mimo_tts/
    engine/
      client.py          # XiaomiMimoClient (aiohttp session injected via constructor)
      models.py          # VoiceConfig, SynthesisResult, TTSCallStats — pure dataclasses
      errors.py          # XiaomiMimoError hierarchy (plain Exception — no HA coupling)
      audio.py           # PCM16/24kHz facts + build_wav_header
    __init__.py          # Integration setup: async_setup_entry / async_unload_entry
    tts.py               # XiaomiMimoTTSEntity — translates engine errors to HA exceptions
    sensor.py            # 14 diagnostic sensors per voice profile (RestoreSensor)
    runtime.py           # XiaomiMimoTTSRuntimeData dataclass (HA refs + engine client)
    config_flow.py       # Config, subentry (built_in/voice_design/voice_clone), reauth, reconfigure flows
    voice_sample.py      # Resolve media_content_id → base64 via HA media_source
    selector.py          # FileSelector + voice_samples dir listing
    repairs.py           # Repair issue definitions
    diagnostics.py       # Redact api_key + voice_sample base64
    const.py             # Constants (CONF_*, DOMAIN, defaults)
  tests/
    engine/              # Pure engine tests — no HA mocking
    unit/                # HA-coupled tests — sys.modules mock
  pyproject.toml         # Project metadata and tool config
```

## Reporting Issues

Please use GitHub Issues with the provided templates. Include:

- Home Assistant version
- Integration version
- Steps to reproduce
- Expected vs actual behavior
- Relevant debug logs (see README for how to enable debug logging)
