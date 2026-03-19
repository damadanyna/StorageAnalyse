import { ipcMain, app, BrowserWindow } from "electron";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
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
ipcMain.handle("mft:scan", async (event, { drive = "C", depth = null } = {}) => {
  const pythonExe = getPythonPath();
  const scriptPath = getScriptPath();
  const { mkdir, writeFile, readFile, unlink, access } = await import("fs/promises");
  const tempDir = "C:\\Temp";
  await mkdir(tempDir, { recursive: true });
  const ts = Date.now();
  const outFile = `${tempDir}\\mft_out_${ts}.json`;
  const ps1File = `${tempDir}\\mft_scan_${ts}.ps1`;
  const args = [scriptPath, drive, "--output", outFile];
  if (depth !== null) args.push("--depth", String(depth));
  const esc = (s) => s.replace(/'/g, "''");
  const argsList = args.map((a) => `'${esc(a)}'`).join(", ");
  const ps1 = `$p = Start-Process -FilePath '${esc(pythonExe)}' -ArgumentList @(${argsList}) -Verb RunAs -WindowStyle Hidden -PassThru -Wait; if ($p) { exit $p.ExitCode } else { exit 1 }`;
  console.log("[*] PS1:", ps1);
  console.log("[*] Output:", outFile);
  await writeFile(ps1File, ps1, "utf-8");
  return new Promise((resolve, reject) => {
    const ps = spawn("powershell", [
      "-NoProfile",
      "-NonInteractive",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      ps1File
    ], { windowsHide: true });
    let psStderr = "";
    ps.stderr.on("data", (chunk) => {
      psStderr += chunk.toString();
      console.error("[PS stderr]", chunk.toString().trim());
    });
    ps.stdout.on("data", (chunk) => {
      console.log("[PS stdout]", chunk.toString().trim());
    });
    ps.on("close", async (code) => {
      unlink(ps1File).catch(() => {
      });
      console.log("[*] PowerShell exit code:", code);
      const maxWait = 5 * 60 * 1e3;
      const interval = 2e3;
      const startWait = Date.now();
      const waitForFile = async () => {
        while (Date.now() - startWait < maxWait) {
          try {
            await access(outFile);
            console.log("[OK] Fichier JSON trouve");
            const data = await readFile(outFile, "utf-8");
            const parsed = JSON.parse(data.trim());
            unlink(outFile).catch(() => {
            });
            resolve(parsed);
            return;
          } catch {
            await new Promise((r) => setTimeout(r, interval));
          }
        }
        reject(new Error(
          `Timeout : Python n'a pas cree le fichier JSON en 5 minutes.
Code PS: ${code}
PS stderr: ${psStderr}`
        ));
      };
      waitForFile();
    });
    ps.on("error", (err) => {
      reject(new Error(`PowerShell introuvable : ${err.message}`));
    });
  });
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
    win.loadFile(join(__dirname$1, "..", "renderer", "index.html"));
  }
}
app.whenReady().then(() => {
  const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? "http://localhost:3000";
  createWindow(devServerUrl);
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    const devServerUrl = process.env.VITE_DEV_SERVER_URL ?? "http://localhost:3000";
    createWindow(devServerUrl);
  }
});
