# Voice transcript chat context

The reported microphone session produced readable text and an AI reply saying it could not hear or accept voice. Capture and transcription succeeded. The chat handler previously sent no voice provenance and its system message omitted the app's speech-to-text integration, allowing the text model's generic capability disclaimer.

Changes:
- Completed microphone transcripts retain a voice source marker through review, Send, and failed-send retry. Successful Send or clearing the input resets the marker for typed follow-ups.
- Chat validates and stores the source alongside existing SQLite JSON records; no schema change is needed. Older clients default to text.
- The system context explains NEXUS microphone transcription and optional speech output, asks the model to answer the transcript normally, and explicitly distinguishes transcript text from raw audio or live listening.
- Review-before-Send, optional speaker output, paid approval, tool approvals, capture engines and saved keys remain unchanged.

Validation: 20 Python tests passed (4 new async HTTP chat tests plus 16 router tests). The Node frontend flow test passed for capture, review, failed-send retry, typed follow-up, and cleared-transcript replacement. Python compilation and JavaScript syntax checks passed. Tests inspect the real inference-bound message context with a mocked provider; actual third-party model adherence and Windows microphone/speaker hardware were not tested.


## Urdu recognition follow-up

The UI previously paired Urdu/Roman Urdu output with an en-IN Google recognition default. Automatic locale now uses ur-PK for Urdu and en-IN for English/unspecified speech; explicit saved locales remain unchanged. The app stores the automatic preference while passing a resolved locale to the worker. Users with an existing en-IN selection can choose automatic or ur-PK in Voice Assistant.

Original script is retained in the response and is now shown in a collapsible, height-bounded review area beside the editable Roman Urdu transcript. Text is inserted with textContent. No dictionary rewriting or additional AI correction calls alter names, numbers or commands. Transliteration spelling remains approximate; actual microphone accuracy has not been measured.

Follow-up validation: 31 Python tests passed (locale selection, chat context and router); updated Node capture/review/retry test passed including original-script visibility and hiding after Send. JavaScript syntax and Python compilation passed. No live recognizer or hardware accuracy measurement performed.
