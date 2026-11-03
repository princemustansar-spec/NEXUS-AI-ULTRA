# WhatsApp contact search and confirmed send

NEXUS now has its own WhatsApp Web window through the existing Windows WebView2 host. There is no additional browser download, API key or WhatsApp Business account requirement. It cannot reuse a separate Chrome/Desktop login automatically: open NEXUS WhatsApp and scan its QR once. The normal NEXUS WebView profile retains the login. No passwords, QR data, session cookies or arbitrary browser-control API are exposed to the model.

## Use

Open WhatsApp Center → **Open WhatsApp / QR login**. After linking, enter the exact saved name (for example, Saad Cheema) and message, then **Prepare & review send**. Safety Center shows the recipient, observed chat identifier and exact message. Only approving that action sends. In auto voice, the existing approval controller reads the same details and accepts `haan approve` or `nahi cancel`.

Chat can use `whatsapp_prepare(contact,message)` followed by `whatsapp_send(draft_id)`; the latter queues confirmation. `whatsapp_search` lists matching names, and `whatsapp_status` checks login or a receipt without sending. Empty draft_id checks the most recent attempt when present. Existing phone-link/manual drafts remain as a fallback.

## Verification and duplicate prevention

- Native DOM operations run only on HTTPS web.whatsapp.com in the NEXUS-owned window, with no custom JavaScript API exposed to that page.
- Names must match exactly and uniquely. Partial/duplicate names produce a clarification result. Existing user drafts, reply/edit/media previews and recipient changes are protected.
- A stable chat identifier must be visible in message IDs or an unsaved-number header. Named chats without observable identity/history, and phone links resolving only to unverified identifiers, are blocked. Open the exact chat with existing history or use the legacy manual draft path in those cases. No number is invented.
- Preparation pins the document/sidebar session, contact name, chat identity, exact composer text and current outgoing-history boundary. Final checks and the single Send click run synchronously in one DOM turn.
- Drafts and approvals expire in five minutes. Repeated approval requests for one draft reuse the same pending approval. A draft is consumed before attempting Send. A recent matching recipient/message attempt also blocks duplicate drafts from sending twice.
- A new outgoing bubble with an acceptance tick yields `sent_verified`; two ticks also yield `delivery_verified`. A pending/failed/unknown outcome is reported separately. An unclear result is never automatically retried. The status tool can observe a later tick without another Send.
- Emergency Stop blocks future sends and cancels prepared drafts. Already dispatched messages cannot be reversed.

## Testing and limits

Tests use local fake contacts and messages only. Python tests cover duplicate/partial names, exact approval metadata, existing/edited drafts, recipient/session changes, expiry, denial, Emergency Stop, one-use approval, pending/failed/accepted/delivered receipts and unknown-attempt deduplication. Chromium runs the production DOM script against intercepted fixture pages. Windows CI additionally maps web.whatsapp.com to a local fixture folder in a fresh private WebView2 profile and checks the actual native controller; a fixture marker is required before any Send action.

No live WhatsApp login or message was sent during development. Actual contact search and WhatsApp Web layout compatibility require a check on the user's laptop after QR login. If WhatsApp changes its DOM or identity/status cannot be established, NEXUS blocks or reports unknown instead of claiming success. Opening a window is not proof of login, and a single acceptance tick is not recipient delivery.

The bridge supports message IDs on a bubble, its enclosing row or a nested message container, and deduplicates editable fields inside test-ID wrappers. Dedicated chat-title metadata takes priority over profile tooltips. Quoted-message IDs cannot supply the conversation identity. When verification still fails, WhatsApp Center → Check WhatsApp / send status shows diagnostic counts (header, message rows, identifiable rows, distinct chat IDs and editable fields), without exposing message history. Share that output to diagnose an unsupported layout instead of repeatedly reopening an old chat.
