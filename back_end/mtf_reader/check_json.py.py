import json
import os

# Chemin du JSON
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mft_output.json")

with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

def find_folder(nodes, name, path=""):
    for n in nodes:
        p = path + "\\" + n["name"]
        if name.lower() in n["name"].lower():
            print(f"{p} = {n['size_bytes']/1024**3:.3f} GB  ({n['size_bytes']:,} bytes)")
        find_folder(n.get("child", []), name, p)

print("=== Recherche 'Downloads' ===")
find_folder(data, "downloads")

print("\n=== Recherche '1489DaDAMA' ===")
find_folder(data, "1489dadama")

print("\n=== Dossiers racine ===")
for n in data:
    print(f"  {n['name']:<40} {n['size_bytes']/1024**3:.3f} GB")