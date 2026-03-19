"""
diag_iso.py — Diagnostic ciblé sur l'ISO ubuntu
Lance en admin dans le même dossier que mft_reader.py
"""
import ctypes, ctypes.wintypes, struct

GENERIC_READ             = 0x80000000
FILE_SHARE_READ          = 0x00000001
FILE_SHARE_WRITE         = 0x00000002
OPEN_EXISTING            = 3
INVALID_HANDLE           = ctypes.c_void_p(-1).value
FSCTL_GET_NTFS_FILE_RECORD = 0x90068
FSCTL_ENUM_USN_DATA      = 0x900B3
FILE_ATTRIBUTE_DIRECTORY = 0x10
NTFS_OUTPUT_HEADER       = 12
SIGNATURE_FILE           = b"FILE"
ATTR_DATA                = 0x80
ATTR_END                 = 0xFFFFFFFF

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateFileW.restype  = ctypes.c_void_p
_k32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD, ctypes.c_void_p, ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD, ctypes.c_void_p]
_k32.DeviceIoControl.restype  = ctypes.wintypes.BOOL
_k32.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.c_void_p,
    ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.c_void_p]
_k32.CloseHandle.restype  = ctypes.wintypes.BOOL
_k32.CloseHandle.argtypes = [ctypes.c_void_p]

class WIN32_FILE_ATTRIBUTE_DATA(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.wintypes.DWORD),
        ("ftCreationTime",   ctypes.wintypes.FILETIME),
        ("ftLastAccessTime", ctypes.wintypes.FILETIME),
        ("ftLastWriteTime",  ctypes.wintypes.FILETIME),
        ("nFileSizeHigh",    ctypes.wintypes.DWORD),
        ("nFileSizeLow",     ctypes.wintypes.DWORD),
    ]
_k32.GetFileAttributesExW.restype  = ctypes.wintypes.BOOL
_k32.GetFileAttributesExW.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p]

ISO_PATH = r"C:\Users\1489DaDAMA\Downloads\ubuntu-24.04.4-desktop-amd64.iso"

# ── Test 1 : GetFileAttributesExW ────────────────────────────────
print("=== Test 1 : GetFileAttributesExW ===")
info = WIN32_FILE_ATTRIBUTE_DATA()
ok   = _k32.GetFileAttributesExW(ISO_PATH, 0, ctypes.byref(info))
print(f"  ok             = {ok}")
print(f"  nFileSizeHigh  = {info.nFileSizeHigh}")
print(f"  nFileSizeLow   = {info.nFileSizeLow}")
size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
print(f"  taille combinée = {size:,} bytes = {size/1024**3:.3f} GB")
print(f"  erreur Win32   = {ctypes.get_last_error()}")

# ── Test 2 : trouver le file_ref de l'ISO via USN ────────────────
print("\n=== Test 2 : Recherche file_ref via USN ===")
vol_handle = _k32.CreateFileW(
    "\\\\.\\C:", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
    None, OPEN_EXISTING, 0, None)

iso_ref = None
next_ref  = 0
out_buf   = ctypes.create_string_buffer(65536)
bytes_ret = ctypes.wintypes.DWORD(0)
seen = set()

while True:
    in_buf = struct.pack("<QQQ", next_ref, 0, 0x7FFFFFFFFFFFFFFF)
    _k32.DeviceIoControl(vol_handle, FSCTL_ENUM_USN_DATA,
        in_buf, len(in_buf), out_buf, 65536, ctypes.byref(bytes_ret), None)
    nb = bytes_ret.value
    if nb < 8: break
    new_next = struct.unpack_from("<Q", out_buf.raw, 0)[0]
    if new_next == next_ref or new_next in seen: break
    seen.add(next_ref)
    next_ref = new_next
    pos = 8
    while pos + 60 <= nb:
        rec_len  = struct.unpack_from("<I", out_buf.raw, pos)[0]
        if rec_len == 0: break
        fn_len   = struct.unpack_from("<H", out_buf.raw, pos + 56)[0]
        fn_off   = struct.unpack_from("<H", out_buf.raw, pos + 58)[0]
        ns = pos + fn_off
        ne = ns + fn_len
        name = out_buf.raw[ns:ne].decode("utf-16-le", errors="replace") if ne <= nb else ""
        if "ubuntu" in name.lower():
            file_ref = struct.unpack_from("<Q", out_buf.raw, pos + 8)[0]
            iso_ref  = file_ref & 0x0000FFFFFFFFFFFF
            print(f"  Trouvé : name={name}  ref={iso_ref}  ref_raw=0x{file_ref:016X}")
        pos += rec_len

# ── Test 3 : FSCTL_GET_NTFS_FILE_RECORD sur l'ISO ────────────────
if iso_ref is not None:
    print(f"\n=== Test 3 : FSCTL_GET_NTFS_FILE_RECORD (ref={iso_ref}) ===")

    class _IN(ctypes.Structure):
        _fields_ = [("FileReferenceNumber", ctypes.c_ulonglong)]

    in_s    = _IN(FileReferenceNumber=iso_ref)
    out_rec = ctypes.create_string_buffer(NTFS_OUTPUT_HEADER + 4096)
    br      = ctypes.wintypes.DWORD(0)
    ok      = _k32.DeviceIoControl(
        vol_handle, FSCTL_GET_NTFS_FILE_RECORD,
        ctypes.byref(in_s), ctypes.sizeof(in_s),
        out_rec, len(out_rec), ctypes.byref(br), None)

    print(f"  DeviceIoControl ok = {ok}")
    print(f"  bytes_returned     = {br.value}")
    print(f"  erreur Win32       = {ctypes.get_last_error()}")

    if br.value >= NTFS_OUTPUT_HEADER + 8:
        rec_len  = struct.unpack_from("<I", out_rec.raw, 8)[0]
        rec_data = bytearray(out_rec.raw[NTFS_OUTPUT_HEADER: NTFS_OUTPUT_HEADER + rec_len])
        print(f"  signature          = {bytes(rec_data[:4])}")
        print(f"  rec_len            = {rec_len}")

        # Scan tous les attributs $DATA
        offset = struct.unpack_from("<H", rec_data, 0x14)[0]
        while offset + 4 <= len(rec_data):
            at = struct.unpack_from("<I", rec_data, offset)[0]
            if at == ATTR_END: break
            if offset + 8 > len(rec_data): break
            al = struct.unpack_from("<I", rec_data, offset + 4)[0]
            if al == 0 or offset + al > len(rec_data): break
            if at == ATTR_DATA:
                nr = rec_data[offset + 8]
                print(f"\n  $DATA trouvé : non_resident={nr}")
                if nr == 0:
                    cl = struct.unpack_from("<I", rec_data, offset + 0x10)[0]
                    print(f"    content_len (résident) = {cl}")
                else:
                    alloc = struct.unpack_from("<Q", rec_data, offset + 0x28)[0]
                    real  = struct.unpack_from("<Q", rec_data, offset + 0x30)[0]
                    init  = struct.unpack_from("<Q", rec_data, offset + 0x38)[0]
                    print(f"    allocated_size = {alloc:,} = {alloc/1024**3:.3f} GB")
                    print(f"    real_size      = {real:,} = {real/1024**3:.3f} GB  ← doit être ~6.2 GB")
                    print(f"    initialized    = {init:,} = {init/1024**3:.3f} GB")
            offset += al
else:
    print("\n  ⚠️  ISO non trouvé dans USN — fichier peut-être absent ou ref_number différent")

_k32.CloseHandle(vol_handle)
print("\nDiagnostic terminé.")
print("\nDiagnostic terminé.")