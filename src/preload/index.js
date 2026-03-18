import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('mftAPI', {
  scan: (drive, depth) => ipcRenderer.invoke('mft:scan', { drive, depth }),
})
