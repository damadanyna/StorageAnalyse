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

ipcMain.handle('mft:scan', async (event, { drive = 'C', depth = null } = {}) => {
  const pythonExe  = getPythonPath()
  const scriptPath = getScriptPath()

  const { mkdir, writeFile, readFile, unlink, access } = await import('fs/promises')
  const tempDir = 'C:\\Temp'
  await mkdir(tempDir, { recursive: true })

  const ts      = Date.now()
  const outFile = `${tempDir}\\mft_out_${ts}.json`
  const ps1File = `${tempDir}\\mft_scan_${ts}.ps1`

  const args = [scriptPath, drive, '--output', outFile]
  if (depth !== null) args.push('--depth', String(depth))

  const esc      = s => s.replace(/'/g, "''")
  const argsList = args.map(a => `'${esc(a)}'`).join(', ')

  // ✅ Sans RedirectStandardOutput — incompatible avec -Verb RunAs
  const ps1 = `$p = Start-Process -FilePath '${esc(pythonExe)}' -ArgumentList @(${argsList}) -Verb RunAs -WindowStyle Hidden -PassThru -Wait; if ($p) { exit $p.ExitCode } else { exit 1 }`

  console.log('[*] PS1:', ps1)
  console.log('[*] Output:', outFile)

  await writeFile(ps1File, ps1, 'utf-8')

  return new Promise((resolve, reject) => {
    const ps = spawn('powershell', [
      '-NoProfile', '-NonInteractive',
      '-ExecutionPolicy', 'Bypass',
      '-File', ps1File
    ], { windowsHide: true })

    let psStderr = ''
    ps.stderr.on('data', chunk => {
      psStderr += chunk.toString()
      console.error('[PS stderr]', chunk.toString().trim())
    })
    ps.stdout.on('data', chunk => {
      console.log('[PS stdout]', chunk.toString().trim())
    })

    ps.on('close', async code => {
      unlink(ps1File).catch(() => {})
      console.log('[*] PowerShell exit code:', code)

      // ✅ Polling : attend jusqu'à 5 minutes que Python crée le fichier JSON
      const maxWait   = 5 * 60 * 1000   // 5 min
      const interval  = 2000             // vérifie toutes les 2s
      const startWait = Date.now()

      const waitForFile = async () => {
        while (Date.now() - startWait < maxWait) {
          try {
            await access(outFile)
            console.log('[OK] Fichier JSON trouve')

            const data   = await readFile(outFile, 'utf-8')
            const parsed = JSON.parse(data.trim())
            unlink(outFile).catch(() => {})
            resolve(parsed)
            return
          } catch {
            // Fichier pas encore prêt — attend
            await new Promise(r => setTimeout(r, interval))
          }
        }
        reject(new Error(
          `Timeout : Python n'a pas cree le fichier JSON en 5 minutes.\n` +
          `Code PS: ${code}\nPS stderr: ${psStderr}`
        ))
      }

      waitForFile()
    })

    ps.on('error', err => {
      reject(new Error(`PowerShell introuvable : ${err.message}`))
    })
  })
})

function createWindow(devServerUrl = null) {
  const preloadPath = join(__dirname, '..', 'preload', 'index.js')
  const win = new BrowserWindow({
    width: 1280, height: 800,
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

app.whenReady().then(() => {
  const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:3000'
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
