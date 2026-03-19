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
const mftCache = {
  drive: null,
  records: {},
  // ref -> { name, is_dir, ext, size_bytes, size_display, parent }
  tree: {}
  // parent_ref -> [child_refs]
};
function buildCache(summary, drive) {
  mftCache.drive = drive;
  mftCache.records = {};
  mftCache.tree = {};
  function indexNode(node, parentRef) {
    mftCache.records[node.record_number] = {
      name: node.name,
      is_dir: node.is_dir !== false,
      ext: node.ext ?? "",
      size_bytes: node.size_bytes,
      size_display: node.size_display
    };
    if (parentRef != null) {
      if (!mftCache.tree[parentRef]) mftCache.tree[parentRef] = [];
      mftCache.tree[parentRef].push(node.record_number);
    }
    if (node.child?.length) {
      for (const child of node.child) {
        indexNode(child, node.record_number);
      }
    }
    if (node.files?.length) {
      for (const file of node.files) {
        mftCache.records[file.record_number] = {
          name: file.name,
          is_dir: false,
          ext: file.ext ?? "",
          size_bytes: file.size_bytes,
          size_display: file.size_display
        };
        if (!mftCache.tree[node.record_number]) mftCache.tree[node.record_number] = [];
        mftCache.tree[node.record_number].push(file.record_number);
      }
    }
  }
  for (const node of summary) indexNode(node, null);
}
function runPythonWithAdmin(args, tempDir) {
  return new Promise(async (resolve, reject) => {
    const { mkdir, writeFile, readFile, unlink, access } = await import("fs/promises");
    await mkdir(tempDir, { recursive: true });
    const ts = Date.now();
    const outFile = `${tempDir}\\mft_out_${ts}.json`;
    const ps1File = `${tempDir}\\mft_scan_${ts}.ps1`;
    const pythonExe = getPythonPath();
    const esc = (s) => s.replace(/'/g, "''");
    const argsList = [...args, "--output", outFile].map((a) => `'${esc(a)}'`).join(", ");
    const ps1 = `$p = Start-Process -FilePath '${esc(pythonExe)}' -ArgumentList @(${argsList}) -Verb RunAs -WindowStyle Hidden -PassThru -Wait; if ($p) { exit $p.ExitCode } else { exit 1 }`;
    await writeFile(ps1File, ps1, "utf-8");
    const ps = spawn("powershell", [
      "-NoProfile",
      "-NonInteractive",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      ps1File
    ], { windowsHide: true });
    let psStderr = "";
    ps.stderr.on("data", (c) => {
      psStderr += c.toString();
    });
    ps.stdout.on("data", (c) => console.log("[PS]", c.toString().trim()));
    ps.on("close", async (code) => {
      unlink(ps1File).catch(() => {
      });
      console.log("[*] PS exit:", code);
      const maxWait = 5 * 60 * 1e3;
      const start = Date.now();
      while (Date.now() - start < maxWait) {
        try {
          await access(outFile);
          const data = await readFile(outFile, "utf-8");
          const parsed = JSON.parse(data.trim());
          unlink(outFile).catch(() => {
          });
          resolve(parsed);
          return;
        } catch {
          await new Promise((r) => setTimeout(r, 2e3));
        }
      }
      reject(new Error(`Timeout. Code PS: ${code}. ${psStderr}`));
    });
    ps.on("error", (err) => reject(new Error(`PowerShell: ${err.message}`)));
  });
}
ipcMain.handle("mft:scan", async (event, { drive = "C", depth = null } = {}) => {
  const scriptPath = getScriptPath();
  const args = [scriptPath, drive];
  if (depth !== null) args.push("--depth", String(depth));
  const summary = await runPythonWithAdmin(args, "C:\\Temp");
  buildCache(summary, drive);
  console.log(`[*] Cache: ${Object.keys(mftCache.records).length} records`);
  return summary;
});
ipcMain.handle("mft:files", async (event, { drive = "C", folderRef } = {}) => {
  if (!mftCache.drive || mftCache.drive !== drive) {
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
