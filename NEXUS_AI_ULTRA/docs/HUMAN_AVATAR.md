# NEXUS digital human face

The floating avatar now defaults to an original stylized human portrait: warm facial shading, eyes/irises, eyebrows, a nose, lips, swept dark hair and thin cyan NEXUS accents. Meshes are generated once with the existing WebGL renderer; there are no downloaded models, image/video generators, camera capture or additional dependencies.

Eyes blink and make small pointer-following movements inside the avatar window. Happy, caring, curious and friendly expressions change eyes, brows and lips. The mouth opens/closes while NEXUS's existing speech state is active. This is speech-state animation, not word/phoneme-accurate lip synchronization or audio emotion detection. Motion Off/reduced-motion preferences freeze continuous motion. Existing transparent background, hover controls, drag, mic consent, mute, Stop & listen and approvals are retained.

Settings → Personal Assistant → Floating face chooses **NEXUS human face** or **Classic robot**. Save personal settings; an open floating window receives the choice through its compact local telemetry. Expressive avatar can still be disabled independently. No profile migration or reset is required.

Friendly & playful conversation now explicitly allows occasional situational humor/gentle teasing when appropriate and practical empathy when the user's words express difficulty. Calm emphasizes supportive phrasing; Short stays warm and concise. Serious or failed-action discussions remain clear and respectful. This changes reply instructions, not the speech-recognition engine, pronunciation pipeline or voice selection.

Browser tests inspect rendered mouth pixels in idle/speaking states, distinguish happy/caring expressions, switch live between human and robot and enforce telemetry-only requests/transparency. The existing real Windows mouse/hover/mic regression remains required. Appearance and playback should also be checked on the user's Intel UHD laptop after updating.
