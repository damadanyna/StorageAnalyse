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
import sys, io, builtins, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os, sys, json, struct, ctypes, ctypes.wintypes, argparse, time
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
FSCTL_QUERY_USN_JOURNAL    = 0x900F4
FSCTL_READ_USN_JOURNAL     = 0x900BB
FILE_ATTRIBUTE_DIRECTORY   = 0x10
FILE_BEGIN                 = 0
READ_BUFFER_SIZE           = 65536

USN_OFF_RECORD_LEN   = 0
USN_OFF_FILE_REF     = 8
USN_OFF_PARENT_REF   = 16
USN_OFF_REASON       = 40
USN_OFF_FILE_ATTR    = 52
USN_OFF_FILENAME_LEN = 56
USN_OFF_FILENAME_OFF = 58

SIGNATURE_FILE     = b"FILE"
ATTR_DATA          = 0x80
FLAG_IN_USE        = 0x0001
ATTR_END           = 0xFFFFFFFF
NTFS_OUTPUT_HEADER = 12
CACHE_VERSION      = 1
USN_REASON_ANY     = 0xFFFFFFFF

_STDOUT_JSON_MODE = False
_PROGRESS_PREFIX = "__SCAN_PROGRESS__"


def print(*args, **kwargs):
    if _STDOUT_JSON_MODE and "file" not in kwargs:
        kwargs["file"] = sys.stderr
    return builtins.print(*args, **kwargs)


def set_stdout_json_mode(enabled: bool):
    global _STDOUT_JSON_MODE
    _STDOUT_JSON_MODE = enabled


def emit_progress(stage: str, message: str, **extra):
    payload = {"stage": stage, "message": message, **extra}
    builtins.print(f"{_PROGRESS_PREFIX}{json.dumps(payload, ensure_ascii=False)}", file=sys.stderr, flush=True)

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
_k32.SetFilePointerEx.restype = ctypes.wintypes.BOOL
_k32.SetFilePointerEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_longlong,
    ctypes.POINTER(ctypes.c_longlong),
    ctypes.wintypes.DWORD,
]
_k32.ReadFile.restype = ctypes.wintypes.BOOL
_k32.ReadFile.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.DWORD),
    ctypes.c_void_p,
]

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


class USN_JOURNAL_DATA_V0(ctypes.Structure):
    _fields_ = [
        ("UsnJournalID", ctypes.c_ulonglong),
        ("FirstUsn", ctypes.c_longlong),
        ("NextUsn", ctypes.c_longlong),
        ("LowestValidUsn", ctypes.c_longlong),
        ("MaxUsn", ctypes.c_longlong),
        ("MaximumSize", ctypes.c_ulonglong),
        ("AllocationDelta", ctypes.c_ulonglong),
    ]


def open_volume(drive_letter: str):
    letter = drive_letter.rstrip(":\\/")[0].upper()
    path   = f"\\\\.\\{letter}:"
    handle = _k32.CreateFileW(
        path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None)
    if handle == INVALID_HANDLE or handle is None:
        error_code = ctypes.get_last_error()
        if error_code == 2:
            raise OSError(f"Impossible d'ouvrir {path} (err=2). Lecteur introuvable ou non monte.")
        if error_code == 5:
            raise OSError(f"Impossible d'ouvrir {path} (err=5). Admin requis.")
        raise OSError(f"Impossible d'ouvrir {path} (err={error_code}).")
    return handle


def query_usn_journal(handle) -> dict | None:
    data = USN_JOURNAL_DATA_V0()
    bytes_ret = ctypes.wintypes.DWORD(0)
    ok = _k32.DeviceIoControl(
        handle, FSCTL_QUERY_USN_JOURNAL,
        None, 0,
        ctypes.byref(data), ctypes.sizeof(data),
        ctypes.byref(bytes_ret), None)
    if not ok:
        return None
    return {
        "journal_id": int(data.UsnJournalID),
        "next_usn": int(data.NextUsn),
        "lowest_valid_usn": int(data.LowestValidUsn),
    }


def get_cache_dir() -> str:
    root = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    cache_dir = os.path.join(root, "StorageAnalyse", "mft-cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_cache_path(drive: str) -> str:
    return os.path.join(get_cache_dir(), f"{drive.upper()}_summary.json")


def load_scan_cache_package(drive: str) -> dict | None:
    cache_path = get_cache_path(drive)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    metadata = cached.get("metadata", {})
    if metadata.get("version") != CACHE_VERSION:
        return None
    if metadata.get("drive") != drive.upper():
        return None
    return cached


def load_scan_cache(drive: str, journal_state: dict | None) -> dict | None:
    if journal_state is None:
        return None

    cached = load_scan_cache_package(drive)
    if cached is None:
        return None

    metadata = cached.get("metadata", {})
    if metadata.get("journal_id") != journal_state["journal_id"]:
        return None
    if metadata.get("next_usn") != journal_state["next_usn"]:
        return None

    payload = cached.get("payload")
    if not isinstance(payload, dict):
        return None
    return payload


def save_scan_cache(drive: str, journal_state: dict | None, payload: dict):
    if journal_state is None:
        return

    cache_path = get_cache_path(drive)
    cached = {
        "metadata": {
            "version": CACHE_VERSION,
            "drive": drive.upper(),
            "journal_id": journal_state["journal_id"],
            "next_usn": journal_state["next_usn"],
            "lowest_valid_usn": journal_state["lowest_valid_usn"],
        },
        "payload": payload,
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cached, f, ensure_ascii=False, default=str)


def emit_payload(payload: dict, output_path: str | None = None):
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        return
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.flush()


def annotate_payload(payload: dict, source: str, elapsed: float, delta_entries: int = 0) -> dict:
    payload["scan_info"] = {
        "source": source,
        "elapsed_seconds": round(elapsed, 2),
        "delta_entries": delta_entries,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    return payload


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


def read_usn_delta(handle, start_usn: int, journal_state: dict, limit_usn: int | None = None):
    out_buf = ctypes.create_string_buffer(1024 * 1024)
    bytes_ret = ctypes.wintypes.DWORD(0)
    next_usn = start_usn

    while True:
        in_buf = struct.pack(
            "<QIIQQQ",
            next_usn,
            USN_REASON_ANY,
            0,
            0,
            0,
            journal_state["journal_id"],
        )
        ok = _k32.DeviceIoControl(
            handle, FSCTL_READ_USN_JOURNAL,
            in_buf, len(in_buf),
            out_buf, len(out_buf),
            ctypes.byref(bytes_ret), None,
        )
        if not ok:
            raise OSError(f"READ_USN_JOURNAL a echoue (err={ctypes.get_last_error()})")

        nb = bytes_ret.value
        if nb < 8:
            break

        returned_next = struct.unpack_from("<Q", out_buf.raw, 0)[0]
        pos = 8
        while pos + 60 <= nb:
            rec_len = struct.unpack_from("<I", out_buf.raw, pos + USN_OFF_RECORD_LEN)[0]
            if rec_len == 0 or pos + rec_len > nb:
                break

            file_ref = struct.unpack_from("<Q", out_buf.raw, pos + USN_OFF_FILE_REF)[0]
            parent_ref = struct.unpack_from("<Q", out_buf.raw, pos + USN_OFF_PARENT_REF)[0]
            reason = struct.unpack_from("<I", out_buf.raw, pos + USN_OFF_REASON)[0]
            file_attr = struct.unpack_from("<I", out_buf.raw, pos + USN_OFF_FILE_ATTR)[0]
            fn_len = struct.unpack_from("<H", out_buf.raw, pos + USN_OFF_FILENAME_LEN)[0]
            fn_off = struct.unpack_from("<H", out_buf.raw, pos + USN_OFF_FILENAME_OFF)[0]

            name_start = pos + fn_off
            name_end = name_start + fn_len
            name = out_buf.raw[name_start:name_end].decode("utf-16-le", errors="replace") if name_end <= nb else ""

            yield {
                "ref": file_ref & 0x0000FFFFFFFFFFFF,
                "parent": parent_ref & 0x0000FFFFFFFFFFFF,
                "reason": reason,
                "name": name,
                "is_dir": bool(file_attr & FILE_ATTRIBUTE_DIRECTORY),
            }
            pos += rec_len

        if returned_next <= next_usn:
            break
        next_usn = returned_next
        if limit_usn is not None and next_usn >= limit_usn:
            break


def wait_for_usn_change(handle, start_usn: int, journal_state: dict, timeout_ms: int = 1500) -> tuple[int, bool]:
    out_buf = ctypes.create_string_buffer(4096)
    bytes_ret = ctypes.wintypes.DWORD(0)
    in_buf = struct.pack(
        "<QIIQQQ",
        start_usn,
        USN_REASON_ANY,
        0,
        timeout_ms,
        1,
        journal_state["journal_id"],
    )
    ok = _k32.DeviceIoControl(
        handle, FSCTL_READ_USN_JOURNAL,
        in_buf, len(in_buf),
        out_buf, len(out_buf),
        ctypes.byref(bytes_ret), None,
    )
    if not ok:
        raise OSError(f"READ_USN_JOURNAL attente a echoue (err={ctypes.get_last_error()})")

    if bytes_ret.value < 8:
        return start_usn, False

    returned_next = struct.unpack_from("<Q", out_buf.raw, 0)[0]
    has_records = bytes_ret.value > 8
    return returned_next, has_records


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


def read_handle_bytes(handle, offset: int, size: int) -> bytes:
    new_pos = ctypes.c_longlong(0)
    if not _k32.SetFilePointerEx(handle, offset, ctypes.byref(new_pos), FILE_BEGIN):
        raise OSError(f"SetFilePointerEx a echoue (err={ctypes.get_last_error()})")

    buffer = ctypes.create_string_buffer(size)
    bytes_ret = ctypes.wintypes.DWORD(0)
    if not _k32.ReadFile(handle, buffer, size, ctypes.byref(bytes_ret), None):
        raise OSError(f"ReadFile a echoue (err={ctypes.get_last_error()})")

    return buffer.raw[:bytes_ret.value]


def get_file_size_from_record_data(rec_data: bytes) -> int:
    if rec_data[:4] != SIGNATURE_FILE:
        return 0

    rec_data   = _apply_fixup(bytearray(rec_data))
    offset     = struct.unpack_from("<H", rec_data, 0x14)[0]
    data_size  = 0
    fn_size    = 0
    fn_ns      = -1

    while offset + 4 <= len(rec_data):
        at = struct.unpack_from("<I", rec_data, offset)[0]
        if at == ATTR_END:
            break
        if offset + 8 > len(rec_data):
            break
        al = struct.unpack_from("<I", rec_data, offset + 4)[0]
        if al == 0 or offset + al > len(rec_data):
            break

        if at == ATTR_DATA:
            if rec_data[offset + 8] == 0:
                cl = struct.unpack_from("<I", rec_data, offset + 0x10)[0]
                if cl > 0 and data_size == 0:
                    data_size = cl
            else:
                if offset + 0x38 <= len(rec_data):
                    real = struct.unpack_from("<Q", rec_data, offset + 0x30)[0]
                    if real > 0:
                        data_size = real

        elif at == ATTR_FILE_NAME:
            if rec_data[offset + 8] == 0:
                co      = struct.unpack_from("<H", rec_data, offset + 0x14)[0]
                cl      = struct.unpack_from("<I", rec_data, offset + 0x10)[0]
                content = rec_data[offset + co: offset + co + cl]
                if len(content) >= 0x38:
                    ns      = content[0x41] if len(content) > 0x41 else -1
                    fn_real = struct.unpack_from("<Q", content, 0x30)[0]
                    if NS_PRIORITY.get(ns, -1) > NS_PRIORITY.get(fn_ns, -1):
                        fn_size = fn_real
                        fn_ns   = ns

        offset += al

    if data_size > 0 and fn_size > 0:
        return max(data_size, fn_size)
    return data_size or fn_size


def get_mft_layout(handle) -> tuple[int, int, int]:
    vbr = read_handle_bytes(handle, 0, 512)
    if len(vbr) < 512:
        raise OSError("Lecture du boot sector incomplete")

    bytes_per_sector = struct.unpack_from("<H", vbr, 0x0B)[0]
    sectors_per_cluster = struct.unpack_from("<B", vbr, 0x0D)[0]
    mft_lcn = struct.unpack_from("<Q", vbr, 0x30)[0]
    clusters_per_record = struct.unpack_from("<b", vbr, 0x40)[0]

    bytes_per_cluster = bytes_per_sector * sectors_per_cluster
    record_size = 2 ** abs(clusters_per_record) if clusters_per_record < 0 else clusters_per_record * bytes_per_cluster
    mft_offset = mft_lcn * bytes_per_cluster

    record_zero = read_handle_bytes(handle, mft_offset, record_size)
    mft_size = get_file_size_from_record_data(record_zero)
    if mft_size <= 0:
        raise OSError("Impossible de determiner la taille du MFT")

    total_records = mft_size // record_size
    return mft_offset, record_size, total_records

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
    rec_data = out_buf.raw[NTFS_OUTPUT_HEADER: NTFS_OUTPUT_HEADER + rec_len]
    return get_file_size_from_record_data(rec_data)


def get_record_data_fsctl(handle, file_ref: int, out_buf, bytes_ret) -> bytes | None:
    in_s = _INPUT(FileReferenceNumber=file_ref)
    ok = _k32.DeviceIoControl(
        handle, FSCTL_GET_NTFS_FILE_RECORD,
        ctypes.byref(in_s), ctypes.sizeof(in_s),
        out_buf, len(out_buf),
        ctypes.byref(bytes_ret), None)
    if not ok or bytes_ret.value < NTFS_OUTPUT_HEADER + 8:
        return None
    rec_len = struct.unpack_from("<I", out_buf.raw, 8)[0]
    return out_buf.raw[NTFS_OUTPUT_HEADER: NTFS_OUTPUT_HEADER + rec_len]


def parse_record_snapshot(rec_data: bytes) -> dict | None:
    if not rec_data or rec_data[:4] != SIGNATURE_FILE:
        return None

    flags = struct.unpack_from("<H", rec_data, 0x16)[0]
    base_raw = struct.unpack_from("<Q", rec_data, 0x20)[0]
    base_ref = base_raw & 0x0000FFFFFFFFFFFF
    if not (flags & FLAG_IN_USE) or base_ref != 0:
        return None

    fixed = _apply_fixup(bytearray(rec_data))
    offset = struct.unpack_from("<H", fixed, 0x14)[0]
    name = ""
    parent = None
    best_ns = -1

    while offset + 4 <= len(fixed):
        attr_type = struct.unpack_from("<I", fixed, offset)[0]
        if attr_type == ATTR_END:
            break
        if offset + 8 > len(fixed):
            break
        attr_len = struct.unpack_from("<I", fixed, offset + 4)[0]
        if attr_len == 0 or offset + attr_len > len(fixed):
            break

        if attr_type == ATTR_FILE_NAME and fixed[offset + 8] == 0:
            content_offset = struct.unpack_from("<H", fixed, offset + 0x14)[0]
            content_len = struct.unpack_from("<I", fixed, offset + 0x10)[0]
            content = fixed[offset + content_offset: offset + content_offset + content_len]
            if len(content) >= 0x42:
                ns = content[0x41]
                if NS_PRIORITY.get(ns, -1) > NS_PRIORITY.get(best_ns, -1):
                    parent_raw = struct.unpack_from("<Q", content, 0)[0]
                    parent = parent_raw & 0x0000FFFFFFFFFFFF
                    name_len = content[0x40]
                    name_bytes = content[0x42: 0x42 + name_len * 2]
                    name = name_bytes.decode("utf-16-le", errors="replace")
                    best_ns = ns

        offset += attr_len

    if not name:
        return None

    return {
        "name": name,
        "parent": parent,
        "is_dir": bool(flags & FILE_ATTRIBUTE_DIRECTORY),
        "file_size": get_file_size_from_record_data(rec_data),
    }


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
        emit_progress("usn-enum", "Enumeration des entrees USN...", processedCount=0, totalCount=None)
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
                emit_progress(
                    "usn-enum",
                    f"{n_files+n_dirs:,} entrees recensees",
                    processedCount=n_files + n_dirs,
                    totalCount=max_records,
                    totalFiles=n_files,
                    totalDirs=n_dirs,
                )

        print(f"[OK] Passe 1 : {n_files+n_dirs:,} entrees "
              f"({n_files:,} fichiers, {n_dirs:,} dossiers)")
        emit_progress(
            "usn-enum",
            f"Passe 1 terminee : {n_files:,} fichiers, {n_dirs:,} dossiers",
            processedCount=n_files + n_dirs,
            totalCount=n_files + n_dirs,
            totalFiles=n_files,
            totalDirs=n_dirs,
        )

        # -- Passe 2 : tailles via lecture sequentielle du MFT -----
        print("[~] Passe 2 ? Lecture sequentielle du MFT...")
        file_refs   = [r for r, rec in self.records.items() if not rec["is_dir"]]
        total_files = len(file_refs)
        found = 0
        emit_progress("mft-read", "Lecture des fichiers de la MFT...", processedCount=0, totalCount=total_files, totalFiles=total_files)

        wanted_refs = set(file_refs)
        if wanted_refs:
            mft_offset, record_size, total_records = get_mft_layout(self.handle)
            max_ref = max(wanted_refs)
            record_limit = min(total_records, max_ref + 1)
            batch_records = max(1, 4 * 1024 * 1024 // record_size)
            done = 0

            for batch_start in range(0, record_limit, batch_records):
                count = min(batch_records, record_limit - batch_start)
                chunk = read_handle_bytes(self.handle, mft_offset + batch_start * record_size, count * record_size)

                for index in range(count):
                    ref = batch_start + index
                    if ref not in wanted_refs:
                        continue

                    start = index * record_size
                    record = chunk[start:start + record_size]
                    if len(record) < record_size or record[:4] != SIGNATURE_FILE:
                        done += 1
                        continue

                    flags = struct.unpack_from("<H", record, 0x16)[0]
                    base_raw = struct.unpack_from("<Q", record, 0x20)[0]
                    base_ref = base_raw & 0x0000FFFFFFFFFFFF
                    if not (flags & FLAG_IN_USE) or base_ref != 0:
                        done += 1
                        continue

                    size = get_file_size_from_record_data(record)
                    if size > 0:
                        self.records[ref]["file_size"] = size
                        found += 1
                    done += 1

                if done and done % 100_000 == 0:
                    print(f"   {done/total_files*100:.0f}% ? "
                          f"{done:,}/{total_files:,} ({found:,} avec taille)")

                if done and (done % 5000 == 0 or done == total_files):
                    current_name = self.records.get(ref, {}).get("name", "") if ref in self.records else ""
                    emit_progress(
                        "mft-read",
                        f"Analyse de {done:,}/{total_files:,} fichiers",
                        processedCount=done,
                        totalCount=total_files,
                        totalFiles=total_files,
                        filesWithSize=found,
                        currentFile=current_name,
                    )

        print(f"[OK] Passe 2 : {found:,}/{total_files:,} fichiers avec taille")
        emit_progress(
            "mft-read",
            f"Passe 2 terminee : {found:,}/{total_files:,} tailles trouvees",
            processedCount=total_files,
            totalCount=total_files,
            totalFiles=total_files,
            filesWithSize=found,
        )

        # -- Passe 3 : fallback GetFileAttributesEx ----------------
        # Pour les ~37k fichiers dont FSCTL a echoue (verrouilles, sparse...)
        zero_refs = [r for r, rec in self.records.items()
                     if not rec["is_dir"] and rec["file_size"] == 0]

        if zero_refs:
            print(f"[~] Passe 3 ? Fallback sur {len(zero_refs):,} fichiers "
                  f"(GetFileAttributesEx)...")
            emit_progress(
                "fallback",
                f"Fallback sur {len(zero_refs):,} fichiers sans taille",
                processedCount=0,
                totalCount=len(zero_refs),
                totalFiles=total_files,
            )

            # Reconstruit les chemins complets pour GetFileAttributesExW
            found3 = 0
            for index, ref in enumerate(zero_refs, start=1):
                path = self._get_full_path_fast(ref)
                if not path:
                    continue
                size = get_file_size_fallback(path)
                if size > 0:
                    self.records[ref]["file_size"] = size
                    found3 += 1

                if index % 250 == 0 or index == len(zero_refs):
                    emit_progress(
                        "fallback",
                        f"Fallback {index:,}/{len(zero_refs):,}",
                        processedCount=index,
                        totalCount=len(zero_refs),
                        totalFiles=total_files,
                        filesRecovered=found3,
                        currentFile=path,
                    )

            print(f"[OK] Passe 3 : {found3:,}/{len(zero_refs):,} tailles recuperees")
            emit_progress(
                "fallback",
                f"Passe 3 terminee : {found3:,}/{len(zero_refs):,} tailles recuperees",
                processedCount=len(zero_refs),
                totalCount=len(zero_refs),
                totalFiles=total_files,
                filesRecovered=found3,
            )

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

    def _folder_counts(self, folder_ref: int) -> tuple[int, int]:
        child_count = 0
        file_count = 0
        for ref in self.folder_tree.get(folder_ref, []):
            rec = self.records.get(ref)
            if not rec:
                continue
            if rec["is_dir"]:
                child_count += 1
            else:
                file_count += 1
        return child_count, file_count

    def _build_folder_node(self, ref: int, sizes: dict, depth: int, max_depth):
        rec = self.records.get(ref)
        if not rec or not rec["is_dir"]:
            return None

        size = sizes.get(ref, 0)
        child_count, file_count = self._folder_counts(ref)
        node = {
            "record_number": ref,
            "name":          rec["name"],
            "is_dir":        True,
            "size_bytes":    size,
            "size_display":  _fmt(size),
            "child_count":   child_count,
            "file_count":    file_count,
            "child":         []
        }

        if max_depth is None or depth < max_depth:
            node["child"] = self._ch(ref, sizes, depth + 1, max_depth)

        return node

    def build_summary(self, max_depth=None):
        sizes   = self.compute_folder_sizes()
        results = []
        for ref in self.folder_tree.get(5, []):
            node = self._build_folder_node(ref, sizes, 0, max_depth)
            if node is not None:
                results.append(node)
        results.sort(key=lambda x: x["size_bytes"], reverse=True)
        return results

    def _ch(self, parent, sizes, depth, max_depth):
        out = []
        for ref in self.folder_tree.get(parent, []):
            node = self._build_folder_node(ref, sizes, depth, max_depth)
            if node is not None:
                out.append(node)
        out.sort(key=lambda x: -x["size_bytes"])
        return out

    def build_cache_payload(self, sizes: dict | None = None) -> dict:
        if sizes is None:
            sizes = self.compute_folder_sizes()

        cache_records = {}
        cache_tree = {}

        for ref, rec in self.records.items():
            if rec["is_dir"]:
                child_count, file_count = self._folder_counts(ref)
                size = sizes.get(ref, 0)
                cache_records[str(ref)] = {
                    "record_number": ref,
                    "name":         rec["name"],
                    "is_dir":       True,
                    "parent":       rec.get("parent"),
                    "size_bytes":   size,
                    "size_display": _fmt(size),
                    "child_count":  child_count,
                    "file_count":   file_count,
                }
            else:
                name = rec["name"]
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                cache_records[str(ref)] = {
                    "record_number": ref,
                    "name":         name,
                    "is_dir":       False,
                    "parent":       rec.get("parent"),
                    "ext":          ext,
                    "size_bytes":   rec["file_size"],
                    "size_display": _fmt(rec["file_size"]),
                }

        for parent_ref, children in self.folder_tree.items():
            cache_tree[str(parent_ref)] = list(children)

        return {
            "records": cache_records,
            "tree": cache_tree,
        }

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


def inflate_cache_state(payload: dict) -> tuple[dict[int, dict], dict[int, list[int]]]:
    records = {}
    tree = defaultdict(list)

    for key, rec in (payload.get("cache", {}).get("records", {}) or {}).items():
        ref = int(key)
        records[ref] = {
            "name": rec["name"],
            "parent": rec.get("parent"),
            "is_dir": rec["is_dir"],
            "file_size": rec.get("size_bytes", 0),
        }

    for key, children in (payload.get("cache", {}).get("tree", {}) or {}).items():
        tree[int(key)] = [int(child) for child in children]

    return records, tree


def remove_child_link(tree: dict[int, list[int]], parent_ref: int | None, ref: int):
    if parent_ref is None:
        return
    children = tree.get(parent_ref)
    if not children:
        return
    tree[parent_ref] = [child for child in children if child != ref]
    if not tree[parent_ref]:
        tree.pop(parent_ref, None)


def remove_record_subtree(records: dict[int, dict], tree: dict[int, list[int]], ref: int):
    rec = records.pop(ref, None)
    if rec is None:
        return
    for child in list(tree.get(ref, [])):
        remove_record_subtree(records, tree, child)
    tree.pop(ref, None)
    remove_child_link(tree, rec.get("parent"), ref)


def upsert_record(records: dict[int, dict], tree: dict[int, list[int]], ref: int, snapshot: dict):
    existing = records.get(ref)
    if existing is not None and existing.get("parent") != snapshot.get("parent"):
        remove_child_link(tree, existing.get("parent"), ref)

    records[ref] = {
        "name": snapshot["name"],
        "parent": snapshot.get("parent"),
        "is_dir": snapshot["is_dir"],
        "file_size": snapshot.get("file_size", 0),
    }

    parent_ref = snapshot.get("parent")
    if parent_ref is not None and parent_ref != ref:
        children = tree[parent_ref]
        if ref not in children:
            children.append(ref)


def build_payload_from_state(drive: str, records: dict[int, dict], tree: dict[int, list[int]], max_depth=None) -> dict:
    reader = MFTReader(drive)
    reader.records = records
    reader.folder_tree = defaultdict(list, {parent: list(children) for parent, children in tree.items()})
    sizes = reader.compute_folder_sizes()
    return {
        "summary": reader.build_summary(max_depth=max_depth),
        "cache": reader.build_cache_payload(sizes),
    }


def apply_usn_delta(handle, drive: str, cached_package: dict, current_journal: dict, max_depth=None) -> tuple[dict | None, int]:
    if cached_package is None:
        return None, 0

    metadata = cached_package.get("metadata", {})
    payload = cached_package.get("payload")
    if not isinstance(payload, dict):
        return None, 0

    cached_journal_id = metadata.get("journal_id")
    cached_next_usn = metadata.get("next_usn")
    if cached_journal_id != current_journal["journal_id"]:
        return None, 0
    if cached_next_usn is None or cached_next_usn >= current_journal["next_usn"]:
        return None, 0
    if cached_next_usn < current_journal["lowest_valid_usn"]:
        return None, 0

    records, tree = inflate_cache_state(payload)
    delta_by_ref = {}
    delta_entries = 0
    for entry in read_usn_delta(handle, cached_next_usn, current_journal, current_journal["next_usn"]):
        delta_entries += 1
        ref = entry["ref"]
        prev = delta_by_ref.get(ref)
        if prev is None:
            delta_by_ref[ref] = entry
        else:
            prev["reason"] |= entry["reason"]
            prev["parent"] = entry["parent"]
            prev["name"] = entry["name"] or prev["name"]
            prev["is_dir"] = entry["is_dir"]

    if not delta_by_ref:
        return None, 0

    out_buf = ctypes.create_string_buffer(NTFS_OUTPUT_HEADER + 4096)
    bytes_ret = ctypes.wintypes.DWORD(0)

    for ref in delta_by_ref:
        rec_data = get_record_data_fsctl(handle, ref, out_buf, bytes_ret)
        snapshot = parse_record_snapshot(rec_data) if rec_data else None
        if snapshot is None:
            remove_record_subtree(records, tree, ref)
            continue
        upsert_record(records, tree, ref, snapshot)

    return build_payload_from_state(drive, records, tree, max_depth=max_depth), delta_entries


def resolve_scan_payload(reader: "MFTReader", max_depth=None) -> tuple[dict, dict | None]:
    start = datetime.now()
    current_journal = query_usn_journal(reader.handle)

    cached_payload = load_scan_cache(reader.drive, current_journal)
    if cached_payload is not None:
        elapsed = (datetime.now() - start).total_seconds()
        return annotate_payload(cached_payload, "cache", elapsed), current_journal

    cached_package = load_scan_cache_package(reader.drive)
    if current_journal is not None and cached_package is not None:
        delta_payload, delta_entries = apply_usn_delta(
            reader.handle,
            reader.drive,
            cached_package,
            current_journal,
            max_depth=max_depth,
        )
        if delta_payload is not None:
            elapsed = (datetime.now() - start).total_seconds()
            delta_payload = annotate_payload(delta_payload, "delta", elapsed, delta_entries)
            save_scan_cache(reader.drive, current_journal, delta_payload)
            return delta_payload, current_journal

    reader.read_all_records()
    sizes = reader.compute_folder_sizes()
    payload = {
        "summary": reader.build_summary(max_depth=max_depth),
        "cache": reader.build_cache_payload(sizes),
    }
    elapsed = (datetime.now() - start).total_seconds()
    payload = annotate_payload(payload, "scan", elapsed)
    save_scan_cache(reader.drive, current_journal, payload)
    return payload, current_journal


def emit_watch_payload(drive: str, payload: dict, event_type: str = "update", delta_entries: int = 0):
    envelope = {
        "type": event_type,
        "drive": drive,
        "payload": payload,
        "deltaEntries": delta_entries,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    builtins.print(json.dumps(envelope, ensure_ascii=False, default=str), flush=True)


def watch_drive_updates(drive: str, max_depth=None, timeout_ms: int = 1500):
    set_stdout_json_mode(True)
    reader = MFTReader(drive)
    reader.open()
    try:
        payload, journal_state = resolve_scan_payload(reader, max_depth=max_depth)
        emit_watch_payload(reader.drive, payload, event_type="ready")

        while True:
            if journal_state is None:
                time.sleep(2)
                journal_state = query_usn_journal(reader.handle)
                continue

            next_usn, has_records = wait_for_usn_change(reader.handle, journal_state["next_usn"], journal_state, timeout_ms=timeout_ms)
            refreshed_journal = query_usn_journal(reader.handle)
            if refreshed_journal is None:
                time.sleep(1)
                continue
            if not has_records and refreshed_journal["next_usn"] <= journal_state["next_usn"]:
                journal_state = refreshed_journal
                continue

            cached_package = load_scan_cache_package(reader.drive)
            delta_payload, delta_entries = apply_usn_delta(
                reader.handle,
                reader.drive,
                cached_package,
                refreshed_journal,
                max_depth=max_depth,
            )

            if delta_payload is None:
                print(f"[~] Watcher {reader.drive}: rescan complet apres changement journal USN")
                payload, refreshed_journal = resolve_scan_payload(reader, max_depth=max_depth)
                emit_watch_payload(reader.drive, payload, event_type="rescan")
                journal_state = refreshed_journal or journal_state
                continue

            delta_payload = annotate_payload(delta_payload, "delta", 0.0, delta_entries)
            save_scan_cache(reader.drive, refreshed_journal, delta_payload)
            emit_watch_payload(reader.drive, delta_payload, event_type="update", delta_entries=delta_entries)
            journal_state = refreshed_journal
            journal_state["next_usn"] = max(journal_state["next_usn"], next_usn)
    finally:
        reader.close()


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
    p.add_argument("--stdout-json", action="store_true",
                   help="Ecrit le resultat JSON sur stdout")
    p.add_argument("--json",        action="store_true",
                   help="Exporte dans mft_output.json (mode CLI)")
    p.add_argument("--max-records", type=int,  default=None,
                   help="Limite records lus (tests)")
    p.add_argument("--files",       type=int,  default=None,
                   help="Retourne les fichiers du dossier ref donne")
    p.add_argument("--watch",       action="store_true",
                   help="Surveille le journal USN et emet les mises a jour en continu")
    a = p.parse_args()
    set_stdout_json_mode(a.stdout_json)

    if a.watch:
        watch_drive_updates(a.drive, max_depth=a.depth)
        return

    r = MFTReader(a.drive)
    try:
        start = datetime.now()
        r.open()
        current_journal = query_usn_journal(r.handle) if a.files is None and a.max_records is None else None

        if a.files is None and a.max_records is None:
            payload, current_journal = resolve_scan_payload(r, max_depth=a.depth)
            if payload.get("scan_info", {}).get("source") == "cache":
                print(f"[OK] Cache USN utilise pour {r.drive}: ({len(payload.get('summary', []))} dossiers racine)")
            elif payload.get("scan_info", {}).get("source") == "delta":
                print(f"[OK] Delta USN applique pour {r.drive}: {payload.get('scan_info', {}).get('delta_entries', 0)} entree(s)")
            else:
                print(f"[OK] Scan complet effectue pour {r.drive}: ({len(payload.get('summary', []))} dossiers racine)")

            if a.output:
                emit_payload(payload, a.output)
            elif a.stdout_json:
                emit_payload(payload)
            elif a.json:
                out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mft_output.json")
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(payload.get("summary", []), f, ensure_ascii=False, indent=2, default=str)
                print(f"[S] Exporte -> {out} ({len(payload.get('summary', []))} dossiers racine)")
            else:
                elapsed = (datetime.now() - start).total_seconds()
                summary = payload.get("summary", [])
                print(f"\n[t]  Termine en {elapsed:.2f}s\n")
                print(f"{'Dossier':<40} {'Taille':>12}")
                print("-" * 54)
                for f in summary[:20]:
                    print(f"{f['name']:<40} {f['size_display']:>12}")
            return

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

        sizes = r.compute_folder_sizes()
        summary = r.build_summary(max_depth=a.depth)
        elapsed = (datetime.now() - start).total_seconds()
        payload = {
            "summary": summary,
            "cache": r.build_cache_payload(sizes),
        }
        payload = annotate_payload(payload, "scan", elapsed)

        if a.max_records is None and a.files is None:
            save_scan_cache(r.drive, current_journal or query_usn_journal(r.handle), payload)

        if a.output:
            # Mode Electron : ecrit dans le fichier specifie par index.js
            emit_payload(payload, a.output)
            print(f"[OK] Exporte -> {a.output} ({len(summary)} dossiers, {elapsed:.1f}s)",
                  flush=True)

        elif a.stdout_json:
            emit_payload(payload)

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