import { app, BrowserWindow, ipcMain, shell, clipboard } from 'electron'
import { spawn } from 'child_process'
import { fileURLToPath } from 'url'
import { join, dirname, extname } from 'path'
import { tmpdir } from 'os'
import { existsSync, statfsSync } from 'fs'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

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

function normalizeDriveLetter(drive = 'C') {
  return String(drive).trim().replace(/[:\\/]+$/g, '').charAt(0).toUpperCase() || 'C'
}

function getAvailableDrives() {
  const drives = []
  for (let code = 67; code <= 90; code += 1) {
    const letter = String.fromCharCode(code)
    if (existsSync(`${letter}:\\`)) drives.push(letter)
  }
  return drives
}

function getDriveUsage(drive = 'C') {
  const normalizedDrive = normalizeDriveLetter(drive)
  const rootPath = `${normalizedDrive}:\\`
  const stats = statfsSync(rootPath)
  const blockSize = Number(stats.bsize || stats.frsize || 0)
  const totalBytes = blockSize * Number(stats.blocks || 0)
  const freeBytes = blockSize * Number(stats.bavail || stats.bfree || 0)
  const usedBytes = Math.max(0, totalBytes - freeBytes)
  const usedPercent = totalBytes > 0 ? Math.min(100, Math.max(0, Math.round((usedBytes / totalBytes) * 100))) : 0

  return {
    drive: normalizedDrive,
    totalBytes,
    freeBytes,
    usedBytes,
    usedPercent,
    totalDisplay: formatBytes(totalBytes),
    freeDisplay: formatBytes(freeBytes),
    usedDisplay: formatBytes(usedBytes),
  }
}

// ── Cache MFT en mémoire ──────────────────────────────────────
// Stocke tous les records après le scan pour servir les fichiers
// sans relancer Python
const mftCacheByDrive = new Map()
const activeScans = new Map()
const watcherProcesses = new Map()
let isAppShuttingDown = false

const STARTUP_SCAN_DEPTH = 1
const WATCHER_RESTART_MS = 5000

const PYTHON_PROGRESS_PREFIX = '__SCAN_PROGRESS__'

function emitScanProgress(target, payload) {
  target?.send('mft:scan-progress', {
    timestamp: new Date().toISOString(),
    ...payload,
  })
}

function emitCacheUpdated(payload) {
  const windows = BrowserWindow.getAllWindows()
  for (const win of windows) {
    win.webContents.send('mft:cache-updated', {
      timestamp: new Date().toISOString(),
      ...payload,
    })
  }
}

function inferStage(message) {
  const text = String(message || '').toLowerCase()
  if (text.includes('cache usn')) return 'cache'
  if (text.includes('delta usn')) return 'delta'
  if (text.includes('ouverture du volume')) return 'open'
  if (text.includes('passe 1')) return 'usn-enum'
  if (text.includes('passe 2')) return 'mft-read'
  if (text.includes('passe 3')) return 'fallback'
  if (text.includes('expor')) return 'finalize'
  return 'scan'
}

function attachLineBuffer(stream, onLine) {
  let buffer = ''
  stream.on('data', chunk => {
    buffer += chunk.toString()
    const lines = buffer.split(/\r?\n/)
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      onLine(trimmed)
    }
  })
  stream.on('end', () => {
    const trimmed = buffer.trim()
    if (trimmed) onLine(trimmed)
  })
}

function buildCache(payload, drive) {
  mftCacheByDrive.set(drive, {
    drive,
    records: payload?.cache?.records ?? {},
    tree: payload?.cache?.tree ?? {},
    summary: payload?.summary ?? [],
    scanInfo: payload?.scan_info ?? null,
    updatedAt: new Date().toISOString(),
  })
}

function getCachedDriveState(drive) {
  return mftCacheByDrive.get(drive) ?? null
}

function formatBytes(value = 0) {
  const size = Number(value) || 0
  if (size >= 1024 ** 4) return `${(size / 1024 ** 4).toFixed(2)} TB`
  if (size >= 1024 ** 3) return `${(size / 1024 ** 3).toFixed(2)} GB`
  if (size >= 1024 ** 2) return `${(size / 1024 ** 2).toFixed(2)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(2)} KB`
  return `${size} B`
}

function buildRecordPath(records, record, guard = 0) {
  if (!record || guard > 64) return ''
  const name = record.name ?? ''
  const parentRef = record.parent
  if (parentRef === undefined || parentRef === null || parentRef === record.record_number || parentRef === 5) {
    return name
  }

  const parent = records[String(parentRef)] ?? records[parentRef]
  const parentPath = buildRecordPath(records, parent, guard + 1)
  if (!parentPath) return name
  return `${parentPath}\\${name}`
}

function resolveRecordAbsolutePath(drive, records, record) {
  const relativePath = buildRecordPath(records, record)
  return relativePath ? `${drive}:\\${relativePath}` : `${drive}:\\${record?.name ?? ''}`
}

function normalizeTypeFilter(typeFilter) {
  const normalized = String(typeFilter || '').trim().toLowerCase()
  return normalized || null
}

function recordMatchesType(record, typeFilter) {
  if (!typeFilter) return true
  if (!record || record.is_dir !== false) return false
  const ext = String(record.ext || '').trim().toLowerCase() || '(sans extension)'
  return ext === typeFilter
}

function folderContainsType(records, tree, folderRef, typeFilter, memo = new Map()) {
  if (!typeFilter) return true

  const cacheKey = String(folderRef)
  if (memo.has(cacheKey)) {
    return memo.get(cacheKey)
  }

  const childRefs = tree[cacheKey] ?? tree[folderRef] ?? []
  let matches = false

  for (const ref of childRefs) {
    const record = records[String(ref)] ?? records[ref]
    if (!record) continue

    if (record.is_dir === false) {
      if (recordMatchesType(record, typeFilter)) {
        matches = true
        break
      }
      continue
    }

    if (folderContainsType(records, tree, record.record_number ?? ref, typeFilter, memo)) {
      matches = true
      break
    }
  }

  memo.set(cacheKey, matches)
  return matches
}

function inferPreviewKind(targetPath) {
  const extension = extname(targetPath).toLowerCase()
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'].includes(extension)) return 'image'
  if (['.txt', '.md', '.json', '.js', '.ts', '.vue', '.css', '.scss', '.html', '.xml', '.yml', '.yaml', '.py', '.log', '.csv'].includes(extension)) return 'text'
  return 'unsupported'
}

function getDriveHighlights(drive, options = {}) {
  const normalizedDrive = normalizeDriveLetter(drive)
  const driveCache = getCachedDriveState(normalizedDrive)
  if (!driveCache) {
    return {
      drive: normalizedDrive,
      folders: [],
      files: [],
      generatedAt: null,
    }
  }

  const limit = Math.max(1, Math.min(Number(options.limit) || 5, 20))
  const summary = Array.isArray(driveCache.summary) ? driveCache.summary : []
  const records = driveCache.records ?? {}

  const folders = summary
    .slice()
    .sort((left, right) => (right.size_bytes ?? 0) - (left.size_bytes ?? 0))
    .slice(0, limit)
    .map(folder => ({
      record_number: folder.record_number,
      name: folder.name,
      path: `${normalizedDrive}:\\${folder.name}`,
      size_bytes: folder.size_bytes ?? 0,
      size_display: folder.size_display ?? formatBytes(folder.size_bytes),
      child_count: folder.child_count ?? 0,
      file_count: folder.file_count ?? 0,
    }))

  const files = Object.values(records)
    .filter(record => record && record.is_dir === false)
    .sort((left, right) => (right.size_bytes ?? 0) - (left.size_bytes ?? 0))
    .slice(0, limit)
    .map(record => ({
      record_number: record.record_number,
      name: record.name,
      path: resolveRecordAbsolutePath(normalizedDrive, records, record),
      size_bytes: record.size_bytes ?? 0,
      size_display: record.size_display ?? formatBytes(record.size_bytes),
      ext: record.ext ?? '',
      preview_kind: inferPreviewKind(record.name ?? ''),
    }))

  return {
    drive: normalizedDrive,
    folders,
    files,
    generatedAt: driveCache.updatedAt ?? null,
  }
}

function getDriveDistribution(drive, options = {}) {
  const normalizedDrive = normalizeDriveLetter(drive)
  const driveCache = getCachedDriveState(normalizedDrive)
  if (!driveCache) {
    return {
      drive: normalizedDrive,
      rootFolders: [],
      fileTypes: [],
      generatedAt: null,
    }
  }

  const limit = Math.max(1, Math.min(Number(options.limit) || 6, 12))
  const summary = Array.isArray(driveCache.summary) ? driveCache.summary : []
  const records = driveCache.records ?? {}

  const rootFolders = summary
    .slice()
    .sort((left, right) => (right.size_bytes ?? 0) - (left.size_bytes ?? 0))
    .slice(0, limit)
    .map(folder => ({
      key: String(folder.record_number),
      label: folder.name,
      path: `${normalizedDrive}:\\${folder.name}`,
      size_bytes: folder.size_bytes ?? 0,
      size_display: folder.size_display ?? formatBytes(folder.size_bytes),
    }))

  const typeBuckets = new Map()
  for (const record of Object.values(records)) {
    if (!record || record.is_dir !== false) continue
    const ext = String(record.ext || '').trim().toLowerCase()
    const key = ext || '(sans extension)'
    const current = typeBuckets.get(key) ?? { key, label: key, size_bytes: 0, count: 0 }
    current.size_bytes += record.size_bytes ?? 0
    current.count += 1
    typeBuckets.set(key, current)
  }

  const fileTypes = [...typeBuckets.values()]
    .sort((left, right) => right.size_bytes - left.size_bytes)
    .slice(0, limit)
    .map(entry => ({
      ...entry,
      size_display: formatBytes(entry.size_bytes),
    }))

  return {
    drive: normalizedDrive,
    rootFolders,
    fileTypes,
    generatedAt: driveCache.updatedAt ?? null,
  }
}

async function readPathPreview(targetPath) {
  const { readFile, stat } = await import('fs/promises')
  if (!targetPath || !existsSync(targetPath)) {
    throw new Error('Chemin introuvable.')
  }

  const details = await stat(targetPath)
  if (details.isDirectory()) {
    return {
      kind: 'directory',
      path: targetPath,
      name: targetPath.split('\\').pop() ?? targetPath,
      message: 'Ce dossier peut etre ouvert ou supprime, mais il n a pas de lecture directe.',
    }
  }

  const kind = inferPreviewKind(targetPath)
  if (kind === 'image') {
    const buffer = await readFile(targetPath)
    const extension = extname(targetPath).toLowerCase().replace('.', '') || 'png'
    return {
      kind,
      path: targetPath,
      name: targetPath.split('\\').pop() ?? targetPath,
      mime: `image/${extension === 'jpg' ? 'jpeg' : extension}`,
      content: buffer.toString('base64'),
    }
  }

  if (kind === 'text') {
    const buffer = await readFile(targetPath)
    const content = buffer.toString('utf8').slice(0, 120_000)
    return {
      kind,
      path: targetPath,
      name: targetPath.split('\\').pop() ?? targetPath,
      content,
      truncated: buffer.length > 120_000,
    }
  }

  return {
    kind: 'unsupported',
    path: targetPath,
    name: targetPath.split('\\').pop() ?? targetPath,
    message: 'Apercu non disponible pour ce type de fichier.',
  }
}

function parseJsonFromStdout(stdout) {
  const lines = stdout
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index]
    if (!line.startsWith('{') && !line.startsWith('[')) continue
    return JSON.parse(line)
  }

  throw new Error(`Aucun JSON detecte dans la sortie Python. Extrait: ${stdout.slice(-500)}`)
}

function isAdminRequiredError(message) {
  const text = String(message || '').toLowerCase()
  return text.includes('admin requis') || text.includes('err=5') || text.includes('accès refusé') || text.includes('access denied')
}

function runPythonJson(args, options = {}) {
  return new Promise((resolve, reject) => {
    const { onProgress } = options
    const pythonExe = getPythonPath()
    const child = spawn(pythonExe, [...args, '--stdout-json'], { windowsHide: true })

    let stdout = ''
    let stderr = ''

    child.stdout.on('data', chunk => {
      stdout += chunk.toString()
    })

    attachLineBuffer(child.stderr, line => {
      stderr += `${line}\n`
      emitPythonProgressLine(line, onProgress)
    })

    child.on('close', code => {
      if (code !== 0) {
        reject(new Error(`Python exit ${code}: ${stderr || stdout}`))
        return
      }

      try {
        resolve(parseJsonFromStdout(stdout))
      } catch (error) {
        reject(new Error(`${error.message}\nStderr: ${stderr}`))
      }
    })

    child.on('error', err => reject(new Error(`Python: ${err.message}`)))
  })
}

function emitPythonProgressLine(line, onProgress) {
  if (!line) return
  if (line.startsWith(PYTHON_PROGRESS_PREFIX)) {
    try {
      const payload = JSON.parse(line.slice(PYTHON_PROGRESS_PREFIX.length))
      onProgress?.({ type: 'progress', stage: payload.stage ?? 'scan', ...payload })
      return
    } catch {
      // Ignore malformed structured progress and fall through to plain log handling.
    }
  }

  onProgress?.({ type: 'log', stage: inferStage(line), message: line })
}

function runPythonJsonElevated(args, options = {}) {
  return new Promise(async (resolve, reject) => {
    const { onProgress } = options
    const { mkdir, writeFile, readFile, unlink, access } = await import('fs/promises')
    const tempDir = join(tmpdir(), 'StorageAnalyse', 'elevated-scan')
    await mkdir(tempDir, { recursive: true })

    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const stdoutPath = join(tempDir, `stdout-${stamp}.json`)
    const stderrPath = join(tempDir, `stderr-${stamp}.log`)
    const errorPath = join(tempDir, `launcher-${stamp}.log`)
    const cmdPath = join(tempDir, `run-${stamp}.cmd`)
    const scriptPath = join(tempDir, `launch-${stamp}.ps1`)

    const escapedPs = value => String(value).replace(/'/g, "''")
    const escapeBatch = value => String(value).replace(/\^/g, '^^').replace(/&/g, '^&').replace(/</g, '^<').replace(/>/g, '^>').replace(/\|/g, '^|').replace(/"/g, '""')
    const commandLine = [
      `"${escapeBatch(getPythonPath())}"`,
      ...args.map(arg => `"${escapeBatch(arg)}"`),
      '"--stdout-json"',
      `1>"${escapeBatch(stdoutPath)}"`,
      `2>"${escapeBatch(stderrPath)}"`,
    ].join(' ')
    const cmdScript = [
      '@echo off',
      'setlocal',
      commandLine,
      'exit /b %errorlevel%',
    ].join('\r\n')
    const psScript = [
      "$ErrorActionPreference = 'Stop'",
      'try {',
      `  $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/d', '/c', '""${escapedPs(cmdPath)}""' -Verb RunAs -WindowStyle Hidden -PassThru -Wait`,
      '  if ($null -eq $proc) {',
      `    Set-Content -Path '${escapedPs(errorPath)}' -Value 'Le processus elevé n a pas demarre.'`,
      '    exit 1',
      '  }',
      '  exit $proc.ExitCode',
      '} catch {',
      `  Set-Content -Path '${escapedPs(errorPath)}' -Value $_.Exception.Message`,
      '  exit 1',
      '}',
    ].join('\n')

    await writeFile(cmdPath, cmdScript, 'utf8')
    await writeFile(scriptPath, psScript, 'utf8')
    onProgress?.({ type: 'status', stage: 'elevation', message: 'Demande d autorisation administrateur...' })

    const child = spawn('powershell', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', scriptPath,
    ], { windowsHide: true })

    let launcherStderr = ''
    let stderrSnapshotLength = 0
    let stderrBuffer = ''

    const flushElevatedStderr = async () => {
      const content = await readFile(stderrPath, 'utf8').catch(() => '')
      if (content.length <= stderrSnapshotLength) return

      const delta = content.slice(stderrSnapshotLength)
      stderrSnapshotLength = content.length
      stderrBuffer += delta

      const lines = stderrBuffer.split(/\r?\n/)
      stderrBuffer = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        emitPythonProgressLine(trimmed, onProgress)
      }
    }

    const stderrTimer = setInterval(() => {
      flushElevatedStderr().catch(() => { })
    }, 350)

    child.stderr.on('data', chunk => {
      launcherStderr += chunk.toString()
    })

    child.on('close', async code => {
      try {
        clearInterval(stderrTimer)
        await flushElevatedStderr().catch(() => { })

        const payloadExists = await access(stdoutPath).then(() => true).catch(() => false)
        const [stdout, stderr, launcherError] = await Promise.all([
          payloadExists ? readFile(stdoutPath, 'utf8').catch(() => '') : '',
          readFile(stderrPath, 'utf8').catch(() => ''),
          readFile(errorPath, 'utf8').catch(() => ''),
        ])

        await Promise.all([
          unlink(stdoutPath).catch(() => { }),
          unlink(stderrPath).catch(() => { }),
          unlink(errorPath).catch(() => { }),
          unlink(cmdPath).catch(() => { }),
          unlink(scriptPath).catch(() => { }),
        ])

        if (code !== 0 || !payloadExists) {
          const detail = stderr || launcherError || launcherStderr || 'Elevation refusee, annulee, ou scan non produit.'
          reject(new Error(`Python elevated exit ${code}: ${detail}`))
          return
        }

        try {
          onProgress?.({ type: 'status', stage: 'elevation', message: 'Scan elevé termine, lecture du resultat...' })
          resolve(parseJsonFromStdout(stdout))
        } catch (error) {
          reject(new Error(`${error.message}\nStderr: ${stderr || launcherError || launcherStderr}`))
        }
      } catch (error) {
        reject(error)
      }
    })

    child.on('error', async err => {
      clearInterval(stderrTimer)
      await Promise.all([
        unlink(stdoutPath).catch(() => { }),
        unlink(stderrPath).catch(() => { }),
        unlink(errorPath).catch(() => { }),
        unlink(cmdPath).catch(() => { }),
        unlink(scriptPath).catch(() => { }),
      ])
      reject(new Error(`PowerShell elevation: ${err.message}`))
    })
  })
}

async function runPythonJsonWithFallback(args, options = {}) {
  try {
    return await runPythonJson(args, options)
  } catch (error) {
    if (!isAdminRequiredError(error.message)) {
      throw error
    }
    options.onProgress?.({ type: 'warning', stage: 'elevation', message: 'Privileges admin requis, bascule vers elevation...' })
    return runPythonJsonElevated(args, options)
  }
}

async function executeDriveScan(drive, options = {}) {
  const { depth = STARTUP_SCAN_DEPTH, progressTargets = [], emitLifecycle = true, notifyCacheUpdate = true } = options
  const scriptPath = getScriptPath()
  const args = [scriptPath, drive]
  if (depth !== null) args.push('--depth', String(depth))

  const emitToTargets = payload => {
    for (const target of progressTargets) emitScanProgress(target, payload)
  }

  if (emitLifecycle && progressTargets.size > 0) {
    emitToTargets({
      type: 'status',
      stage: 'start',
      message: `Initialisation du scan ${drive}:`,
    })
  }

  const payload = await runPythonJsonWithFallback(args, {
    onProgress: progress => emitToTargets(progress),
  })

  buildCache(payload, drive)

  if (emitLifecycle && progressTargets.size > 0) {
    emitToTargets({
      type: 'success',
      stage: 'done',
      message: 'Analyse terminee.',
      scanInfo: payload.scan_info ?? null,
    })
  }

  if (notifyCacheUpdate) {
    emitCacheUpdated({
      drive,
      summary: payload.summary ?? [],
      scanInfo: payload.scan_info ?? null,
    })
  }

  return payload
}

async function ensureDriveScanned(drive, options = {}) {
  const normalizedDrive = normalizeDriveLetter(drive)
  const availableDrives = getAvailableDrives()
  if (!availableDrives.includes(normalizedDrive)) {
    throw new Error(`Le lecteur ${normalizedDrive}: est introuvable ou non monte.`)
  }

  const progressTarget = options.progressTarget ?? null
  const existing = activeScans.get(normalizedDrive)
  if (existing) {
    if (progressTarget) existing.progressTargets.add(progressTarget)
    return existing.promise
  }

  const progressTargets = new Set(progressTarget ? [progressTarget] : [])
  const scanPromise = executeDriveScan(normalizedDrive, {
    ...options,
    progressTargets,
  }).finally(() => {
    activeScans.delete(normalizedDrive)
  })

  activeScans.set(normalizedDrive, { promise: scanPromise, progressTargets })
  return scanPromise
}

async function warmupAllDrives() {
  const drives = getAvailableDrives()
  for (const drive of drives) {
    try {
      await ensureDriveScanned(drive, {
        depth: STARTUP_SCAN_DEPTH,
        emitLifecycle: false,
        notifyCacheUpdate: true,
      })
    } catch (error) {
      console.warn(`[warmup] ${drive}: ${error.message}`)
    }
  }
}

function startDriveWatcher(drive) {
  const normalizedDrive = normalizeDriveLetter(drive)
  if (watcherProcesses.has(normalizedDrive)) return

  const watcherArgs = [getScriptPath(), normalizedDrive, '--watch', '--depth', String(STARTUP_SCAN_DEPTH), '--stdout-json']
  const child = spawn(getPythonPath(), watcherArgs, { windowsHide: true })
  const state = { child, stderr: '' }
  watcherProcesses.set(normalizedDrive, state)

  attachLineBuffer(child.stdout, line => {
    try {
      const event = JSON.parse(line)
      if (!event?.payload) return
      buildCache(event.payload, normalizedDrive)
      emitCacheUpdated({
        drive: normalizedDrive,
        summary: event.payload.summary ?? [],
        scanInfo: event.payload.scan_info ?? null,
        watchEventType: event.type ?? 'update',
        deltaEntries: event.deltaEntries ?? 0,
      })
    } catch (error) {
      console.warn(`[watcher:${normalizedDrive}] JSON invalide: ${error.message}`)
    }
  })

  attachLineBuffer(child.stderr, line => {
    state.stderr += `${line}\n`
    console.log(`[watcher:${normalizedDrive}] ${line}`)
  })

  child.on('close', code => {
    watcherProcesses.delete(normalizedDrive)
    if (isAppShuttingDown) return

    const stderr = state.stderr.toLowerCase()
    const blocked = stderr.includes('admin requis') || stderr.includes('err=5') || stderr.includes('access denied')
    if (blocked) {
      console.warn(`[watcher:${normalizedDrive}] arret sans redemarrage: privileges insuffisants`)
      return
    }

    console.warn(`[watcher:${normalizedDrive}] termine (code ${code}), redemarrage programme`)
    setTimeout(() => {
      if (!isAppShuttingDown && getAvailableDrives().includes(normalizedDrive)) {
        startDriveWatcher(normalizedDrive)
      }
    }, WATCHER_RESTART_MS)
  })

  child.on('error', error => {
    watcherProcesses.delete(normalizedDrive)
    if (!isAppShuttingDown) {
      console.warn(`[watcher:${normalizedDrive}] erreur: ${error.message}`)
    }
  })
}

function startAllDriveWatchers() {
  for (const drive of getAvailableDrives()) {
    startDriveWatcher(drive)
  }
}

function stopAllDriveWatchers() {
  isAppShuttingDown = true
  for (const { child } of watcherProcesses.values()) {
    child.kill()
  }
  watcherProcesses.clear()
}

// ── Handler : scan complet ────────────────────────────────────
ipcMain.handle('mft:scan', async (event, { drive = 'C', depth = null } = {}) => {
  try {
    const payload = await ensureDriveScanned(drive, {
      depth,
      progressTarget: event.sender,
      emitLifecycle: true,
      notifyCacheUpdate: true,
    })

    return {
      summary: payload.summary ?? [],
      scanInfo: payload.scan_info ?? null,
    }
  } catch (error) {
    emitScanProgress(event.sender, {
      type: 'error',
      stage: 'error',
      message: error.message,
    })
    throw error
  }
})

// ── Handler : fichiers d'un dossier (depuis le cache) ─────────
ipcMain.handle('mft:files', async (event, { drive = 'C', folderRef, typeFilter = null } = {}) => {
  const normalizedDrive = normalizeDriveLetter(drive)
  const driveCache = getCachedDriveState(normalizedDrive)
  const normalizedTypeFilter = normalizeTypeFilter(typeFilter)
  // Si pas de cache ou mauvais drive → retourne tableau vide
  if (!driveCache) {
    console.warn('[!] Cache vide ou drive different')
    return []
  }

  const childRefs = driveCache.tree[folderRef] ?? []
  const files = []

  for (const ref of childRefs) {
    const rec = driveCache.records[String(ref)] ?? driveCache.records[ref]
    if (!rec || rec.is_dir) continue
    if (!recordMatchesType(rec, normalizedTypeFilter)) continue
    files.push({
      record_number: ref,
      name: rec.name,
      is_dir: false,
      ext: rec.ext,
      path: resolveRecordAbsolutePath(normalizedDrive, driveCache.records, rec),
      size_bytes: rec.size_bytes,
      size_display: rec.size_display,
      preview_kind: inferPreviewKind(rec.name ?? ''),
      child: []
    })
  }

  // Trie par taille décroissante
  files.sort((a, b) => b.size_bytes - a.size_bytes)
  console.log(`[*] getFiles(${folderRef}): ${files.length} fichiers`)
  return files
})

ipcMain.handle('mft:children', async (event, { drive = 'C', folderRef, typeFilter = null } = {}) => {
  const normalizedDrive = normalizeDriveLetter(drive)
  const driveCache = getCachedDriveState(normalizedDrive)
  const normalizedTypeFilter = normalizeTypeFilter(typeFilter)
  if (!driveCache) {
    console.warn('[!] Cache vide ou drive different')
    return []
  }

  const childRefs = driveCache.tree[String(folderRef)] ?? driveCache.tree[folderRef] ?? []
  const folders = []
  const memo = new Map()

  for (const ref of childRefs) {
    const rec = driveCache.records[String(ref)] ?? driveCache.records[ref]
    if (!rec || rec.is_dir === false) continue
    if (!folderContainsType(driveCache.records, driveCache.tree, rec.record_number ?? ref, normalizedTypeFilter, memo)) continue
    folders.push({
      record_number: rec.record_number ?? ref,
      name: rec.name,
      is_dir: true,
      path: resolveRecordAbsolutePath(normalizedDrive, driveCache.records, rec),
      size_bytes: rec.size_bytes,
      size_display: rec.size_display,
      child_count: rec.child_count ?? 0,
      file_count: rec.file_count ?? 0,
      child: []
    })
  }

  folders.sort((a, b) => b.size_bytes - a.size_bytes)
  return folders
})

ipcMain.handle('mft:drives', async () => {
  return getAvailableDrives()
})

ipcMain.handle('mft:drive-usage', async (event, { drive = 'C' } = {}) => {
  return getDriveUsage(drive)
})

ipcMain.handle('mft:summary', async (event, { drive = 'C', typeFilter = null } = {}) => {
  const normalizedDrive = normalizeDriveLetter(drive)
  const driveCache = getCachedDriveState(normalizedDrive)
  const normalizedTypeFilter = normalizeTypeFilter(typeFilter)
  const summary = Array.isArray(driveCache?.summary) ? driveCache.summary : []
  const memo = new Map()
  return {
    summary: summary.filter(folder => folderContainsType(driveCache?.records ?? {}, driveCache?.tree ?? {}, folder.record_number, normalizedTypeFilter, memo)),
    scanInfo: driveCache?.scanInfo ?? null,
    cached: Boolean(driveCache),
    updatedAt: driveCache?.updatedAt ?? null,
  }
})

ipcMain.handle('mft:highlights', async (event, { drive = 'C', limit = 5 } = {}) => {
  return getDriveHighlights(drive, { limit })
})

ipcMain.handle('mft:distribution', async (event, { drive = 'C', limit = 6 } = {}) => {
  return getDriveDistribution(drive, { limit })
})

ipcMain.handle('clipboard:write-text', async (event, { text } = {}) => {
  clipboard.writeText(String(text ?? ''))
  return { ok: true }
})

ipcMain.handle('file:preview', async (event, { path } = {}) => {
  return readPathPreview(path)
})

ipcMain.handle('shell:file-icon', async (event, { path, size = 'normal' } = {}) => {
  if (!path || !existsSync(path)) {
    return { dataUrl: null }
  }

  const icon = await app.getFileIcon(path, { size: size === 'small' ? 'small' : 'normal' })
  return {
    dataUrl: icon?.isEmpty?.() ? null : icon.toDataURL(),
  }
})

let folderIconModule
async function loadFolderIconModule() {
  if (folderIconModule === undefined) {
    try {
      folderIconModule = await import('folder-icon')
    } catch {
      folderIconModule = null
    }
  }
  return folderIconModule
}

ipcMain.handle('shell:jumbo-icon', async (event, { path, size = 256 } = {}) => {
  if (!path || !existsSync(path)) {
    return { dataUrl: null }
  }

  const module = await loadFolderIconModule()
  if (!module) {
    return { dataUrl: null }
  }

  try {
    const buffer = await module.getJumboIcon(path, size)
    return { dataUrl: `data:image/png;base64,${buffer.toString('base64')}` }
  } catch {
    return { dataUrl: null }
  }
})

ipcMain.handle('shell:open-path', async (event, { path } = {}) => {
  if (!path || !existsSync(path)) {
    throw new Error('Chemin introuvable.')
  }
  const error = await shell.openPath(path)
  if (error) {
    throw new Error(error)
  }
  return { ok: true }
})

ipcMain.handle('shell:reveal-path', async (event, { path } = {}) => {
  if (!path || !existsSync(path)) {
    throw new Error('Chemin introuvable.')
  }
  shell.showItemInFolder(path)
  return { ok: true }
})

ipcMain.handle('shell:trash-path', async (event, { path } = {}) => {
  if (!path || !existsSync(path)) {
    throw new Error('Chemin introuvable.')
  }
  await shell.trashItem(path)
  return { ok: true }
})

ipcMain.handle('window:minimize', event => {
  BrowserWindow.fromWebContents(event.sender)?.minimize()
  return { ok: true }
})

ipcMain.handle('window:toggle-maximize', event => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return { isMaximized: false }
  if (win.isMaximized()) {
    win.unmaximize()
  } else {
    win.maximize()
  }
  return { isMaximized: win.isMaximized() }
})

ipcMain.handle('window:close', event => {
  BrowserWindow.fromWebContents(event.sender)?.close()
  return { ok: true }
})

ipcMain.handle('window:is-maximized', event => {
  return { isMaximized: BrowserWindow.fromWebContents(event.sender)?.isMaximized() ?? false }
})

// ── Fenêtre principale ────────────────────────────────────────
function createWindow(devServerUrl = null) {
  const preloadPath = join(__dirname, '..', 'preload', 'index.js')
  const win = new BrowserWindow({
    width: 1280, height: 800,
    show: false,
    frame: false,
    titleBarStyle: 'hidden',
    transparent: true,
    backgroundColor: '#00000000',
    autoHideMenuBar: true,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  win.removeMenu()

  const emitWindowState = () => {
    win.webContents.send('window:state', {
      isMaximized: win.isMaximized(),
    })
  }

  win.on('maximize', emitWindowState)
  win.on('unmaximize', emitWindowState)
  win.on('enter-full-screen', emitWindowState)
  win.on('leave-full-screen', emitWindowState)

  win.once('ready-to-show', () => {
    win.show()
    emitWindowState()
  })

  if (devServerUrl) {
    // ── Mode dev : charge depuis Vite dev server ──
    win.loadURL(devServerUrl)
    win.webContents.openDevTools()
  } else {
    // ── Mode production : charge le fichier buildé ──
    // electron-vite place le renderer dans out/renderer/index.html
    win.loadFile(join(__dirname, '..', 'renderer', 'index.html'))
      .catch(err => {
        console.error('loadFile failed:', err)
        // Fallback si le chemin est différent
        win.loadFile(join(process.resourcesPath, 'app', 'out', 'renderer', 'index.html'))
          .catch(console.error)
      })
    // ✅ Pas de openDevTools en production
  }
}

function getDevServerUrl() {
  if (app.isPackaged) return null
  return process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:3000'
}

app.whenReady().then(() => {
  createWindow(getDevServerUrl())
  warmupAllDrives().catch(error => {
    console.warn(`[warmup] ${error.message}`)
  }).finally(() => {
    startAllDriveWatchers()
  })
})

app.on('window-all-closed', () => {
  stopAllDriveWatchers()
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow(getDevServerUrl())
  }
})
