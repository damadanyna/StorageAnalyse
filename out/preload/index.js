"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("mftAPI", {
  getDrives: () => electron.ipcRenderer.invoke("mft:drives"),
  getDriveUsage: (drive) => electron.ipcRenderer.invoke("mft:drive-usage", { drive }),
  getSummary: (drive, options) => electron.ipcRenderer.invoke("mft:summary", { drive, ...options }),
  getHighlights: (drive, options) => electron.ipcRenderer.invoke("mft:highlights", { drive, ...options }),
  getDistribution: (drive, options) => electron.ipcRenderer.invoke("mft:distribution", { drive, ...options }),
  scan: (drive, depth) => electron.ipcRenderer.invoke("mft:scan", { drive, depth }),
  getChildren: (drive, folderRef, options) => electron.ipcRenderer.invoke("mft:children", { drive, folderRef, ...options }),
  getFiles: (drive, folderRef, options) => electron.ipcRenderer.invoke("mft:files", { drive, folderRef, ...options }),
  copyText: (text) => electron.ipcRenderer.invoke("clipboard:write-text", { text }),
  previewPath: (path) => electron.ipcRenderer.invoke("file:preview", { path }),
  getFileIcon: (path, size) => electron.ipcRenderer.invoke("shell:file-icon", { path, size }),
  getJumboIcon: (path, size) => electron.ipcRenderer.invoke("shell:jumbo-icon", { path, size }),
  openPath: (path) => electron.ipcRenderer.invoke("shell:open-path", { path }),
  revealPath: (path) => electron.ipcRenderer.invoke("shell:reveal-path", { path }),
  trashPath: (path) => electron.ipcRenderer.invoke("shell:trash-path", { path }),
  minimizeWindow: () => electron.ipcRenderer.invoke("window:minimize"),
  toggleMaximizeWindow: () => electron.ipcRenderer.invoke("window:toggle-maximize"),
  closeWindow: () => electron.ipcRenderer.invoke("window:close"),
  getWindowState: () => electron.ipcRenderer.invoke("window:is-maximized"),
  onScanProgress: (callback) => {
    const listener = (_event, payload) => callback(payload);
    electron.ipcRenderer.on("mft:scan-progress", listener);
    return () => electron.ipcRenderer.removeListener("mft:scan-progress", listener);
  },
  onCacheUpdated: (callback) => {
    const listener = (_event, payload) => callback(payload);
    electron.ipcRenderer.on("mft:cache-updated", listener);
    return () => electron.ipcRenderer.removeListener("mft:cache-updated", listener);
  },
  onWindowState: (callback) => {
    const listener = (_event, payload) => callback(payload);
    electron.ipcRenderer.on("window:state", listener);
    return () => electron.ipcRenderer.removeListener("window:state", listener);
  }
});
