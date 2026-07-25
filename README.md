# Xiaomi MiMo TTS for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/hass-cortex/xiaomi-mimo-tts)](https://github.com/hass-cortex/xiaomi-mimo-tts/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-blue.svg)](https://hacs.xyz/)
[![HA Version](https://img.shields.io/badge/HA-2026.3.0+-green.svg)](https://www.home-assistant.io/)
[![GitHub License](https://img.shields.io/github/license/hass-cortex/xiaomi-mimo-tts)](https://github.com/hass-cortex/xiaomi-mimo-tts/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/hass-cortex/xiaomi-mimo-tts)

A Home Assistant custom integration providing cloud-based text-to-speech via the [Xiaomi MiMo TTS v2.5 API](https://platform.xiaomimimo.com), with built-in voices, natural-language voice design, and voice cloning from audio samples.

```
Text ──► Sentence Pipeline ──► Xiaomi MiMo API ──► Streaming Audio
              │                    ▲
              │                    │
       schedule [1, 3, ALL]    voice profile
       (CJK + ASCII boundaries)
```

Replies start playing as soon as the first sentence is synthesised; subsequent batches stream in while the previous batch plays, dramatically reducing perceived TTFT for Assist Pipeline.

## Features

- **Three voice profile types** — built-in voices, voice design (text-described), and voice cloning (mp3/wav samples)
- **Streaming TTS pipeline** — CJK-aware sentence detection + `[1, 3, ALL]` batch schedule reduces TTFT from ~30s to ~5s on long replies
- **15 diagnostic sensors per profile** — request counts, durations, audio size/seconds, TTFT, sentence count, last text
- **Media Browser-managed samples** — voice clone samples live under `/media/voice_samples/`, reusable across multiple profiles
- **Platinum quality scale** — config flow, runtime data, reauth, reconfigure, repair issues, diagnostics with redaction

## Getting Started

**Prerequisites:** Home Assistant **2026.3.0+** and a [Xiaomi MiMo platform account](https://platform.xiaomimimo.com) with v2.5 API access.

### 1. Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hass-cortex&repository=xiaomi-mimo-tts&category=integration)

Click the button above, or manually: HACS > three-dot menu > **Custom repositories** > add `https://github.com/hass-cortex/xiaomi-mimo-tts` (Integration) > install > restart HA.

<details>
<summary>Manual installation</summary>

Copy `custom_components/xiaomi_mimo_tts/` to your HA `config/custom_components/` directory, then restart.

</details>

### 2. Get Xiaomi MiMo API Key

1. Sign up at the [Xiaomi MiMo Platform](https://platform.xiaomimimo.com)
2. Navigate to **Console > API Keys**
3. Create a new key (format `sk-...`) and copy it

### 3. Add Integration

[![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=xiaomi_mimo_tts)

Click the button above, or manually: **Settings > Devices & Services > Add Integration** > search "Xiaomi MiMo TTS".

Enter your **API key**. The integration validates against `GET /v1/models` (free, no inference) before completing setup.

### 4. Add a Voice Profile

After the integration is created, click **Add built-in voice**, **Add designed voice**, or **Add cloned voice** on the integration card. Each subentry creates one TTS entity + a device with 15 sensors.

| Type                   | What it does                                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Built-in**     | Pick from `Chloe`, `Mia`, `Milo`, `Dean`, `冰糖`, `茉莉`, `苏打`, `白桦`, or `mimo_default` |
| **Voice design** | Describe the voice in natural language (e.g. "young female,*Taiwanese accent*, warm tone")                  |
| **Voice clone**  | Upload an mp3/wav sample (≤10 MB) or pick an existing one from `/media/voice_samples/`                     |

### 5. Assign to Voice Pipeline

[![Open your Home Assistant instance and manage your voice assistants.](https://my.home-assistant.io/badges/voice_assistants.svg)](https://my.home-assistant.io/redirect/voice_assistants/)

Select or create a voice pipeline, then set **Text-to-speech** to your Xiaomi MiMo TTS profile. Streaming kicks in automatically for multi-sentence assistant replies.

### Configuration Options

[![Open your Home Assistant instance and show this integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=xiaomi_mimo_tts)

Configure via the integration page > **Configure**:

- **Request timeout** -- per-call timeout in seconds (default 60)
- **Streaming enabled** -- master switch for the streaming pipeline (default on)
- **Voice samples directory** -- where uploaded clone samples are persisted (default `/media/voice_samples`)
- **Default audio format** -- `wav` or `pcm16` (default `wav`)

Each voice profile can be reconfigured independently from its three-dot menu (rename, switch voice, replace sample).

### Uninstallation

**Settings > Devices & Services** > Xiaomi MiMo TTS > three-dot menu > **Delete** > remove `custom_components/xiaomi_mimo_tts/` > restart HA. Voice sample files under `/media/voice_samples/` are not removed automatically.

## Debugging

Enable debug logging to see synthesis details and SSE chunks:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.xiaomi_mimo_tts: debug
```

## FAQ

**Why does the audio still take ~5 seconds before playing?**

Xiaomi MiMo v2.5 streaming is currently in **compatibility mode** — each batch's full inference completes before chunks dump. Real per-call low-latency streaming is announced but not yet live. The integration's sentence pipeline still helps long replies: while batch 1 plays, batch 2 is being synthesised in parallel.

**The TTS cache is masking my new voice settings.**

HA caches TTS audio by `(message, language, options)`. Reconfiguring a profile doesn't invalidate the cache. Either change the message slightly, pass `cache: false` on the call, or run `tts.clear_cache`.

**Where do voice clone samples live?**

`/media/voice_samples/`. Files uploaded through the config flow land there with auto-named `clone_<uuid>.{mp3,wav}` (or your chosen filename). They appear in HA's Media Browser and can be reused across multiple voice clone profiles.

**Can I configure multiple Xiaomi MiMo accounts?**

Yes. Add the integration multiple times with different API keys. Each instance has independent voice profiles, sensors, and quotas. Config entries deduplicate by hashed API key, so the same key cannot be configured twice.

**How do I track Xiaomi MiMo quota usage?**

The **Total audio minutes** and **Total characters synthesized** sensors track cumulative usage per profile. The full set of 15 sensors covers request counts, durations, last text, TTFT, sentence count, and last result enum.

**How do I install the latest development version?**

After the integration is installed via HACS, switch to the latest `main` branch using the `update.install` action:

1. Go to **Developer Tools > Actions**
2. Select the `update.install` action
3. In **Target**, select the Xiaomi MiMo TTS update entity (e.g., `update.xiaomi_mimo_tts_update`)
4. In **Version**, enter `main` (or a specific commit hash)
5. Click **Perform Action**
6. Restart HA

To revert, run the same action with a release tag (e.g., `0.1.0`).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

[MIT](LICENSE)
