'use strict';

const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage, screen, session, shell } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

if (require('electron-squirrel-startup')) app.quit();

app.enableSandbox();

const DEFAULT_APP_URL = 'https://vigzoneai.onrender.com/chat';
const PET_COLLAPSED = Object.freeze({ width: 190, height: 226 });
const PET_EXPANDED = Object.freeze({ width: 380, height: 520 });
const GOOGLE_OAUTH_HOSTS = new Set(['accounts.google.com', 'accounts.googleusercontent.com']);

let mainWindow = null;
let petWindow = null;
let tray = null;
let quitting = false;
let petExpanded = false;
let preferences = { petEnabled: true };

function requestedAppUrl() {
  const argument = process.argv.find(value => value.startsWith('--app-url='));
  return argument ? argument.slice('--app-url='.length) : (process.env.VIGZONE_DESKTOP_URL || DEFAULT_APP_URL);
}

function normalizeAppUrl(value) {
  try {
    const candidate = new URL(String(value || ''));
    const localHttp = candidate.protocol === 'http:' && ['127.0.0.1', 'localhost', '::1'].includes(candidate.hostname);
    if (candidate.protocol !== 'https:' && !localHttp) throw new Error('Only HTTPS or local development URLs are allowed.');
    if (!candidate.pathname || candidate.pathname === '/') candidate.pathname = '/chat';
    candidate.hash = '';
    return candidate.toString();
  } catch (_) {
    return DEFAULT_APP_URL;
  }
}

const appUrl = normalizeAppUrl(requestedAppUrl());
const appOrigin = new URL(appUrl).origin;

function preferencePath() {
  return path.join(app.getPath('userData'), 'desktop-vigi.json');
}

function loadPreferences() {
  try {
    const parsed = JSON.parse(fs.readFileSync(preferencePath(), 'utf8'));
    preferences = { petEnabled: parsed.petEnabled !== false };
  } catch (_) {
    preferences = { petEnabled: true };
  }
}

function savePreferences() {
  try {
    fs.writeFileSync(preferencePath(), JSON.stringify(preferences, null, 2), 'utf8');
  } catch (error) {
    console.warn('Could not save Vigi desktop preferences:', error.message);
  }
}

function trustedAppNavigation(rawUrl) {
  try {
    const candidate = new URL(rawUrl);
    return candidate.origin === appOrigin ||
      (candidate.protocol === 'https:' && GOOGLE_OAUTH_HOSTS.has(candidate.hostname));
  } catch (_) {
    return false;
  }
}

function openExternalHttps(rawUrl) {
  try {
    const candidate = new URL(rawUrl);
    if (candidate.protocol === 'https:') shell.openExternal(candidate.toString());
  } catch (_) {}
}

function configureRemoteWebContents(webContents) {
  webContents.setWindowOpenHandler(({ url }) => {
    openExternalHttps(url);
    return { action: 'deny' };
  });
  webContents.on('will-navigate', (event, url) => {
    if (trustedAppNavigation(url)) return;
    event.preventDefault();
    openExternalHttps(url);
  });
}

function configurePermissions() {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback, details) => {
    let trusted = false;
    try { trusted = new URL(webContents.getURL()).origin === appOrigin; } catch (_) {}
    if (!trusted) return callback(false);
    if (permission === 'clipboard-sanitized-write') return callback(true);
    if (permission === 'media') {
      const mediaTypes = Array.isArray(details?.mediaTypes) ? details.mediaTypes : [];
      return callback(mediaTypes.length > 0 && mediaTypes.every(type => type === 'audio'));
    }
    callback(false);
  });
}

function iconPath(size = 256) {
  return path.join(__dirname, '..', 'static', 'icons', `vigzone-icon-${size}.png`);
}

function positionPet(expanded = petExpanded, preserveAnchor = false) {
  if (!petWindow || petWindow.isDestroyed()) return;
  const size = expanded ? PET_EXPANDED : PET_COLLAPSED;
  const previous = petWindow.getBounds();
  const display = screen.getDisplayNearestPoint({
    x: previous.x + Math.max(1, previous.width - 1),
    y: previous.y + Math.max(1, previous.height - 1)
  });
  const area = display.workArea;
  const desiredX = preserveAnchor ? previous.x + previous.width - size.width : area.x + area.width - size.width - 16;
  const desiredY = preserveAnchor ? previous.y + previous.height - size.height : area.y + area.height - size.height - 12;
  const x = Math.max(area.x, Math.min(desiredX, area.x + area.width - size.width));
  const y = Math.max(area.y, Math.min(desiredY, area.y + area.height - size.height));
  petWindow.setBounds({ x, y, width: size.width, height: size.height }, true);
}

function sendToPet(channel, payload = {}) {
  if (!petWindow || petWindow.isDestroyed()) return;
  petWindow.webContents.send(channel, payload);
}

function setPetExpanded(next, preserveAnchor = true) {
  petExpanded = !!next;
  positionPet(petExpanded, preserveAnchor);
  sendToPet('vigi:expanded', { expanded: petExpanded });
}

function showPet({ expand = false, announceMinimized = false } = {}) {
  if (!preferences.petEnabled || !petWindow || petWindow.isDestroyed()) return;
  if (expand) setPetExpanded(true);
  petWindow.showInactive();
  petWindow.setAlwaysOnTop(true, 'floating');
  if (announceMinimized) sendToPet('vigi:main-minimized', { message: 'Ask anything from Vigi…' });
  rebuildTrayMenu();
}

function hidePet() {
  preferences.petEnabled = false;
  savePreferences();
  if (petWindow && !petWindow.isDestroyed()) petWindow.hide();
  rebuildTrayMenu();
}

function restorePet() {
  preferences.petEnabled = true;
  savePreferences();
  showPet({ expand: true });
}

function openMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
  sendToPet('vigi:main-restored');
}

async function companionState() {
  if (!mainWindow || mainWindow.isDestroyed() || mainWindow.webContents.isLoadingMainFrame()) {
    return { ready: false, authenticated: false, busy: false, title: 'Vigzone is loading…' };
  }
  try {
    return await mainWindow.webContents.executeJavaScript(
      `(() => window.VigzoneDesktopCompanion?.getState?.() || ({ready:false, authenticated:false, busy:false, title:'Open Vigzone to continue'}))()`,
      true
    );
  } catch (_) {
    return { ready: false, authenticated: false, busy: false, title: 'Open Vigzone to continue' };
  }
}

async function askThroughMainWindow(rawPrompt) {
  const prompt = String(rawPrompt || '').replace(/\0/g, '').trim().slice(0, 4000);
  if (!prompt) return { ok: false, error: 'Type a message for Vigi first.' };
  if (!mainWindow || mainWindow.isDestroyed() || mainWindow.webContents.isLoadingMainFrame()) {
    return { ok: false, error: 'Vigzone is still loading. Open it once, then try again.' };
  }
  const encodedPrompt = JSON.stringify(prompt);
  try {
    const result = await mainWindow.webContents.executeJavaScript(
      `(async () => {
        if (!window.VigzoneDesktopCompanion?.ask) return {ok:false,error:'Open Vigzone and sign in first.'};
        return await window.VigzoneDesktopCompanion.ask(${encodedPrompt});
      })()`,
      true
    );
    return result && typeof result === 'object' ? result : { ok: false, error: 'Vigi returned an invalid desktop response.' };
  } catch (error) {
    return { ok: false, error: error?.message || 'Vigi could not reach the active chat.' };
  }
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1420,
    height: 920,
    minWidth: 960,
    minHeight: 640,
    show: false,
    title: 'Vigzone AI',
    icon: iconPath(256),
    backgroundColor: '#090a0f',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload-main.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      backgroundThrottling: false
    }
  });

  configureRemoteWebContents(mainWindow.webContents);
  mainWindow.loadURL(appUrl);
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.webContents.on('did-finish-load', async () => {
    sendToPet('vigi:status', await companionState());
  });
  mainWindow.webContents.on('did-fail-load', (_event, _code, description) => {
    sendToPet('vigi:status', { ready: false, error: description || 'Vigzone could not load.' });
  });
  mainWindow.on('minimize', () => showPet({ expand: true, announceMinimized: true }));
  mainWindow.on('restore', () => sendToPet('vigi:main-restored'));
  mainWindow.on('focus', () => sendToPet('vigi:main-restored'));
  mainWindow.on('close', event => {
    if (quitting) return;
    event.preventDefault();
    mainWindow.hide();
    showPet({ expand: true, announceMinimized: true });
  });
  mainWindow.on('closed', () => { mainWindow = null; });
}

function createPetWindow() {
  petWindow = new BrowserWindow({
    ...PET_COLLAPSED,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    focusable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload-vigi.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true
    }
  });

  petWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  petWindow.loadFile(path.join(__dirname, 'vigi.html'));
  petWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  petWindow.webContents.on('will-navigate', event => event.preventDefault());
  petWindow.webContents.on('context-menu', () => {
    const menu = Menu.buildFromTemplate([
      { label: 'Open Vigzone', click: openMainWindow },
      { label: petExpanded ? 'Collapse message box' : 'Ask Vigi', click: () => setPetExpanded(!petExpanded) },
      { type: 'separator' },
      { label: 'Close Vigi', click: hidePet }
    ]);
    menu.popup({ window: petWindow });
  });
  petWindow.on('close', event => {
    if (quitting) return;
    event.preventDefault();
    hidePet();
  });
  petWindow.on('closed', () => { petWindow = null; });
  petWindow.once('ready-to-show', () => {
    positionPet(false);
    showPet();
  });
}

function rebuildTrayMenu() {
  if (!tray) return;
  const login = app.getLoginItemSettings();
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open Vigzone', click: openMainWindow },
    { label: preferences.petEnabled ? 'Hide Vigi' : 'Show Vigi', click: preferences.petEnabled ? hidePet : restorePet },
    { label: 'Ask Vigi', enabled: preferences.petEnabled, click: () => { showPet({ expand: true }); petWindow?.focus(); } },
    { type: 'separator' },
    {
      label: 'Start Vigi with Windows',
      type: 'checkbox',
      enabled: app.isPackaged,
      checked: !!login.openAtLogin,
      click: item => { if (app.isPackaged) app.setLoginItemSettings({ openAtLogin: !!item.checked }); }
    },
    { type: 'separator' },
    { label: 'Quit Vigzone AI', click: () => { quitting = true; app.quit(); } }
  ]));
}

function createTray() {
  const image = nativeImage.createFromPath(iconPath(64)).resize({ width: 20, height: 20 });
  tray = new Tray(image);
  tray.setToolTip('Vigzone AI · Vigi companion');
  tray.on('click', () => preferences.petEnabled ? showPet({ expand: true }) : restorePet());
  tray.on('double-click', openMainWindow);
  rebuildTrayMenu();
}

function trustedPetSender(event) {
  return !!petWindow && !petWindow.isDestroyed() && event.sender.id === petWindow.webContents.id;
}

function registerIpc() {
  ipcMain.handle('vigi:get-status', event => trustedPetSender(event)
    ? companionState()
    : { ready: false, error: 'Untrusted desktop request.' });
  ipcMain.handle('vigi:ask', (event, prompt) => trustedPetSender(event)
    ? askThroughMainWindow(prompt)
    : { ok: false, error: 'Untrusted desktop request.' });
  ipcMain.handle('vigi:open', event => {
    if (!trustedPetSender(event)) return false;
    openMainWindow();
    return true;
  });
  ipcMain.handle('vigi:close', event => {
    if (!trustedPetSender(event)) return false;
    hidePet();
    return true;
  });
  ipcMain.handle('vigi:set-expanded', (event, expanded) => {
    if (!trustedPetSender(event)) return false;
    setPetExpanded(!!expanded);
    return true;
  });
}

const singleInstance = app.requestSingleInstanceLock();
if (!singleInstance) {
  app.quit();
} else {
  app.on('second-instance', openMainWindow);
  app.whenReady().then(() => {
    loadPreferences();
    configurePermissions();
    registerIpc();
    createMainWindow();
    createPetWindow();
    createTray();
  });
}

app.on('activate', openMainWindow);
app.on('before-quit', () => { quitting = true; });
app.on('window-all-closed', () => {
  // The tray and Vigi remain alive until the user chooses Quit Vigzone AI.
});
