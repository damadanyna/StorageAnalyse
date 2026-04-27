import { ipcMain, app, BrowserWindow } from "electron";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { tmpdir } from "os";
import { existsSync } from "fs";
import __cjs_mod__ from "node:module";
const __filename = import.meta.filename;
const __dirname = import.meta.dirname;
const require2 = __cjs_mod__.createRequire(import.meta.url);
const __filename$1 = fileURLToPath(import.meta.url);
const __dirname$1 = dirname(__filename$1);
function getPythonPath() {
  if (app.isPackaged) {
    return join(process.resourcesPath, "python-embed", "python.exe");
  }
  return join(__dirname$1, "..", "..", "resources", "python-embed", "python.exe");
}
function getScriptPath() {
  if (app.isPackaged) {
    return join(process.resourcesPath, "python", "mft_reader.py");
  }
  return join(__dirname$1, "..", "..", "python", "mft_reader.py");
}
function normalizeDriveLetter(drive = "C") {
  return String(drive).trim().replace(/[:\\/]+$/g, "").charAt(0).toUpperCase() || "C";
}
function getAvailableDrives() {
  const drives = [];
  for (let code = 67; code <= 90; code += 1) {
    const letter = String.fromCharCode(code);
    if (existsSync(`${letter}:\\`)) drives.push(letter);
  }
  return drives;
}
const mftCache = {
  drive: null,
  records: {},
  // ref -> { name, is_dir, ext, size_bytes, size_display, parent }
  tree: {}
  // parent_ref -> [child_refs]
};
function emitScanProgress(target, payload) {
  target?.send("mft:scan-progress", {
    timestamp: (/* @__PURE__ */ new Date()).toISOString(),
    ...payload
  });
}
function inferStage(message) {
  const text = String(message || "").toLowerCase();
  if (text.includes("cache usn")) return "cache";
  if (text.includes("delta usn")) return "delta";
  if (text.includes("ouverture du volume")) return "open";
  if (text.includes("passe 1")) return "usn-enum";
  if (text.includes("passe 2")) return "mft-read";
  if (text.includes("passe 3")) return "fallback";
  if (text.includes("expor")) return "finalize";
  return "scan";
}
function attachLineBuffer(stream, onLine) {
  let buffer = "";
  stream.on("data", (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      onLine(trimmed);
    }
  });
  stream.on("end", () => {
    const trimmed = buffer.trim();
    if (trimmed) onLine(trimmed);
  });
}
function buildCache(payload, drive) {
  mftCache.drive = drive;
  mftCache.records = payload?.cache?.records ?? {};
  mftCache.tree = payload?.cache?.tree ?? {};
}
function parseJsonFromStdout(stdout) {
  const lines = stdout.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index];
    if (!line.startsWith("{") && !line.startsWith("[")) continue;
    return JSON.parse(line);
  }
  throw new Error(`Aucun JSON detecte dans la sortie Python. Extrait: ${stdout.slice(-500)}`);
}
function isAdminRequiredError(message) {
  const text = String(message || "").toLowerCase();
  return text.includes("admin requis") || text.includes("err=5") || text.includes("accès refusé") || text.includes("access denied");
}
function runPythonJson(args, options = {}) {
  return new Promise((resolve, reject) => {
    const { onProgress } = options;
    const pythonExe = getPythonPath();
    const child = spawn(pythonExe, [...args, "--stdout-json"], { windowsHide: true });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    attachLineBuffer(child.stderr, (line) => {
      stderr += `${line}
`;
      onProgress?.({ type: "log", stage: inferStage(line), message: line });
    });
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Python exit ${code}: ${stderr || stdout}`));
        return;
      }
      try {
        resolve(parseJsonFromStdout(stdout));
      } catch (error) {
        reject(new Error(`${error.message}
Stderr: ${stderr}`));
      }
    });
    child.on("error", (err) => reject(new Error(`Python: ${err.message}`)));
  });
}
function runPythonJsonElevated(args, options = {}) {
  return new Promise(async (resolve, reject) => {
    const { onProgress } = options;
    const { mkdir, writeFile, readFile, unlink, access } = await import("fs/promises");
    const tempDir = join(tmpdir(), "StorageAnalyse", "elevated-scan");
    await mkdir(tempDir, { recursive: true });
    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const stdoutPath = join(tempDir, `stdout-${stamp}.json`);
    const stderrPath = join(tempDir, `stderr-${stamp}.log`);
    const errorPath = join(tempDir, `launcher-${stamp}.log`);
    const cmdPath = join(tempDir, `run-${stamp}.cmd`);
    const scriptPath = join(tempDir, `launch-${stamp}.ps1`);
    const escapedPs = (value) => String(value).replace(/'/g, "''");
    const escapeBatch = (value) => String(value).replace(/\^/g, "^^").replace(/&/g, "^&").replace(/</g, "^<").replace(/>/g, "^>").replace(/\|/g, "^|").replace(/"/g, '""');
    const commandLine = [
      `"${escapeBatch(getPythonPath())}"`,
      ...args.map((arg) => `"${escapeBatch(arg)}"`),
      '"--stdout-json"',
      `1>"${escapeBatch(stdoutPath)}"`,
      `2>"${escapeBatch(stderrPath)}"`
    ].join(" ");
    const cmdScript = [
      "@echo off",
      "setlocal",
      commandLine,
      "exit /b %errorlevel%"
    ].join("\r\n");
    const psScript = [
      "$ErrorActionPreference = 'Stop'",
      "try {",
      `  $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/d', '/c', '""${escapedPs(cmdPath)}""' -Verb RunAs -PassThru -Wait`,
      "  if ($null -eq $proc) {",
      `    Set-Content -Path '${escapedPs(errorPath)}' -Value 'Le processus elevé n a pas demarre.'`,
      "    exit 1",
      "  }",
      "  exit $proc.ExitCode",
      "} catch {",
      `  Set-Content -Path '${escapedPs(errorPath)}' -Value $_.Exception.Message`,
      "  exit 1",
      "}"
    ].join("\n");
    await writeFile(cmdPath, cmdScript, "utf8");
    await writeFile(scriptPath, psScript, "utf8");
    onProgress?.({ type: "status", stage: "elevation", message: "Demande d autorisation administrateur..." });
    const child = spawn("powershell", [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      scriptPath
    ], { windowsHide: true });
    let launcherStderr = "";
    child.stderr.on("data", (chunk) => {
      launcherStderr += chunk.toString();
    });
    child.on("close", async (code) => {
      try {
        const payloadExists = await access(stdoutPath).then(() => true).catch(() => false);
        const [stdout, stderr, launcherError] = await Promise.all([
          payloadExists ? readFile(stdoutPath, "utf8").catch(() => "") : "",
          readFile(stderrPath, "utf8").catch(() => ""),
          readFile(errorPath, "utf8").catch(() => "")
        ]);
        await Promise.all([
          unlink(stdoutPath).catch(() => {
          }),
          unlink(stderrPath).catch(() => {
          }),
          unlink(errorPath).catch(() => {
          }),
          unlink(cmdPath).catch(() => {
          }),
          unlink(scriptPath).catch(() => {
          })
        ]);
        if (code !== 0 || !payloadExists) {
          const detail = stderr || launcherError || launcherStderr || "Elevation refusee, annulee, ou scan non produit.";
          reject(new Error(`Python elevated exit ${code}: ${detail}`));
          return;
        }
        try {
          onProgress?.({ type: "status", stage: "elevation", message: "Scan elevé termine, lecture du resultat..." });
          resolve(parseJsonFromStdout(stdout));
        } catch (error) {
          reject(new Error(`${error.message}
Stderr: ${stderr || launcherError || launcherStderr}`));
        }
      } catch (error) {
        reject(error);
      }
    });
    child.on("error", async (err) => {
      await Promise.all([
        unlink(stdoutPath).catch(() => {
        }),
        unlink(stderrPath).catch(() => {
        }),
        unlink(errorPath).catch(() => {
        }),
        unlink(cmdPath).catch(() => {
        }),
        unlink(scriptPath).catch(() => {
        })
      ]);
      reject(new Error(`PowerShell elevation: ${err.message}`));
    });
  });
}
async function runPythonJsonWithFallback(args, options = {}) {
  try {
    return await runPythonJson(args, options);
  } catch (error) {
    if (!isAdminRequiredError(error.message)) {
      throw error;
    }
    options.onProgress?.({ type: "warning", stage: "elevation", message: "Privileges admin requis, bascule vers elevation..." });
    return runPythonJsonElevated(args, options);
  }
}
ipcMain.handle("mft:scan", async (event, { drive = "C", depth = null } = {}) => {
  const scriptPath = getScriptPath();
  const normalizedDrive = normalizeDriveLetter(drive);
  const availableDrives = getAvailableDrives();
  if (!availableDrives.includes(normalizedDrive)) {
    throw new Error(`Le lecteur ${normalizedDrive}: est introuvable ou non monte.`);
  }
  const args = [scriptPath, normalizedDrive];
  if (depth !== null) args.push("--depth", String(depth));
  emitScanProgress(event.sender, {
    type: "status",
    stage: "start",
    message: `Initialisation du scan ${normalizedDrive}:`
  });
  try {
    const payload = await runPythonJsonWithFallback(args, {
      onProgress: (progress) => emitScanProgress(event.sender, progress)
    });
    buildCache(payload, normalizedDrive);
    console.log(`[*] Cache: ${Object.keys(mftCache.records).length} records`);
    emitScanProgress(event.sender, {
      type: "success",
      stage: "done",
      message: "Analyse terminee.",
      scanInfo: payload.scan_info ?? null
    });
    return {
      summary: payload.summary ?? [],
      scanInfo: payload.scan_info ?? null
    };
  } catch (error) {
    emitScanProgress(event.sender, {
      type: "error",
      stage: "error",
      message: error.message
    });
    throw error;
  }
});
ipcMain.handle("mft:files", async (event, { drive = "C", folderRef } = {}) => {
  const normalizedDrive = normalizeDriveLetter(drive);
  if (!mftCache.drive || mftCache.drive !== normalizedDrive) {
    console.warn("[!] Cache vide ou drive different");
    return [];
  }
  const childRefs = mftCache.tree[folderRef] ?? [];
  const files = [];
  for (const ref of childRefs) {
    const rec = mftCache.records[ref];
    if (!rec || rec.is_dir) continue;
    files.push({
      record_number: ref,
      name: rec.name,
      is_dir: false,
      ext: rec.ext,
      size_bytes: rec.size_bytes,
      size_display: rec.size_display,
      child: []
    });
  }
  files.sort((a, b) => b.size_bytes - a.size_bytes);
  console.log(`[*] getFiles(${folderRef}): ${files.length} fichiers`);
  return files;
});
ipcMain.handle("mft:children", async (event, { drive = "C", folderRef } = {}) => {
  const normalizedDrive = normalizeDriveLetter(drive);
  if (!mftCache.drive || mftCache.drive !== normalizedDrive) {
    console.warn("[!] Cache vide ou drive different");
    return [];
  }
  const childRefs = mftCache.tree[String(folderRef)] ?? mftCache.tree[folderRef] ?? [];
  const folders = [];
  for (const ref of childRefs) {
    const rec = mftCache.records[String(ref)] ?? mftCache.records[ref];
    if (!rec || rec.is_dir === false) continue;
    folders.push({
      record_number: rec.record_number ?? ref,
      name: rec.name,
      is_dir: true,
      size_bytes: rec.size_bytes,
      size_display: rec.size_display,
      child_count: rec.child_count ?? 0,
      file_count: rec.file_count ?? 0,
      child: []
    });
  }
  folders.sort((a, b) => b.size_bytes - a.size_bytes);
  return folders;
});
ipcMain.handle("mft:drives", async () => {
  return getAvailableDrives();
});
function createWindow(devServerUrl = null) {
  const preloadPath = join(__dirname$1, "..", "preload", "index.js");
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  if (devServerUrl) {
    win.loadURL(devServerUrl);
    win.webContents.openDevTools();
  } else {
    win.loadFile(join(__dirname$1, "..", "renderer", "index.html")).catch((err) => {
      console.error("loadFile failed:", err);
      win.loadFile(join(process.resourcesPath, "app", "out", "renderer", "index.html")).catch(console.error);
    });
  }
}
function getDevServerUrl() {
  if (app.isPackaged) return null;
  return process.env.VITE_DEV_SERVER_URL ?? "http://localhost:3000";
}
app.whenReady().then(() => {
  createWindow(getDevServerUrl());
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow(getDevServerUrl());
  }
});
