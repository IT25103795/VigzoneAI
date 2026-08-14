'use strict';

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('vigzoneDesktopShell', Object.freeze({
  isDesktop: true,
  platform: process.platform
}));

window.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('vigzone-desktop-shell');
});
