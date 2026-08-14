import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_desktop_package_is_pinned_and_buildable():
    package = json.loads(_read("package.json"))
    forge = _read("forge.config.cjs")

    assert package["main"] == "desktop/main.cjs"
    assert package["version"] == "1.0.2"
    assert package["scripts"]["desktop:dev"].endswith("--app-url=http://127.0.0.1:8000/chat")
    assert package["scripts"]["desktop:make"] == "electron-forge make --platform=win32 --arch=x64"
    assert package["dependencies"]["electron-squirrel-startup"] == "1.0.1"
    assert package["devDependencies"]["electron"] == "43.2.0"
    assert package["devDependencies"]["@electron-forge/cli"] == "7.11.2"
    assert "@electron-forge/maker-squirrel" in package["devDependencies"]
    assert package["devDependencies"]["electron-winstaller"] == "5.4.4"
    assert package["overrides"]["yauzl"] == "3.3.1"
    assert "asar: true" in forge
    assert "setupIcon" in forge
    assert "\\.env" in forge
    assert "(?:data|tests?|test-projects|tmp|uploads)" in forge


def test_desktop_host_keeps_vigi_alive_and_secures_remote_content():
    main = _read("desktop/main.cjs")
    main_preload = _read("desktop/preload-main.cjs")
    pet_preload = _read("desktop/preload-vigi.cjs")

    assert "transparent: true" in main
    assert "alwaysOnTop: true" in main
    assert "skipTaskbar: true" in main
    assert "backgroundThrottling: false" in main
    assert main.count("nodeIntegration: false") == 2
    assert main.count("contextIsolation: true") == 2
    assert main.count("sandbox: true") == 2
    assert "app.enableSandbox()" in main
    assert "setPermissionRequestHandler" in main
    assert "trustedPetSender" in main
    assert "event.sender.id === petWindow.webContents.id" in main
    assert "setWindowOpenHandler" in main
    assert "trustedAppNavigation" in main
    assert "mainWindow.on('minimize'" in main
    assert "mainWindow.on('close'" in main
    assert "Menu.buildFromTemplate" in main
    assert "Close Vigi" in main
    assert "Start Vigi with Windows" in main
    assert "app.setLoginItemSettings" in main
    assert "contextBridge.exposeInMainWorld('vigzoneDesktopShell'" in main_preload
    assert "ipcRenderer.send" not in main_preload
    assert "getAppVersion: () => ipcRenderer.invoke('desktop:get-version')" in main_preload
    assert "notifyUpdate: update => ipcRenderer.invoke('desktop:notify-update'" in main_preload
    assert "contextBridge.exposeInMainWorld('vigiDesktop'" in pet_preload
    assert "ask: message => ipcRenderer.invoke('vigi:ask'" in pet_preload
    assert "moveBy: delta => ipcRenderer.invoke('vigi:move'" in pet_preload
    assert "send: ipcRenderer.send" not in pet_preload
    assert "openUpdate: () => ipcRenderer.invoke('vigi:open-update')" in pet_preload
    assert "onUpdateAvailable" in pet_preload


def test_desktop_pet_quick_chat_uses_the_real_active_conversation():
    html = _read("desktop/vigi.html")
    renderer = _read("desktop/vigi-renderer.js")
    app_js = _read("static/js/app.js")
    css = _read("static/css/styles.css")

    assert "Content-Security-Policy" in html
    assert 'id="quickPrompt"' in html
    assert "Ask anything from Vigi" in html
    assert 'id="replyPreview"' in html
    assert "Open full conversation" in html
    assert "api.ask(message)" in renderer
    assert "api.moveBy(movement)" in renderer
    assert "petButton.addEventListener('pointermove'" in renderer
    assert "suppressPetClick" in renderer
    assert "api.openVigzone()" in renderer
    assert "api.onMainMinimized" in renderer
    assert "api.onUpdateAvailable" in renderer
    assert "api.openUpdate()" in renderer
    assert "window.vigzoneDesktopShell?.isDesktop" in app_js
    assert "VigzoneDesktopCompanion" in app_js
    assert "await sendMessage(message, {source:'desktop-vigi'})" in app_js
    assert "messages.slice(messageCountBefore)" in app_js
    assert "conversationId: store.activeId || null" in app_js
    assert "pendingFiles.length" in app_js
    assert "quotedMessage" in app_js
    assert ".vigzone-desktop-shell .vigi-companion{display:none!important;}" in css


def test_desktop_documentation_explains_runtime_and_distribution():
    documentation = _read("DESKTOP.md")

    assert "npm run desktop:dev" in documentation
    assert "Node.js 22.12 or newer" in documentation
    assert "VIGZONE_DESKTOP_URL" in documentation
    assert "npm run desktop:make" in documentation
    assert "code-signing certificate" in documentation
    assert "last opened conversation" in documentation
    assert "VIGZONE_DESKTOP_RELEASE_REPO" in documentation
    assert "never silently installs" in documentation
