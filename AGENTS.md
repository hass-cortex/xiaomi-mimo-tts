# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Overview

Home Assistant custom integration for **Xiaomi MiMo TTS v2.5** (text-to-speech) with three voice profile types — built-in voices, natural-language voice design, and audio-sample voice cloning — plus a streaming pipeline that improves perceived TTFT for HA Assist Pipeline.

## Tech Stack

- **Runtime**: Python 3.14+, aiohttp, sentence-stream
- **Package manager**: `uv` (not pip)
- **Testing**: pytest, pytest-asyncio (asyncio_mode = "auto"), pytest-cov, aioresponses
- **Linting**: ruff (lint + format)
- **Type checking**: pyright (standard mode; `reportMissingImports = "none"` — `homeassistant` is not installed)
- **Version management**: commitizen (`cz bump`)
- **CI**: GitHub Actions (ruff, pytest, pyright, hassfest, HACS validation, uv lock check)

## Architecture

The integration is split into a **HA-decoupled engine** (`engine/`) and a **HA shell** around it. Boundary contract: `engine/` may not import `homeassistant.*`. This lets the engine be unit-tested without `sys.modules` mocking and reused by future tools (CLI, MCP server) without dragging the HA shell along.

```
custom_components/xiaomi_mimo_tts/
│  HA-DECOUPLED CORE  (stdlib + aiohttp + sentence-stream only)
├── engine/
│   ├── __init__.py
│   ├── client.py            # XiaomiMimoClient — aiohttp-based Xiaomi MiMo API client
│   ├── models.py            # VoiceConfig, ValidationResult, SynthesisResult, TTSCallStats
│   ├── errors.py            # XiaomiMimoError tree (extends Exception, NOT HomeAssistantError)
│   └── stream.py            # make_streaming_wav_header + sentence pipeline
│
│  HA-INTEGRATION SHELL  (imports engine + homeassistant.*)
├── __init__.py              # async_setup_entry / async_unload_entry / update_listener
├── manifest.json            # quality_scale: platinum
├── const.py                 # CONF_*, DOMAIN, BUILT_IN_VOICES, MAX_SAMPLE_BYTES
├── runtime.py               # XiaomiMimoTTSRuntimeData (client + cache + sensors registry)
├── tts.py                   # XiaomiMimoTTSEntity — non-streaming + streaming + stats push
├── voice_sample.py          # VoiceSampleResolver — resolve media_content_id → base64
├── selector.py              # list_existing_samples + save_uploaded_sample helpers
├── sensor.py                # 15 SensorEntityDescriptions + RestoreSensor subclass
├── config_flow.py           # ConfigFlow + 3 SubentryFlows + Reauth + Reconfigure + Options
├── repairs.py               # 4 issue helpers (sample missing, model unavailable, quota, dir)
├── diagnostics.py           # async_get_config_entry_diagnostics with redaction
├── icons.json
├── strings.json             # UI strings (source of truth)
├── translations/
│   ├── en.json              # ≡ strings.json byte-identical
│   └── zh-Hant.json
└── quality_scale.yaml       # Platinum compliance matrix
```

### Key Design Patterns

- **Engine boundary**: `engine/` is pure Python — `XiaomiMimoClient` accepts `aiohttp.ClientSession` via constructor (Dependency Inversion). HA shell passes `async_get_clientsession(hass)`; engine tests pass an `aioresponses`-mocked session.
- **Error translation at boundary**: `engine/errors.py` defines `XiaomiMimoError` (subclass of `Exception`). The HA shell (`tts.py`) catches `XiaomiMimoAuthError` → `ConfigEntryAuthFailed` (and triggers `entry.async_start_reauth(hass)`); other `XiaomiMimoError` → `HomeAssistantError`.
- **Subentry-per-voice-profile**: 1 config entry = 1 API key. Each subentry (`built_in` / `voice_design` / `voice_clone`) maps to one Xiaomi MiMo model and produces one HA device + 1 TTS entity + 15 sensors.
- **Voice sample storage**: clones live in `/media/voice_samples/`. Subentries store only a `media_content_id` (small). `VoiceSampleResolver` resolves on demand with mtime-based caching keyed by content_id; the resolver instance is cached on the entity to avoid per-call allocation.
- **Streaming pipeline**: `engine/stream.py::synthesize_text_stream` reads an `AsyncIterator[str]` (HA `request.message_gen`), uses `sentence-stream` for CJK + ASCII boundary detection, batches per `[1, 3, ALL]` schedule (mirror ElevenLabs), and yields PCM bytes. The shell `tts.py::_stream` prepends a streaming WAV header (sentinel `0xFFFFFFFF` length) and counts emitted PCM bytes for `TTSCallStats.audio_seconds`.
- **Sensor push updates**: `XiaomiMimoTTSEntity._push_stats(TTSCallStats)` fires after each call (success or failure). Sensors are `RestoreSensor` (state persists across HA restarts) and self-register in `runtime_data.sensors_by_subentry` on `async_added_to_hass`.

## Development Commands

```bash
uv sync                                    # Install all deps
uv run pytest tests/ -v                    # Run all tests (engine + unit)
uv run pytest tests/engine/ -v             # Pure engine tests (no HA mocking)
uv run pytest tests/unit/ -v               # HA-mocked shell tests
uv run pytest tests/ --cov=custom_components --cov-report=term-missing
uv run ruff check .                        # Lint
uv run ruff format .                       # Format
uv run pyright                             # Type check (excludes tests/)
uv run cz bump --prerelease beta           # Version bump for beta release
```

## Testing

- **`tests/engine/`** — pure tests against the HA-decoupled engine. `tests/engine/conftest.py` adds `aiohttp_session` + `aioresponses` fixtures only; no HA mocking.
- **`tests/unit/`** — HA-mocked tests for shell modules. `tests/conftest.py` (root) injects mock `homeassistant.*` into `sys.modules` before any test imports.
- **`tests/integration/test_real_api.py`** — gated on `MIMO_API_KEY` env var; calls real Xiaomi MiMo API. Skipped in CI.
- Coverage threshold: 70% (`fail_under` in pyproject.toml). Current actual: ~82%.

## Conventions

- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `perf:`, `ci:`, `build:`, `style:`, `revert:`). Enforced by commitizen `commit-msg` hook. Breaking changes use `feat!:` or `BREAKING CHANGE:` footer.
- **Versioning**: Semver. `major_version_zero = true` — breaking changes bump MINOR during 0.x, not MAJOR. Pre-release uses PEP 440 format (`0.2.0b1`), not semver hyphen format (`0.2.0-beta.1`).
- **Release notes**: Auto-generated by GitHub when `release.yml` creates a release. No `CHANGELOG.md` maintained.
- **Releasing**: `cz bump` locally (updates `pyproject.toml` + `manifest.json`, creates commit + tag), sync `uv.lock`, push with `--follow-tags`. GitHub Actions creates the release automatically. See [Release Workflow](#release-workflow) for full steps.
- **Docstrings**: Google-style with Args/Returns/Raises sections.
- **Type annotations**: required on all public functions. Use `TYPE_CHECKING` guard for HA imports (engine never imports HA at all).
- **Error handling**: engine errors extend `Exception`. The HA shell translates them at the boundary (`tts.py`). Non-streaming `synthesize` retries once on 429/5xx/connection errors; streaming `synthesize_stream` does NOT retry (would corrupt yielded byte order).
- **Translations**: `strings.json` is source of truth. `translations/en.json` must be kept in sync (byte-identical). When modifying schemas, also update both translation files for any new field labels.

## Known Issues

- `homeassistant` is not installed as a dependency (it's mocked in tests), so pyright is configured with `reportMissingImports = "none"` and `reportMissingTypeStubs = "none"`. IDE setups (e.g. Pylance) may surface those import warnings locally; suppress per-workspace if noisy.
- Xiaomi MiMo v2.5 streaming is in **compatibility mode** — each batch's full inference completes before SSE chunks dump. Real per-call low-latency streaming is announced but not yet live. The integration's sentence pipeline still helps long replies (next batch synthesises while current plays).

## Quality Scale

This integration targets **Platinum** HA Integration Quality Scale. `quality_scale.yaml` documents per-rule status. Summary:

- **Bronze** (18/18): config-flow, runtime-data, unique-config-entry, test-before-configure, test-before-setup, has-entity-name, entity-unique-id, entity-event-setup, dependency-transparency, etc.
- **Silver** (10/10): config-entry-unloading, reauthentication-flow, parallel-updates, entity-unavailable, action-exceptions, log-when-unavailable, test-coverage (≥70%), etc.
- **Gold** (19/21): devices, entity-category, entity-translations, exception-translations, icon-translations, reconfiguration-flow, repair-issues, diagnostics, dynamic-devices, stale-devices. **N/A**: discovery, discovery-update-info (cloud API).
- **Platinum** (3/3): async-dependency, inject-websession, strict-typing.

## Release & Distribution

### Version Files

Version is tracked in two places, kept in sync by commitizen (`cz bump`):

| File | Field |
|------|-------|
| `pyproject.toml` | `[project] version` and `[tool.commitizen] version` |
| `custom_components/xiaomi_mimo_tts/manifest.json` | `version` |

### HACS Configuration

`hacs.json`:
- `name` — display name in HACS UI
- `homeassistant` — minimum HA version (currently `2026.3.0`, required for Python 3.14+)
- `render_readme` — show README.md directly in HACS detail page (no separate `info.md`)

### HACS Version Selection Logic

HACS determines which version to show users based on this priority:

1. `show_beta=true` and prerelease exists → display prerelease tag
2. Stable release exists → display latest stable tag
3. No releases at all → display default branch `last_commit`

Users can always manually select a specific version (including main branch) via HACS download dialog → "Need a different version?"

### Distribution Channels

| Channel | GitHub Release | HACS Behaviour |
|---------|---------------|----------------|
| **Stable** | Release (`prerelease: false`) | Shown to all users by default |
| **Beta** | Pre-release (`prerelease: true`) | Only shown when user enables "Pre-release" switch entity per repository |
| **Dev (main)** | No release needed | Available via "Need a different version?" in download dialog |

### Release Workflow

Local bump + push triggers GitHub Actions to create the release automatically.

```bash
# Bump version (commitizen reads conventional commits to determine increment)
uv run cz bump                    # auto-detect: feat→minor, fix→patch
uv run cz bump --increment minor  # force minor
uv run cz bump --prerelease beta  # beta release (e.g., 0.3.0b1)

# Push (triggers release.yml)
git push origin main --follow-tags
```

`cz bump` automatically: updates version in `pyproject.toml` + `manifest.json`, syncs `uv.lock` (via `pre_bump_hooks`), creates commit + annotated tag.

GitHub Actions (`release.yml`) then:
1. Validates (ruff, pytest, pyright, hassfest)
2. Verifies tag == pyproject.toml == manifest.json
3. Generates release notes from conventional commits
4. Packages `xiaomi_mimo_tts.zip`
5. Creates GitHub Release (prerelease auto-detected from tag)

### Version Naming

HACS uses `AwesomeVersion` for comparison. Tag format follows commitizen's `tag_format = "$version"` (no `v` prefix):

| Type | Tag Example | manifest.json version |
|------|------------|----------------------|
| Stable | `1.0.0` | `1.0.0` |
| Beta | `1.1.0b1` | `1.1.0b1` |

HACS only checks GitHub's `prerelease` boolean flag — tag naming does not affect channel routing.

## Do NOT

- Import `homeassistant.*` from anything under `engine/` — boundary contract violation. Engine errors must extend `Exception`, never `HomeAssistantError`.
- Create `aiohttp.ClientSession` in the HA shell — use `async_get_clientsession(hass)` and inject into `XiaomiMimoClient`.
- Add `homeassistant` as a dependency in `pyproject.toml` — it's mocked in tests.
- Modify `translations/en.json` without updating `strings.json` (or vice versa). They must stay byte-identical.
- Log Xiaomi MiMo API response bodies for auth errors (401/403) — security risk. The `api_key` must also be redacted in `XiaomiMimoClient.__repr__` and in `diagnostics.py`.
- Use `vol.Optional(key, default=X)` to pre-fill reconfigure forms for fields users may want to clear. `default=` falls back to `X` when HA frontend omits the empty key, silently restoring the old value. Use `description={"suggested_value": X}` instead.
- `await` `async_update_reload_and_abort` or `async_update_and_abort` — they are `@callback` synchronous methods that return result dicts.
- Retry streaming calls — `synthesize_stream` cannot be replayed mid-stream without restarting audio. Only `synthesize` (non-streaming) retries.
