import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn } from 'child_process'
import { fileURLToPath } from 'url'
import path, { join, dirname } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname  = dirname(__filename)

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

  const { mkdir } = await import('fs/promises')
  const tempDir = 'C:\\Temp'
  await mkdir(tempDir, { recursive: true })

  const ts      = Date.now()
  const outFile = `${tempDir}\\mft_out_${ts}.json`

  const args = [scriptPath, drive, '--output', outFile]
  if (depth !== null) args.push('--depth', String(depth))

  console.log('🐍 Python:', pythonExe)
  console.log('📜 Script:', scriptPath)
  console.log('📂 Output:', outFile)
  console.log('⚙️  Args:', args)

  const { readFile, unlink, access } = await import('fs/promises')

  return new Promise((resolve, reject) => {
    // ✅ spawn direct — pas de RunAs, pas de PowerShell intermédiaire
    // L'app Electron doit être lancée en admin (via le manifest ou manuellement)
    const proc = spawn(pythonExe, args, {
      windowsHide: false,   // false pour voir la fenêtre Python si erreur
      stdio: ['ignore', 'pipe', 'pipe']
    })

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', chunk => {
      stdout += chunk.toString()
      console.log('[Python stdout]', chunk.toString().trim())
    })
    proc.stderr.on('data', chunk => {
      stderr += chunk.toString()
      console.error('[Python stderr]', chunk.toString().trim())
    })

    proc.on('close', async code => {
      console.log('Python exit code:', code)
      console.log('Python stdout:', stdout)
      console.log('Python stderr:', stderr)

      if (code !== 0) {
        reject(new Error(
          `Python a échoué (code ${code})\n` +
          `Stderr: ${stderr}\nStdout: ${stdout}`
        ))
        return
      }

      try {
        await access(outFile)
      } catch {
        reject(new Error(
          `Python n'a pas créé le fichier JSON.\n` +
          `Stderr: ${stderr}\nStdout: ${stdout}`
        ))
        return
      }

      try {
        const data   = await readFile(outFile, 'utf-8')
        const parsed = JSON.parse(data.trim())
        unlink(outFile).catch(() => {})
        resolve(parsed)
      } catch (e) {
        reject(new Error(`Lecture JSON échouée : ${e.message}`))
      }
    })

    proc.on('error', err => {
      reject(new Error(`Python introuvable : ${err.message}\nChemin: ${pythonExe}`))
    })
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
