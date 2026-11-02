# Voice latency and interruption

The user reports typed replies are already fast and spoken replies are slow. This change targets the voice path and leaves typed chat delivery unchanged.

- Roman Urdu's Uroman converter is retained inside the reusable microphone worker instead of rebuilding its language tables for every utterance. A local fixture measured about 2046 ms for its first load and 0.3 ms for reuse; this is a cloud development measurement, not a laptop benchmark.
- Installed Windows speech initializes once per completed reply instead of once per small chunk. If optional online speech fails, it is not retried on every remaining chunk of that reply.
- ChatGPT requests reuse a bounded keep-alive HTTP connection pool. Credentials remain attached per request, never as shared client headers.
- Ordinary answers are concise by default, with detail when asked. No account model is silently switched, and no new provider/reasoning parameters are imposed.

## Interrupt a spoken reply

Auto voice defaults to **Any speech** as requested. While NEXUS speaks, an interruption microphone probe listens. With an initially quiet microphone (typically headphones), sustained new input can stop playback before transcription completes; the same recording continues so the user's full follow-up is preserved. Otherwise recognized speech differing from the current reply can interrupt. After recognition, the follow-up enters the existing chat/tool/approval loop.

This is speech detection plus a basic text echo guard, not acoustic echo cancellation. Laptop speakers can confuse the detector; **headphones are recommended for reliable Any speech interruption**. Immediate detection depends on microphone level and a quiet baseline. Recognition still takes time, and this feature is not a promise of instant full-duplex conversation on every device.

Settings → Floating AI → Voice interruption offers **Any speech (use headphones)**, **Say Nexus ruko**, and **Off — button only**. Save and restart auto voice to apply. Wake mode also accepts `Nexus stop`; words after the stop phrase become the follow-up.

Hover over the avatar and click **Stop & listen** for a reliable manual interruption. The normal Voice Assistant page also has **Stop reply & listen**. These stop the current auto-voice reply while retaining the session. The mic button still pauses/stops auto voice completely. Interruption does not approve tools, enable paid requests, or clear existing pending approvals.

Interruption means the microphone may capture during speech output. With Google recognition, captured speech clips go online under the existing continuous-microphone/online consent. Off mode closes the capture during output and retains the manual button. A cancelled probe is discarded without transcription/upload; reusable workers remain warm. Silence never causes spoken complaints. Speaker-only manual playback outside auto voice does not use the interruption listener.

Automated validation uses simulated audio/status and speaker services. It checks early playback stop before a transcript, preservation of a complete follow-up, no-wake-word interruption, basic echo rejection, optional wake mode, authenticated manual interruption, microphone discard without recognition, resource reuse and existing approvals/mute/stop regressions. Real microphone echo and latency require a laptop check. No real user account request or microphone recording was made during development.
