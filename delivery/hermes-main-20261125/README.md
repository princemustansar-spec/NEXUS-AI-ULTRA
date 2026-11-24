# NEXUS + Hermes integration v3

[Download NEXUS-Hermes-Integration-v3.zip](NEXUS-Hermes-Integration-v3.zip?raw=true)

[Open the tested PowerShell command](INSTALL_COMMAND-v3.ps1)

Save the ZIP to Downloads with that exact filename. Close all NEXUS windows,
then copy the command into PowerShell. This v3 package recognizes the supplied
32,733-byte laptop app, preserving New Chat/saved sessions, active-chat checks
and Male/Female voice settings. It also supports the original stock app baseline.

Original private project notes are retained; a new integration section is appended.
Unknown code hashes still stop installation. The session-store, voice implementation,
account-provider module, GUI, database and credentials are not replaced.
Startup is checked with temporary data and failures restore applied source files.

- Fixes Windows PowerShell removing quotes from Python `-c` arguments. All three
  probes now use a hash-verified Python helper file and file-based schema transport.
- Full Linux suite: **323 passed, 6 skipped**, using the real pinned Hermes runtime.
- Nine PowerShell 7.7/Linux installer checks passed, including Legacy argument
  passing with spaces in paths and modified-helper refusal before execution.
- Native Windows CI: **307 passed, 22 skipped**, including real PowerShell 5.1
  version/schema/fixture-startup probes. Existing WebView2 and updater checks passed.
  [Test run](https://github.com/princemustansar-spec/NEXUS-AI-ULTRA/actions/runs/45497479290)
- Session-store collaborators are used in tests; unpublished store internals,
  the full native Hermes installation, real providers and physical mic/speaker
  still require laptop acceptance.
- ZIP SHA-256: `0aa037fbe940b74307f99bf9bf1cf2513d89e5003ed362c5b21d8a53a69d16dc`

Older v1/v2 archives are retained unchanged. Use the v3 ZIP and matching command.

The integration remains on its feature branch and is not merged into main.
No API credentials, private project-note content, user database or portrait files
are in this download.
