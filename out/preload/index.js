"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("mftAPI", {
  getDrives: () => electron.ipcRenderer.invoke("mft:drives"),
  getSummary: (drive) => electron.ipcRenderer.invoke("mft:summary", { drive }),
  scan: (drive, depth) => electron.ipcRenderer.invoke("mft:scan", { drive, depth }),
  getChildren: (drive, folderRef) => electron.ipcRenderer.invoke("mft:children", { drive, folderRef }),
  getFiles: (drive, folderRef) => electron.ipcRenderer.invoke("mft:files", { drive, folderRef }),
  onScanProgress: (callback) => {
    const listener = (_event, payload) => callback(payload);
    electron.ipcRenderer.on("mft:scan-progress", listener);
    return () => electron.ipcRenderer.removeListener("mft:scan-progress", listener);
  },
  onCacheUpdated: (callback) => {
    const listener = (_event, payload) => callback(payload);
    electron.ipcRenderer.on("mft:cache-updated", listener);
    return () => electron.ipcRenderer.removeListener("mft:cache-updated", listener);
  }
});
