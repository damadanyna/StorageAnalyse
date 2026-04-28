import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('mftAPI', {
  getDrives: ()                     => ipcRenderer.invoke('mft:drives'),
  getSummary: (drive)               => ipcRenderer.invoke('mft:summary', { drive }),
  scan:     (drive, depth)           => ipcRenderer.invoke('mft:scan',  { drive, depth }),
  getChildren: (drive, folderRef)    => ipcRenderer.invoke('mft:children', { drive, folderRef }),
  getFiles: (drive, folderRef)       => ipcRenderer.invoke('mft:files', { drive, folderRef }),
  onScanProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('mft:scan-progress', listener)
    return () => ipcRenderer.removeListener('mft:scan-progress', listener)
  },
  onCacheUpdated: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('mft:cache-updated', listener)
    return () => ipcRenderer.removeListener('mft:cache-updated', listener)
  },
})
