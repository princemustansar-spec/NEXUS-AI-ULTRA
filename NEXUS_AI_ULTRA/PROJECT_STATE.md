# NEXUS AI ULTRA — project state

Updated: 5 November 2026 (Asia/Riyadh).

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
