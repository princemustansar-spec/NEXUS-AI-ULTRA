# ChatGPT and Claude account connections

Open Settings → ChatGPT and Claude accounts. Existing API providers, keys, saved data, voice controls and approvals remain available. Nothing launches a sign-in or spends account usage just by opening Settings.

## ChatGPT

1. Click **Continue with ChatGPT**. Sign in and review the plan-usage permissions in your system browser.
2. Return to NEXUS and click **Check connection**. A signed-in identity is distinct from a working inference connection.
3. Click **Load account models**, choose one and **Save account model**. Leaving the model unselected uses the first model in the account's returned catalog.
4. Click **Test response (uses plan credits)**. Only a completed response containing text marks the connection tested.
5. Click **Use for chat and voice** to enable and select this account. Usage consumes the plan's limits or credits; extra usage can cost money according to the account's settings.

NEXUS registers under its own name and host ID. It does not import JARVIS, Codex or browser credentials. OAuth uses PKCE, random state and nonce, signed ID-token validation, loopback callbacks, and token refresh. Credentials are encrypted for the current Windows user with DPAPI and stored under `%USERPROFILE%\.nexus_ai_ultra\accounts\chatgpt` (or `NEXUS_DATA_DIR`), outside the source installation. They are not returned through the API or stored in SQLite. Disconnect clears the local session and attempts remote revocation; check ChatGPT settings for the remote connection.

This uses the official open-source Sign in with ChatGPT flow and public Responses endpoint. It does not access ChatGPT history or memory and does not unlock ChatGPT app voices or Realtime audio. Spoken transcripts and replies continue through existing NEXUS speech settings.

## Claude

Install the official native Claude Code using **`winget install Anthropic.ClaudeCode`**, then restart NEXUS if PATH changed. NEXUS also checks the default native installation path.

Click **Open official Claude login**, finish signing in in the official CLI/browser, then **Check connection**, **Test response (uses plan credits)** and **Use for chat and voice**. This adapter accepts Claude-account authentication; it does not silently switch to an API key. Check your plan's applicable usage limits and credits. If CLI options are unsupported, update Claude Code and test again.

NEXUS launches the unmodified native executable and never reads Claude token files. For inference, native tools and MCP tools are disabled, user/project customizations are skipped, hooks disabled, and session persistence disabled. Claude returns a structured text/tool proposal. NEXUS's existing tool runner handles those proposals with its ordinary approvals; no Claude permission bypass is enabled. **Disable in NEXUS** leaves your independent Claude Code login untouched.

Both connections remain disabled until explicitly enabled after a successful test. Selecting an account does not silently fall back to another provider on account errors. The account adapters do not provide image generation or new speech engines.

## Validation and limits

Automated checks cover the loopback OAuth callback with incorrect/correct state, PKCE exchange, JWT signature/audience/expiry/nonce, token refresh, DPAPI round trips on Windows, completed-stream handling, mixed text/tools, authenticated activation and usage consent, CLI arguments, subprocess timeout cleanup and Settings interactions. Windows tests also retain the real floating avatar drag/hover/mic checks.

No real user account login or subscription inference was performed in the development environment. Those need to be completed on the user's laptop using the Settings test buttons. Signing in alone is never reported as a successful response test.

Official references:

- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://code.claude.com/docs/en/legal-and-compliance
- https://code.claude.com/docs/en/cli-reference
