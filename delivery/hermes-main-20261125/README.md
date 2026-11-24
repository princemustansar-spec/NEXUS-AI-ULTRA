# NEXUS + Hermes integration v2

[Download NEXUS-Hermes-Integration-v2.zip](NEXUS-Hermes-Integration-v2.zip?raw=true)

[Open the tested PowerShell command](INSTALL_COMMAND.ps1)

Save the ZIP to Downloads with that exact filename. Close all NEXUS windows,
then copy the command into PowerShell. This v2 package recognizes the supplied
32,733-byte laptop app, preserving New Chat/saved sessions, active-chat checks
and Male/Female voice settings. It also supports the original stock app baseline.

Original private project notes are retained; a new integration section is appended.
Unknown code hashes still stop installation. The session-store, voice implementation,
account-provider module, GUI, database and credentials are not replaced.
Startup is checked with temporary data and failures restore applied source files.

- Full suite: **321 passed, 5 skipped**, using the real pinned Hermes runtime.
- Seven PowerShell 7.7/Linux installer checks passed, including the reviewed
  laptop app, note preservation and restoration after missing-dependency failure.
- Session-store collaborators are used in tests; unpublished store internals,
  native Windows, real providers and physical mic/speaker require laptop acceptance.
- SHA-256: `c8c39502def3931ec10ea6d5c8a73f2ca6f6e793bacaef320b4fbd7a50495d8c`

The integration remains on its feature branch and is not merged into main.
No API credentials, private project-note content, user database or portrait files
are in this download.
