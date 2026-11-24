

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

The updated suite passed 321 tests (5 skipped), with the real Hermes SDK,
controlled HTTP providers and reviewed laptop variant. Seven PowerShell/Linux
installer checks passed; details are in the HERMES_MAIN_AGENT guide. App startup
and dependency checks use temporary data rather than the real user database.
The installer checks app
startup against temporary data, never the existing user database. Native Windows,
live providers, physical microphone/speaker and actual session-store behavior
still need laptop acceptance. No guaranteed fallback or zero downtime is claimed.
