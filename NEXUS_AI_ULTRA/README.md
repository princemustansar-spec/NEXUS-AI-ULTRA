# NEXUS AI ULTRA

A Windows desktop assistant combining AI chat, voice, a floating companion, personal routines and approved computer actions. FastAPI serves the existing interface on loopback; pywebview hosts it in Microsoft Edge WebView2. SQLite stores chat, settings, approved memory, reminders and activity.

This guide describes the current source. See [PROJECT_STATE.md](PROJECT_STATE.md) for implementation scope and validation.

## Windows installation

Requirements:

- Windows with Python **3.11 or 3.12 x64** and the Python launcher.
- Microsoft Edge **WebView2 Evergreen Runtime**.
- An internet connection for installing dependencies and using online features.
- A configured AI provider/account, or an installed Ollama model, for general conversation.

Download or clone the repository, then open the inner **NEXUS_AI_ULTRA** folder containing this README and INSTALL.bat.

1. Run **INSTALL.bat**. It creates the virtual environment, installs dependencies and creates the desktop shortcut.
2. Launch the **NEXUS desktop shortcut** or **START_NEXUS.bat**.
3. Open **Settings** and complete a provider/account setup below.
4. Open **Voice Assistant** to choose the microphone, recognition language and speech options.

The Python requirement includes voice dependencies; **INSTALL_VOICE.bat** can install or repair them separately. The offline recognition model is a separate, optional download from Voice Assistant.

After moving the installation, run **CREATE_DESKTOP_SHORTCUT.bat**. Close NEXUS normally before updating; **STOP_NEXUS.bat** is the identity-checked emergency stop for its own process.

### Updating an existing installation

Close the dashboard, floating companion and any other NEXUS windows. Run the updater from the source package you intend to install, using the actual installation path:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_update.ps1 -Destination "$env:USERPROFILE\NEXUS_AI_ULTRA" -Revision main
~~~

Change the destination if NEXUS is installed elsewhere. A reviewed commit SHA may replace **main** when testing a specific revision. The updater refreshes the source, dependencies and desktop shortcut while preserving user data and credentials.

The installer also prints a backup path and recovery command. **Rollback is a testing/recovery aid**, not a normal usage step. Keep the backup and updater script while evaluating an update; use the printed command if recovery is needed.

### Portable build

On Windows, run **BUILD_WINDOWS.bat** after installation. Distribute the entire **dist\NEXUS_AI_ULTRA** directory, including its internal files. The target computer still needs WebView2, but not a separate Python installation. Rebuild after source changes.

## AI providers and accounts

Open **Settings** and choose the connection you want to use.

| Connection | Setup |
| --- | --- |
| ChatGPT account | Continue with ChatGPT → Check connection → choose an account model → Test response → Use for chat and voice |
| Claude account | Install the official Claude Code app, complete its login, then check, test and select it in NEXUS |
| API provider | Save the base URL, credential and model; test the saved endpoint and a real response |
| Ollama | Install/run Ollama and a model yourself; Find installed models → select a mode/model → Save → Test local reply |

ChatGPT and Claude access depends on the account's supported plan, usage limits and available models. A sign-in alone does not confirm that inference works. Account adapters keep the existing NEXUS tools, approvals and speech pipeline; ChatGPT sign-in does not provide the ChatGPT app's voices or Realtime audio.

API connections support OpenAI-compatible endpoints, including configured Gemini, Groq, OpenRouter, FreeLLMAPI and local services. Use the API **base URL**, not the full chat-completions URL. Use a returned model ID or supported automatic discovery. Provider fallback follows the saved settings; requests that may incur API charges require the existing per-request approval.

**Ollama on this laptop** uses installed models only. Local-only mode stays local; fallback to a local model is opt-in. Model size, cold starts and context length affect responsiveness on a Core i3 / 12 GB laptop. NEXUS does not download an LLM automatically.

Detailed account and storage behavior: [ACCOUNT_CONNECTIONS.md](docs/ACCOUNT_CONNECTIONS.md). Local model controls: [PERSONAL_ASSISTANT.md](docs/PERSONAL_ASSISTANT.md).

## Voice conversation

**Voice Assistant** provides microphone selection, input-level diagnostics, recognition language, speech-pause settings and online/offline recognition options.

- Google recognition sends a completed speech clip online. The verified multilingual Whisper tiny model can provide an optional CPU-based offline fallback.
- Urdu recognition and Roman Urdu output spelling are separate settings; recognition and transliteration can make mistakes.
- Existing output uses optional Edge TTS with pygame playback, installed Windows SAPI voices and the browser speech fallback where available.
- Auto voice starts a microphone session only after the existing consent/start controls. Mute, stop and Emergency Stop remain available.
- Configurable interruption can stop a spoken reply on detected speech, a stop phrase or a manual button. Speaker echo can affect detection; headphones improve reliability.

Recognition currently runs after an utterance has been captured. The AI response and speech preparation also take time. These controls do not provide instant, word-by-word streaming transcription or guarantee an immediate spoken response.

See [voice setup](docs/JARVIS_VOICE_UPGRADE.md) and [latency/interruption](docs/VOICE_LATENCY_AND_INTERRUPTION.md). Actual microphone and speaker timing must be checked on the laptop.

## Floating companion and photo avatar

Open **Floating AI** from the GUI. Hover for controls; drag the figure to move it. Existing controls cover the dashboard, microphone, motion, interruption and closing the companion.

In **Settings → Floating avatar appearance**, select:

- **Original floating AI Core**, or
- **Floating photo avatar**.

The dashboard always retains its original AI Core. The appearance setting changes only the floating figure.

Choose a transparent **8-bit RGBA PNG**, 64–2048 pixels and smaller than 1.9 MB, or a **.zip / .nexus-avatar** pack smaller than 4 MB. Select the pack whole; it must contain exactly **portrait.png**, **expressions.png** and **rig.json**.

A photo alone provides subtle connected head movement and breathing. Matching expression frames from the same person enable blinks and speaking mouth poses. Playback cues come from the existing voice pipeline. This is lightweight **2D / hybrid animation**, with coarse mouth shapes rather than precise phoneme lip sync.

Photos and expression packs remain in local application data. They are not included in this public repository, AI prompts or provider requests. A different photo clears the previous expression sheet. Switching to the original Core keeps the saved portrait available.

Setup, formats and synchronization limits: [LIVE_HUMAN_AVATAR.md](docs/LIVE_HUMAN_AVATAR.md).

## Personal assistant

**Settings → Personal Assistant** controls the preferred name, reply style, welcome, spoken welcome, routine inclusion, online startup headlines and expressive avatar behavior.

Daily routines use the laptop's local time and selected weekdays. Reminders and due routines notify while NEXUS runs; eligible overdue items are checked after restart. News uses dated Dawn and BBC World RSS headlines with source links.

Windows startup is optional and applied explicitly through its settings control. The PC-lock command uses the existing action approval flow. Long-term memories are saved through **Knowledge & Memory**.

Details and supported routine/news commands: [PERSONAL_ASSISTANT.md](docs/PERSONAL_ASSISTANT.md).

## WhatsApp

Open **WhatsApp Center → Open WhatsApp / QR login** and link the NEXUS-owned window. A separate Chrome or WhatsApp Desktop login is not automatically reused.

Contact search and message preparation require a verified recipient. **Prepare & review send** queues the exact recipient/message for approval. Sending uses a single attempt with an observed receipt; unclear outcomes are not automatically retried. Manual drafts remain available as a fallback.

Live compatibility depends on WhatsApp Web's layout and observable contact identity. If verification fails, use **Check WhatsApp / send status** and the [layout diagnostic guide](docs/WHATSAPP_LAYOUT_DIAGNOSTIC.md). An open chat alone does not prove that its identity or sending controls were verified.

Full instructions: [WHATSAPP_SENDING.md](docs/WHATSAPP_SENDING.md).

## Tools, permissions and data

Existing tools cover system information, processes, approved files/folders, allowlisted applications, browser/search actions, reminders, memory, compatible image generation and supported integrations. Capabilities depend on the selected provider and installed Windows services.

**Safety Center** retains per-tool permissions, reviewed action approvals, cancellation and Emergency Stop. Stopping cannot reverse an action already completed.

Default application data: **%USERPROFILE%\.nexus_ai_ultra**. Set **NEXUS_DATA_DIR** to use a different directory.

- **nexus.sqlite3** stores chat, settings, memory, reminders and activity.
- API credentials use the configured OS credential vault or explicit environment overrides.
- ChatGPT credentials use Windows user encryption; Claude Code maintains its own login.
- Managed avatar files live under **avatars** in application data.
- Source updates preserve the application data directory. Stop the app before backing it up.

Online AI, recognition, speech and news features contact their configured services. Personal avatar files stay local. Keep credentials, private photos and application data out of source commits.

## Project layout and development

~~~text
NEXUS_AI_ULTRA/
  nexus/              Backend, providers, tools, voice and native window hosts
  static/             Existing dashboard, floating view and avatar rendering
  tests/              Python checks
  docs/               Feature guides, diagnostics and validation records
  PROJECT_STATE.md    Current scope and verification
  run.py              Desktop/headless entry point
  install_update.ps1  Existing installation updater
  INSTALL.bat         Windows dependency/shortcut setup
  START_NEXUS.bat     Desktop launcher
  BUILD_WINDOWS.bat   Portable Windows build
~~~

For Python checks from this folder after installation:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~

Browser and native acceptance checks are recorded in the repository's CI and feature guides. Tests use synthetic portraits, audio and WhatsApp fixtures. Actual account access, microphone latency, speaker echo, perceived lip sync, live WhatsApp compatibility and hardware resource use require checks on the user's Windows laptop.

Start with [PROJECT_STATE.md](PROJECT_STATE.md) and [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md). A [Roman Urdu guide](docs/USER_GUIDE_ROMAN_URDU.md) and older feature reports are also available; older reports describe their respective historical scope.
