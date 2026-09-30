"""
renderer.py — Rendu optimisé de la grille (objets canvas persistants + diff).

Ancienne approche (« immediate mode ») :
    à chaque frame : canvas.delete("all") puis recréer ~500 objets Tk
    → ~30 000 créations d'objets par seconde à 60 FPS.

Nouvelle approche (« retained mode ») :
    * les lignes de grille et les objets de chaque cellule sont créés UNE fois ;
    * à chaque frame on calcule l'état voulu des 200 cellules (une clé par
      cellule) et on ne reconfigure QUE les cellules qui ont changé.
    → en jeu typique : 0 à ~16 cellules modifiées par frame.

Clés de style d'une cellule :
    None             cellule vide
    ("n", color)     bloc normal biseauté (color = index PIECE_COLORS)
    ("g",)           fantôme (ghost piece)
    ("x",)           bloc gris (animation game over)
    ("f", phase)     flash de suppression de ligne (phase 0..2)
"""

from functools import lru_cache
import tkinter as tk

from constants import COLS, ROWS, CELL, PIECE_COLORS, PIECE_COLORS_LIGHT, GHOST_COLOR, BG, ACCENT
from ui_components import draw_grid_lines, darken, lighten

# Index des objets d'une cellule
_RECT, _TOP, _LEFT, _RIGHT, _BOTTOM, _INNER_DASH, _INNER = range(7)
_N_SLOTS = 7

FLASH_COLORS = ("#ffffff", ACCENT, "#ffe066")


@lru_cache(maxsize=None)
def _style(key) -> tuple:
    """Configuration Tk de chaque objet pour une clé donnée.

    Retourne un tuple de 7 éléments : dict d'options (objet visible)
    ou None (objet caché). Mis en cache : calculé une seule fois par clé.
    """
    slots = [None] * _N_SLOTS
    kind = key[0]
    if kind == "n":
        color = PIECE_COLORS.get(key[1], BG)
        light = PIECE_COLORS_LIGHT.get(key[1], lighten(color, 0.3))
        dark = darken(color, 0.3)
        slots[_RECT] = {"fill": color, "outline": darken(color, 0.4)}
        slots[_TOP] = slots[_LEFT] = {"fill": light}
        slots[_RIGHT] = slots[_BOTTOM] = {"fill": dark}
    elif kind == "g":
        slots[_RECT] = {"fill": GHOST_COLOR, "outline": GHOST_COLOR}
        slots[_INNER_DASH] = {"outline": "#505070"}
    elif kind == "x":
        slots[_RECT] = {"fill": "#3a3a4a", "outline": "#2a2a3a"}
        slots[_INNER] = {"outline": "#4a4a5a"}
    elif kind == "f":
        color = FLASH_COLORS[key[1] % 3]
        slots[_RECT] = {"fill": color, "outline": darken(color, 0.2)}
    return tuple(slots)


class BoardRenderer:
    """Dessine une grille Tetris sur un canvas en ne mettant à jour que le nécessaire."""

    def __init__(self, canvas: tk.Canvas, cols: int = COLS, rows: int = ROWS,
                 cell_size: int = CELL):
        self.canvas = canvas
        self.cols = cols
        self.rows = rows
        self.cs = cell_size
        self._state: list = [None] * (cols * rows)
        self._visible: list[list[bool]] = []
        self._items: list[tuple[int, ...]] = []
        self._static_overlay_key = None
        self._build()

    # ── Construction (une seule fois) ─────────────────────────
    def _build(self):
        c = self.canvas
        c.delete("all")
        draw_grid_lines(c, self.cols, self.rows, cell_size=self.cs)
        cs = self.cs
        m = max(2, cs // 10)          # marge du biseau (identique à draw_cell)
        mi = 3                        # marge du contour intérieur
        hidden = "hidden"
        for row in range(self.rows):
            for col in range(self.cols):
                x1, y1 = col * cs, row * cs
                x2, y2 = x1 + cs, y1 + cs
                items = (
                    c.create_rectangle(x1, y1, x2, y2, width=1, state=hidden),
                    c.create_line(x1 + m, y1 + m, x2 - m, y1 + m, width=1, state=hidden),
                    c.create_line(x1 + m, y1 + m, x1 + m, y2 - m, width=1, state=hidden),
                    c.create_line(x2 - m, y1 + m, x2 - m, y2 - m, width=1, state=hidden),
                    c.create_line(x1 + m, y2 - m, x2 - m, y2 - m, width=1, state=hidden),
                    c.create_rectangle(x1 + mi, y1 + mi, x2 - mi, y2 - mi, fill="",
                                       width=1, dash=(2, 2), state=hidden),
                    c.create_rectangle(x1 + mi, y1 + mi, x2 - mi, y2 - mi, fill="",
                                       width=1, state=hidden),
                )
                self._items.append(items)
                self._visible.append([False] * _N_SLOTS)

    # ── API ───────────────────────────────────────────────────
    def empty_frame(self) -> list:
        """Liste de clés « toutes vides » à remplir par l'appelant."""
        return [None] * (self.cols * self.rows)

    def frame_from_grid(self, grid) -> list:
        """Crée une frame à partir de la grille figée du plateau."""
        return [("n", v) if v else None for row in grid for v in row]

    def put(self, frame: list, col: int, row: int, key):
        """Place une clé dans la frame (ignore les cases hors grille)."""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            frame[row * self.cols + col] = key

    def render(self, frame: list) -> int:
        """Applique la frame. Retourne le nombre de cellules modifiées."""
        state = self._state
        changed = 0
        for i, key in enumerate(frame):
            if key != state[i]:
                self._apply(i, key)
                state[i] = key
                changed += 1
        return changed

    def static_overlay(self, key, draw_fn=None):
        """Overlay qui ne change pas d'une frame à l'autre (PAUSE, GAME OVER…).

        Redessiné uniquement quand `key` change. `draw_fn(canvas, tag)` doit
        créer ses objets avec tags=tag. key=None efface l'overlay.
        """
        if key == self._static_overlay_key:
            return
        self.canvas.delete("static_overlay")
        self._static_overlay_key = key
        if key is not None and draw_fn is not None:
            draw_fn(self.canvas, "static_overlay")
        self.canvas.tag_raise("static_overlay")

    def invalidate(self):
        """Force un redessin complet à la prochaine frame."""
        self._state = [object()] * (self.cols * self.rows)
        self._static_overlay_key = object()

    # ── Interne ───────────────────────────────────────────────
    def _apply(self, i: int, key):
        c = self.canvas
        items = self._items[i]
        visible = self._visible[i]
        slots = _style(key) if key is not None else (None,) * _N_SLOTS
        for s in range(_N_SLOTS):
            cfg = slots[s]
            if cfg is None:
                if visible[s]:
                    c.itemconfigure(items[s], state="hidden")
                    visible[s] = False
            else:
                c.itemconfigure(items[s], state="normal", **cfg)
                visible[s] = True
