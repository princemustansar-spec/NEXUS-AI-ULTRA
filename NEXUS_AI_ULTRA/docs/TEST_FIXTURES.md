# Synthetic WhatsApp test contacts

WhatsApp fixtures use the generic display names **Nexus Test Contact**, **Other Contact** and **Wrong Contact**. They are test labels, not user contact records.

Phone-shaped fixture values use the reserved fictional North American range **+1 202 555 0100–0199**. The primary fixture is +1 202 555 0101; mismatch/quote fixtures use other values in that range. Tests do not log in to an account or send real messages.

Opaque message IDs are generated locally from fixed test strings. Assertions derived from the reported bug use only structural counts (22 message containers/IDs, no legacy prefixes/classes); no uploaded report, contact name, real phone number, chat text or private identifier is committed.

The live-avatar suites draw synthetic portraits in Canvas and generate test PNGs
with fixed colours. `tests/fixtures/avatar-tone.mp3.b64` is a generated 220 Hz
tone, not a voice recording. No personal portrait, expression sheet or private
avatar pack is included in tests or public source.
