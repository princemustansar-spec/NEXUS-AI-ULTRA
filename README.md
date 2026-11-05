# NEXUS AI ULTRA

A Windows desktop AI assistant with chat, voice conversation, a floating AI companion and approved computer actions. The interface runs in a native pywebview / Microsoft Edge WebView2 window.

The dashboard keeps its original animated AI Core. The floating companion can use either the original Core or an optional local photo avatar.

## Current features

- Chat through configured API providers, a connected ChatGPT account or the official Claude Code adapter.
- Local Ollama models, with explicit local-only or fallback selection.
- Google speech recognition with optional offline Whisper fallback; Edge / pygame speech output and installed Windows voice fallbacks.
- Auto voice, mute, stop and configurable interruption while the assistant speaks.
- A draggable floating companion with hover controls and optional photo animation.
- Personal welcome, reply style, daily routines, reminders and Pakistan / international headlines.
- WhatsApp contact search and reviewed sending through the NEXUS WhatsApp window.
- System information, file and application tools, approved memory and an action approval center.

Features that use accounts, online services, local models or Windows integrations require their respective setup. Voice recognition processes recorded utterances; instant streaming conversation is not implemented.

## Start on Windows

1. Install **Python 3.11 or 3.12 x64** and **Microsoft Edge WebView2 Evergreen Runtime**.
2. Download or clone this repository and open the [NEXUS_AI_ULTRA](NEXUS_AI_ULTRA/) folder.
3. Run **INSTALL.bat**, then launch the NEXUS desktop shortcut or **START_NEXUS.bat**.
4. Open **Settings**, configure a provider or account, test a response and select it for chat and voice.

For an existing installation, follow the [installation and update guide](NEXUS_AI_ULTRA/README.md#updating-an-existing-installation).

## Documentation

| Guide | Contents |
| --- | --- |
| [Project guide](NEXUS_AI_ULTRA/README.md) | Installation, updates, settings, data and development |
| [Project state](NEXUS_AI_ULTRA/PROJECT_STATE.md) | Current scope, validation and remaining laptop checks |
| [ChatGPT and Claude accounts](NEXUS_AI_ULTRA/docs/ACCOUNT_CONNECTIONS.md) | Sign-in, account selection and usage |
| [Voice setup](NEXUS_AI_ULTRA/docs/JARVIS_VOICE_UPGRADE.md) | Recognition, speech output and online consent |
| [Voice interruption](NEXUS_AI_ULTRA/docs/VOICE_LATENCY_AND_INTERRUPTION.md) | Auto voice, stopping speech and current limitations |
| [Floating photo avatar](NEXUS_AI_ULTRA/docs/LIVE_HUMAN_AVATAR.md) | Local photos, expression packs and animation |
| [Personal assistant and Ollama](NEXUS_AI_ULTRA/docs/PERSONAL_ASSISTANT.md) | Welcome, routines, headlines, startup and local models |
| [WhatsApp](NEXUS_AI_ULTRA/docs/WHATSAPP_SENDING.md) | QR login, contact verification, approvals and receipts |
| [Troubleshooting](NEXUS_AI_ULTRA/docs/TROUBLESHOOTING.md) | Installation and runtime issues |

## Data and verification

Chat, settings and approved memories are stored locally. Provider credentials use the configured OS credential storage; avatar photos stay local. Online recognition and AI providers receive the content needed for their enabled features.

The photo avatar is lightweight **2D / hybrid animation**. A matching expression pack is required for blinking and speaking mouth shapes; precise phoneme lip sync is not claimed.

See [PROJECT_STATE.md](NEXUS_AI_ULTRA/PROJECT_STATE.md) for test evidence. Actual microphone latency, speaker echo, perceived lip sync, live WhatsApp compatibility and CPU/RAM usage still require checking on the user's Windows laptop.
