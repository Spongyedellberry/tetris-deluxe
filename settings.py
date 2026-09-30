"""
settings.py — Paramètres persistants du jeu (difficulté, plein écran, touches).

Les paramètres sont sauvegardés dans tetris_settings.json et rechargés au lancement.
Emplacement : voir paths.user_data_dir() (dossier du projet en dev,
%APPDATA%\\Tetris pour le .exe).
"""

import json
import os
import copy

from paths import user_data_dir

SETTINGS_FILE = "tetris_settings.json"

# ─── Presets de difficulté ────────────────────────────────────
# Chaque preset définit les paramètres du SpeedManager
DIFFICULTY_PRESETS = {
    "Facile": {
        "label":       "Facile",
        "description": "Chute lente, accélération douce — idéal pour débuter",
        "base_speed":  0.70,
        "min_speed":   0.12,
        "level_factor": 0.03,   # réduction de vitesse par niveau
        "score_factor": 0.01,   # réduction de vitesse par palier de score
    },
    "Normal": {
        "label":       "Normal",
        "description": "La vitesse classique du Tetris",
        "base_speed":  0.50,
        "min_speed":   0.05,
        "level_factor": 0.05,
        "score_factor": 0.02,
    },
    "Difficile": {
        "label":       "Difficile",
        "description": "Départ rapide, accélération agressive",
        "base_speed":  0.32,
        "min_speed":   0.03,
        "level_factor": 0.05,
        "score_factor": 0.025,
    },
    "Extrême": {
        "label":       "Extrême",
        "description": "Réservé aux experts — chaque seconde compte",
        "base_speed":  0.18,
        "min_speed":   0.02,
        "level_factor": 0.04,
        "score_factor": 0.02,
    },
}

# ─── Touches par défaut ──────────────────────────────────────
# Noms lisibles pour les touches tkinter
KEY_DISPLAY_NAMES = {
    "<Left>":    "←",
    "<Right>":   "→",
    "<Up>":      "↑",
    "<Down>":    "↓",
    "<space>":   "Espace",
    "<Return>":  "Entrée",
    "<Tab>":     "Tab",
    "<Escape>":  "Échap",
    "<Shift_L>": "Shift G",
    "<Shift_R>": "Shift D",
    "<Control_L>": "Ctrl G",
    "<Control_R>": "Ctrl D",
}

# Actions et leur nom affiché
SOLO_ACTIONS = {
    "move_left":   "Gauche",
    "move_right":  "Droite",
    "soft_drop":   "Descente",
    "rotate_cw":   "Rotation ↻",
    "rotate_ccw":  "Rotation ↺",
    "hard_drop":   "Hard Drop",
    "hold":        "Hold (stocker)",
    "pause":       "Pause",
    "quit":        "Quitter",
    "restart":     "Recommencer",
}

MULTI_P1_ACTIONS = {
    "move_left":   "J1 Gauche",
    "move_right":  "J1 Droite",
    "soft_drop":   "J1 Descente",
    "rotate_cw":   "J1 Rotation",
    "hard_drop":   "J1 Hard Drop",
}

MULTI_P2_ACTIONS = {
    "move_left":   "J2 Gauche",
    "move_right":  "J2 Droite",
    "soft_drop":   "J2 Descente",
    "rotate_cw":   "J2 Rotation",
    "hard_drop":   "J2 Hard Drop",
}

# ─── Valeurs par défaut complètes ────────────────────────────
DEFAULT_SETTINGS = {
    "fullscreen": False,
    "difficulty": "Normal",
    "ghost_piece": True,
    "music_enabled": True,
    "sfx_enabled": True,
    "bgm_volume": 0.3,
    "sfx_volume": 0.6,
    "solo_keys": {
        "move_left":  "<Left>",
        "move_right": "<Right>",
        "soft_drop":  "<Down>",
        "rotate_cw":  "<Up>",
        "rotate_ccw": "z",
        "hard_drop":  "<space>",
        "hold":       "c",
        "pause":      "p",
        "quit":       "q",
        "restart":    "r",
    },
    "multi_p1_keys": {
        "move_left":  "q",
        "move_right": "d",
        "soft_drop":  "s",
        "rotate_cw":  "z",
        "hard_drop":  "<Tab>",
    },
    "multi_p2_keys": {
        "move_left":  "<Left>",
        "move_right": "<Right>",
        "soft_drop":  "<Down>",
        "rotate_cw":  "<Up>",
        "hard_drop":  "<Return>",
    },
}


def key_display(key: str) -> str:
    """Retourne le nom lisible d'une touche tkinter."""
    if key in KEY_DISPLAY_NAMES:
        return KEY_DISPLAY_NAMES[key]
    if len(key) == 1:
        return key.upper()
    # Ex: <Key-a> → A
    return key.strip("<>").replace("Key-", "").upper()


class Settings:
    """Gestionnaire de paramètres avec persistance JSON."""

    def __init__(self, filename: str | None = None):
        self.filename = filename or os.path.join(user_data_dir(), SETTINGS_FILE)
        self.data: dict = copy.deepcopy(DEFAULT_SETTINGS)
        self._load()

    # ── Persistance ───────────────────────────────────────────
    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Fusion : on garde les valeurs sauvegardées mais on complète
                # avec les valeurs par défaut pour les nouvelles clés
                self._merge(self.data, saved)
            except Exception:
                pass  # garder les valeurs par défaut

    def _merge(self, base: dict, overlay: dict):
        """Fusionne overlay dans base (récursif)."""
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge(base[key], value)
            else:
                base[key] = value

    def save(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ── Accès rapide ──────────────────────────────────────────
    @property
    def fullscreen(self) -> bool:
        return self.data.get("fullscreen", False)

    @fullscreen.setter
    def fullscreen(self, val: bool):
        self.data["fullscreen"] = val

    @property
    def difficulty(self) -> str:
        return self.data.get("difficulty", "Normal")

    @difficulty.setter
    def difficulty(self, val: str):
        self.data["difficulty"] = val

    @property
    def ghost_piece(self) -> bool:
        return self.data.get("ghost_piece", True)

    @ghost_piece.setter
    def ghost_piece(self, val: bool):
        self.data["ghost_piece"] = val

    @property
    def music_enabled(self) -> bool:
        return self.data.get("music_enabled", True)

    @music_enabled.setter
    def music_enabled(self, val: bool):
        self.data["music_enabled"] = val

    @property
    def sfx_enabled(self) -> bool:
        return self.data.get("sfx_enabled", True)

    @sfx_enabled.setter
    def sfx_enabled(self, val: bool):
        self.data["sfx_enabled"] = val

    @property
    def bgm_volume(self) -> float:
        return self.data.get("bgm_volume", 0.3)

    @bgm_volume.setter
    def bgm_volume(self, val: float):
        self.data["bgm_volume"] = max(0.0, min(1.0, val))

    @property
    def sfx_volume(self) -> float:
        return self.data.get("sfx_volume", 0.6)

    @sfx_volume.setter
    def sfx_volume(self, val: float):
        self.data["sfx_volume"] = max(0.0, min(1.0, val))

    @property
    def difficulty_preset(self) -> dict:
        """Retourne le preset de difficulté actuel."""
        return DIFFICULTY_PRESETS.get(self.difficulty,
                                     DIFFICULTY_PRESETS["Normal"])

    def solo_key(self, action: str) -> str:
        return self.data["solo_keys"].get(action, "")

    def multi_p1_key(self, action: str) -> str:
        return self.data["multi_p1_keys"].get(action, "")

    def multi_p2_key(self, action: str) -> str:
        return self.data["multi_p2_keys"].get(action, "")

    def set_solo_key(self, action: str, key: str):
        self.data["solo_keys"][action] = key

    def set_multi_p1_key(self, action: str, key: str):
        self.data["multi_p1_keys"][action] = key

    def set_multi_p2_key(self, action: str, key: str):
        self.data["multi_p2_keys"][action] = key

    def reset_to_defaults(self):
        """Remet tous les paramètres aux valeurs par défaut."""
        self.data = copy.deepcopy(DEFAULT_SETTINGS)

    # ── Helpers pour les jeux ─────────────────────────────────
    def make_speed_manager(self):
        """Crée un SpeedManager configuré selon la difficulté choisie."""
        from score import SpeedManager
        p = self.difficulty_preset
        return SpeedManager(base=p["base_speed"], minimum=p["min_speed"],
                            level_factor=p["level_factor"],
                            score_factor=p["score_factor"])
