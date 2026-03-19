"""
mft_reader.py
-----------------------------------------------------------------
Enumeration NTFS via FSCTL_ENUM_USN_DATA + FSCTL_GET_NTFS_FILE_RECORD.
Passe 3 : GetFileAttributesEx pour les fichiers verrouilles.

[!]  PREREQUIS : Windows, droits Administrateur
UTILISATION :
    python mft_reader.py              -> scan C:\\ par defaut
    python mft_reader.py D:\\         -> scan le volume D:
    python mft_reader.py C:\\ --json  -> exporte dans mft_output.json
-----------------------------------------------------------------
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os, sys, json, struct, ctypes, ctypes.wintypes, argparse
from datetime import datetime
from collections import defaultdict

# -- Win32 constants -----------------------------------------------
GENERIC_READ               = 0x80000000
FILE_SHARE_READ            = 0x00000001
FILE_SHARE_WRITE           = 0x00000002
OPEN_EXISTING              = 3
INVALID_HANDLE             = ctypes.c_void_p(-1).value
FSCTL_ENUM_USN_DATA        = 0x900B3
FSCTL_GET_NTFS_FILE_RECORD = 0x90068
FILE_ATTRIBUTE_DIRECTORY   = 0x10
READ_BUFFER_SIZE           = 65536

USN_OFF_RECORD_LEN   = 0
USN_OFF_FILE_REF     = 8
USN_OFF_PARENT_REF   = 16
USN_OFF_FILE_ATTR    = 52
USN_OFF_FILENAME_LEN = 56
USN_OFF_FILENAME_OFF = 58

SIGNATURE_FILE     = b"FILE"
ATTR_DATA          = 0x80
ATTR_END           = 0xFFFFFFFF
NTFS_OUTPUT_HEADER = 12

# -- kernel32 ------------------------------------------------------
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateFileW.restype  = ctypes.c_void_p
_k32.CreateFileW.argtypes = [
    ctypes.c_wchar_p, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.c_void_p]
_k32.DeviceIoControl.restype  = ctypes.wintypes.BOOL
_k32.DeviceIoControl.argtypes = [
    ctypes.c_void_p, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.c_void_p]
_k32.CloseHandle.restype  = ctypes.wintypes.BOOL
_k32.CloseHandle.argtypes = [ctypes.c_void_p]

# GetFileAttributesExW pour les fichiers verrouilles
class WIN32_FILE_ATTRIBUTE_DATA(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes",  ctypes.wintypes.DWORD),
        ("ftCreationTime",    ctypes.wintypes.FILETIME),
        ("ftLastAccessTime",  ctypes.wintypes.FILETIME),
        ("ftLastWriteTime",   ctypes.wintypes.FILETIME),
        ("nFileSizeHigh",     ctypes.wintypes.DWORD),
        ("nFileSizeLow",      ctypes.wintypes.DWORD),
    ]

_k32.GetFileAttributesExW.restype  = ctypes.wintypes.BOOL
_k32.GetFileAttributesExW.argtypes = [
    ctypes.c_wchar_p,
    ctypes.c_int,       # GET_FILEEX_INFO_LEVELS = 0
    ctypes.c_void_p,
]


def open_volume(drive_letter: str):
    letter = drive_letter.rstrip(":\\/")[0].upper()
    path   = f"\\\\.\\{letter}:"
    handle = _k32.CreateFileW(
        path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None)
    if handle == INVALID_HANDLE or handle is None:
        raise OSError(f"Impossible d'ouvrir {path} (err={ctypes.get_last_error()}). Admin requis.")
    return handle


# -- Enumeration USN -----------------------------------------------

def enum_usn_data(handle):
    next_ref  = 0
    max_usn   = 0x7FFFFFFFFFFFFFFF
    out_buf   = ctypes.create_string_buffer(READ_BUFFER_SIZE)
    bytes_ret = ctypes.wintypes.DWORD(0)
    seen_refs = set()

    while True:
        in_buf = struct.pack("<QQQ", next_ref, 0, max_usn)
        ok = _k32.DeviceIoControl(
            handle, FSCTL_ENUM_USN_DATA,
            in_buf, len(in_buf),
            out_buf, READ_BUFFER_SIZE,
            ctypes.byref(bytes_ret), None)

        nb = bytes_ret.value
        if nb < 8:
            break

        new_next = struct.unpack_from("<Q", out_buf.raw, 0)[0]

        if new_next == next_ref or new_next in seen_refs:
            break

        seen_refs.add(next_ref)
        next_ref = new_next

        pos = 8
        while pos + 60 <= nb:
            rec_len = struct.unpack_from("<I", out_buf.raw, pos + USN_OFF_RECORD_LEN)[0]
            if rec_len == 0 or rec_len > nb:
                break

            file_ref   = struct.unpack_from("<Q", out_buf.raw, pos + USN_OFF_FILE_REF)[0]
            parent_ref = struct.unpack_from("<Q", out_buf.raw, pos + USN_OFF_PARENT_REF)[0]
            file_attr  = struct.unpack_from("<I", out_buf.raw, pos + USN_OFF_FILE_ATTR)[0]
            fn_len     = struct.unpack_from("<H", out_buf.raw, pos + USN_OFF_FILENAME_LEN)[0]
            fn_off     = struct.unpack_from("<H", out_buf.raw, pos + USN_OFF_FILENAME_OFF)[0]

            name_start = pos + fn_off
            name_end   = name_start + fn_len
            name = out_buf.raw[name_start:name_end].decode("utf-16-le", errors="replace") \
                   if name_end <= nb else ""

            ref    = file_ref   & 0x0000FFFFFFFFFFFF
            parent = parent_ref & 0x0000FFFFFFFFFFFF

            yield ref, parent, name, bool(file_attr & FILE_ATTRIBUTE_DIRECTORY)
            pos += rec_len


# -- Taille via FSCTL_GET_NTFS_FILE_RECORD -------------------------

class _INPUT(ctypes.Structure):
    _fields_ = [("FileReferenceNumber", ctypes.c_ulonglong)]


def _apply_fixup(data: bytearray) -> bytearray:
    uo = struct.unpack_from("<H", data, 4)[0]
    uc = struct.unpack_from("<H", data, 6)[0]
    if uo == 0 or uc < 2: return data
    us = data[uo: uo+2]
    for i in range(1, uc):
        se = i * 512 - 2
        if se + 2 > len(data): break
        if data[se:se+2] == us:
            fx = data[uo+i*2: uo+i*2+2]
            data[se] = fx[0]; data[se+1] = fx[1]
    return data


ATTR_FILE_NAME = 0x30
NS_PRIORITY    = {1: 3, 3: 2, 0: 1, 2: 0}

def get_file_size_fsctl(handle, file_ref: int, out_buf, bytes_ret) -> int:
    """
    Taille depuis MFT record via FSCTL_GET_NTFS_FILE_RECORD.
    Lit $DATA (non-resident) ET $FILE_NAME, retourne le maximum.
    Cas reparse point : $DATA resident contient ~137 bytes (tag),
    la vraie taille est dans $FILE_NAME.
    """
    in_s = _INPUT(FileReferenceNumber=file_ref)
    ok   = _k32.DeviceIoControl(
        handle, FSCTL_GET_NTFS_FILE_RECORD,
        ctypes.byref(in_s), ctypes.sizeof(in_s),
        out_buf, len(out_buf),
        ctypes.byref(bytes_ret), None)

    if not ok or bytes_ret.value < NTFS_OUTPUT_HEADER + 8:
        return 0

    rec_len  = struct.unpack_from("<I", out_buf.raw, 8)[0]
    rec_data = bytearray(out_buf.raw[NTFS_OUTPUT_HEADER: NTFS_OUTPUT_HEADER + rec_len])

    if rec_data[:4] != SIGNATURE_FILE:
        return 0

    rec_data   = _apply_fixup(rec_data)
    offset     = struct.unpack_from("<H", rec_data, 0x14)[0]
    data_size  = 0   # taille depuis $DATA
    fn_size    = 0   # taille depuis $FILE_NAME (meilleur namespace)
    fn_ns      = -1  # namespace courant

    while offset + 4 <= len(rec_data):
        at = struct.unpack_from("<I", rec_data, offset)[0]
        if at == ATTR_END: break
        if offset + 8 > len(rec_data): break
        al = struct.unpack_from("<I", rec_data, offset + 4)[0]
        if al == 0 or offset + al > len(rec_data): break

        if at == ATTR_DATA:
            if rec_data[offset + 8] == 0:
                # Resident : on ne prend cette taille QUE si pas de $DATA non-resident
                cl = struct.unpack_from("<I", rec_data, offset + 0x10)[0]
                if cl > 0 and data_size == 0:
                    data_size = cl
            else:
                # Non-resident : source la plus fiable -> priorite absolue
                if offset + 0x38 <= len(rec_data):
                    real = struct.unpack_from("<Q", rec_data, offset + 0x30)[0]
                    if real > 0:
                        data_size = real  # non-resident ecrase le resident

        elif at == ATTR_FILE_NAME:
            if rec_data[offset + 8] == 0:   # toujours resident
                co      = struct.unpack_from("<H", rec_data, offset + 0x14)[0]
                cl      = struct.unpack_from("<I", rec_data, offset + 0x10)[0]
                content = rec_data[offset + co: offset + co + cl]
                if len(content) >= 0x38:
                    ns      = content[0x41] if len(content) > 0x41 else -1
                    fn_real = struct.unpack_from("<Q", content, 0x30)[0]
                    # Garde la taille du meilleur namespace (WIN32 prioritaire)
                    if NS_PRIORITY.get(ns, -1) > NS_PRIORITY.get(fn_ns, -1):
                        fn_size = fn_real
                        fn_ns   = ns

        offset += al

    # Logique de selection finale :
    # - $DATA non-resident  -> toujours prioritaire (fichier normal)
    # - $DATA resident petit + fn_size grand -> reparse/sparse -> prendre fn_size
    # - Pas de $DATA        -> prendre fn_size
    if data_size > 0 and fn_size > 0:
        # Si fn_size >> data_size c'est un reparse point (ex: ISO sparse)
        # On prend le maximum
        return max(data_size, fn_size)
    return data_size or fn_size


def get_file_size_fallback(path: str) -> int:
    """
    Fallback pour les fichiers verrouilles :
    GetFileAttributesExW lit les metadonnees sans ouvrir le fichier.
    Fonctionne sur hiberfil.sys, pagefile.sys, etc.
    """
    info = WIN32_FILE_ATTRIBUTE_DATA()
    ok   = _k32.GetFileAttributesExW(path, 0, ctypes.byref(info))
    if not ok:
        return 0
    return (info.nFileSizeHigh << 32) | info.nFileSizeLow


# -- Lecteur principal ---------------------------------------------

class MFTReader:
    def __init__(self, drive: str):
        self.drive       = drive.rstrip(":\\/")[0].upper()
        self.handle      = None
        self.records     : dict[int, dict] = {}
        self.folder_tree : dict[int, list] = defaultdict(list)

    def open(self):
        print(f"[*] Ouverture du volume {self.drive}: ...")
        self.handle = open_volume(self.drive)
        print("[OK] Volume ouvert")

    def close(self):
        if self.handle:
            _k32.CloseHandle(self.handle)
            self.handle = None

    def read_all_records(self, max_records: int = None):
        if not self.handle:
            raise RuntimeError("Appelle open() d'abord.")

        # -- Passe 1 : USN enumeration -----------------------------
        print("[>] Passe 1 ? Enumeration USN...")
        n_files = n_dirs = 0

        for ref, parent, name, is_dir in enum_usn_data(self.handle):
            if not name:
                continue
            self.records[ref] = {"name": name, "parent": parent,
                                  "is_dir": is_dir, "file_size": 0}
            if parent != ref:
                self.folder_tree[parent].append(ref)
            if is_dir: n_dirs += 1
            else:      n_files += 1

            if max_records and (n_files + n_dirs) >= max_records:
                break
            if (n_files + n_dirs) % 100_000 == 0 and (n_files + n_dirs) > 0:
                print(f"   {n_files+n_dirs:,} entrees "
                      f"({n_files:,} fichiers, {n_dirs:,} dossiers)...")

        print(f"[OK] Passe 1 : {n_files+n_dirs:,} entrees "
              f"({n_files:,} fichiers, {n_dirs:,} dossiers)")

        # -- Passe 2 : tailles via FSCTL ---------------------------
        print("[~] Passe 2 ? Lecture des tailles (FSCTL_GET_NTFS_FILE_RECORD)...")
        file_refs   = [r for r, rec in self.records.items() if not rec["is_dir"]]
        total_files = len(file_refs)
        found = done = 0

        out_buf   = ctypes.create_string_buffer(NTFS_OUTPUT_HEADER + 4096)
        bytes_ret = ctypes.wintypes.DWORD(0)

        for ref in file_refs:
            size = get_file_size_fsctl(self.handle, ref, out_buf, bytes_ret)
            if size > 0:
                self.records[ref]["file_size"] = size
                found += 1
            done += 1
            if done % 100_000 == 0:
                print(f"   {done/total_files*100:.0f}% ? "
                      f"{done:,}/{total_files:,} ({found:,} avec taille)")

        print(f"[OK] Passe 2 : {found:,}/{total_files:,} fichiers avec taille")

        # -- Passe 3 : fallback GetFileAttributesEx ----------------
        # Pour les ~37k fichiers dont FSCTL a echoue (verrouilles, sparse...)
        zero_refs = [r for r, rec in self.records.items()
                     if not rec["is_dir"] and rec["file_size"] == 0]

        if zero_refs:
            print(f"[~] Passe 3 ? Fallback sur {len(zero_refs):,} fichiers "
                  f"(GetFileAttributesEx)...")

            # Reconstruit les chemins complets pour GetFileAttributesExW
            found3 = 0
            for ref in zero_refs:
                path = self._get_full_path_fast(ref)
                if not path:
                    continue
                size = get_file_size_fallback(path)
                if size > 0:
                    self.records[ref]["file_size"] = size
                    found3 += 1

            print(f"[OK] Passe 3 : {found3:,}/{len(zero_refs):,} tailles recuperees")

        # -- Resume final ------------------------------------------
        total_gb = sum(rec["file_size"] for rec in self.records.values()
                       if not rec["is_dir"]) / 1024**3
        remaining_zero = sum(1 for rec in self.records.values()
                             if not rec["is_dir"] and rec["file_size"] == 0)
        print(f"[=] Total compte : {total_gb:.2f} GB "
              f"({remaining_zero:,} fichiers encore a 0)")

    def _get_full_path_fast(self, ref: int, _depth: int = 0) -> str:
        """Reconstruit le chemin complet d'un fichier."""
        if _depth > 64:
            return ""
        rec = self.records.get(ref)
        if not rec:
            return ""
        parent = rec["parent"]
        if parent is None or parent == ref or parent == 5:
            return f"{self.drive}:\\{rec['name']}"
        parent_path = self._get_full_path_fast(parent, _depth + 1)
        if not parent_path:
            return ""
        return f"{parent_path}\\{rec['name']}"

    # -- Tailles dossiers ------------------------------------------

    def compute_folder_sizes(self) -> dict:
        sizes = {}
        def acc(ref):
            if ref in sizes: return sizes[ref]
            rec = self.records.get(ref)
            t   = rec["file_size"] if rec and not rec["is_dir"] else \
                  sum(acc(c) for c in self.folder_tree.get(ref, []))
            sizes[ref] = t
            return t
        for ref, rec in self.records.items():
            if rec["is_dir"]: acc(ref)
        return sizes

    def build_summary(self, max_depth=None):
        sizes   = self.compute_folder_sizes()
        results = []
        for ref in self.folder_tree.get(5, []):
            rec = self.records.get(ref)
            if not rec or not rec["is_dir"]: continue
            size = sizes.get(ref, 0)

            # Fichiers directs du dossier racine
            files = []
            for fref in self.folder_tree.get(ref, []):
                frec = self.records.get(fref)
                if not frec or frec["is_dir"]: continue
                fname = frec["name"]
                fext  = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                files.append({
                    "record_number": fref,
                    "name":          fname,
                    "is_dir":        False,
                    "ext":           fext,
                    "size_bytes":    frec["file_size"],
                    "size_display":  _fmt(frec["file_size"]),
                })
            files.sort(key=lambda x: -x["size_bytes"])

            results.append({
                "record_number": ref,
                "name":          rec["name"],
                "is_dir":        True,
                "size_bytes":    size,
                "size_display":  _fmt(size),
                "file_count":    len(files),
                "files":         files,
                "child":         self._ch(ref, sizes, 1, max_depth)
            })
        results.sort(key=lambda x: x["size_bytes"], reverse=True)
        return results

    def _ch(self, parent, sizes, depth, max_depth):
        if max_depth is not None and depth >= max_depth: return []
        out = []
        for ref in self.folder_tree.get(parent, []):
            rec = self.records.get(ref)
            if not rec or not rec["is_dir"]: continue
            size = sizes.get(ref, 0)

            # Collecte les fichiers directs de ce dossier
            files = []
            for fref in self.folder_tree.get(ref, []):
                frec = self.records.get(fref)
                if not frec or frec["is_dir"]: continue
                fname = frec["name"]
                fext  = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                files.append({
                    "record_number": fref,
                    "name":          fname,
                    "is_dir":        False,
                    "ext":           fext,
                    "size_bytes":    frec["file_size"],
                    "size_display":  _fmt(frec["file_size"]),
                })
            files.sort(key=lambda x: -x["size_bytes"])

            out.append({
                "record_number": ref,
                "name":          rec["name"],
                "is_dir":        True,
                "size_bytes":    size,
                "size_display":  _fmt(size),
                "file_count":    len(files),
                "files":         files,
                "child":         self._ch(ref, sizes, depth+1, max_depth)
            })
        out.sort(key=lambda x: -x["size_bytes"])
        return out

    def get_folder_files(self, folder_ref: int) -> list:
        """Retourne les fichiers directs d un dossier (charge a la demande)."""
        files = []
        for ref in self.folder_tree.get(folder_ref, []):
            rec = self.records.get(ref)
            if not rec or rec["is_dir"]: continue
            name = rec["name"]
            ext  = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            files.append({
                "record_number": ref,
                "name":          name,
                "is_dir":        False,
                "ext":           ext,
                "size_bytes":    rec["file_size"],
                "size_display":  _fmt(rec["file_size"]),
                "child":         []
            })
        files.sort(key=lambda x: -x["size_bytes"])
        return files

    def export_json(self, path, max_depth=None):
        s = self.build_summary(max_depth=max_depth)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2, default=str)
        print(f"[S] Exporte -> {path} ({len(s)} dossiers racine)")


def _fmt(n):
    for u, t in (("TB",1024**4),("GB",1024**3),("MB",1024**2),("KB",1024)):
        if n >= t: return f"{n/t:.2f} {u}"
    return f"{n} B"


def main_electron():
    """
    Point d'entree compatible CLI et Electron.

    Usage CLI :
        python mft_reader.py C:\\ --json
        python mft_reader.py C:\\ --depth 3

    Usage Electron (depuis index.js) :
        python mft_reader.py C --output "C:\\tmp\\result.json" --depth 3
    """
    p = argparse.ArgumentParser(description="Lecteur MFT NTFS via USN + FSCTL")
    p.add_argument("drive",         nargs="?", default="C:\\",
                   help="Lettre du lecteur (ex: C ou C:\\)")
    p.add_argument("--depth",       type=int,  default=None,
                   help="Profondeur max de l'arborescence")
    p.add_argument("--output",      type=str,  default=None,
                   help="Chemin JSON de sortie (mode Electron)")
    p.add_argument("--json",        action="store_true",
                   help="Exporte dans mft_output.json (mode CLI)")
    p.add_argument("--max-records", type=int,  default=None,
                   help="Limite records lus (tests)")
    p.add_argument("--files",       type=int,  default=None,
                   help="Retourne les fichiers du dossier ref donne")
    a = p.parse_args()

    r = MFTReader(a.drive)
    try:
        start = datetime.now()
        r.open()
        r.read_all_records(max_records=a.max_records)

        # Mode --files : retourne les fichiers directs d un dossier
        if a.files is not None:
            files = r.get_folder_files(a.files)
            if a.output:
                with open(a.output, "w", encoding="utf-8") as f:
                    json.dump(files, f, ensure_ascii=False, default=str)
                print(f"[OK] {len(files)} fichiers -> {a.output}", flush=True)
            else:
                print(json.dumps(files, ensure_ascii=False, default=str))
            return

        summary = r.build_summary(max_depth=a.depth)
        elapsed = (datetime.now() - start).total_seconds()

        if a.output:
            # Mode Electron : ecrit dans le fichier specifie par index.js
            with open(a.output, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, default=str)
            print(f"[OK] Exporte -> {a.output} ({len(summary)} dossiers, {elapsed:.1f}s)",
                  flush=True)

        elif a.json:
            # Mode CLI --json
            out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "mft_output.json")
            r.export_json(out, max_depth=a.depth)

        else:
            # Mode CLI console
            print(f"\n[t]  Termine en {elapsed:.2f}s\n")
            print(f"{'Dossier':<40} {'Taille':>12}")
            print("-" * 54)
            for f in summary[:20]:
                print(f"{f['name']:<40} {f['size_display']:>12}")

    except PermissionError as e:
        print(f"[ERR] {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"[ERR] {e}", file=sys.stderr, flush=True)
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        r.close()
if __name__ == "__main__":
    main_electron()