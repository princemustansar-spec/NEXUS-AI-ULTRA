# Figure-only floating AI with auto voice

Install this source revision, close previous NEXUS windows, then run **START_FLOATING_NEXUS.bat** from the existing installation. It starts the native app with the dashboard hidden, opens the optional transparent robot/rings window and explicitly enables the auto-voice session. It does not register a Windows login task or change the existing normal launcher. START_UPDATED_NEXUS.bat still opens the normal dashboard; its Floating AI button opens the companion and starts auto voice.

The permanent rectangular panel, title, large status area and Open NEXUS section have been removed. The real WebGL robot/rings float on a transparent page, with motion approximately 1.8 times the prior speed at the same 15 FPS idle / 24 FPS active cap. Hover/focus reveals small motion/close/dashboard controls. A small microphone control remains visible: green indicates an enabled auto-voice session; click it to pause. Drag the figure/window to move. Open NEXUS restores the dashboard when needed; closing the companion stops auto voice and returns to the main window. Closing NEXUS shuts down the companion and owned media window.

## Voice flow

The session repeatedly captures a bounded speech clip, transcribes it, automatically submits the transcript to the existing chat/tool engine, speaks the response, and listens again. It is half-duplex: recording does not run during the app's own TTS output, followed by a short cooldown. It is not full-duplex streaming or acoustic echo cancellation; media playback/background speech may interfere, and headphones can help. Quiet clips do not generate chat/provider requests. No startup capture occurs unless the user invokes the floating launcher, Floating AI, or the avatar's microphone start control.

Use **mic band karo** / **stop listening**, or the microphone button, to stop. Start remains subject to microphone/session consent, configured voice mute, existing operation checks and Emergency Stop. Google recognition mode sends successive captured clips online while the session is enabled; offline mode uses the installed local model. TTS is installed Windows speech by default. An explicit online-speaker preference from the normal UI can be saved for later starts; it is not enabled implicitly.

The session uses the existing configured recognition language/device and existing enabled tools/providers. It does not bypass tool permissions, approved file roots, tool schemas, URL validation, paid API restrictions or Emergency Stop. A manual chat/capture should be paused while auto voice owns the session. The normal GUI does not separately consume/re-submit hands-free transcripts.

## Spoken approvals

The controller reads only real queued tool approval IDs and their exact arguments. Say **haan approve** / **yes approve** to approve, or **nahi cancel** / **no cancel** to deny. A casual bare “haan” or unrelated sentence is not sufficient. It also recognizes the original Urdu confirmation/stop phrases so Roman transliteration does not lose control intent. Existing single-use/expiry and disabled-tool checks still run at execution. Long action details are read in bounded TTS chunks before confirmation capture resumes, rather than requiring the GUI. The microphone button remains available to stop a long prompt.

If a free provider cannot answer and a paid request would be needed, the controller explicitly asks before retrying. Permission applies only to that turn, never future turns. The model itself cannot grant approval. Speaking a request does not waive sensitive-tool confirmation. The controller waits for its approval prompt to finish before opening capture again. Voice confirmation is not biometric speaker authentication.

## Limits and validation

No dependency, AI model, browser download, startup registry task or PC-lock command was added. Laptop-start welcome/PC locking are intentionally deferred to the next upgrade. All existing source data/key namespaces and paid/file controls are preserved; new settings are stored in existing SQLite JSON settings without a migration.

Full Python suite: **155 passed**, including auto-submission, speak/listen order, Urdu controls, ambiguous/denied approvals, paid-turn isolation, consent, stop/cleanup, authenticated endpoints, speaker preference persistence and explicit floating-only launch. Browser tests passed for the transparent figure-only layout, 3D motion/state reactions, auto-voice button start/pause, unchanged four-size chat layout and manual transcript flow. Compilation/JS syntax passed. The exact HTML/CSS baseline was updated for the requested header help text.

Audio/model/tool responses and native host APIs are mocked in these tests; the rendering tests use Chromium/SwiftShader. The user's Windows WebView2 transparency, real microphone/speaker turn-taking, recognition quality, acoustic echo, voice approval reliability, all real tool outcomes, GPU/FPS and RAM usage are not verified remotely. The screenshot showed 11.8 GB usable RAM, not a direct hardware scan or a performance guarantee. Test the preview on the actual laptop before relying on hands-free operation. Main remains unmerged.
