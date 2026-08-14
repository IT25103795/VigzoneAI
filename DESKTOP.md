# Vigzone AI Desktop and Vigi

The desktop build wraps the production Vigzone web app in a secure Electron window and adds a separate transparent Vigi companion window. Render remains the web/API deployment; the desktop package is an optional Windows client.

## What works

- Vigi remains available when the main Vigzone window is minimized or hidden.
- Right-click Vigi to open Vigzone, collapse the message box, or close the pet.
- The tray icon can restore Vigi after it is closed and can enable launch at Windows sign-in.
- Quick-chat messages run inside the already loaded, authenticated Vigzone window.
- The message is appended to the last opened conversation with its current model, plan quota, project context, and chat history.
- Vigi shows a short reply preview. **Open full conversation** restores the same chat for the complete reply.

## Development

1. Install Node.js 22.12 or newer.
2. Run `npm install` once.
3. Start the normal local Vigzone server on port 8000.
4. Run `npm run desktop:dev`.

To use a different secure deployment URL:

```powershell
$env:VIGZONE_DESKTOP_URL='https://your-vigzone-domain.example/chat'
npm run desktop
```

## Windows package

Run `npm run desktop:make`. Electron Forge writes the Windows installer artifacts under `out/make/`.

Before public distribution, sign the installer and application executable with your Windows code-signing certificate. Never package `.env`, database, upload, or test data; the Forge configuration explicitly excludes those paths.

`npm audit --omit=dev` must remain at zero before release. Electron Forge and its packager are development-only dependencies; run installer builds only in a trusted CI/workstation environment and review their current advisories during every desktop release.
