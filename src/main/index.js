import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn } from 'child_process'
import { fileURLToPath } from 'url'
import path, { join, dirname } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname  = dirname(__filename)

// ── Chemins Python ────────────────────────────────────────────
function getPythonPath() {
  if (app.isPackaged) {
    return join(process.resourcesPath, 'python-embed', 'python.exe')
  }
  return join(__dirname, '..', '..', 'resources', 'python-embed', 'python.exe')
}

function getScriptPath() {
  if (app.isPackaged) {
    return join(process.resourcesPath, 'python', 'mft_reader.py')
  }
  return join(__dirname, '..', '..', 'python', 'mft_reader.py')
}

// ── Handler IPC ───────────────────────────────────────────────
ipcMain.handle('mft:scan', async (event, { drive = 'C', depth = null } = {}) => {
  const pythonExe  = getPythonPath()
  const scriptPath = getScriptPath()
  const outFile    = path.join(app.getPath('temp'), `mft_out_${Date.now()}.json`)

  const args = [scriptPath, drive, '--output', outFile]
  if (depth !== null) args.push('--depth', String(depth))

  // ✅ Backslash simple — correct pour PowerShell
  const argList    = args.map(a => `'${a}'`).join(',')
  const ps1Content = `Start-Process -FilePath '${pythonExe}' -ArgumentList @(${argList}) -Verb RunAs -WindowStyle Hidden -Wait`
  const ps1File    = path.join(app.getPath('temp'), `mft_scan_${Date.now()}.ps1`)

  console.log('📄 PS1 content:\n', ps1Content)

  const { writeFile, readFile, unlink, access } = await import('fs/promises')
  await writeFile(ps1File, ps1Content, 'utf-8')

  return new Promise((resolve, reject) => {
    const ps = spawn('powershell', [
      '-NoProfile',
      '-NonInteractive',
      '-ExecutionPolicy', 'Bypass',
      '-File', ps1File
    ], { windowsHide: true })

    let stderr = ''
    ps.stderr.on('data', chunk => { stderr += chunk.toString() })

    // ✅ Bloc close corrigé
    ps.on('close', async code => {
      unlink(ps1File).catch(() => {})
      console.log('PowerShell exit code:', code)

      // Vérifie si Python a bien créé le fichier JSON
      try {
        await access(outFile)
        console.log('✅ Fichier JSON trouvé')
      } catch {
        reject(new Error(`Python n'a pas créé le fichier JSON. Code PS: ${code}. Stderr: ${stderr}`))
        return
      }

      try {
        const data = await readFile(outFile, 'utf-8')
        resolve(JSON.parse(data.trim()))
        unlink(outFile).catch(() => {})
      } catch (e) {
        reject(new Error(`Lecture JSON échouée : ${e.message}`))
      }
    })

    ps.on('error', err => reject(new Error(`PowerShell introuvable : ${err.message}`)))
  })
})

// ── Fenêtre principale ────────────────────────────────────────
function createWindow(devServerUrl = null) {
  const preloadPath = join(__dirname, '..', 'preload', 'index.js')
  console.log('✅ Preload path:', preloadPath)

  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  if (devServerUrl) {
    win.loadURL(devServerUrl)
    win.webContents.openDevTools()
  } else {
    win.loadFile(join(__dirname, '..', 'renderer', 'index.html'))
  }
}

// ── Cycle de vie app ──────────────────────────────────────────
app.whenReady().then(() => {
  const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:3000'
  console.log('Dev server URL:', devServerUrl)
  createWindow(devServerUrl)
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:3000'
    createWindow(devServerUrl)
  }
})
