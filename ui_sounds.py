"""
ui_sounds.py — Sons et musique de l'interface (menus, paramètres, classement).

Une seule instance par application (créée par App). Elle :
  * ajoute à TOUS les tk.Button un son de survol et de clic, via des
    liaisons de classe (bind_class, add="+") : les écrans existants et
    futurs en profitent sans rien modifier ;
  * respecte les réglages « Effets sonores » / « Musique de fond » ;
  * ne fait rien si l'audio est indisponible (pygame absent).

Personnaliser le son d'un bouton :
    btn.ui_sound = "ui_back"   # ou "ui_start", ou None pour aucun son
"""

import time
import tkinter as tk

HOVER_MIN_INTERVAL = 0.045      # s — évite la « mitraillette » en balayant les boutons


class UISounds:
    def __init__(self, root: tk.Tk, settings):
        self.root = root
        self.settings = settings
        self._last_hover = 0.0
        try:
            from audio import get_audio
            self.audio = get_audio()
            self.audio.set_sfx_volume(settings.sfx_volume)
            self.audio.set_bgm_volume(settings.bgm_volume)
            if not self.audio.available:
                self.audio = None
        except Exception:
            self.audio = None

    # ── Liaisons globales ─────────────────────────────────────
    def install(self):
        """Survol + clic pour tous les boutons de l'application."""
        self.root.bind_class("Button", "<Enter>", self._on_hover, add="+")
        self.root.bind_class("Button", "<ButtonPress-1>", self._on_press, add="+")

    def _on_hover(self, event):
        w = event.widget
        if not isinstance(w, tk.Button) or str(w.cget("state")) == "disabled":
            return
        if getattr(w, "ui_sound", "ui_select") is None:
            return
        now = time.monotonic()
        if now - self._last_hover >= HOVER_MIN_INTERVAL:
            self._last_hover = now
            self.sfx("ui_hover")

    def _on_press(self, event):
        w = event.widget
        if not isinstance(w, tk.Button) or str(w.cget("state")) == "disabled":
            return
        name = getattr(w, "ui_sound", "ui_select")
        if name:
            self.sfx(name)

    # ── API ───────────────────────────────────────────────────
    def sfx(self, name: str):
        if self.audio and self.settings.sfx_enabled:
            self.audio.play_sfx(name)

    def music(self, track: str = "menu"):
        """Lance la piste (sans la redémarrer si elle joue déjà)."""
        if not self.audio:
            return
        if self.settings.music_enabled:
            self.audio.set_bgm_volume(self.settings.bgm_volume)
            self.audio.play_bgm(track)
        else:
            self.audio.stop_bgm()
