'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vigzoneDesktopShell', Object.freeze({
  isDesktop: true,
  platform: process.platform,
  getAppVersion: () => ipcRenderer.invoke('desktop:get-version'),
  notifyUpdate: update => ipcRenderer.invoke('desktop:notify-update', update)
}));

window.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('vigzone-desktop-shell');
});
