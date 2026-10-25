# Xiaomi MiMo TTS for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/hass-cortex/xiaomi-mimo-tts)](https://github.com/hass-cortex/xiaomi-mimo-tts/releases)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://hacs.xyz/)
[![HA Version](https://img.shields.io/badge/HA-2026.3.0+-green.svg)](https://www.home-assistant.io/)
[![GitHub License](https://img.shields.io/github/license/hass-cortex/xiaomi-mimo-tts)](https://github.com/hass-cortex/xiaomi-mimo-tts/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/hass-cortex/xiaomi-mimo-tts)

A Home Assistant custom integration providing cloud-based text-to-speech via the [Xiaomi MiMo TTS v2.5 API](https://platform.xiaomimimo.com), with built-in voices, natural-language voice design, and voice cloning from audio samples.

```
Reply text ──► Xiaomi MiMo API ──► Audio ──► Media player
   (whole)          ▲          (streamed on built-in voices)
                  voice
```

## Features

- **One engine, every voice** — the built-in voices and your own voice profiles (text-described designs, mp3/wav clones, styled built-in voices) are all voices of one TTS entity, picked per call
- **Streaming audio output** — built-in voices start playing on the first chunk, so the wait does not grow with the length of the reply
- **Diagnostic sensors** — request counts, durations, audio size/seconds, time to first audio, last text and voice, for the whole account and per profile
- **Media Browser-managed samples** — pick or upload voice clone samples from the Media Browser, and reuse one sample across profiles
- **Platinum quality scale** — config flow, runtime data, reauth, reconfigure, repair issues, diagnostics with redaction

## Getting Started

**Prerequisites:** Home Assistant **2026.3.0+** and a [Xiaomi MiMo platform account](https://platform.xiaomimimo.com) with v2.5 API access.

### 1. Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hass-cortex&repository=xiaomi-mimo-tts&category=integration)

Click the button above, or manually: **HACS** > search "Xiaomi MiMo TTS" > **Download** > restart HA.

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

The integration creates one TTS entity, whose voices are the built-in ones (`Chloe`, `Mia`, `Milo`, `Dean`, `冰糖`, `茉莉`, `苏打`, `白桦`, `mimo_default`) and every voice profile you add. Click **Add built-in voice**, **Add designed voice**, or **Add cloned voice** on the integration card to add one; each profile gets a device with 14 diagnostic sensors that count the calls its voice spoke, plus a Voice sensor for built-in and clone profiles. A profile's name is how the voice picker shows it: left blank, a built-in profile goes by its voice and a cloned one by its sample's file name.

| Type                   | What it does                                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Built-in**     | A built-in voice with a default style prompt                                                               |
| **Voice design** | Describe the voice in natural language (e.g. "young female, Taiwanese accent, warm tone")                  |
| **Voice clone**  | Upload an mp3/wav sample (≤10 MB) or pick an existing one from your samples directory                     |

A pipeline, a `tts.speak` call or a voice satellite picks the voice per call: a built-in voice by name (`options: {voice: 茉莉}`), a profile by its title in the voice picker or by its subentry ID in `options`. A call that names no voice gets the **Default voice** option.

### 5. Assign to Voice Pipeline

[![Open your Home Assistant instance and manage your voice assistants.](https://my.home-assistant.io/badges/voice_assistants.svg)](https://my.home-assistant.io/redirect/voice_assistants/)

Select or create a voice pipeline, set **Text-to-speech** to Xiaomi MiMo TTS and pick its voice.

### Configuration Options

[![Open your Home Assistant instance and show this integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=xiaomi_mimo_tts)

Configure via the integration page > **Configure**:

- **Default voice** -- the voice of a call that names none (default `mimo_default`)
- **Request timeout** -- per-call timeout in seconds (default 60)
- **Streaming enabled** -- stream audio out as it is inferred (default on). Only built-in voices stream; designed and cloned voices arrive in one piece either way.
- **Voice samples directory** -- where uploaded clone samples are persisted (default `/media/voice_samples`)

Each voice profile can be reconfigured independently from its three-dot menu (rename, switch voice, replace sample).

### Uninstallation

**Settings > Devices & Services** > Xiaomi MiMo TTS > three-dot menu > **Delete** > remove `custom_components/xiaomi_mimo_tts/` > restart HA. Voice sample files in your samples directory are not removed automatically.

## Debugging

The client logs its retry and backoff decisions at debug level. Per-call figures are on the diagnostic sensors, not in the log.

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.xiaomi_mimo_tts: debug
```

## FAQ

**Why is a voice design or clone profile so much slower to start than a built-in voice?**

Only `mimo-v2.5-tts` has low-latency streaming. `mimo-v2.5-tts-voicedesign` and `mimo-v2.5-tts-voiceclone` are still in **compatibility mode**: one call returns the whole clip in a single chunk once inference has finished. There is nothing to stream, so a designed or cloned voice synthesises the whole reply in one call and plays it once it is back.

Cutting the text into several calls would report first audio sooner, but each call is an independent inference. Voice design generates a fresh voice every time, so a long reply changes speaker partway through; voice clone stays closer to its sample but still shifts in pitch and pace, and re-uploads the whole sample on every call. Splitting also makes the reply slower overall. Use a built-in voice for the Assist Pipeline and keep design/clone for announcements, where a few seconds of lead time does not matter.

**The TTS cache is masking my new voice settings.**

HA caches TTS audio by `(message, language, options)`. Reconfiguring a profile doesn't invalidate the cache. Either change the message slightly, pass `cache: false` on the call, or run `tts.clear_cache`.

**Where do voice clone samples live?**

In the samples directory, `/media/voice_samples/` by default. Files uploaded through the config flow land there with auto-named `clone_<uuid>.{mp3,wav}` (or your chosen filename). They appear in HA's Media Browser and can be reused across multiple voice clone profiles.

**Can I configure multiple Xiaomi MiMo accounts?**

Yes. Add the integration multiple times with different API keys. Each instance has its own TTS entity, voice profiles, sensors, and quotas. Config entries deduplicate by hashed API key, so the same key cannot be configured twice.

**How do I track Xiaomi MiMo quota usage?**

The **Total audio minutes** and **Total characters synthesized** sensors track cumulative usage, on the account's device for every call and on each profile's device for the calls its voice spoke. The full set covers request counts, durations, last text, time to first audio, and last result enum.

**How long before a reply starts playing?**

The **Last time to first audio** sensor answers this for every call: a streaming call reports the time to its first chunk, a one-shot call reports the whole synthesis, because nothing can play until it finishes. **Streaming** says which of the two happened. For design and clone the wait grows with the length of the reply, since the whole clip has to be inferred first.

**How do I install the latest development version?**

After the integration is installed via HACS, switch to the latest `main` branch using the `update.install` action:

1. Go to **Developer Tools > Actions**
2. Select the `update.install` action
3. In **Target**, select the Xiaomi MiMo TTS update entity (e.g., `update.xiaomi_mimo_tts_update`)
4. In **Version**, enter `main` (or a specific commit hash)
5. Click **Perform Action**
6. Restart HA

To revert, run the same action with a release tag instead of `main`.
