# NEXUS + Hermes main agent

NEXUS keeps its name, dashboard, floating avatar, microphone/TTS, SQLite data,
memory, settings, tools and approval controls. Hermes is the main conversation
and task loop for both GUI chat and auto voice. There is no optional legacy
planner fallback: missing or incompatible Hermes causes a clear task error.

## Runtime and routing

The adapter reuses the existing native Windows installation supplied by the user:

- Hermes Agent v0.23.3, Git build `caafe5389ae585ef77387a962aee05b1bcf17029`.
- Source: `%LOCALAPPDATA%\hermes\hermes-agent`.
- Launcher: `%LOCALAPPDATA%\hermes\bin\hermes.exe`.
- Existing Hermes Python 3.14.9; NEXUS retains its separate Python environment.

The NEXUS process starts a reusable child using Hermes's installed interpreter
and committed dependency environment. The real `AIAgent.run_conversation` loop
plans and dispatches registered NEXUS tools. Exact routine/news/lock/media
commands use Hermes's scripted prelude, then the same model/tool conversation.
Their final wording now comes through the selected NEXUS provider instead of the
old hardcoded fast-response branch; an available permitted provider is needed
for that final reply. Chat-only models can still receive prelude tool receipts.

JSON pipes carry model requests and tool results. NEXUS's **existing Providers**
instance handles each model request, keeping model discovery, successful-model
priority, API timeouts, cooldowns, paid-request permission and configured Ollama
policy. Hermes requests additionally allow enabled account providers to fail
over through that same router. Account attempts use a six-second bound, matching
the existing API attempt timeout; the remote routing deadline remains 45 seconds.
Account failures enter a 60-second cooldown; rate-limited API providers honor the
existing bounded Retry-After rule. Ordinary account connection tests retain their
previous behavior. Disabled providers and unapproved paid calls are not tried.
Local-only Ollama selection still stays local; local fallback remains opt-in.

Each retry receives the current conversation, including completed tool receipts.
Only inference is retried during provider switching. Mutating actions and pending
approvals are fingerprinted and journaled before dispatch. An identical action
in the same task returns its existing receipt, including an unknown outcome,
instead of executing again. A worker failure, cancellation or exhausted router
ends that task; no task is automatically restarted or replayed.

The adapter limits planning to five model rounds and eight tool calls per model
response. Calls retain existing permissions and single-use approvals. Emergency
Stop cancels inference, closes the Hermes worker and clears pending approvals.
Already dispatched external actions cannot be reversed by cancellation.

## Configuration and isolation

The installer writes `hermes_runtime.json` inside the existing NEXUS installation.
It contains only local paths and the checked Hermes build, never provider keys.
This machine-specific file is excluded from source commits. User data remains in
the existing NEXUS data directory (`NEXUS_DATA_DIR` or the normal user-profile path).

Hermes runs with a NEXUS-owned isolated profile and frozen embedding configuration.
Its private provider settings, dotenv files, plugins, hooks, memory and built-in
terminal/file/browser tools are not used. The fixed tool surface contains only
the existing NEXUS catalog, including NEXUS's guarded search_files implementation.
The child receives no provider credentials. An audit guard rejects independent
network connections and process launches; this is defense in depth, not an OS
sandbox claim. Installed Hermes source and personal profile are not rewritten.

This is a version-locked adapter to the installed build's managed-worker and
registry seams. A different Hermes checkout is rejected until compatibility is
tested. The pipe's virtual context accounting is 65,536 tokens to meet this
Hermes build's internal requirement; this neither allocates a local model nor
expands any actual provider window. NEXUS retains its existing Ollama 4,096-token
setting. A provider can still reject a long context, and all providers can fail.

## Reviewed laptop compatibility (v2)

The initial installer refused the supplied laptop's app.py because it genuinely
differs from the inspected main-branch baseline; the difference was not CRLF or
encoding. The uploaded file is 32,733 bytes, SHA-256
`7931f0dbef329bcddc925547e1a30a47915fb9d9aaae26640bf1dde2f9a05e1d`.
It adds saved/new chat sessions, active-chat protection and Male/Female online
voice controls. A reviewed three-way merge adds Hermes to this exact app while
retaining those controllers unchanged. Both stock and reviewed laptop apps are
supported; unrecognized app hashes still stop the installation.

The supplied account_providers.py matches the original source and is not changed.
The user separately confirmed that providers.py and .gitignore match the tested
baseline. Their existing session-store and voice implementation files are not
in the payload. API delegation is tested with session-store collaborators; their
unpublished store internals are not claimed as tested in the cloud.

The user also supplied the hash of a different PROJECT_STATE.md, without sharing
its contents. Packages append a small integration note to either reviewed
state baseline, preserving the document's original bytes. Backup/restore and
concurrent-change checks use the original raw hashes. The ZIP does not contain
that private document. Only this documentation path permits append operations.

After applying files, the installer imports the actual installed app and checks
its state against a temporary data directory. This checks dependencies such as
chat_sessions without opening the real user database, starting the desktop,
recording audio or running provider probes. Startup failure restores the applied
files and notes. No force/ignore-baseline switch is introduced.

## Installation

Save **NEXUS-Hermes-Integration-v3.zip** to Downloads. Close NEXUS completely and run
the provided PowerShell command to extract it into a fresh temporary folder and
invoke **Install-NexusHermes.ps1** against the existing installation.

Version 3 fixes Windows PowerShell 5.1 removing embedded quotes from native
Python `-c` arguments. The version, tool-schema and app-startup probes now run
through a bundled Python file, verified against its format-3 manifest hash before
execution. Schemas travel through a UTF-8 JSON file. No inline Python code or
JSON string is passed through native command arguments. The reported SyntaxError
in version 2 occurred before application files were changed; it did not establish
that the existing Hermes interpreter was missing.

The installer verifies package hashes and the prior hashes of every file it
will change, selects only a reviewed matching app variant, probes the real
installed Hermes API, saves a source backup, applies only the listed source/doc
files and runtime descriptor, and checks app startup against temporary data.
Unknown source changes cause a refusal before patching. A failed
application attempts restoration of its own changes without deleting concurrent
edits. SQLite, credentials, user settings, avatar assets and other projects are
outside the payload. No model, package, account login or API request is performed
by the installer. Launch the same NEXUS desktop shortcut afterward.

Nonstandard installations can supply **-Destination**, **-HermesRoot**,
**-HermesHome** and **-HermesPython**. The default native paths match those supplied
by the user. No WSL installation is created or required.

## Validation and limits

The v3 full Linux suite passed **323 tests with 6 skips** using the real pinned Hermes
runtime. Its reviewed laptop app receives real bridge responses; session API
collaborators verify delegation without claiming to test the user's unpublished
store implementation. Nine PowerShell 7.7/Linux installer checks cover both app variants,
original note/data preservation, refusal of unknown code, startup dependency
failure recovery, unsafe-path refusal, Legacy native argument passing with spaces
in paths, and refusal of a modified helper before executing it. The private-note fixture uses its own
reviewed hash because the user's actual document was never uploaded.

Native Windows CI at commit `4eace97ad1b20c3e468654435b989c434994322a`
passed **307 tests with 22 skips**, including a real Windows PowerShell 5.1 test:
the old inline version command fails as expected, while the file-based version,
quoted/Unicode schemas and app-startup probes succeed with paths containing
spaces. The app-startup probe in that test uses a disposable fixture, not the
user's Hermes installation. Existing WebView2 drag/hover/mic-control fixtures,
the WhatsApp local fixture, disposable updater/rollback and SAPI diagnostics
also passed. Run: https://github.com/princemustansar-spec/NEXUS-AI-ULTRA/actions/runs/45497479290

Focused acceptance runs the actual pinned Hermes source and Python 3.14.9,
the production NEXUS router and controlled HTTP provider endpoints. It is not
a paid/live-model benchmark. Tests exercise HTTP failures, rate limits, real
timeouts, context transfer, tool receipts, duplicate protection, GUI/voice
dispatch and existing approval execution on temporary files.

PowerShell installer verification and the exact observed results are recorded in
[PROJECT_STATE.md](../PROJECT_STATE.md). The full Hermes installer on native
Windows, physical speakers/microphone/echo, real user provider credentials,
native Hermes startup latency and the user's installed Python/runtime path
discovery still need laptop acceptance.
No zero-downtime, guaranteed fallback, instant voice or hardware performance claim
is made. Installation requires closing NEXUS. JARVIS and ZAYRON are not modified.

The ZIP includes a source patch for review and the focused test file under
validation/. SDK tests use HERMES_TEST_PYTHON, HERMES_TEST_ROOT and HERMES_TEST_HOME
to select the existing runtime. Tests without that runtime report explicit skips;
they do not replace Hermes with a substitute planner.
