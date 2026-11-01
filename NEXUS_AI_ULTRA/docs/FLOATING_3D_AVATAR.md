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

Audio/model/tool responses and native host APIs are mocked in these tests; the rendering tests use Chromium/SwiftShader. The user's Windows WebView2 transparency, real microphone/speaker turn-taking, recognition quality, acoustic echo, voice approval reliability, all real tool outcomes, GPU/FPS and RAM usage are not verified remotely. The screenshot showed 11.8 GB usable RAM, not a direct hardware scan or a performance guarantee. Test the preview on the actual laptop before relying on hands-free operation. Merge status is tracked on the pull request; earlier preview restrictions were superseded by the user-authorized consolidation.

## Native background and one desktop shortcut update

The white rectangle reported on Windows was outside the HTML scene: pywebview's Edge control alpha did not make its WinForms parent transparent. The avatar now applies an explicit colour key to the native parent and native WebView2 control on the UI thread (shown/loaded callbacks), while keeping the actual WebView2 background transparent. Only the companion uses this native cutout; the dashboard and YouTube window are unaffected. The selected RGB 1/2/3 key avoids keying normal robot/ring colours. Native colour-key behavior and click-through still need checking on the user's real Windows/GPU setup; browser alpha screenshots alone cannot prove that result.

Every avatar button and caption is now hidden outside hover/keyboard focus, including the microphone button. A brief 600 ms hover grace period lets the pointer travel from the figure to a control across transparent desktop pixels. Live listening/thinking/speaking/approval/error colour feedback remains in the figure. Showing from the normal GUI no longer hides the dashboard.

**Settings → Floating AI** provides Show, Hide, auto-voice preference, Desktop shortcut opens (Dashboard / Floating AI only), Save, and Update desktop shortcut. Turning auto voice off stops the running auto-voice session. Showing with auto voice unchecked does not start capture. The saved desktop mode applies on the next launch of the same NEXUS AI ULTRA desktop shortcut. Explicit START_FLOATING_NEXUS.bat still forces floating mode; START_GUI_NEXUS.bat / --gui is a dashboard recovery override.

The updater repairs the same desktop shortcut to the updated .venv Python source, preserving the existing SQLite/keys. Source shortcut helpers now prefer updated source over a retained old portable EXE, so an old EXE cannot silently reopen after a source update. The GUI shortcut-repair action is session-protected. No login/autostart registry task is added; the normal desktop shortcut honors the saved mode. The updater's default revision is now main.

Validation for this follow-up: 167 Python tests passed, including native parent/control cutout properties, UI-thread dispatch, preserved GUI visibility, validated/persisted preferences, auto-voice shutdown on opt-out, saved/explicit launch modes and source-over-old-EXE shortcut repair. Chromium tests passed for hover-only controls, transparent scene, Settings save/show/hide, mic opt-out and shortcut action; existing four-size chat layout/manual transcript checks passed. Native Windows visual transparency, desktop mouse hit-through, actual user shortcut/OneDrive permissions and audio hardware remain unverified remotely; Windows CI tests use explicit native doubles.

### Quiet listening and mouse movement

Hold the left mouse button on the avatar itself and move it to drag the floating window. Windows follows the physical screen cursor while the left button is held, using SetWindowPos without a caption move loop; other hosts retain the marked pywebview drag region. Hover controls remain independent buttons.

Auto voice listens for speech but stays silent during empty or unrecognized recordings. It sends no chat request for these clips and no longer greets or announces pending actions on startup. A sustained speech onset reduces accidental clicks being treated as speech. Actual microphone failures pause the session with a visual error instead of repeatedly speaking. Replies and action errors are spoken only after a recognized user request. Speaker failures also stop without a repeated speech attempt. Existing action and paid-request approvals still apply.

Click the mic control to stop listening completely. Native Windows movement and microphone behavior still need a check on the user's laptop; automated tests cover dispatch, held-button guards, authentication and simulated silence/error cycles.

### Windows hover and drag regression

A color-keyed WinForms parent can look transparent while making its entire GPU-rendered WebView click-through. The avatar now uses DWM glass with an empty native TransparencyKey, plus a transparent WebView background. This preserves mouse input without restoring a backing rectangle. The Windows integration check opens the actual WebView2 avatar, verifies a blank corner reveals the underlying window, injects real cursor/button input, and checks left/right movement, release, hover controls, Motion and Open NEXUS. It uses temporary data and does not start the microphone or call an AI provider.
