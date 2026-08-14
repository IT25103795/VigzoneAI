# Vigzone AI Desktop and Vigi

The desktop build wraps the production Vigzone web app in a secure Electron window and adds a separate transparent Vigi companion window. Render remains the web/API deployment; the desktop package is an optional Windows client.

## What works

- Vigi remains available when the main Vigzone window is minimized or hidden.
- Right-click Vigi to open Vigzone, collapse the message box, or close the pet.
- The tray icon can restore Vigi after it is closed and can enable launch at Windows sign-in.
- Quick-chat messages run inside the already loaded, authenticated Vigzone window.
- The message is appended to the last opened conversation with its current model, plan quota, project context, and chat history.
- Vigi shows a short reply preview. **Open full conversation** restores the same chat for the complete reply.
- Vigzone checks the configured GitHub Releases channel after desktop startup and every six hours.
- The collapsed-sidebar download button and Settings both show the installed version, latest release notes, and official installer link.
- Vigi can announce a newer release; the user still chooses when to download and run the installer.

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

## Publishing desktop updates

The release checker reads Windows installers from GitHub Releases. Configure Render with:

```text
VIGZONE_DESKTOP_RELEASE_REPO=IT25103795/VigzoneAI
VIGZONE_UPDATE_CHANNEL=stable
VIGZONE_UPDATE_CACHE_SECONDS=300
```

`stable` ignores draft and prerelease entries. Use `beta` only when beta users should receive prerelease notifications. `GITHUB_RELEASES_TOKEN` is optional and must remain server-side; it only raises GitHub API limits or lets the server inspect a private repository. Public users cannot download private release assets without GitHub access, so production installers should be published from a public release repository.

For every Windows release:

1. Increase `version` in `package.json` (and the lockfile) before building.
2. Run the tests, `npm audit --omit=dev`, and `npm run desktop:make`.
3. Create a GitHub Release whose tag contains that version, such as `v1.0.1`.
4. Upload the generated `*Setup.exe` asset and write clear release notes.
5. Publish the release. Drafts are never offered, and stable clients ignore prereleases.

The current workflow is intentionally notification-and-download only: it never silently installs an unsigned executable. Once both the application and installer are code-signed, a separately reviewed in-app installer workflow can be added safely.
