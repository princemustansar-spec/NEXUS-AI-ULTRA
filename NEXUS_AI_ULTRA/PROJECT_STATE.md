# NEXUS AI ULTRA — project state

Updated: 25 November 2026 (Asia/Riyadh).

## Hermes main-agent integration (delivery branch; not merged)

- NEXUS baseline: `b630568caa735e756f96b22db07a354f041db88b`.
- Local recoverable checkpoint: `checkpoint/pre-hermes-20261124`.
- Delivery branch: `feature/hermes-main-20261124`. Source/package publication
  was authorized by the user; the integration is not merged into main.
- Existing native Hermes v0.23.3 / Python 3.14.9 is reused, pinned to supplied
  build `caafe5389ae585ef77387a962aee05b1bcf17029`.
- GUI chat and auto voice enter the real Hermes AIAgent loop. Exact legacy
  commands use its scripted prelude; all model requests use the existing NEXUS
  Providers instance and all actions use the existing approval/permission runner.
- Enabled account fallback is added to that router for Hermes requests only.
  Existing API discovery, model selection, timeouts, cooldowns and paid/local
  policies remain authoritative. No independent Hermes provider is configured.
- Current-turn tool receipts stay in model context across provider switches.
  Mutation fingerprints/receipts are journaled before dispatch. Failures and
  unknown outcomes do not automatically replay tasks/actions.
- NEXUS branding, GUI/static assets, avatar, voice selection, existing database,
  settings and credentials are preserved. Hermes gets an isolated NEXUS profile,
  NEXUS-only tools and credential-free JSON-pipe callbacks. JARVIS/ZAYRON untouched.
- Minimal hash-checked ZIP installer is provided. No model/package download
  or API inference is performed by that installer. Existing Hermes source/profile
  is not patched. Source backup is retained for testing/recovery.

### Observed integration validation

- Full NEXUS Python suite with the real Hermes SDK configured: **319 passed,
  5 skipped** (NEXUS Python 3.12; Hermes Python 3.14.9). Existing recognition
  dependencies were installed only in an isolated cloud test directory.
- Ten focused main-agent cases are included in that total. They run the real
  pinned AIAgent, production router and controlled HTTP servers, exercising 429,
  503 and actual six-second timeout fallback; identical context at the switched
  provider; enabled-account failure; duplicate calls with different IDs; real
  approved file creation; exhausted-provider failure without restart; shared
  GUI/voice dispatch; reusable worker PID; explicit voice-command prelude; and
  Emergency Stop during an in-flight request.
- Legacy chat API tests now exercise the actual Hermes main agent rather than
  assuming the removed app-local planning loop. They report an explicit SDK
  requirement skip if no external Hermes test runtime is supplied.
- PowerShell **7.7.0 on Linux** executes the exact delivery command with native-
  layout path fixtures, default interpreter discovery and the real Hermes probe.
  Checks cover successful integration, source backup, SQLite/avatar/shortcut/
  private-profile preservation, refusal of unknown source edits, restoration
  after an induced post-install failure and rejection of a traversal path.
- ZIP CRCs, payload SHA-256 values and prior source hashes are checked. The ZIP
  contains a reviewable source patch, focused test file and minimal payload;
  no credentials, application data, private portraits, Hermes dependencies or
  models are included. Static GUI, avatar, voice/TTS, hands-free and store source
  files are byte-identical to the inspected NEXUS baseline.

Native Windows PowerShell/WebView2 and installed interpreter discovery on the
actual laptop remain unverified. No live user provider inference, subscription
request, physical microphone/speaker or message sending was performed. Real
provider access, hardware latency, interruption echo and CPU/RAM need laptop
acceptance. Controlled providers verify switching behavior, not guaranteed live
service availability. No zero-downtime or guaranteed-fallback claim is made.
Details: `docs/HERMES_MAIN_AGENT.md`.

### Reviewed laptop compatibility update

- Local checkpoint before this update: `checkpoint/pre-laptop-app-compat-20261125`.
- The original package correctly refused laptop app SHA-256
  `7931f0dbef329bcddc925547e1a30a47915fb9d9aaae26640bf1dde2f9a05e1d`.
  The supplied source has New Chat/session APIs and Male/Female voice controls.
- A conflict-free reviewed merge is stored under `compatibility/laptop-7931f0/`.
  Its payload SHA-256 is
  `971e16a30cb414a67afbd10a82c137546810bb1c9f5e540719ae3d1bb842d601`.
  Existing controllers other than chat, lifespan and safety are unchanged.
- The supplied account_providers.py is byte-identical to the baseline and is
  left untouched. User-provided hashes confirm the existing providers.py and
  .gitignore match the original tested baseline.
- A reviewed different project-state hash is accepted only for append mode.
  The original private notes are not uploaded or replaced. All code baselines
  still require exact recognized hashes; there is no force option.
- Format-2 installer selects the matching stock/laptop payload, backs up original
  bytes, stages appended notes, and checks app import/state with temporary data.
  Missing dependencies cause restoration instead of a broken successful install.
- The user session-store and voice source files are not modified. Session API
  delegation is tested with collaborators; their unpublished internals and native
  Windows behavior require laptop acceptance.
- Updated full suite with the real Hermes SDK: **321 passed, 5 skipped**. New
  compatibility tests verify all untouched uploaded controllers and run the
  reviewed app through the real Hermes bridge, including stale-chat rejection,
  session API delegation and saved voice settings.
- Seven PowerShell 7.7/Linux checks passed: stock install, exact laptop app
  selection with retained notes, unchanged source/data/voice-store dependencies,
  source refusal, failure restoration, traversal refusal and restoration when a
  required session-store dependency is missing. A session-store interface and
  private-note fixture are used where unpublished source/content was not supplied;
  those originals are not falsely claimed as cloud-tested.

## Archived avatar notes (5 November 2026)

These notes predate the baseline's later avatar lip-sync update. The Hermes
integration leaves the baseline's current avatar code and assets unchanged.

## Baseline and recovery

- Inspected merged baseline: `bf478924e520392ae9539c73295d58c8e4c1bae8`.
- Recoverable upstream checkpoint: `checkpoint/pre-live-avatar-20261105`.
- Feature branch: `feature/live-human-avatar`.
- Earlier procedural-avatar PR #20 and experimental portrait renderers were not
  merged or used as application baselines. JARVIS and ZAYRON were not modified.
- Release scope: the photo replaces only the floating figure. Desktop installation
  remains a separate user-run update using the existing backup/rollback installer.

## Current implementation

Optional local Human Avatar replaces only the existing floating figure. The
dashboard keeps its original AI Core; settings and speech observers remain in the
GUI, with no dashboard photo renderer. The original floating Core is selectable. Portraits and expression packs
stay in local application data. The existing settings table gains one optional
`human_avatar` key; there is no schema migration, provider change or new AI brain.

Existing Edge/pygame, Windows SAPI and browser fallback paths gain optional
playback observers. Native visemes or actual audio position drive bounded mouth
cues. Preparation, listening, thinking, speech, stop and idle are distinct. A
connected portrait mesh avoids the experimental neck cut-line. No new model or
runtime dependency is added. Full details: docs/LIVE_HUMAN_AVATAR.md.

## Validation

- Linux Python suite: **282 passed, 4 Windows-only checks skipped**.
- Browser checks: Human Avatar import, idle/listening/thinking, actual timed-cue
  rendering/expiry, cross-window browser speech boundaries, mute, Motion Off, Core switch and
  restore, native drag dispatch, and no-WebGL fallback passed.
- Existing GUI: 17 navigation sections, memory persistence, system tool, action
  approval, Emergency Stop/resume and four viewport sizes passed without JS
  errors or horizontal overflow. Existing settings, Core and drag suites passed.
- Real pygame MP3 decode/playback clock passed using synthetic audio and an SDL
  dummy output device. It does not verify a physical speaker.
- Native Windows SAPI visemes/file synthesis and both WebView2 mouse modes are
  required CI checks on this branch. Their observed outcome is in the feature
  PR's GitHub checks; physical laptop acceptance remains separate.
  The native file probe independently checks whether the runner emits visemes;
  if its independent observer receives none, synthesis is verified but viseme
  acceptance is explicitly skipped and must be checked with a real audio device.

Tests use synthetic images/audio, not private portraits. A raw photo alone has
head/breathing movement; matching local expression frames are required for full
blink/mouth animation. Three mouth poses do not provide exact phoneme lip sync.

Still requires the user's Windows laptop: perceived audio/lip alignment with
their selected voice, actual portrait appearance, physical speaker/microphone and
interruption behavior, and measured CPU/RAM on the Core i3/12 GB system.
