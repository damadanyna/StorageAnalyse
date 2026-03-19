"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("mftAPI", {
  scan: (drive, depth) => electron.ipcRenderer.invoke("mft:scan", { drive, depth }),
  getFiles: (drive, folderRef) => electron.ipcRenderer.invoke("mft:files", { drive, folderRef })
});
