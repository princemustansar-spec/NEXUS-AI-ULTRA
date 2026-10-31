# Install and check the combined voice/chat preview on Windows

This preview combines the voice-context/Urdu-locale fix from PR #4 and the larger chat from PR #5. It has not been merged into main.

## Existing source installation

1. Close NEXUS and its console. Open PowerShell **inside your existing NEXUS_AI_ULTRA folder**, where run.py is present. Do not run from a drive root or from Downloads.
2. Run the following. It refuses to continue unless the current folder contains NEXUS source:

```powershell
if (!(Test-Path .\run.py) -or !(Test-Path .\nexus\app.py)) { throw 'Open PowerShell inside the existing NEXUS_AI_ULTRA folder first.' }
$nexusUpdateScript = Join-Path $env:TEMP 'nexus-preview-update.ps1'
Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/princemustansar-spec/jarvis/preview/voice-chat-install/NEXUS_AI_ULTRA/install_update.ps1' -OutFile $nexusUpdateScript
powershell -NoProfile -ExecutionPolicy Bypass -File $nexusUpdateScript -Destination (Get-Location).Path -Revision 'preview/voice-chat-install'
```

The existing updater backs up the installation before overlaying source, preserves SQLite/user files and the credential namespace, installs requirements, and prints a rollback command. Keep that receipt. It does not merge GitHub branches. It does not rebuild a portable EXE; use START_UPDATED_NEXUS.bat so you launch the updated source instead of an old EXE.

If you only have a portable EXE, or your folder has no run.py, do not use this command against an arbitrary directory; the installation method needs to be identified first.

## Check on the actual PC

- Launch START_UPDATED_NEXUS.bat.
- Voice Assistant: choose Roman Urdu and set Google recognition locale to automatic or ur-PK. Existing explicit en-IN settings are deliberately preserved.
- Press Voice, say “NEXUS, meri awaaz aa rahi hai tumhein?”, and compare the original Urdu transcript with the editable Roman Urdu text before Send.
- Send and check that the assistant responds to the transcript. Enable “Speak AI responses” if spoken replies are desired.
- Open AI Chat or Expand chat: the conversation should fill the content area; confirm the larger input, Voice and Send controls.
- Verify existing chat history and provider configuration. Paid requests still need approval.

## Verification performed in the Linux test environment

Installed the previously missing SpeechRecognition 3.17.0, edge-tts 7.3.1 and pygame 2.6.1 dependencies into an isolated test directory. Full Python suite: 98 passed. Node transcript/review/retry test passed; Chromium layout tests passed at 1366x768, 1920x1080, 800x600 and 390x844. Compilation and JavaScript syntax checks passed. Updated the existing exact HTML/CSS baseline to reflect the requested layout; retained the voice-output preservation check.

The user's Windows installation, Windows updater/COM/WebView2, real microphone transcription quality, live cloud inference, speaker output and 4GB-device RAM were not tested remotely. No access to that PC was available.

## Microphone/core visual feedback update

Added live input-level feedback to the core and a measured progress meter on Voice Assistant. Calibration, listening (with dBFS), transcription, errors and microphone-off states are shown explicitly. Input-level feedback resets after capture. The microphone still opens only after an explicit Voice/Start action; transcripts still require review and Send.

Added a persisted Animation control with System / On / Off modes. System respects reduced-motion preferences; explicit On restores core rotation even when the OS requests reduced motion. Off disables core animation. This addresses the code's previous blanket animation suppression under reduced-motion settings without silently overriding that preference for everyone.

Validation: 98 Python tests passed; Chromium tests verified actual changing rotation matrices, OS reduced-motion behavior and explicit override persistence, start action, calibration, increasing synthetic microphone levels, the Voice Assistant meter, transcription, errors, and no automatic microphone restart after reload. Four layout sizes and the transcript flow passed. Actual user Windows microphone/speaker behavior is still unverified.

## Chat keyboard update

Enter submits the existing chat form through the normal validation and approval path; Shift+Enter inserts a newline. Empty/whitespace drafts, repeated Enter keydown, composition/IME Enter and already-running requests do not submit. Ctrl/Alt/Meta+Enter are left unchanged. The Send button still works and request failures retain the draft. Browser keyboard tests and the existing transcript flow passed; JavaScript syntax passed. No backend or dependency change.
