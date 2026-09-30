#!/usr/bin/env python3
"""
main.py — Point d'entrée du Tetris tkinter.
Menu principal animé avec pièces qui tombent en arrière-plan.

Optimisation (v3) : les objets du fond animé sont créés une seule fois
puis déplacés (canvas.move / coords) au lieu d'être détruits et recréés
à chaque frame. La grille de fond n'est redessinée qu'au redimensionnement.
"""

import os
import sys
import tkinter as tk
from tkinter import simpledialog
import random
import math
import time

from constants import (
    PANEL_BG, BG, TEXT_COLOR, ACCENT, ACCENT2, DIM_TEXT,
    PIECE_COLORS, PIECE_COLORS_LIGHT, SHAPES,
)
from leaderboard import Leaderboard
from settings import Settings, key_display
from ui_components import make_label
from paths import asset, user_data_dir
from version import APP_NAME, APP_ID, __version__

# ─── Dimensions du menu ────────────────────────────────────
MENU_W = 620
MENU_H = 580
BG_CELL = 18  # taille des cellules dans l'animation de fond


# ══════════════════════════════════════════════════════════════
#  Pièce flottante pour l'animation d'arrière-plan
# ══════════════════════════════════════════════════════════════

class FloatingPiece:
    """Une pièce Tetris qui tombe doucement dans l'arrière-plan du menu."""

    def __init__(self, canvas_w: int, canvas_h: int):
        shape_data = random.choice(SHAPES)
        self.matrix = shape_data[0]
        self.color_idx = shape_data[1]
        self.color = PIECE_COLORS[self.color_idx]
        self.light = PIECE_COLORS_LIGHT.get(self.color_idx, self.color)

        # Position et mouvement
        piece_w = len(self.matrix[0]) * BG_CELL
        self.x = random.uniform(0, canvas_w - piece_w)
        self.y = random.uniform(-canvas_h * 0.4, -40)
        self.speed = random.uniform(0.3, 1.2)          # px par frame
        self.drift = random.uniform(-0.15, 0.15)       # dérive horizontale
        self.rotation = 0.0
        self.rot_speed = random.uniform(-0.5, 0.5)     # degrés par frame

        # Apparence
        self.alpha = random.uniform(0.15, 0.45)         # opacité simulée
        self.scale = random.uniform(0.7, 1.3)
        self.canvas_h = canvas_h

        # Couleurs calculées une seule fois (elles ne changent jamais)
        self.fill = _blend(self.color, BG, self.alpha)
        self.outline = _blend(self.light, BG, self.alpha * 0.7)

        # Objets canvas (créés au premier draw, ensuite simplement déplacés)
        self._tag = f"fp{id(self)}"
        self._drawn_x = None
        self._drawn_y = None

    @property
    def cell(self) -> int:
        return max(6, int(BG_CELL * self.scale))

    def update(self):
        self.y += self.speed
        self.x += self.drift
        self.rotation += self.rot_speed

    def is_off_screen(self) -> bool:
        return self.y > self.canvas_h + 60

    def draw(self, canvas: tk.Canvas):
        if self._drawn_x is None:
            self._create(canvas)
        else:
            canvas.move(self._tag, self.x - self._drawn_x, self.y - self._drawn_y)
        self._drawn_x, self._drawn_y = self.x, self.y

    def _create(self, canvas: tk.Canvas):
        cs = self.cell
        tags = ("anim", self._tag)
        for ry, row in enumerate(self.matrix):
            for rx, cell in enumerate(row):
                if cell:
                    x1 = self.x + rx * cs
                    y1 = self.y + ry * cs
                    x2 = x1 + cs - 1
                    y2 = y1 + cs - 1
                    canvas.create_rectangle(x1, y1, x2, y2,
                                            fill=self.fill, outline=self.outline,
                                            width=1, tags=tags)
                    # Mini reflet
                    m = max(2, cs // 5)
                    canvas.create_rectangle(x1 + m, y1 + m,
                                            x1 + cs // 2, y1 + cs // 2,
                                            fill="", outline=self.outline,
                                            width=1, tags=tags)

    def remove(self, canvas: tk.Canvas):
        canvas.delete(self._tag)


# ══════════════════════════════════════════════════════════════
#  Particule scintillante
# ══════════════════════════════════════════════════════════════

class Sparkle:
    """Petite étoile scintillante dans l'arrière-plan."""

    def __init__(self, canvas_w: int, canvas_h: int):
        self.x = random.uniform(0, canvas_w)
        self.y = random.uniform(0, canvas_h)
        self.life = random.uniform(1.0, 3.0)   # durée de vie en secondes
        self.max_life = self.life
        self.size = random.uniform(1, 3)
        self.color = random.choice([ACCENT, ACCENT2, "#ffffff", "#ffd700"])
        self._item = None

    def update(self, dt: float):
        self.life -= dt

    def is_dead(self) -> bool:
        return self.life <= 0

    def draw(self, canvas: tk.Canvas):
        # Pulse
        t = self.life / self.max_life
        pulse = abs(math.sin(t * math.pi * 3))
        s = self.size * (0.5 + pulse * 0.5)

        c = _blend(self.color, BG, t * pulse * 0.6)
        coords = (self.x - s, self.y - s, self.x + s, self.y + s)

        if self._item is None:
            self._item = canvas.create_oval(*coords, fill=c, outline="", tags="anim")
        else:
            canvas.coords(self._item, *coords)
            canvas.itemconfigure(self._item, fill=c)

    def remove(self, canvas: tk.Canvas):
        if self._item is not None:
            canvas.delete(self._item)


# ══════════════════════════════════════════════════════════════
#  Utilitaires couleur
# ══════════════════════════════════════════════════════════════

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(fg: str, bg: str, a: float) -> str:
    """Mélange fg sur bg avec l'opacité a (simule la transparence)."""
    r, g, b = _hex_to_rgb(fg)
    br, bg_, bb = _hex_to_rgb(bg)
    return (f"#{int(br + (r - br) * a):02x}"
            f"{int(bg_ + (g - bg_) * a):02x}"
            f"{int(bb + (b - bb) * a):02x}")


# ══════════════════════════════════════════════════════════════
#  Application principale
# ══════════════════════════════════════════════════════════════

class App:
    """Application principale avec menu animé."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME}  v{__version__}")
        _set_window_icon(self.root)
        install_crash_handler(self.root)
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(500, 400)

        self.leaderboard = Leaderboard()
        self.settings = Settings()

        if self.settings.fullscreen:
            self.root.attributes("-fullscreen", True)

        # État de l'animation menu
        self._menu_active = False
        self._anim_id = None
        self._pieces: list[FloatingPiece] = []
        self._sparkles: list[Sparkle] = []
        self._last_time = time.monotonic()
        self._grid_size = None

        self._show_menu()

    # ── Nettoyage ─────────────────────────────────────────────
    def _clear(self):
        self._stop_menu_anim()
        for w in self.root.winfo_children():
            w.destroy()
        for seq in ["<Left>", "<Right>", "<Up>", "<Down>", "<space>",
                     "<Return>", "<Escape>", "<Tab>", "<Key>",
                     "q", "Q", "d", "D", "z", "Z", "s", "S",
                     "c", "C", "p", "P", "r", "R"]:
            try:
                self.root.unbind(seq)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════
    #  MENU PRINCIPAL ANIMÉ
    # ══════════════════════════════════════════════════════════

    def _show_menu(self):
        self._clear()

        # ── Canvas plein écran pour l'animation ───────────────
        # Taille explicite : sinon la fenêtre (non plein écran) prend la taille
        # par défaut d'un canvas et le menu est coupé en haut et en bas.
        self.menu_canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0,
                                     width=MENU_W, height=MENU_H)
        self.menu_canvas.pack(fill=tk.BOTH, expand=True)

        # ── Frame du menu (centré sur le canvas) ──────────────
        self.menu_frame = tk.Frame(self.menu_canvas, bg=PANEL_BG,
                                   highlightthickness=2,
                                   highlightbackground="#2a2a5a")
        self._menu_window_id = self.menu_canvas.create_window(
            0, 0, window=self.menu_frame, anchor="center")

        self._build_menu_content()

        # Repositionner le menu au centre quand la fenêtre change de taille
        self.menu_canvas.bind("<Configure>", self._on_canvas_resize)

        # ── Initialiser l'animation ───────────────────────────
        self._pieces = []
        self._sparkles = []
        self._last_time = time.monotonic()
        self._grid_size = None
        self._menu_active = True

        # Pré-remplir avec quelques pièces déjà en cours de chute
        self.root.update_idletasks()
        cw = max(MENU_W, self.menu_canvas.winfo_width())
        ch = max(MENU_H, self.menu_canvas.winfo_height())
        for _ in range(12):
            p = FloatingPiece(cw, ch)
            p.y = random.uniform(-ch * 0.3, ch)  # position aléatoire
            self._pieces.append(p)

        self._menu_tick()

    def _build_menu_content(self):
        f = self.menu_frame
        f.configure(padx=30, pady=20)

        # ── Titre ─────────────────────────────────────────────
        title_frame = tk.Frame(f, bg=PANEL_BG)
        title_frame.pack(pady=(5, 0))

        # Grand titre stylisé
        title_text = "T  E  T  R  I  S"
        title_lbl = tk.Label(title_frame, text=title_text,
                             font=("Consolas", 28, "bold"),
                             fg=ACCENT, bg=PANEL_BG)
        title_lbl.pack()

        # Sous-titre avec effet de couleur
        subtitle = tk.Label(title_frame, text="── ÉDITION DELUXE ──",
                            font=("Consolas", 10), fg=ACCENT2, bg=PANEL_BG)
        subtitle.pack()

        # Animation du titre : les lettres changent de couleur
        self._title_label = title_lbl
        self._title_colors = [
            PIECE_COLORS[1], PIECE_COLORS[2], PIECE_COLORS[3],
            PIECE_COLORS[4], PIECE_COLORS[5], PIECE_COLORS[6],
            PIECE_COLORS[7],
        ]

        tk.Frame(f, height=16, bg=PANEL_BG).pack()

        # ── Boutons ───────────────────────────────────────────
        btn_style = dict(
            font=("Consolas", 14),
            fg=TEXT_COLOR, bg="#1e1e40",
            activeforeground=ACCENT, activebackground="#2a2a5a",
            relief="flat", cursor="hand2",
            width=30, pady=8,
            borderwidth=0, highlightthickness=1,
            highlightbackground="#3a3a6a",
        )

        buttons = [
            ("🎮  Mode Solo", self._start_solo),
            ("👥  Multijoueur (2 joueurs)", self._start_multi),
            ("🏆  Classement", self._show_leaderboard),
            ("⚙   Paramètres", self._show_settings),
            ("❌  Quitter", self.root.destroy),
        ]

        for text, cmd in buttons:
            b = tk.Button(f, text=text, command=cmd, **btn_style)
            b.pack(pady=4)
            b.bind("<Enter>", lambda e, b=b: b.config(bg="#2a2a5a", fg=ACCENT))
            b.bind("<Leave>", lambda e, b=b: b.config(bg="#1e1e40", fg=TEXT_COLOR))

        # ── Info ligne ────────────────────────────────────────
        tk.Frame(f, height=10, bg=PANEL_BG).pack()
        diff = self.settings.difficulty
        preset = self.settings.difficulty_preset
        make_label(f, f"Difficulté : {diff}  —  {preset['description']}",
                   size=9, color=DIM_TEXT).pack()

        sk = self.settings.data["solo_keys"]
        keys_txt = (f"{key_display(sk['move_left'])} {key_display(sk['move_right'])} "
                    f"{key_display(sk['rotate_cw'])} {key_display(sk['soft_drop'])} "
                    f"  Drop={key_display(sk['hard_drop'])}  "
                    f"Pause={key_display(sk['pause'])}  Hold={key_display(sk['hold'])}")
        make_label(f, f"Solo : {keys_txt}", size=8, color=DIM_TEXT).pack()

        p1k = self.settings.data["multi_p1_keys"]
        p2k = self.settings.data["multi_p2_keys"]
        m_txt = (f"J1: {key_display(p1k['move_left'])}{key_display(p1k['move_right'])}"
                 f"{key_display(p1k['rotate_cw'])}{key_display(p1k['soft_drop'])}"
                 f"+{key_display(p1k['hard_drop'])}  |  "
                 f"J2: {key_display(p2k['move_left'])}{key_display(p2k['move_right'])}"
                 f"{key_display(p2k['rotate_cw'])}{key_display(p2k['soft_drop'])}"
                 f"+{key_display(p2k['hard_drop'])}")
        make_label(f, f"Multi : {m_txt}", size=8, color=DIM_TEXT).pack()

    def _on_canvas_resize(self, event):
        """Recentre le menu quand la fenêtre change de taille."""
        cx = event.width // 2
        cy = event.height // 2
        self.menu_canvas.coords(self._menu_window_id, cx, cy)

    # ── Animation du menu ─────────────────────────────────────
    def _menu_tick(self):
        if not self._menu_active:
            return

        now = time.monotonic()
        dt = now - self._last_time
        self._last_time = now

        cw = max(MENU_W, self.menu_canvas.winfo_width())
        ch = max(MENU_H, self.menu_canvas.winfo_height())

        # Spawner de nouvelles pièces
        if len(self._pieces) < 18 and random.random() < 0.04:
            self._pieces.append(FloatingPiece(cw, ch))

        # Spawner des particules
        if len(self._sparkles) < 25 and random.random() < 0.08:
            self._sparkles.append(Sparkle(cw, ch))

        c = self.menu_canvas

        # Update pièces (les objets des pièces sorties sont supprimés)
        alive = []
        for p in self._pieces:
            p.update()
            if p.is_off_screen():
                p.remove(c)
            else:
                alive.append(p)
        self._pieces = alive

        # Update particules
        alive = []
        for sp in self._sparkles:
            sp.update(dt)
            if sp.is_dead():
                sp.remove(c)
            else:
                alive.append(sp)
        self._sparkles = alive

        # ── Dessiner ──────────────────────────────────────────
        # Grille de fond très subtile : seulement si la taille a changé
        if self._grid_size != (cw, ch):
            self._grid_size = (cw, ch)
            c.delete("bg_grid")
            grid_color = "#12122a"
            for x in range(0, cw, BG_CELL * 2):
                c.create_line(x, 0, x, ch, fill=grid_color, tags="bg_grid")
            for y in range(0, ch, BG_CELL * 2):
                c.create_line(0, y, cw, y, fill=grid_color, tags="bg_grid")
            c.tag_lower("bg_grid")

        # Déplacer pièces flottantes et particules (pas de recréation)
        for p in self._pieces:
            p.draw(c)
        for sp in self._sparkles:
            sp.draw(c)

        # Menu toujours au-dessus
        c.tag_raise(self._menu_window_id)

        # ── Titre arc-en-ciel ─────────────────────────────────
        if hasattr(self, '_title_label') and self._title_label.winfo_exists():
            idx = int(now * 2) % len(self._title_colors)
            self._title_label.config(fg=self._title_colors[idx])

        self._anim_id = self.root.after(33, self._menu_tick)  # ~30 FPS

    def _stop_menu_anim(self):
        self._menu_active = False
        if self._anim_id:
            self.root.after_cancel(self._anim_id)
            self._anim_id = None

    # ══════════════════════════════════════════════════════════
    #  NAVIGATION
    # ══════════════════════════════════════════════════════════

    def _ask_name(self, prompt: str = "Entrez votre nom :") -> str:
        name = simpledialog.askstring("Joueur", prompt, parent=self.root)
        return name.strip() if name and name.strip() else "Joueur"

    def _start_solo(self):
        name = self._ask_name("Votre nom (Mode Solo) :")
        self._clear()
        from game_solo import SoloGame
        SoloGame(self.root, name, self.leaderboard, self.settings,
                 on_quit=self._show_menu)

    def _start_multi(self):
        name1 = self._ask_name("Joueur 1 — Entrez votre nom :")
        name2 = self._ask_name("Joueur 2 — Entrez votre nom :")
        self._clear()
        from game_multi import MultiplayerGame
        MultiplayerGame(self.root, name1, name2, self.settings,
                        on_quit=self._show_menu)

    def _show_settings(self):
        self._clear()
        from settings_screen import SettingsScreen
        SettingsScreen(self.root, self.settings, on_back=self._show_menu)

    def _show_leaderboard(self):
        self._clear()
        frame = tk.Frame(self.root, bg=PANEL_BG)
        frame.pack(padx=30, pady=20)

        make_label(frame, "🏆  CLASSEMENT DES MEILLEURS SCORES", size=14,
                   bold=True, color=ACCENT).pack(pady=(0, 14))

        header_frame = tk.Frame(frame, bg="#1e1e40")
        header_frame.pack(fill=tk.X)
        headers = [("Rang", 6), ("Joueur", 14), ("Score", 10),
                   ("Lignes", 8), ("Niveau", 8), ("Date", 16)]
        for text, w in headers:
            tk.Label(header_frame, text=text, font=("Consolas", 10, "bold"),
                     fg=ACCENT2, bg="#1e1e40", width=w, anchor="w"
                     ).pack(side=tk.LEFT, padx=2)

        tk.Frame(frame, height=2, bg=ACCENT).pack(fill=tk.X, pady=2)

        if not self.leaderboard.scores:
            make_label(frame, "Aucun score enregistré", size=11,
                       color=DIM_TEXT).pack(pady=20)
        else:
            rank_colors = [ACCENT, "#ffd700", "#c0c0c0", "#cd7f32"]
            for i, entry in enumerate(self.leaderboard.scores):
                row_bg = "#1a1a30" if i % 2 == 0 else "#1e1e3a"
                row = tk.Frame(frame, bg=row_bg)
                row.pack(fill=tk.X)
                color = rank_colors[i] if i < len(rank_colors) else TEXT_COLOR
                vals = [
                    (f"#{i+1}", 6),
                    (entry["name"][:12], 14),
                    (str(entry["score"]), 10),
                    (str(entry["lines"]), 8),
                    (str(entry["level"]), 8),
                    (entry["date"], 16),
                ]
                for text, w in vals:
                    tk.Label(row, text=text, font=("Consolas", 10),
                             fg=color, bg=row_bg, width=w, anchor="w"
                             ).pack(side=tk.LEFT, padx=2)

        tk.Frame(frame, height=16, bg=PANEL_BG).pack()
        tk.Button(frame, text="← Retour au menu", command=self._show_menu,
                  font=("Consolas", 11), fg=TEXT_COLOR, bg="#1e1e40",
                  activeforeground=ACCENT, activebackground="#2a2a5a",
                  relief="flat", cursor="hand2", padx=16, pady=6).pack()

    # ── Lancer ────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════
#  Intégration système (icône, journal d'erreurs)
# ══════════════════════════════════════════════════════════════

def _set_window_icon(root: tk.Tk):
    """Icône de fenêtre / barre des tâches (aussi appliquée aux dialogues)."""
    try:
        if sys.platform == "win32":
            # Sans cet identifiant, Windows regroupe la fenêtre sous l'icône
            # de python.exe dans la barre des tâches (en mode développement).
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
            root.iconbitmap(default=asset("icon.ico"))
        else:
            root._icon_img = tk.PhotoImage(file=asset("icon.png"))
            root.iconphoto(True, root._icon_img)
    except Exception:
        pass            # une icône manquante ne doit jamais empêcher de jouer


def _log_crash(text: str) -> str:
    path = os.path.join(user_data_dir(), "crash.log")
    try:
        from datetime import datetime
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}  v{__version__} ---\n{text}\n")
    except OSError:
        pass
    if sys.stderr:                       # None dans un .exe sans console
        sys.stderr.write(text)
    return path


def install_crash_handler(root: tk.Tk):
    """Dans un .exe sans console, une exception serait invisible : le jeu
    semblerait juste figé. On l'écrit dans crash.log et on prévient le joueur
    (une seule fois, pour ne pas empiler les fenêtres d'erreur)."""
    import traceback
    from tkinter import messagebox
    shown = []

    def report(exc, val, tb):
        path = _log_crash("".join(traceback.format_exception(exc, val, tb)))
        if not shown:
            shown.append(True)
            messagebox.showerror(f"{APP_NAME} — erreur",
                                 f"Une erreur inattendue est survenue.\n\n"
                                 f"Détails enregistrés dans :\n{path}")

    root.report_callback_exception = report


def main():
    try:
        App().run()
    except Exception:
        import traceback
        _log_crash(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
