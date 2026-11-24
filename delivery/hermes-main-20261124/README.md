# NEXUS + Hermes integration download

This folder contains the unchanged, tested integration ZIP built from source commit
`96f912186e57bd0bc8e51711a8b1c5e652ffa7fe`.

- **Download:** [NEXUS-Hermes-Integration.zip](NEXUS-Hermes-Integration.zip?raw=true)
- **Installation command:** [INSTALL_COMMAND.ps1](INSTALL_COMMAND.ps1)
- SHA-256: `d1f03fa7b23f4befa3000c7448853b4f1db8055f05da5a9dc46f17780d05b327`
- Size: 63,088 bytes.

Save the ZIP in Downloads under its exact filename. Close all NEXUS windows, then
copy the installation command into PowerShell. It verifies the source baseline,
existing Hermes build and package hashes before applying the integration.

The source build passed **319 tests**, with **5 skipped**. The command and installer
were exercised with PowerShell 7.7 on Linux and the real pinned Hermes runtime.
Native Windows, live user providers and physical mic/speaker acceptance remain
pending. The package contains no API keys, user database, private portraits or
Hermes models/dependencies.

Publication of this source and package was authorized by the user on
24 November 2026 after local validation. The ZIP's PROJECT_STATE.md retains its
pre-publication build snapshot. This delivery does not merge the integration
into main.
