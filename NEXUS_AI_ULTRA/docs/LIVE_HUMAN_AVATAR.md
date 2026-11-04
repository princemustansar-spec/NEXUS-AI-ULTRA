# Optional live Human Avatar

Settings → Avatar appearance offers Original AI Core (the default) and Human
Avatar. The same portrait renderer is used in the existing dashboard Core area
and the existing native floating window. Other GUI sections, providers, tools,
voice selection, recognition and SQLite records remain in place.

## Local portrait setup

Choose a transparent PNG (8-bit RGBA, non-interlaced, 64–2048 pixels, <1.9 MB)
or a private `.nexus-avatar` pack (<4 MB). A pack contains exactly `portrait.png`,
`expressions.png` and `rig.json`. The expression image is a 2×2 sheet: closed-eye
blink, gently parted lips, round lips and open/smiling lips. The rig maps those
frames onto the portrait. Use matching frames of the same person only.

A photo alone gives connected head movement and breathing. Natural eyelids and
visible speaking mouth shapes require matching expression frames: the app does
not invent unseen facial details or upload a photo to generate them. The approved
portrait/expression pack is distributed privately, outside this public source
repository. Changing to a new photo clears the previous expression sheet.

Photos are saved only in `NEXUS_DATA_DIR/avatars/<revision>/`, normally beneath
`%USERPROFILE%/.nexus_ai_ultra`. They never enter the source checkout, AI prompts
or provider requests. PNG and ZIP structure, size, dimensions, CRCs and rig bounds
are validated before replacing the selected profile. No archive is extracted to
caller-controlled paths. Browser uploads target only the existing loopback API
and require the existing session token. Image responses prohibit cross-origin
embedding. Removing the avatar deletes its managed local copies; the original
selected file is retained.

Apply avatar switches modes and saves optional expression alignment. AI Core
retains the saved portrait for switching back. Speech synchronization is enabled
for the next TTS job; an already-running legacy job is not restarted or replaced.

## Synchronization and states

Human Avatar opts the existing TTS worker into small playback-cue messages over
its existing pipe. No second voice engine, AI brain or audio player is created.

- Edge keeps its current voice, online consent, chunking and pygame playback.
  PCM amplitude is measured locally for the current audio chunk; pygame's actual
  playback position anchors short future mouth cues. Available word boundaries
  choose coarse mouth shapes. Audio preparation is distinct from playback.
- Installed Windows voices keep pyttsx3/SAPI. A second optional SAPI event sink
  receives native visemes without replacing pyttsx3's own listeners. Voices that
  expose only word callbacks use a clearly limited word-timing mode.
- Browser speech fallback keeps its original voice selection and callbacks. An
  additional observer forwards available word boundaries between the GUI and
  floating view through a same-origin BroadcastChannel. No text/audio is sent to
  an additional server. Browsers without word events keep the mouth closed.

A compact same-origin event stream carries playback position/cues, job ID and
idle/listening/thinking/speaking state; it includes no photo, audio, transcript,
chat history or provider credentials. Expired cues, disconnects, cancellation,
mute and Emergency Stop close the mouth. Listening and thinking use subtle gaze
and head motion. Idle has brief blinks and breathing. Motion Off and reduced
motion retain a stable portrait.

This is layered 2D animation with a connected mesh, not photorealistic 3D. The
neck is never cut into a separate moving rectangle. Speech movement follows
real playback, but three mouth poses and amplitude/word timing are not precise
phoneme lip sync. Native viseme quality depends on the selected Windows voice.

## Resources and acceptance

No new dependency or AI model is required. Maximum rendering rates are 24 FPS
speaking and 12 FPS otherwise; pixel ratio is capped at 1.25. The 768-pixel-wide
portrait texture is uploaded only when facial pixels change. Hidden views skip
drawing; native Core rendering pauses while its Human Avatar is visible. A 2D
fallback keeps the entire portrait connected when WebGL is unavailable.

Tests use synthetic portraits and a generated audio tone, never personal photos.
They cover preparation versus playback, actual pygame decode/clock, SAPI event
contracts, stale/expired cues, state transitions, mute/cancel, local import,
invalid packs, mode switching, GUI controls and native drag dispatch. Windows CI
also exercises native SAPI file synthesis and physical WebView2 mouse input in
both avatar modes. See PROJECT_STATE.md for observed results and remaining checks.

Physical speaker/microphone behavior, perceived lip sync, portrait alignment and
CPU/RAM on the user's Core i3/12 GB laptop require laptop acceptance. No hardware
performance figure or photorealism is claimed from synthetic tests.
