from email import generator
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import string
import shutil 
import subprocess

from fastapi.responses import StreamingResponse
import psutil


class DiskAnalyzer:
    def __init__(self, path, max_workers=5):
        
        self.partitions = [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]

        self.path = path
        self.max_workers = max_workers
        if not os.path.exists(self.path):
            raise ValueError(f"Le chemin {self.path} n'existe pas.")
        if not os.path.isdir(self.path):
            raise ValueError(f"{self.path} n'est pas un dossier.")
        self.total, self.used, self.free = shutil.disk_usage(self.path)


    def list_partitions(self):
        """Liste les partitions/lecteurs et leur taille"""
        partitions = psutil.disk_partitions()
        listDisk= []
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                listDisk.append({f"Partition": {p.device}, "Mountpoint": {p.mountpoint}, "Total": {usage.total}})
            except Exception  : 
                pass
                # return {'code': '500', 'message': f"Erreur lors de la récupération des partitions {e}"}
        
        return listDisk
            
    def get_size(self, start_path):
        """Calcul récursif optimisé de la taille d'un dossier"""
        total_size = 0
        try:
            with os.scandir(start_path) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total_size += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            total_size += self.get_size(entry.path)
                    except Exception:
                        pass
        except Exception:
            pass
        return total_size

    def format_size(self, size_in_bytes):
        """Format lisible : Go si >= 1 Go sinon Mo"""
        if size_in_bytes >= 1024**3:
            return f"{size_in_bytes / (1024**3):.2f} Go"
        else:
            return f"{size_in_bytes / (1024**2):.2f} Mo"
        
    def _scan_children(self, folder_path: str, optimal_workers: int) -> list:
        """Scan récursif de tous les sous-dossiers imbriqués"""
        children = []
        try:
            subfolders = [
                entry.path for entry in os.scandir(folder_path)
                if entry.is_dir(follow_symlinks=False)
            ]
        except (PermissionError, OSError):
            return children

        if not subfolders:
            return children

        # Scan parallèle des tailles
        child_results = []
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            child_futures = {
                executor.submit(self.get_size_fast, p): p
                for p in subfolders
            }
            for future in as_completed(child_futures):
                p = child_futures[future]
                try:
                    child_size = future.result()
                    child_results.append((p, os.path.basename(p), child_size))
                except Exception:
                    pass

        child_results.sort(key=lambda x: x[2], reverse=True)
        total_child_size = sum(s for _, _, s in child_results)

        for full_path, name, size in child_results:
            percent = round((size / total_child_size * 100) if total_child_size > 0 else 0, 2)
            children.append({
                "name":         name,
                "size_bytes":   size,
                "size_display": self.format_size(size),
                "percent":      percent,
                "child":        self._scan_children(full_path, optimal_workers)  # ← récursion
            })

        return children


    def analyze_root_folders(self):
        """Analyse des dossiers à la racine + tous les sous-dossiers récursivement"""

        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "folders.json")

        try:
            folders = [
                entry.path for entry in os.scandir(self.path)
                if entry.is_dir(follow_symlinks=False)
            ]
        except PermissionError:
            yield json.dumps({"error": f"Accès refusé à {self.path}"})
            return

        if not folders:
            yield json.dumps({"error": "Aucun dossier trouvé."})
            return

        optimal_workers = min(32, os.cpu_count() or 8)
        results = []

        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            futures = {
                executor.submit(self.get_size_fast, path): path
                for path in folders
            }
            for future in as_completed(futures):
                path = futures[future]
                try:
                    size = future.result()
                    results.append((path, os.path.basename(path), size))
                except Exception as e:
                    yield json.dumps({"error": str(e)})

        results.sort(key=lambda x: x[2], reverse=True)

        file = []
        for full_path, name, size in results:
            percent = round((size / self.used * 100) if self.used > 0 else 0, 2)
            file.append({
                "name":         name,
                "size_bytes":   size,
                "size_display": self.format_size(size),
                "percent":      percent,
                "child":        self._scan_children(full_path, optimal_workers)  # ← récursif
            })

        # Écriture AVANT les yields
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(file, f, ensure_ascii=False, indent=2)
            print(f"💾 folders.json sauvegardé → {cache_file}")
        except OSError as e:
            print(f"⚠️  Impossible d'écrire folders.json : {e}")

        for entry in file:
            yield json.dumps(entry)
    
    # def analyze_root_folders(self):
    #     """Analyse des dossiers à la racine avec threads"""
    #     try:
    #         folders = [
    #             entry.path for entry in os.scandir(self.path)
    #             if entry.is_dir(follow_symlinks=False)
    #         ]
    #     except PermissionError:
    #         yield json.dumps({"error": f"Accès refusé à {self.path}"})
    #         return
        

    #     if not folders:
    #         yield json.dumps({"error": "Aucun dossier trouvé."})
    #         return

    #     # optimal_workers = min(32, (os.cpu_count() or 8) * 2)
    #     optimal_workers = min(32, (os.cpu_count() or 8))
    #     results = []

    #     with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
    #         futures = {
    #             executor.submit(self.get_size_fast, path): path
    #             for path in folders
    #         }
    #         for future in as_completed(futures):
    #             path = futures[future]
    #             try:
    #                 size = future.result()
    #                 results.append((os.path.basename(path), size))
    #             except Exception as e:
    #                 yield json.dumps({"error": str(e)})

    #     # ✅ Tri APRÈS que tous les threads ont fini
    #     results.sort(key=lambda x: x[1], reverse=True)

    #     # ✅ Un seul yield ici, après le tri
    #     for name, size in results:
    #         percent = round((size / self.used * 100) if self.used > 0 else 0, 2)
    #         yield json.dumps({
    #             "name": name,
    #             "size_bytes": size,
    #             "size_display": self.format_size(size),
    #             "percent": percent
    #         })

    def get_size_fast(self, path: str) -> int:
        total = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            total += self.get_size_fast(entry.path)
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError):
            pass
        return total

    def analyze_subfolders(self, folder_name: str):
        """Analyse parallèle optimisée des sous-dossiers"""
        target_path = os.path.join(self.path, folder_name)
        print(f"🔍 Analyse de {target_path} avec {self.max_workers} threads...")
        print(f"📁 Chemin complet : {target_path}")

        if not os.path.exists(target_path) or not os.path.isdir(target_path):
            yield json.dumps({"error": f"Dossier '{folder_name}' introuvable"})
            return

        try:
            subfolders = [
                entry.path for entry in os.scandir(target_path)
                if entry.is_dir(follow_symlinks=False)
            ]
        except PermissionError:
            yield json.dumps({"error": f"Accès refusé à {target_path}"})
            return

        if not subfolders:
            yield json.dumps({"error": "Aucun sous-dossier trouvé."})
            return

        # optimal_workers = min(32, (os.cpu_count() or 8) * 2)
        optimal_workers = min(32, (os.cpu_count() or 8) )
        results = []

        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            futures = {
                executor.submit(self.get_size_fast, path): path
                for path in subfolders
            }
            for future in as_completed(futures):
                path = futures[future]
                try:
                    size = future.result()
                    results.append((os.path.basename(path), size))
                except Exception as e:
                    yield json.dumps({"error": str(e)})

        # ✅ Tri correct sur int
        results.sort(key=lambda x: x[1], reverse=True)
        total_size = sum(size for _, size in results)

        # ✅ yield propre, pas de StreamingResponse ici !
        for name, size in results:
            percent = round((size / total_size * 100) if total_size > 0 else 0, 2)
            yield json.dumps({
                "name": name,
                "size_bytes": size,
                "size_display": self.format_size(size),
                "percent": percent
            })
    
    def analyze_unnecessary_files(self, start_path=None, max_workers=10):
        """
        Analyse multithreadée des fichiers considérés comme inutiles (temp, log, bak, dmp, cache)
        dans start_path (par défaut, self.path).
        Affiche la taille totale et par type d’extension.
        """

        if start_path is None:
            start_path = self.path

        unnecessary_extensions = {'.tmp', '.log', '.bak', '.dmp', '.old', '.chk', '.temp'}
        unnecessary_names = {'thumbs.db', 'desktop.ini'}

        def check_file(file_info):
            dirpath, file = file_info
            try:
                ext = os.path.splitext(file)[1].lower()
                if ext in unnecessary_extensions or file.lower() in unnecessary_names:
                    filepath = os.path.join(dirpath, file)
                    return ext, os.path.getsize(filepath)
            except Exception:
                pass
            return None

        # Collecter tous les fichiers (dirpath, filename)
        files_to_check = []
        for dirpath, dirnames, filenames in os.walk(start_path):
            for file in filenames:
                files_to_check.append((dirpath, file))

        total_unnecessary_size = 0
        size_by_extension = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(check_file, fi) for fi in files_to_check]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    ext, size = result
                    total_unnecessary_size += size
                    size_by_extension[ext] = size_by_extension.get(ext, 0) + size

        print(f"\nAnalyse des fichiers inutiles dans {start_path}:")
        print(f"Taille totale des fichiers inutiles : {total_unnecessary_size / (1024**2):.2f} Mo")
        print("Détail par type d'extension :")
        for ext, size in size_by_extension.items():
            print(f"  {ext or '[sans extension]':<10} : {size / (1024**2):.2f} Mo")

        if total_unnecessary_size == 0:
            print("Aucun fichier inutile détecté.") 

    def get_connected_disks(self):
        """Retourne une liste des lettres de disque existantes (ex: C:\, D:\, etc.)"""
        return [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]

    def get_disk_usage(self, partition):
        """Retourne les informations d'utilisation d'un disque (Go)"""
        total, used, free = shutil.disk_usage(partition)
        return {
            "total_GB": total // (1024 ** 3),
            "used_GB": used // (1024 ** 3),
            "free_GB": free // (1024 ** 3)
        }
        
    def display_disks_info(self):
        """Affiche les informations des disques et appareils ADB connectés"""
        print("💽 Disques locaux détectés :")
    
        partitions = self.list_partitions()  # Récupère la liste des partitions
        results = []

        for disk in partitions:
            # Extraire le mountpoint depuis le dict retourné par list_partitions
            mountpoint = list(disk["Mountpoint"])[0]
            device     = list(disk["Partition"])[0]
            
            try:
                usage = psutil.disk_usage(mountpoint)
                
                total_GB = round(usage.total / (1024 ** 3), 2)
                used_GB  = round(usage.used  / (1024 ** 3), 2)
                free_GB  = round(usage.free  / (1024 ** 3), 2)

                print(f"📁 Partition : {device} ({mountpoint})")
                print(f"  📦 Taille totale : {total_GB} Go")
                print(f"  🗃️ Espace utilisé : {used_GB} Go")
                print(f"  📂 Espace libre   : {free_GB} Go\n")

                results.append({
                    "partition": device,
                    "mountpoint": mountpoint,
                    "total_GB": total_GB,
                    "used_GB": used_GB,
                    "free_GB": free_GB
                })

            except PermissionError:
                print(f"❌ Accès refusé à {mountpoint}")
                results.append({'code': 500, 'message': f"Accès refusé à {mountpoint}"})

            except FileNotFoundError:
                print(f"❌ Partition non trouvée : {mountpoint}")
                results.append({'code': 404, 'message': f"Partition non trouvée : {mountpoint}"})

            except Exception as e:
                print(f"⚠️ Erreur avec {mountpoint} : {e}")
                results.append({'code': 500, 'message': f"Erreur avec {mountpoint} : {e}"})

        return results
    
    def get_disk_usage(self, partition):
        total, used, free = shutil.disk_usage(partition)
        return {
            "total_GB": total // (1024 ** 3),
            "used_GB": used // (1024 ** 3),
            "free_GB": free // (1024 ** 3)
        }

    def list_android_devices(self):
        """Retourne une liste d'appareils Android connectés via ADB"""
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            lines = result.stdout.strip().splitlines()[1:]  # Ignore la 1re ligne "List of devices attached"
            devices = [line.split()[0] for line in lines if "device" in line]
            return devices
        except Exception as e:
            print(f"⚠️ Erreur lors de la détection ADB : {e}")
            return []



    def lister_dossier_telephone(self, path="/sdcard/"):
        try:
            result = subprocess.run(["adb", "shell", "ls", path], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"📂 Contenu de {path} :\n{result.stdout}")
            else:
                print(f"❌ Erreur ADB : {result.stderr}")
        except Exception as e:
            print(f"⚠️ Erreur lors de la commande ADB : {e}")
            
    def afficher_stockage_interne_visiteur(self):
        """Affiche les fichiers visibles dans le stockage interne accessible de l'utilisateur"""
        try:
            result = subprocess.run(["adb", "shell", "ls", "/sdcard/"], capture_output=True, text=True)
            if result.returncode == 0:
                print("📁 Stockage interne (/sdcard/) :\n" + result.stdout)
            else:
                print("❌ Erreur ADB :\n" + result.stderr)
        except Exception as e:
            print(f"⚠️ Erreur : {e}")
        
# # Exemple d'utilisation :
# if __name__ == "__main__":
#     analyzer = DiskAnalyzer("C:\\",max_workers=10)
#     disk_info = DiskAnalyzer("C:\\",max_workers=10) 
#     analyzer.analyze_subfolders("Users/")
    
    # disk_info.display_disks_info()
    # disk_info.lister_dossier_telephone()
    # disk_info.afficher_stockage_interne_visiteur()
    # analyzer.analyze_root_folders()
    # Pour analyser un dossier spécifique à l'intérieur de C:
    # analyzer.analyze_subfolders("Users/1489DaDAMA/Documents/project_2024/etat_des_encours")
    # analyzer.analyze_subfolders("Users/")
    # analyzer.analyze_subfolders("Users/1489DaDAMA/AppData/Local")
    # analyzer.analyze_subfolders("Users/1489DaDAMA/Documents")
    # analyzer.analyze_subfolders("Users/1489DaDAMA/Documents/project_2024")
    # analyzer.analyze_unnecessary_files("C:\\Windows", max_workers=20)
