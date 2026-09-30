# -*- mode: python ; coding: utf-8 -*-
"""
packaging/tetris.spec — Recette PyInstaller pour Tetris Deluxe.

    make exe            → dist/TetrisDeluxe/TetrisDeluxe.exe  (dossier, démarrage rapide)
    make exe-onefile    → dist/TetrisDeluxe.exe               (un seul fichier)

Mode dossier (défaut) : c'est ce que font les jeux Steam — un .exe à côté
de ses bibliothèques. Démarre instantanément.
Mode fichier unique : pratique à partager, mais se décompresse dans un
dossier temporaire à chaque lancement (≈1–2 s de plus).

Appel direct : pyinstaller packaging/tetris.spec [-- --onefile]
"""

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))       # noqa: F821 (fourni par PyInstaller)
sys.path.insert(0, ROOT)
import version  # noqa: E402

opts = argparse.ArgumentParser()
opts.add_argument("--onefile", action="store_true")
opts = opts.parse_args()

EXE_NAME = version.APP_NAME.replace(" ", "")               # TetrisDeluxe
ICON = os.path.join(ROOT, "assets", "icon.ico")


# ── Propriétés du fichier Windows (clic droit → Propriétés → Détails) ──
def _version_file() -> str:
    parts = (version.__version__.split(".") + ["0"] * 4)[:4]
    nums = ", ".join(parts)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({nums}), prodvers=({nums}), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040C04B0', [
      StringStruct('CompanyName', '{version.AUTHOR}'),
      StringStruct('FileDescription', '{version.APP_NAME}'),
      StringStruct('FileVersion', '{version.__version__}'),
      StringStruct('InternalName', '{EXE_NAME}'),
      StringStruct('OriginalFilename', '{EXE_NAME}.exe'),
      StringStruct('ProductName', '{version.APP_NAME}'),
      StringStruct('ProductVersion', '{version.__version__}'),
      StringStruct('LegalCopyright', '© {version.AUTHOR}')])]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)"""
    path = os.path.join(workpath, "version_info.txt")      # noqa: F821
    os.makedirs(workpath, exist_ok=True)                    # noqa: F821
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


a = Analysis(                                               # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets"), "assets")],       # sons + icône
    # Modules importés à l'intérieur de fonctions (chargement paresseux)
    hiddenimports=["game_solo", "game_multi", "settings_screen", "audio"],
    excludes=[
        # Inutiles au jeu : réduisent la taille de la distribution
        "numpy", "PIL", "unittest", "pydoc", "doctest", "test",
        "tools", "ruff", "snakeviz", "PyInstaller",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)                                           # noqa: F821

exe_common = dict(
    name=EXE_NAME,
    icon=ICON,
    version=_version_file() if sys.platform == "win32" else None,
    console=False,          # pas de fenêtre de console noire
    upx=False,              # UPX déclenche souvent des faux positifs antivirus
    debug=False,
    strip=False,
)

if opts.onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **exe_common)   # noqa: F821
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_common)  # noqa: F821
    coll = COLLECT(exe, a.binaries, a.datas, name=EXE_NAME, upx=False)  # noqa: F821
