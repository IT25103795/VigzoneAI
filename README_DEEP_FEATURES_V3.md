# Vigzone AI Deep Features v3

Implemented practical deep-product upgrades:

- Workspaces: per-user project spaces with private notes/context.
- Smart Modes: General, Website Studio, Code Fixer, Study Helper, File Analyzer, Business Writer, Voice.
- Workspace-aware chat context.
- File Intelligence: quick local summary/keywords/risks for uploaded text files.
- Chat Export: TXT and HTML download.
- Website ZIP export backend endpoint.
- PWA manifest for installable app foundation.
- Existing Groq production, Learning Center, Usage Cycle, Admin, Voice, and Website Studio remain included.

Notes:
- Workspaces and notes are private per account in SQLite.
- File Intelligence is a fast local analysis layer; users can still ask the AI to deeply analyze the attached file.
- Payment plans/WhatsApp integration are intentionally not enabled in this build.


## UI fix

- Usage cycle popup now closes when the user taps/clicks anywhere outside the cycle button, including mobile touch events.


## UI fix 4

- Floating Usage and Export menus now close reliably when the user taps/clicks anywhere outside them.


## UI fix 5

- Floating Usage and Export menus now use an invisible full-screen backdrop so tapping anywhere outside them reliably closes them.


## UI fix 6

- Fixed floating menus staying visible after close by clearing the inline `display` style, not only removing the `visible` class.
- Usage popup, Export menu, close buttons, and outside tap now all force-hide the menu correctly.


## UI fix 7

- Export TXT / Export HTML button clicks are preserved by treating clicks inside the export menu as inside-menu events, while outside taps still close the menu.


## PDF Upload Fix

- PDF uploads no longer fail just because the PDF has no selectable text layer. Scanned/image-based PDFs are accepted with a clear note.
- Upload limit is now 25 MB by default and can be changed with `MAX_UPLOAD_SIZE_BYTES`.


## Groq Vision Model Fix

- Replaced deprecated `llama-3.2-11b-vision-preview` with `meta-llama/llama-4-scout-17b-16e-instruct`.
- Added `GROQ_VISION_FALLBACK_MODELS` support.
- Vision requests now retry fallback models if Groq returns a decommissioned-model error.

## Final PDF accept fallback

- PDFs are now accepted even if backend text extraction fails.
- The frontend also treats failed PDF uploads as accepted with a fallback note instead of turning the chip red.
- For scanned/design PDFs, users should upload screenshots/images of pages when they need visual analysis.


## Voice language detection fix

- Voice recorder now always asks server-side Groq transcription too, because browser SpeechRecognition can mishear Sinhala as Hindi.
- Hands-free mode now records each turn and sends it to `/api/transcribe` for language-aware transcription.
- Backend tries the first words plus language candidates and scores Sinhala/Tamil/Hindi/English output.
- Optional Railway variable: `VOICE_TRANSCRIPTION_LANG_PRIORITY=si,ta,en,hi`.

## Groq rate-limit clarity and fallback

- The usage circle is Vigzone's local app-side usage estimate, not Groq's real live quota.
- Groq can still return 429 earlier because Groq limits are organization/project/model-level.
- Default backup models are now configured:
  `openai/gpt-oss-20b,llama-3.1-8b-instant,qwen/qwen3-32b`
- Override backups in Railway with `GROQ_BACKUP_MODELS`.


## Gemini-style + menu

- Redesigned the composer + menu to look like a modern tool drawer.
- Added Upload files, Add from Drive placeholder, More uploads, Create image, Create video placeholder, More tools, and Smart Mode chips.
- Composer button now shows only a clean + mark.


## Gemini-style plus menu

- Redesigned the composer + menu to a Gemini-like tools panel.
- Added Upload files, Add from Drive placeholder, More uploads, Create image, Create video placeholder, and More tools.
- Smart modes now live under More tools.


## Plus button click fix

- The composer + button now opens on pointerdown and click.
- Disabled the old full-screen floating backdrop from blocking composer clicks.
- Added forced inline show/hide for the plus menu.


## Plus final and sidebar overflow fix

- Removed duplicate + button toggle handlers that opened and immediately closed the menu.
- Added one pointerdown handler for the + button.
- Sidebar now scrolls correctly on smaller screens so My Usage / Export Chat / Admin are not clipped.

## Down arrow scroll button fix

- The down-arrow button now floats above the composer/message box like ChatGPT.
- It appears only when the user scrolls up away from the latest message.
- Pressing it smoothly scrolls to the bottom of the chat.
- The old composer-middle arrow button is hidden.

## Voice transcription and no-time greeting fix

- Voice transcription now tries Groq auto-detect first instead of burning multiple language attempts first.
- Added transcription model fallback with `GROQ_TRANSCRIPTION_MODELS`.
- Voice recorder keeps browser transcript as fallback if Groq transcription fails.
- Hands-free mode records audio and also runs browser recognition as fallback.
- Lowered hands-free mic level threshold for quieter microphones.
- Vigzone no longer announces date/time in casual greetings; it only mentions time/date when the user asks or the answer needs it.

## Custom chat wallpaper settings

- Added a Settings row below Export Chat in the sidebar.
- Moved account identity and Sign out into Settings.
- Added Chat theme controls:
  - browse a local image from the user's device
  - apply it as the chat wallpaper
  - adjust blur
  - adjust brightness
  - remove wallpaper
- Wallpaper is saved in browser localStorage only; it is not uploaded to the server.

## PWA desktop icon fix

- Added PNG PWA icons generated from the real Vigzone SVG logo.
- Updated `manifest.json` to include 64/128/192/512 icons and maskable icons.
- Added cache-busting query strings so browsers re-fetch the manifest/icon.
- Users may need to uninstall/reinstall the desktop app because Windows caches installed app icons.

## Bottom blur bar removal

- Removed the horizontal fade/blur bar behind the composer area in both light and dark modes.
- The area behind the message box now shows the normal Vigzone background or the user's custom wallpaper.

## Roller-door composer shield

- Chat bubbles no longer scroll visually under the message box.
- The bottom composer area now acts like a roller door: messages disappear behind it while the normal theme or custom wallpaper remains visible.
- No blur/fade bar is used.

## Roller-door double-layer fix

- Removed the extra top strip/layer that appeared above the composer after the roller-door effect.
- The composer now uses one clean background shield only inside its own area.

## Final roller-door fix: no visual layer

- Removed the composer shield/background layer completely.
- Composer is now a real bottom section in the flex layout instead of an absolute overlay.
- The chat scroll area ends above the composer, so messages cannot pass under the message box.
- This removes the two-layer wallpaper strip issue.


## Clean composer dock fix

- Removed all earlier stacked bottom/composer patches.
- Composer is now docked below chat as a normal flex item.
- Messages no longer slide behind the message box.
- Removed duplicate/dark wallpaper layer caused by stacked overlay patches.

## FINAL single composer layout repair

- Removed stacked composer/roller-door/blur patches.
- Header, chat, and composer are now one CSS grid: auto / minmax(0, 1fr) / auto.
- Chat bubbles are clipped inside the chat row and cannot pass behind the message box.
- The original compact composer design is preserved.


## New chat greeting visibility card

- Added a glass-style background card behind the new-chat greeting information.
- Works in both light and dark themes.
- Improves readability over custom wallpapers and the default Vigzone background.

## Remove user message label

- Removed the `You` avatar/label from user messages.
- Assistant avatar remains unchanged.
- Added CSS fallback to hide any old user avatar from cached messages.

## High-quality image generation upgrade

- Image provider now defaults to `IMAGE_API_PROVIDER=auto`.
- If `OPENAI_API_KEY` is present, Vigzone uses OpenAI GPT Image with high quality PNG output.
- If no OpenAI key is present, Vigzone falls back to Pollinations with Flux + enhanced prompts.
- Added server-side prompt enhancement before generation/editing.
- Increased max prompt length to 3000 chars for detailed accurate prompts.
- Recommended Railway variables:
  - `IMAGE_API_PROVIDER=auto`
  - `OPENAI_API_KEY=...`
  - `OPENAI_IMAGE_MODEL=gpt-image-1`
  - `OPENAI_IMAGE_QUALITY=high`
  - `OPENAI_IMAGE_OUTPUT_FORMAT=png`
  - `IMAGE_PROMPT_ENHANCER=auto`
  - `IMAGE_PROMPT_ENHANCER_MODEL=llama-3.1-8b-instant`

## Vigzone Brain

- Added a visual project memory room in the sidebar.
- Automatically organizes chat history into categories: Projects, Code, Designs, Websites, Study, Files, Business, Personal, and General.
- Includes:
  - Overview dashboard
  - memory cards
  - unfinished task tracker
  - project timeline
  - recent files/images
  - pinned/done states
  - continue-from-here button
  - search
  - export Brain as JSON
- Data is built from local chat history and saved in browser localStorage.

## Collapsed sidebar quick-access icon rail

- When the sidebar is collapsed on desktop, it now stays as a slim icon-only rail.
- Quick access icons remain visible: Appearance, Workspace, Learning, Vigzone Brain, My Usage, Export Chat, Settings, and Admin when enabled.
- Full labels/history/API panel are hidden only in collapsed mode.
- Mobile behavior remains drawer-style.

## Floating blurred quick launcher

- Replaced the collapsed sidebar's white/dark icon rail with a single blurred arrow button near the composer.
- When collapsed, quick icons stay hidden inside the arrow button.
- Tapping the down arrow expands the tools upward in a blurred popup.
- The arrow becomes an up arrow; tapping again collapses the tools downward.
- Works for Appearance, Workspace, Learning, Vigzone Brain, My Usage, Export Chat, Settings, and Admin when enabled.

## Full-screen floating top controls

- Removed the visible white/dark top navigation bar.
- Header controls now float directly on the chat theme/wallpaper as blurred glass buttons.
- Toggle history, Vigzone logo/status, usage cycle, and new chat remain visible in both light/dark themes.
- Chat area now uses the full top space with safe padding so messages do not hide under the controls.

## Remove assistant response logo

- Assistant response bubbles no longer display the Vigzone logo/avatar.
- Header and app branding remain unchanged.
- JS avatar element remains hidden in the DOM so streaming/loading code stays stable.

## Mobile sidebar New Chat and Pin Chat update

- Replaced mobile sidebar New Chat text with an icon-only compose button to avoid truncation.
- Removed the duplicate top-right New Chat button beside My Usage.
- Moved the Your AI/settings tools block directly under New Chat so Recent Chats scroll below it.
- Added Pin Chat button before Delete Chat in the recent chat list.
- Pinned chats appear first and keep a pinned style.

## Unified sidebar scroll fix

- Removed the separate internal scroll from the Your AI/tools section.
- The full sidebar content now scrolls as one list: New Chat, tools, Recent Chats, and chat history.
- Prevents the Your AI panel from being clipped/truncated while scrolling.

## Stable New Chat sidebar scroll

- New Chat now stays fixed below the sidebar brand.
- The tools section and Recent Chats scroll together underneath New Chat.
- Prevents the New Chat button from scrolling away while still allowing the sidebar content below it to scroll.

## Vigzone Product Suite v4

Implemented:
- Brain Pro backend cloud sync via `/api/brain/cloud`
- Continue Where I Stopped banner on new chat screen
- Smart project grouping through Vigzone Brain categories
- File Studio panel for uploaded/generated files and source chat opening
- Website Studio panel to generate stronger website prompts in Website mode
- Feedback Learning System saving 👍/👎 feedback to `/api/feedback`
- Share Chat public link endpoint `/api/share/chat` and `/share/{id}`
- App Update/version modal using `/api/app/version`
- Admin analytics expansion using `/api/admin/analytics`

Storage:
- Cloud Brain, feedback and shared chats are stored under `VIGZONE_DATA_DIR` (default: `data/`).

## Living config / hardcoded text cleanup

- Added `/api/public/config` so UI branding, greetings, Groq tutorial URL, and new-chat copy can be changed from environment variables instead of editing HTML.
- Added env variables:
  - `VIGZONE_APP_NAME`
  - `VIGZONE_SHORT_NAME`
  - `VIGZONE_BUILD_NAME`
  - `VIGZONE_NEW_CHAT_TOPLINE`
  - `VIGZONE_NEW_CHAT_SUBTITLE`
  - `VIGZONE_GROQ_HINT`
  - `VIGZONE_GREETING_OPTIONS`
  - `GROQ_KEYS_URL`
  - `GROQ_DOCS_URL`
  - `VIGZONE_BACKEND_LABEL`
- Health/setup messages now use the configured app name and Groq key URL.
- Frontend applies live config at runtime and uses hardcoded text only as fallback.


## Admin-only professional dashboard

- Admin users no longer enter the normal chat interface.
- When `/api/auth/me` returns `is_admin=true`, the frontend switches to a full-screen admin dashboard and hides sidebar/chat/composer.
- Added `/api/admin/full-dashboard` with: users, active users, daily/weekly usage, top users, provider usage, Brain users, shares, feedback mix, and latest bad feedback details.
- Added canvas-based visual graphs for usage trend and feedback quality.
- Sign out now clears stale local auth/session storage to prevent cross-account UI carryover.

## Admin dashboard scroll fix

- Admin dashboard now uses its own fixed viewport scroller.
- The normal chat UI remains hidden/locked for admin accounts, but the admin dashboard can scroll on desktop and mobile.
- Admin tables can scroll horizontally on narrow screens.


## Offline mode / PWA access

- Added a root-scoped service worker at `/service-worker.js`.
- Cached the app shell, landing page, chat page, manifest, icons, offline page, and public config/version endpoints.
- Added `/offline` fallback page.
- Users can reopen Vigzone while offline after visiting once online.
- Saved chats remain readable offline because they are kept in localStorage.
- AI replies, uploads, image generation, Brain cloud sync, and admin live data show a clear offline message because they need internet.

## Offline local knowledge mode

- Vigzone now replies while offline using a browser-side local knowledge engine.
- Sources used offline:
  - saved conversations in localStorage
  - local Vigzone Brain metadata
  - already-extracted attached document text
  - built-in mini knowledge base and templates
  - simple calculator logic
- Offline local mode does not call Groq or the backend.
- Offline limitations:
  - no web search
  - no Groq-level reasoning
  - no new image analysis/generation
  - no cloud Brain sync
  - no new server-side file extraction
  - no live admin analytics
- The service worker version was bumped so users receive the new offline engine after redeploy and hard refresh.

## Admin mobile graph stability fix

- Fixed admin dashboard canvas charts on phones.
- Chart canvas now uses a locked responsive container size.
- Canvas bitmap size is capped for high-DPI mobile devices.
- Dashboard refresh and resize now redraw charts after layout stabilizes.
- Prevents Usage trend and Feedback quality graphs from expanding, clipping, or disappearing during refresh.

## Message copy context menu

- Added copy feature for both user and assistant messages.
- Desktop: right-click any user/AI message and choose Copy message.
- Mobile: tap and hold any user/AI message and choose Copy message.
- Copies the stored message text, including reply context and attachment names when available.

## Actually-working hardcode cleanup

Fixed hardcoded/dead items that were not actually wired:
- Defined `authHeaders()` compatibility helper so Workspaces and File Analyzer do not fail.
- Removed `.env` from the production zip so placeholder secrets are not loaded on deployment.
- Added Groq API key placeholder guard; fake keys like `your_groq_api_key_here` are ignored.
- Scoped local conversations, Brain metadata, mode memory, and upload history per signed-in user.
- File Studio now includes local uploaded-file history, not only files discovered inside chat summaries.
- Website Studio now has `Export last HTML ZIP`, wired to `/api/website/export`.
- Export Chat now uses `/api/export/chat` and falls back to browser export if offline.
- Admin dashboard now displays provider usage and system notes.
- Admin daily chart grouping now uses configured local timezone instead of UTC SQL date buckets.
- Added dynamic `/manifest.json` so PWA app naming is not frozen in static manifest JSON.
- Service worker cache updated to use `/manifest.json` and bumped cache version.

## Deterministic date/time answers

- Direct date/time/day questions no longer go through the model guessing path.
- `/api/chat` and `/api/chat/sync` now answer simple current date/time requests directly from server/browser timezone context.
- Frontend sends `client_timezone` and `client_now_iso` with chat requests so Railway does not need a `USER_TIMEZONE` variable for the user's local date/time.
- Offline local knowledge mode answers date/time from the device clock.

## Real-time world knowledge reliability upgrade

Important note: no AI app can literally guarantee 100% accuracy for every fact in the world, because live sources can be delayed, missing, blocked, or contradictory. This build improves Vigzone so it verifies live information when possible and avoids guessing when live verification is unavailable.

Implemented:
- RealWorld context now falls back to live web/news search when the query asks about latest, recent, current, news, sports, scores, roles, elections, markets, or world happenings.
- Added keyless live search sources:
  - DuckDuckGo Instant Answer
  - DuckDuckGo HTML search
  - GDELT article search for news/current events
  - Wikipedia summary for stable encyclopedia questions
- Weather queries now attempt location extraction instead of always using the default location.
- Crypto/stock price extraction now understands common names such as Bitcoin, Ethereum, Apple, Tesla, Nvidia, Microsoft, Google, Meta, Amazon, etc.
- Currency exchange extraction now understands USD/LKR/rupee/dollar/euro/pound/common currency words.
- Added `/api/realworld-data/live-context?query=...` diagnostic endpoint.
- Added `/api/realworld-data/capabilities` diagnostic endpoint.
- Strengthened the system prompt so current/recent claims prefer live sources over memory and avoid guessing when live data is unavailable.
- Removed `.env` from output zip so placeholder/fake keys are not deployed.

## Google Drive import

- The "Add from Drive" menu item is now active/visible.
- Users can paste a Google Drive share link or file ID and attach the file.
- Shared/public Drive links work without extra Railway variables.
- Private Drive Picker support is included:
  - set `GOOGLE_DRIVE_CLIENT_ID`
  - set `GOOGLE_DRIVE_API_KEY` (or `GOOGLE_API_KEY`)
  - authorized JS origin must match the deployed Vigzone domain.
- Backend endpoint: `POST /api/drive/import`
- Google Docs/Sheets/Slides are exported into DOCX/XLSX/PPTX when possible.
- Imported Drive files go into the same pending attachments system, so when the user sends a prompt, Vigzone includes the extracted Drive-file content in the chat request for analysis.
