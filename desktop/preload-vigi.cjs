'use strict';

const { contextBridge, ipcRenderer } = require('electron');

function subscribe(channel, callback) {
  if (typeof callback !== 'function') return () => {};
  const listener = (_event, payload) => callback(payload || {});
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
}

contextBridge.exposeInMainWorld('vigiDesktop', Object.freeze({
  getStatus: () => ipcRenderer.invoke('vigi:get-status'),
  ask: message => ipcRenderer.invoke('vigi:ask', String(message || '')),
  openVigzone: () => ipcRenderer.invoke('vigi:open'),
  openUpdate: () => ipcRenderer.invoke('vigi:open-update'),
  closePet: () => ipcRenderer.invoke('vigi:close'),
  moveBy: delta => ipcRenderer.invoke('vigi:move', {
    x: Number(delta?.x) || 0,
    y: Number(delta?.y) || 0
  }),
  setExpanded: expanded => ipcRenderer.invoke('vigi:set-expanded', !!expanded),
  onMainMinimized: callback => subscribe('vigi:main-minimized', callback),
  onMainRestored: callback => subscribe('vigi:main-restored', callback),
  onStatus: callback => subscribe('vigi:status', callback),
  onUpdateAvailable: callback => subscribe('vigi:update-available', callback),
  onExpanded: callback => subscribe('vigi:expanded', callback)
}));
