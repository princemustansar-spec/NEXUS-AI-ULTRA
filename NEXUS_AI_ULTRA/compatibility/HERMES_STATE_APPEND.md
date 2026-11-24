

<!-- nexus-hermes-main:20261125 -->
## NEXUS + Hermes main agent integration — 25 November 2026

Hermes v0.23.3 (Git caafe5389ae5), using its existing native Python 3.14.9,
is the main chat/voice planner. Its JSON-pipe requests use NEXUS's existing
provider router; tools retain NEXUS approvals, permissions and Emergency Stop.
Provider switches keep current tool receipts, and unknown/completed actions are
not automatically replayed. The original GUI, voice engine, data and settings
remain in place. No credentials or private avatar assets are in the package.

The installer recognizes the reviewed stock app and the supplied laptop app
SHA-256 7931f0dbef329bcddc925547e1a30a47915fb9d9aaae26640bf1dde2f9a05e1d.
The latter retains its New Chat, saved chat selection, active-chat guard and
Male/Female voice settings. Other code versions are refused. This section is
appended to retain prior project notes; their original bytes are backed up.

Version 3 fixes legacy Windows PowerShell stripping quotes from Python commands.
Version/schema/startup probes use a hash-verified helper file and UTF-8 JSON.
The Linux suite passed 323 tests (6 skipped), with the real Hermes SDK and
controlled HTTP providers. Nine PowerShell/Linux installer checks passed.
Native Windows CI passed 307 tests (22 skipped), including real PowerShell 5.1
helper probes with spaces in paths. That test uses a disposable app fixture,
not the user's Hermes runtime. Details are in the HERMES_MAIN_AGENT guide.
Installer startup/dependency checks use temporary data, never the real database.
Full native Hermes installation, live providers, physical microphone/speaker
and actual session-store behavior still need laptop acceptance.
No guaranteed fallback or zero downtime is claimed.
