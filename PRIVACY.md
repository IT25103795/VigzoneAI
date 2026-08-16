# Privacy

Vigzone stores data for the signed-in account only. Automatic global "self-learning" has been removed.

Zoner v0 performs no model training. Its checked-in evaluation corpus is product-authored and synthetic; private chats, uploads, memories, workspaces, team data, and feedback are not silently converted into training data.

## Stored locally on the server

- Account profile, password hash or Google account identifier, verified role, and hashed sessions.
- Encrypted personal Groq key when a user activates one.
- Explicit Learning Center memories.
- Brain snapshot, conversations, workspaces, feedback, public-share metadata, and usage records.
- Rate-limit counters and one-time verification/reset token digests.

The server does not persist raw uploaded files after a request. It temporarily writes upload bytes only for malware scanning and removes that file afterward.

## Browser storage

Chat history, UI preferences, and file-history metadata are scoped to the signed-in account. Signing out switches the browser to a separate guest scope without exposing the previous account's data. Large generated-image data may be omitted from persistent browser history when browser quota would be exceeded; the current tab still shows the result.

Verification, password-reset, and public-share URLs are not stored by the offline service worker.

## Third-party processing

- Chat, vision, and transcription content is sent to Groq.
- Image prompts/source images are sent to OpenAI when configured, otherwise to the labelled Pollinations fallback.
- Live queries may be sent to the source APIs/search providers shown in the response context.
- Google sign-in/Drive and SMTP are used only when configured and invoked.

Do not upload information that the configured providers are not permitted to process.

## User controls

- Learning memories can be viewed, paused, edited, and deleted.
- Public chat links expire in 1–30 days and can be revoked.
- Account data can be exported from Settings.
- Account deletion removes the user row and cascades through all server-side user data, then removes that account's scoped browser data on the current device.

Backups may retain deleted records until the deployment operator's backup-retention window expires. Operators should document that window for their users.
