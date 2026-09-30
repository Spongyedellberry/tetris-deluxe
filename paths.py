"""
paths.py — Résolution centralisée des chemins (ressources et données utilisateur).

Pourquoi un module dédié ?
  * En développement, les ressources (sons…) sont à côté du code source.
  * Une fois empaqueté en .exe (PyInstaller / Nuitka), le code tourne depuis
    un dossier temporaire en lecture seule : `sys._MEIPASS` (PyInstaller) ou
    le dossier de l'exécutable (Nuitka). Tout accès fichier doit donc passer
    par ici pour que le jeu fonctionne dans les deux cas.
"""

import os
import sys

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))


def is_frozen() -> bool:
    """Vrai si le jeu tourne depuis un exécutable empaqueté."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def resource_dir() -> str:
    """Dossier racine des ressources en lecture seule (assets/...)."""
    return getattr(sys, "_MEIPASS", _SRC_DIR)


def asset(*parts: str) -> str:
    """Chemin absolu d'une ressource, ex. asset('audio', 'bgm.wav')."""
    return os.path.join(resource_dir(), "assets", *parts)


def user_data_dir(app_name: str = "Tetris") -> str:
    """Dossier inscriptible pour les sauvegardes (paramètres, classement).

    En développement : le dossier du projet (comportement historique).
    En .exe : %APPDATA%/Tetris (Windows) ou ~/.local/share/Tetris.
    """
    if not is_frozen():
        return _SRC_DIR
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path
