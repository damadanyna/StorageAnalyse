"""
mft_diag.py  — Diagnostic MFT
Affiche des stats détaillées pour comprendre pourquoi les tailles sont fausses.
"""

import os, sys, json, struct, ctypes
from datetime import datetime
from collections import defaultdict

MFT_RECORD_SIZE     = 1024
SIGNATURE_FILE      = b"FILE"
ATTR_STANDARD_INFO  = 0x10
ATTR_ATTRIBUTE_LIST = 0x20
ATTR_FILE_NAME      = 0x30
ATTR_DATA           = 0x80
ATTR_END            = 0xFFFFFFFF
FLAG_IN_USE         = 0x0001
FLAG_DIRECTORY      = 0x0002

def open_volume(drive_letter):
    import win32file, win32con
    volume_path = f"\\\\.\\{drive_letter.rstrip(':\\/')}:"
    handle = win32file.CreateFile(
        volume_path, win32con.GENERIC_READ,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
        None, win32con.OPEN_EXISTING, win32con.FILE_ATTRIBUTE_NORMAL, None)
    return handle

def read_bytes(handle, offset, size):
    import win32file
    win32file.SetFilePointer(handle, offset, 0)
    _, data = win32file.ReadFile(handle, size)
    return data

def apply_fixup(data):
    data = bytearray(data)
    usa_offset = struct.unpack_from("<H", data, 0x04)[0]
    usa_count  = struct.unpack_from("<H", data, 0x06)[0]
    if usa_offset == 0 or usa_count < 2:
        return bytes(data)
    update_seq = data[usa_offset: usa_offset + 2]
    for i in range(1, usa_count):
        sector_end = i * 512 - 2
        if sector_end + 2 > len(data): break
        if data[sector_end: sector_end + 2] == update_seq:
            fix = data[usa_offset + i*2: usa_offset + i*2 + 2]
            data[sector_end]   = fix[0]
            data[sector_end+1] = fix[1]
    return bytes(data)

def parse_record_full(data, record_number):
    """Retourne un dict avec TOUT ce qu'on trouve dans le record, pour diagnostic."""
    result = {
        "rn": record_number,
        "valid": False, "in_use": False, "is_dir": False,
        "base_ref": 0,
        "names": [],          # tous les $FILE_NAME trouvés
        "data_sizes": [],     # toutes les tailles $DATA trouvées (résident + non-résident)
        "has_attr_list": False,
        "attr_list_refs": [], # références dans $ATTRIBUTE_LIST résident
    }

    if data[:4] != SIGNATURE_FILE:
        return result
    result["valid"] = True

    flags = struct.unpack_from("<H", data, 0x16)[0]
    result["in_use"] = bool(flags & FLAG_IN_USE)
    result["is_dir"] = bool(flags & FLAG_DIRECTORY)
    base_raw = struct.unpack_from("<Q", data, 0x20)[0]
    result["base_ref"] = base_raw & 0x0000FFFFFFFFFFFF

    data = apply_fixup(data)
    offset = struct.unpack_from("<H", data, 0x14)[0]

    while offset + 4 <= len(data):
        attr_type = struct.unpack_from("<I", data, offset)[0]
        if attr_type == ATTR_END: break
        if offset + 8 > len(data): break
        attr_len = struct.unpack_from("<I", data, offset + 4)[0]
        if attr_len == 0 or offset + attr_len > len(data): break

        non_res = data[offset + 8]

        if non_res == 0:
            co  = struct.unpack_from("<H", data, offset + 0x14)[0]
            cl  = struct.unpack_from("<I", data, offset + 0x10)[0]
            cs  = offset + co
            content = data[cs: cs + cl]

            if attr_type == ATTR_FILE_NAME and len(content) >= 66:
                parent_raw = struct.unpack_from("<Q", content, 0)[0]
                parent     = parent_raw & 0x0000FFFFFFFFFFFF
                ns         = content[0x41]
                nlen       = content[0x40]
                nb         = content[0x42: 0x42 + nlen*2]
                name       = nb.decode("utf-16-le", errors="replace")
                fn_alloc   = struct.unpack_from("<Q", content, 0x28)[0]
                fn_real    = struct.unpack_from("<Q", content, 0x30)[0]
                result["names"].append({
                    "name": name, "ns": ns,
                    "parent": parent,
                    "fn_alloc": fn_alloc, "fn_real": fn_real
                })

            elif attr_type == ATTR_DATA and cl > 0:
                result["data_sizes"].append(("resident", cl))

            elif attr_type == ATTR_ATTRIBUTE_LIST:
                result["has_attr_list"] = True
                # Parse les entrées
                pos = 0
                while pos + 26 <= len(content):
                    et  = struct.unpack_from("<I", content, pos)[0]
                    el  = struct.unpack_from("<H", content, pos + 4)[0]
                    if el == 0: break
                    rr  = struct.unpack_from("<Q", content, pos + 0x10)[0]
                    rr &= 0x0000FFFFFFFFFFFF
                    if rr != record_number:
                        result["attr_list_refs"].append((et, rr))
                    pos += el
        else:
            if attr_type == ATTR_DATA and offset + 0x38 <= len(data):
                alloc = struct.unpack_from("<Q", data, offset + 0x28)[0]
                real  = struct.unpack_from("<Q", data, offset + 0x30)[0]
                init  = struct.unpack_from("<Q", data, offset + 0x38)[0]
                result["data_sizes"].append(("nonres", real, alloc, init))
            elif attr_type == ATTR_ATTRIBUTE_LIST:
                result["has_attr_list"] = True
                result["attr_list_refs"].append((-1, -1))  # non-résident, pas lisible ici

        offset += attr_len

    return result


def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("❌ Droits admin requis")
        sys.exit(1)

    drive = sys.argv[1] if len(sys.argv) > 1 else "C"
    drive = drive.rstrip(":\\/")[0].upper()

    handle = open_volume(drive)

    # Boot sector
    vbr = read_bytes(handle, 0, 512)
    bps  = struct.unpack_from("<H", vbr, 0x0B)[0]
    spc  = struct.unpack_from("<B", vbr, 0x0D)[0]
    lcn  = struct.unpack_from("<Q", vbr, 0x30)[0]
    cpr  = struct.unpack_from("<b", vbr, 0x40)[0]
    bpc  = bps * spc
    rsz  = 2**abs(cpr) if cpr < 0 else cpr * bpc
    mft_offset = lcn * bpc

    print(f"Boot: bps={bps}, spc={spc}, bpc={bpc}, record_size={rsz}")
    print(f"MFT offset: 0x{mft_offset:X}")

    # Taille du MFT depuis record 0
    r0d = read_bytes(handle, mft_offset, rsz)
    r0  = parse_record_full(r0d, 0)
    mft_size = 0
    for ds in r0["data_sizes"]:
        if ds[0] == "nonres" and ds[1] > 0:
            mft_size = ds[1]
            break
    total_records = mft_size // rsz if mft_size else 0
    print(f"MFT size: {mft_size/1024/1024:.1f} MB → {total_records:,} records\n")

    # ── Échantillon des 500 000 premiers records ──────────────────
    SAMPLE = min(total_records, 500_000)
    BATCH  = 256

    stats = {
        "total_read": 0,
        "valid_in_use": 0,
        "base_records": 0,       # base_ref == 0
        "ext_records": 0,        # base_ref != 0
        "base_with_name": 0,
        "base_no_name": 0,
        "base_no_data": 0,       # base, name, mais file_size==0
        "base_data_nonzero": 0,
        "has_attr_list": 0,
        "total_file_size_from_data": 0,
        "total_file_size_from_fn": 0,
        "size_discrepancy_count": 0,  # fn_real != data_real
        "users_files": [],        # 20 premiers fichiers sous Users
        "zero_size_examples": [], # fichiers avec taille 0
    }

    # Pour les 50 000 premiers : affiche exemples détaillés
    examples_printed = 0
    users_ref = None

    for batch_start in range(0, SAMPLE, BATCH):
        off = mft_offset + batch_start * rsz
        try:
            bd = read_bytes(handle, off, BATCH * rsz)
        except Exception as e:
            continue

        for i in range(BATCH):
            rn = batch_start + i
            if rn >= SAMPLE: break

            rd = bd[i*rsz: (i+1)*rsz]
            if len(rd) < rsz: break

            r = parse_record_full(rd, rn)
            stats["total_read"] += 1

            if not r["valid"] or not r["in_use"]: continue
            stats["valid_in_use"] += 1

            if r["base_ref"] != 0:
                stats["ext_records"] += 1
                continue

            stats["base_records"] += 1

            if r["names"]:
                stats["base_with_name"] += 1

                # Meilleur nom (priorité WIN32)
                priority = {1:3, 3:2, 0:1, 2:0}
                best = max(r["names"], key=lambda x: priority.get(x["ns"], -1))
                name = best["name"]
                fn_real = best["fn_real"]

                # Détecter Users
                if name == "Users" and users_ref is None:
                    users_ref = rn

                # Taille depuis $DATA
                data_real = 0
                for ds in r["data_sizes"]:
                    if ds[0] == "nonres" and ds[1] > 0:
                        data_real = ds[1]
                        break
                if data_real == 0:
                    for ds in r["data_sizes"]:
                        if ds[0] == "resident":
                            data_real = ds[1]
                            break

                if not r["is_dir"]:
                    if data_real > 0:
                        stats["base_data_nonzero"] += 1
                        stats["total_file_size_from_data"] += data_real
                    else:
                        stats["base_no_data"] += 1
                        stats["total_file_size_from_fn"] += fn_real

                        if len(stats["zero_size_examples"]) < 30:
                            stats["zero_size_examples"].append({
                                "rn": rn, "name": name,
                                "fn_real": fn_real,
                                "has_attr_list": r["has_attr_list"],
                                "attr_list_refs_count": len(r["attr_list_refs"]),
                                "base_ref": r["base_ref"]
                            })

                    if fn_real > 0 and data_real > 0 and fn_real != data_real:
                        stats["size_discrepancy_count"] += 1

                if r["has_attr_list"]:
                    stats["has_attr_list"] += 1

            else:
                stats["base_no_name"] += 1

        if batch_start % (BATCH * 200) == 0 and batch_start > 0:
            pct = batch_start / SAMPLE * 100
            print(f"  {pct:.0f}%...")

    print("\n══════════════════════════════════════════")
    print("           RAPPORT DIAGNOSTIC MFT")
    print("══════════════════════════════════════════")
    print(f"Records lus           : {stats['total_read']:>12,}")
    print(f"Valides & en-usage    : {stats['valid_in_use']:>12,}")
    print(f"Records PRINCIPAUX    : {stats['base_records']:>12,}  (base_ref == 0)")
    print(f"Records EXTENSION     : {stats['ext_records']:>12,}  (base_ref != 0)")
    print(f"Principaux AVEC nom   : {stats['base_with_name']:>12,}")
    print(f"Principaux SANS nom   : {stats['base_no_name']:>12,}  ← perdus !")
    print(f"Fichiers avec $DATA   : {stats['base_data_nonzero']:>12,}")
    print(f"Fichiers SANS $DATA   : {stats['base_no_data']:>12,}  ← taille manquante !")
    print(f"Avec $ATTRIBUTE_LIST  : {stats['has_attr_list']:>12,}")
    print(f"Discordances fn/data  : {stats['size_discrepancy_count']:>12,}")
    print()
    total_counted = stats['total_file_size_from_data'] + stats['total_file_size_from_fn']
    print(f"Taille totale comptée : {total_counted/1024**3:.2f} GB")
    print(f"  dont depuis $DATA   : {stats['total_file_size_from_data']/1024**3:.2f} GB")
    print(f"  dont depuis $FN     : {stats['total_file_size_from_fn']/1024**3:.2f} GB  (fallback)")
    print()

    print(f"\n── 30 fichiers SANS taille $DATA (zero_size_examples) ──")
    for ex in stats["zero_size_examples"]:
        print(f"  rn={ex['rn']:>8}  fn_real={ex['fn_real']:>14,}  "
              f"attr_list={ex['has_attr_list']}  refs={ex['attr_list_refs_count']}  "
              f"name={ex['name']}")

    # Exporte en JSON pour analyse
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mft_diag.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 Rapport complet → {out}")

if __name__ == "__main__":
    main()