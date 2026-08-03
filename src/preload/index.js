import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('mftAPI', {
  getDrives: () => ipcRenderer.invoke('mft:drives'),
  getDriveUsage: drive => ipcRenderer.invoke('mft:drive-usage', { drive }),
  getSummary: (drive, options) => ipcRenderer.invoke('mft:summary', { drive, ...options }),
  getHighlights: (drive, options) => ipcRenderer.invoke('mft:highlights', { drive, ...options }),
  getDistribution: (drive, options) => ipcRenderer.invoke('mft:distribution', { drive, ...options }),
  scan: (drive, depth) => ipcRenderer.invoke('mft:scan', { drive, depth }),
  getChildren: (drive, folderRef, options) => ipcRenderer.invoke('mft:children', { drive, folderRef, ...options }),
  getFiles: (drive, folderRef, options) => ipcRenderer.invoke('mft:files', { drive, folderRef, ...options }),
  copyText: text => ipcRenderer.invoke('clipboard:write-text', { text }),
  previewPath: path => ipcRenderer.invoke('file:preview', { path }),
  getFileIcon: (path, size) => ipcRenderer.invoke('shell:file-icon', { path, size }),
  getJumboIcon: (path, size) => ipcRenderer.invoke('shell:jumbo-icon', { path, size }),
  openPath: path => ipcRenderer.invoke('shell:open-path', { path }),
  revealPath: path => ipcRenderer.invoke('shell:reveal-path', { path }),
  trashPath: path => ipcRenderer.invoke('shell:trash-path', { path }),
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  toggleMaximizeWindow: () => ipcRenderer.invoke('window:toggle-maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),
  getWindowState: () => ipcRenderer.invoke('window:is-maximized'),
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
  onWindowState: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('window:state', listener)
    return () => ipcRenderer.removeListener('window:state', listener)
  },
})
