"""
mft_reader.py
─────────────────────────────────────────────────────────────────
Lecture directe du MFT (Master File Table) NTFS sur Windows.

⚠️  PRÉREQUIS :
    - Windows uniquement (NTFS)
    - Droits Administrateur obligatoires (accès raw au volume)
    - pip install pywin32

UTILISATION :
    python mft_reader.py              → scan C:\\ par défaut
    python mft_reader.py D:\\         → scan le volume D:
    python mft_reader.py C:\\ --json  → exporte dans mft_output.json
─────────────────────────────────────────────────────────────────
"""

import os
import sys
import json
import struct
import ctypes
import argparse
from datetime import datetime
from collections import defaultdict


# ─────────────────────────────────────────────────────────────────
# CONSTANTES MFT / NTFS
# ─────────────────────────────────────────────────────────────────

MFT_RECORD_SIZE         = 1024          # taille standard d'un record MFT
SIGNATURE_FILE          = b"FILE"       # signature d'un record valide
ATTR_STANDARD_INFO      = 0x10          # $STANDARD_INFORMATION
ATTR_FILE_NAME          = 0x30          # $FILE_NAME
ATTR_DATA               = 0x80          # $DATA
ATTR_END                = 0xFFFFFFFF    # marqueur de fin des attributs

# Flags de record
FLAG_IN_USE             = 0x0001
FLAG_DIRECTORY          = 0x0002

# Namespace $FILE_NAME
NAMESPACE_POSIX         = 0
NAMESPACE_WIN32         = 1
NAMESPACE_DOS           = 2
NAMESPACE_WIN32_DOS     = 3


# ─────────────────────────────────────────────────────────────────
# ACCÈS RAW AU VOLUME (WIN32 API)
# ─────────────────────────────────────────────────────────────────

def open_volume(drive_letter: str):
    """
    Ouvre un accès raw au volume NTFS.
    Ex : drive_letter = 'C'
    Retourne un handle Windows ou lève une exception.
    """
    import win32file
    import win32con

    volume_path = f"\\\\.\\{drive_letter.rstrip(':\\/')}:"
    handle = win32file.CreateFile(
        volume_path,
        win32con.GENERIC_READ,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
        None,
        win32con.OPEN_EXISTING,
        win32con.FILE_ATTRIBUTE_NORMAL,
        None
    )
    if handle == win32file.INVALID_HANDLE_VALUE:
        raise OSError(f"Impossible d'ouvrir le volume {volume_path}. Droits admin requis.")
    return handle


def read_bytes(handle, offset: int, size: int) -> bytes:
    """Lit `size` octets à partir de `offset` dans le volume."""
    import win32file
    win32file.SetFilePointer(handle, offset, 0)  # 0 = FILE_BEGIN
    _, data = win32file.ReadFile(handle, size)
    return data


# ─────────────────────────────────────────────────────────────────
# PARSING DU BOOT SECTOR (VBR)
# ─────────────────────────────────────────────────────────────────

class NTFSBootSector:
    """Parse le Volume Boot Record pour extraire les paramètres NTFS."""

    def __init__(self, data: bytes):
        # Octets par secteur (offset 0x0B, 2 bytes)
        self.bytes_per_sector    = struct.unpack_from("<H", data, 0x0B)[0]
        # Secteurs par cluster (offset 0x0D, 1 byte)
        self.sectors_per_cluster = struct.unpack_from("<B", data, 0x0D)[0]
        # LCN du $MFT (offset 0x30, 8 bytes)
        self.mft_lcn             = struct.unpack_from("<Q", data, 0x30)[0]
        # Taille d'un record MFT (offset 0x40, 1 byte signé)
        clusters_per_record      = struct.unpack_from("<b", data, 0x40)[0]

        self.bytes_per_cluster   = self.bytes_per_sector * self.sectors_per_cluster

        # Si valeur négative : taille = 2^|valeur|
        if clusters_per_record < 0:
            self.record_size = 2 ** abs(clusters_per_record)
        else:
            self.record_size = clusters_per_record * self.bytes_per_cluster

        # Offset absolu du $MFT dans le volume
        self.mft_offset = self.mft_lcn * self.bytes_per_cluster

    def __repr__(self):
        return (
            f"NTFSBootSector("
            f"bytes_per_sector={self.bytes_per_sector}, "
            f"bytes_per_cluster={self.bytes_per_cluster}, "
            f"record_size={self.record_size}, "
            f"mft_offset=0x{self.mft_offset:X})"
        )


# ─────────────────────────────────────────────────────────────────
# PARSING D'UN RECORD MFT
# ─────────────────────────────────────────────────────────────────

class MFTRecord:
    """Parse un record MFT de 1024 octets."""

    __slots__ = (
        "record_number", "is_valid", "is_directory", "is_in_use",
        "parent_ref", "file_size", "name", "namespace",
        "created", "modified",
    )

    def __init__(self, data: bytes, record_number: int):
        self.record_number = record_number
        self.is_valid      = False
        self.is_directory  = False
        self.is_in_use     = False
        self.parent_ref    = None
        self.file_size     = 0
        self.name          = ""
        self.namespace     = -1
        self.created       = None
        self.modified      = None

        # Vérifie la signature "FILE"
        if data[:4] != SIGNATURE_FILE:
            return

        self.is_valid = True

        # Flags (offset 0x16, 2 bytes)
        flags = struct.unpack_from("<H", data, 0x16)[0]
        self.is_in_use    = bool(flags & FLAG_IN_USE)
        self.is_directory = bool(flags & FLAG_DIRECTORY)

        # Applique la correction Update Sequence (fixup)
        data = self._apply_fixup(bytearray(data))

        # Offset du premier attribut (offset 0x14, 2 bytes)
        attr_offset = struct.unpack_from("<H", data, 0x14)[0]

        # Parcourt les attributs
        self._parse_attributes(data, attr_offset)

    def _apply_fixup(self, data: bytearray) -> bytearray:
        """Corrige les Update Sequence Array pour la lecture des secteurs."""
        usa_offset = struct.unpack_from("<H", data, 0x04)[0]
        usa_count  = struct.unpack_from("<H", data, 0x06)[0]

        if usa_offset == 0 or usa_count < 2:
            return data

        update_seq = data[usa_offset: usa_offset + 2]

        for i in range(1, usa_count):
            sector_end = i * 512 - 2
            if sector_end + 2 > len(data):
                break
            # Vérifie que le marqueur correspond
            if data[sector_end: sector_end + 2] == update_seq:
                fix = data[usa_offset + i * 2: usa_offset + i * 2 + 2]
                data[sector_end]     = fix[0]
                data[sector_end + 1] = fix[1]

        return data

    def _parse_attributes(self, data: bytes, offset: int):
        """Parcourt et parse les attributs du record."""
        while offset + 4 <= len(data):
            attr_type = struct.unpack_from("<I", data, offset)[0]

            if attr_type == ATTR_END:
                break

            # Taille de l'attribut (offset + 4, 4 bytes)
            if offset + 8 > len(data):
                break
            attr_len = struct.unpack_from("<I", data, offset + 4)[0]
            if attr_len == 0 or offset + attr_len > len(data):
                break

            # Attribut résident ou non-résident ?
            non_resident = data[offset + 8]

            if non_resident == 0:
                # Résident : offset du contenu (offset + 0x14, 2 bytes)
                content_offset = struct.unpack_from("<H", data, offset + 0x14)[0]
                content_len    = struct.unpack_from("<I", data, offset + 0x10)[0]
                content_start  = offset + content_offset
                content_end    = content_start + content_len
                content        = data[content_start:content_end]

                if attr_type == ATTR_STANDARD_INFO and len(content) >= 48:
                    self._parse_standard_info(content)

                elif attr_type == ATTR_FILE_NAME and len(content) >= 66:
                    self._parse_file_name(content)

            else:
                # Non-résident : taille réelle (offset + 0x30, 8 bytes)
                if attr_type == ATTR_DATA and offset + 0x38 <= len(data):
                    real_size = struct.unpack_from("<Q", data, offset + 0x30)[0]
                    if real_size > 0:
                        self.file_size = real_size

            offset += attr_len

    def _parse_standard_info(self, content: bytes):
        """Parse $STANDARD_INFORMATION : timestamps."""
        # Timestamps FILETIME (100ns depuis 1601-01-01)
        created_ft  = struct.unpack_from("<Q", content, 0)[0]
        modified_ft = struct.unpack_from("<Q", content, 8)[0]

        self.created  = self._filetime_to_datetime(created_ft)
        self.modified = self._filetime_to_datetime(modified_ft)

    def _parse_file_name(self, content: bytes):
        """Parse $FILE_NAME : nom du fichier + référence parent."""
        # Référence du parent (8 bytes, les 6 premiers = numéro de record)
        parent_ref_raw = struct.unpack_from("<Q", content, 0)[0]
        parent_ref     = parent_ref_raw & 0x0000FFFFFFFFFFFF  # masque sur 48 bits

        # Namespace (offset 0x41, 1 byte)
        namespace = content[0x41] if len(content) > 0x41 else -1

        # Longueur du nom (offset 0x40, 1 byte) en caractères UTF-16
        name_len = content[0x40] if len(content) > 0x40 else 0
        name_start = 0x42
        name_end   = name_start + name_len * 2

        if name_end <= len(content):
            name = content[name_start:name_end].decode("utf-16-le", errors="replace")
        else:
            name = ""

        # Taille du fichier dans $FILE_NAME (offset 0x30, 8 bytes)
        allocated_size = struct.unpack_from("<Q", content, 0x28)[0]
        real_size      = struct.unpack_from("<Q", content, 0x30)[0]

        # Priorité des namespaces : WIN32 > WIN32_DOS > POSIX > DOS
        priority = {
            NAMESPACE_WIN32:     3,
            NAMESPACE_WIN32_DOS: 2,
            NAMESPACE_POSIX:     1,
            NAMESPACE_DOS:       0,
        }
        current_priority = priority.get(self.namespace, -1)
        new_priority     = priority.get(namespace, -1)

        if new_priority > current_priority:
            self.name       = name
            self.namespace  = namespace
            self.parent_ref = parent_ref
            if real_size > 0 and self.file_size == 0:
                self.file_size = real_size

    @staticmethod
    def _filetime_to_datetime(filetime: int):
        """Convertit un FILETIME Windows en datetime Python."""
        if filetime == 0:
            return None
        try:
            # FILETIME = 100ns depuis 1601-01-01
            # Unix epoch = 1970-01-01 → delta = 116444736000000000 * 100ns
            unix_timestamp = (filetime - 116444736000000000) / 10_000_000
            return datetime.utcfromtimestamp(unix_timestamp)
        except (OSError, OverflowError, ValueError):
            return None


# ─────────────────────────────────────────────────────────────────
# LECTEUR MFT PRINCIPAL
# ─────────────────────────────────────────────────────────────────

class MFTReader:
    """
    Lit le MFT d'un volume NTFS et reconstruit l'arborescence complète.
    """

    def __init__(self, drive: str):
        """
        drive : lettre du lecteur, ex. 'C' ou 'C:\\' ou 'C:/'
        """
        self.drive       = drive.rstrip(":\\/")[0].upper()
        self.handle      = None
        self.boot        = None
        self.records     = {}          # record_number → MFTRecord
        self.folder_tree = defaultdict(list)   # parent_ref → [children record_numbers]

    def _check_admin(self):
        """Vérifie les droits administrateur."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False

    def open(self):
        """Ouvre le volume et lit le boot sector."""
        if not self._check_admin():
            raise PermissionError(
                "Droits administrateur requis pour lire le MFT.\n"
                "Lance le script avec 'Exécuter en tant qu'administrateur'."
            )

        print(f"📂 Ouverture du volume {self.drive}: ...")
        self.handle = open_volume(self.drive)

        # Lit les 512 premiers octets = VBR
        vbr_data   = read_bytes(self.handle, 0, 512)
        self.boot  = NTFSBootSector(vbr_data)
        print(f"✅ Boot sector lu : {self.boot}")

    def close(self):
        """Ferme le handle du volume."""
        if self.handle:
            import win32file
            win32file.CloseHandle(self.handle)
            self.handle = None

    def read_all_records(self, max_records: int = None):
        """
        Lit tous les records MFT et les stocke dans self.records.

        max_records : limite optionnelle (utile pour les tests)
        """
        if not self.handle or not self.boot:
            raise RuntimeError("Appelle open() d'abord.")

        record_size = self.boot.record_size
        mft_offset  = self.boot.mft_offset

        print(f"📖 Lecture du MFT depuis l'offset 0x{mft_offset:X}...")

        # Lit d'abord le record 0 ($MFT lui-même) pour connaître la taille totale
        mft_record_0_data = read_bytes(self.handle, mft_offset, record_size)
        mft_record_0      = MFTRecord(mft_record_0_data, 0)
        total_mft_size    = mft_record_0.file_size
        total_records     = total_mft_size // record_size if total_mft_size else 0

        print(f"📊 Taille du MFT : {total_mft_size / (1024**2):.1f} Mo → {total_records:,} records estimés")

        if max_records:
            total_records = min(total_records, max_records)

        # Lecture par blocs pour minimiser les appels système
        BATCH_SIZE = 256  # records par batch
        batch_bytes = BATCH_SIZE * record_size

        read_count = 0
        valid_count = 0

        for batch_start in range(0, total_records, BATCH_SIZE):
            offset = mft_offset + batch_start * record_size
            try:
                batch_data = read_bytes(self.handle, offset, batch_bytes)
            except Exception as e:
                print(f"⚠️  Erreur lecture offset 0x{offset:X} : {e}")
                continue

            for i in range(BATCH_SIZE):
                record_number = batch_start + i
                if record_number >= total_records:
                    break

                start = i * record_size
                end   = start + record_size
                record_data = batch_data[start:end]

                if len(record_data) < record_size:
                    break

                record = MFTRecord(record_data, record_number)
                read_count += 1

                if record.is_valid and record.is_in_use and record.name:
                    self.records[record_number] = record
                    valid_count += 1

                    # Construit l'arbre parent → enfants
                    if record.parent_ref is not None and record.parent_ref != record_number:
                        self.folder_tree[record.parent_ref].append(record_number)

            # Progression
            if batch_start % (BATCH_SIZE * 100) == 0 and batch_start > 0:
                pct = batch_start / total_records * 100
                print(f"   {pct:.1f}% — {valid_count:,} entrées valides lues...")

        print(f"✅ Lecture terminée : {valid_count:,} entrées valides sur {read_count:,} records lus")

    def get_full_path(self, record_number: int, _depth: int = 0) -> str:
        """Reconstruit le chemin complet d'un record."""
        if _depth > 64:  # protection contre les cycles
            return "..."

        record = self.records.get(record_number)
        if not record:
            return f"{self.drive}:\\"

        parent_ref = record.parent_ref
        if parent_ref is None or parent_ref == record_number or parent_ref == 5:
            # Record 5 = racine du volume
            return f"{self.drive}:\\{record.name}"

        parent_path = self.get_full_path(parent_ref, _depth + 1)
        return f"{parent_path}\\{record.name}"

    def compute_folder_sizes(self) -> dict:
        """
        Calcule la taille de chaque dossier en sommant
        récursivement la taille de tous ses fichiers enfants.
        Retourne un dict : record_number → taille_totale_bytes
        """
        sizes = {}

        def accumulate(record_number: int) -> int:
            if record_number in sizes:
                return sizes[record_number]

            record = self.records.get(record_number)
            total = 0

            if record and not record.is_directory:
                total = record.file_size
            else:
                for child_number in self.folder_tree.get(record_number, []):
                    total += accumulate(child_number)

            sizes[record_number] = total
            return total

        # Calcule pour tous les dossiers
        for record_number, record in self.records.items():
            if record.is_directory:
                accumulate(record_number)

        return sizes

    def build_summary(self, max_depth: int = None) -> list:
        """max_depth=None → arborescence complète sans limite."""
        sizes = self.compute_folder_sizes()
        ROOT_REF = 5
        root_children = self.folder_tree.get(ROOT_REF, [])

        results = []
        for record_number in root_children:
            record = self.records.get(record_number)
            if not record or not record.is_directory:
                continue

            size = sizes.get(record_number, 0)
            results.append({
                "record_number": record_number,
                "name":          record.name,
                "size_bytes":    size,
                "size_display":  self._format_size(size),
                "child":         self._build_children(record_number, sizes, depth=1, max_depth=max_depth)
            })

        results.sort(key=lambda x: x["size_bytes"], reverse=True)
        return results

    def _build_children(self, parent_number: int, sizes: dict, depth: int, max_depth: int = None) -> list:
        """Construit récursivement la liste des enfants — sans limite si max_depth=None."""
        
        # Arrêt uniquement si max_depth est défini
        if max_depth is not None and depth >= max_depth:
            return []

        children = []
        for child_number in self.folder_tree.get(parent_number, []):
            child = self.records.get(child_number)
            if not child or not child.is_directory:
                continue

            size = sizes.get(child_number, 0)
            children.append({
                "record_number": child_number,
                "name":          child.name,
                "size_bytes":    size,
                "size_display":  self._format_size(size),
                "child":         self._build_children(child_number, sizes, depth + 1, max_depth)
            })

        children.sort(key=lambda x: x["size_bytes"], reverse=True)
        return children

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / 1024 ** 2:.2f} MB"
        elif size_bytes < 1024 ** 4:
            return f"{size_bytes / 1024 ** 3:.2f} GB"
        else:
            return f"{size_bytes / 1024 ** 4:.2f} TB"

    def export_json(self, output_path: str, max_depth: int = 2):
        """Exporte le résumé dans un fichier JSON."""
        summary = self.build_summary(max_depth=max_depth)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        print(f"💾 Exporté → {output_path} ({len(summary)} dossiers racine)")


# ─────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────
# python/mft_reader.py
# Ajoute cette fonction à la fin, remplace main()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("drive",     nargs="?", default="C")
    parser.add_argument("--depth",   type=int,  default=None)
    parser.add_argument("--output",  type=str,  default=None)  # ← nouveau
    args = parser.parse_args()

    reader = MFTReader(args.drive)
    try:
        reader.open()
        reader.read_all_records()
        summary = reader.build_summary(max_depth=args.depth)

        if args.output:
            # ✅ Écrit dans le fichier spécifié par Electron
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, default=str)
        else:
            # Fallback stdout
            print(json.dumps(summary, ensure_ascii=False, default=str))
            sys.stdout.flush()

    finally:
        reader.close()

if __name__ == "__main__":
    main()