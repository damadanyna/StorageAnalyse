import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('mftAPI', {
  scan:     (drive, depth)           => ipcRenderer.invoke('mft:scan',  { drive, depth }),
  getFiles: (drive, folderRef)       => ipcRenderer.invoke('mft:files', { drive, folderRef }),
})
