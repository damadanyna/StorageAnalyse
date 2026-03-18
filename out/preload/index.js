"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("mftAPI", {
  scan: (drive, depth) => electron.ipcRenderer.invoke("mft:scan", { drive, depth })
});
