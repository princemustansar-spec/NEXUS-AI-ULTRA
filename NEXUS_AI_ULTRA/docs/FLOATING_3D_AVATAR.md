# NEXUS Floating 3D AI preview

Open the native Windows source app through START_UPDATED_NEXUS.bat, then click **Floating AI** in the top header. The optional companion is frameless, transparent, draggable and always on top. Drag it to move it, use Open NEXUS to return to the dashboard, or × to close only the companion. Closing NEXUS also closes the companion. The window is created only when requested and reused while open.

The avatar is actual WebGL 3D geometry: a shaded robot head, emissive eyes, ear pods and orbit rings. It uses the already-installed WebView2 runtime with no external assets, AI model, new dependency or bundled browser download. Rendering is capped at 15 FPS idle / 24 FPS active, pixel ratio at 1.5, and redundant static frames are skipped when motion is off. No microphone is opened or paid API called by the avatar.

The companion reads compact local telemetry and reflects calibration, microphone listening/level, thinking, speaking, voice errors and Emergency Stop. It does not capture speech itself: continue using NEXUS Voice, review the transcript and Send. Telemetry excludes chat history, stored memory, transcripts and API keys. Its controls use the existing local session token. Motion follows the existing core preference/OS reduced-motion setting; use Motion to choose an explicit On or Off. If WebGL is unavailable, the status/control UI remains usable with a static fallback.

Validation:
- Full Python suite: 139 passed, including lazy native-window creation/reuse, transparent/on-top/drag configuration, close/reopen, main-window return, authenticated actions and telemetry minimization.
- Chromium/SwiftShader test: actual WebGL rendering, visibly different animated frames, transparent page background, listening/input level, thinking, speaking, Emergency Stop, static Motion Off, authenticated controls and telemetry-only network requests passed.
- Existing 1366x768, 1920x1080, 800x600 and 390x844 chat-layout checks and transcript/retry flow passed. Python compilation and JS syntax passed.
- The pre-existing exact HTML/CSS baseline was updated for the new Floating AI header button. Browser tests verify the resulting responsive layout.

No access to the user's Windows laptop was available. Actual Windows WebView2 transparency/drag/topmost behavior, hardware FPS, GPU compatibility, RAM usage, microphone and speaker response are not measured. The user's screenshot reports 11.8 GB usable RAM; this is not a direct hardware scan or a performance guarantee. This branch is based on the combined preview so it retains earlier voice/chat/browser fixes; main is not merged.
