# Optional live Human Avatar

Settings → Floating avatar appearance offers Original floating AI Core (the
default) and Floating photo avatar. Only the existing native floating figure
changes. The dashboard keeps its original AI Core and does not load a portrait
renderer or avatar event stream. Its existing speech output can still drive the
floating figure. Other GUI sections, providers, tools, voice selection, recognition
and SQLite records remain in place.

## Local portrait setup

Choose a transparent PNG (8-bit RGBA, non-interlaced, 64–2048 pixels, <1.9 MB)
or a private `.nexus-avatar` pack (<4 MB). A pack contains exactly `portrait.png`,
`expressions.png` and `rig.json`. The expression image is a 2×2 sheet: closed-eye
blink, gently parted lips, round lips and open/smiling lips. The rig maps those
frames onto the portrait. Use matching frames of the same person only.

A photo alone gives connected head movement, breathing and a small jaw movement
that follows the voice. Natural eyelids and visible speaking mouth shapes require
matching expression frames: the app does not invent unseen facial details or
upload a photo to generate them.

### More mouth shapes (optional)

The 2×2 pack above gives three mouth frames. A pack can carry up to eight, on a
3×3 sheet (`rig.json` gets `"grid":[3,3]` and `"shapes":[1,…,8]`). Cell 0 is the
blink; the other cells run left to right, top to bottom:

| Cell / shape | Mouth | Typical sounds |
| --- | --- | --- |
| 1 | slightly parted | t d n s l th |
| 2 | round | o u w |
| 3 | wide open | a |
| 4 | wide smile | e i |
| 5 | lips pressed | m b p |
| 6 | teeth on lower lip | f v |
| 7 | pursed | sh ch r |
| 8 | half open | uh h k g |

You do not need all eight. For any shape a pack does not have, the app shows the
nearest frame it does have (shape 5 just leaves the lips at rest), so old three-frame
packs keep working unchanged. To build a pack from your own images, run
`python make_avatar_pack.py portrait.png expressions.png my.nexus-avatar` from the
NEXUS folder (see the top of that file for options such as `--shapes 1,2,3,4,5` or a
custom `rig.json`). The frames must show the same person and line up with the portrait;
use "Adjust expression alignment" in Settings to nudge them. The approved
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
real playback, but amplitude/word timing is not precise phoneme lip sync. Native
viseme quality depends on the selected Windows voice.

How speech is drawn: every spoken word is split into a rough sequence of mouth
shapes from its letters (works for English and Roman Urdu spelling; words in other
scripts only open and close the mouth). Windows voices that report visemes use those
instead. The shape changes blend into each other over a few frames, the chin and
lower lip drop with how wide the mouth opens, and the lip corners pull in for round
sounds and out for smiles. Blinks come at uneven intervals, and the head sways a
little more while speaking. The `eight shapes` need a pack that has the frames (see
above); without them you get the blended three-frame version.

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
The SAPI file test uses an independent event observer: if the runner exposes no
native visemes, it reports a skip rather than claiming a successful lip-sync test.

Physical speaker/microphone behavior, perceived lip sync, portrait alignment and
CPU/RAM on the user's Core i3/12 GB laptop require laptop acceptance. No hardware
performance figure or photorealism is claimed from synthetic tests.

## Return to the previous version

For an immediate appearance change, select Original floating AI Core and Apply
avatar. For a full source/dependency rollback, close NEXUS and use the exact
Rollback command printed by `install_update.ps1`, with its recognized backup
folder. Keep that backup and updater script. Existing user data outside the
installation, including the database and photos, is retained; older code ignores
the new avatar setting. Automatic recovery after a failed install and manual
rollback are covered by the existing Windows updater tests.
