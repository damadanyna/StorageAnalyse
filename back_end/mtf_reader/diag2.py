"""
diag_iso2.py — Test ciblé sur ref=449621 (l'ISO ubuntu)
"""
import ctypes, ctypes.wintypes, struct

GENERIC_READ             = 0x80000000
FILE_SHARE_READ          = 0x00000001
FILE_SHARE_WRITE         = 0x00000002
OPEN_EXISTING            = 3
INVALID_HANDLE           = ctypes.c_void_p(-1).value
FSCTL_GET_NTFS_FILE_RECORD = 0x90068
NTFS_OUTPUT_HEADER       = 12
SIGNATURE_FILE           = b"FILE"
ATTR_DATA                = 0x80
ATTR_FILE_NAME           = 0x30
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

class _IN(ctypes.Structure):
    _fields_ = [("FileReferenceNumber", ctypes.c_ulonglong)]

def apply_fixup(data):
    uo = struct.unpack_from("<H", data, 4)[0]
    uc = struct.unpack_from("<H", data, 6)[0]
    if uo == 0 or uc < 2: return data
    us = data[uo:uo+2]
    for i in range(1, uc):
        se = i * 512 - 2
        if se + 2 > len(data): break
        if data[se:se+2] == us:
            fx = data[uo+i*2:uo+i*2+2]
            data[se] = fx[0]; data[se+1] = fx[1]
    return data

# Ouvre le volume
vol = _k32.CreateFileW("\\\\.\\C:", GENERIC_READ,
    FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)

ISO_REF = 449621   # ref exacte de ubuntu-24.04.4-desktop-amd64.iso

print(f"=== FSCTL_GET_NTFS_FILE_RECORD sur ref={ISO_REF} ===")

in_s    = _IN(FileReferenceNumber=ISO_REF)
out_rec = ctypes.create_string_buffer(NTFS_OUTPUT_HEADER + 4096)
br      = ctypes.wintypes.DWORD(0)
ok      = _k32.DeviceIoControl(vol, FSCTL_GET_NTFS_FILE_RECORD,
    ctypes.byref(in_s), ctypes.sizeof(in_s),
    out_rec, len(out_rec), ctypes.byref(br), None)

print(f"  ok           = {ok}")
print(f"  bytes_ret    = {br.value}")
print(f"  erreur Win32 = {ctypes.get_last_error()}")

if br.value >= NTFS_OUTPUT_HEADER + 8:
    # Les 8 premiers bytes = FileReferenceNumber retourné
    returned_ref = struct.unpack_from("<Q", out_rec.raw, 0)[0] & 0x0000FFFFFFFFFFFF
    print(f"  ref retournée = {returned_ref}  ({'✅ correct' if returned_ref == ISO_REF else '❌ WRONG — Windows a retourné un autre record !'})")

    rec_len  = struct.unpack_from("<I", out_rec.raw, 8)[0]
    rec_data = bytearray(out_rec.raw[NTFS_OUTPUT_HEADER: NTFS_OUTPUT_HEADER + rec_len])
    print(f"  signature    = {bytes(rec_data[:4])}")
    rec_data = apply_fixup(rec_data)

    # Lit tous les attributs
    offset = struct.unpack_from("<H", rec_data, 0x14)[0]
    while offset + 4 <= len(rec_data):
        at = struct.unpack_from("<I", rec_data, offset)[0]
        if at == ATTR_END: break
        if offset + 8 > len(rec_data): break
        al = struct.unpack_from("<I", rec_data, offset + 4)[0]
        if al == 0 or offset + al > len(rec_data): break

        if at == ATTR_FILE_NAME:
            nr = rec_data[offset + 8]
            if nr == 0:
                co = struct.unpack_from("<H", rec_data, offset + 0x14)[0]
                cl = struct.unpack_from("<I", rec_data, offset + 0x10)[0]
                content = rec_data[offset+co: offset+co+cl]
                if len(content) >= 66:
                    nlen = content[0x40]
                    name = content[0x42: 0x42+nlen*2].decode("utf-16-le", errors="replace")
                    fn_real = struct.unpack_from("<Q", content, 0x30)[0]
                    print(f"\n  $FILE_NAME : name={name}  fn_real={fn_real:,} = {fn_real/1024**3:.3f} GB")

        elif at == ATTR_DATA:
            nr = rec_data[offset + 8]
            print(f"\n  $DATA : non_resident={nr}")
            if nr == 0:
                cl = struct.unpack_from("<I", rec_data, offset + 0x10)[0]
                print(f"    content_len = {cl:,}")
            else:
                if offset + 0x40 <= len(rec_data):
                    alloc = struct.unpack_from("<Q", rec_data, offset + 0x28)[0]
                    real  = struct.unpack_from("<Q", rec_data, offset + 0x30)[0]
                    init  = struct.unpack_from("<Q", rec_data, offset + 0x38)[0]
                    print(f"    allocated  = {alloc:,} = {alloc/1024**3:.3f} GB")
                    print(f"    real_size  = {real:,} = {real/1024**3:.3f} GB")
                    print(f"    initialized= {init:,} = {init/1024**3:.3f} GB")
                else:
                    print(f"    ❌ header trop court pour lire les tailles")
                    print(f"    offset={offset}, len={len(rec_data)}, besoin={offset+0x40}")

        offset += al

# Test fallback GetFileAttributesExW
print(f"\n=== GetFileAttributesExW (fallback) ===")
ISO_PATH = r"C:\Users\1489DaDAMA\Downloads\ubuntu-24.04.4-desktop-amd64.iso"
info = WIN32_FILE_ATTRIBUTE_DATA()
ok2  = _k32.GetFileAttributesExW(ISO_PATH, 0, ctypes.byref(info))
size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
print(f"  ok      = {ok2}")
print(f"  High    = {info.nFileSizeHigh}  Low = {info.nFileSizeLow}")
print(f"  taille  = {size:,} = {size/1024**3:.3f} GB  {'✅' if size > 6e9 else '❌'}")

_k32.CloseHandle(vol)
print("\nDiagnostic terminé.")