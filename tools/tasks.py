#!/usr/bin/env python3
"""
tools/tasks.py — Petites tâches utilitaires appelées par le Makefile.

Pourquoi ? Sous Windows, make exécute les recettes avec cmd.exe, qui ne
comprend pas les guillemets échappés (\\") des commandes `python -c "..."`.
En déplaçant la logique ici, le Makefile reste identique sur Windows,
Linux et macOS.

Usage : python tools/tasks.py help | mkdir <dossier> | clean | zip
"""

import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def cmd_help():
    """Liste les cibles documentées (« cible: ## description ») du Makefile."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    print("Commandes disponibles :\n")
    for target, desc in re.findall(r"^([a-z][a-z-]*):.*?## (.*)$", text, re.M):
        print(f"  make {target:<14} {desc}")
    print("\nAutre Python :  make run PYTHON=py")


def cmd_mkdir(path: str):
    (ROOT / path).mkdir(parents=True, exist_ok=True)


def cmd_clean():
    targets = [ROOT / "build", ROOT / "dist", ROOT / ".ruff_cache",
               *ROOT.rglob("__pycache__")]
    for p in targets:
        shutil.rmtree(p, ignore_errors=True)
    print("Nettoyé : build/, dist/, .ruff_cache/, __pycache__/")


def cmd_zip():
    """Archive dist/<App>/ en dist/<App>-<version>-<plateforme>.zip."""
    sys.path.insert(0, str(ROOT))
    import version
    name = version.APP_NAME.replace(" ", "")
    src = ROOT / "dist" / name
    if not src.is_dir():
        sys.exit(f"{src} introuvable : lancer d'abord « make exe »")
    plat = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    base = ROOT / "dist" / f"{name}-{version.__version__}-{plat}"
    archive = shutil.make_archive(str(base), "zip", root_dir=src.parent, base_dir=name)
    size = pathlib.Path(archive).stat().st_size / 1_048_576
    print(f"Créé : {pathlib.Path(archive).relative_to(ROOT)}  ({size:.1f} Mo)")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "help":
        cmd_help()
    elif cmd == "mkdir" and args:
        cmd_mkdir(args[0])
    elif cmd == "clean":
        cmd_clean()
    elif cmd == "zip":
        cmd_zip()
    else:
        sys.exit(f"Tâche inconnue : {cmd}")


if __name__ == "__main__":
    main()
