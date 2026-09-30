"""
ui_components.py — Composants graphiques réutilisables pour tkinter.
"""

import tkinter as tk
from functools import lru_cache
from constants import (
    CELL, PIECE_COLORS, PIECE_COLORS_LIGHT, GHOST_COLOR,
    BG, GRID_LINE, PANEL_BG, BORDER_COLOR, TEXT_COLOR, ACCENT, DIM_TEXT,
    COLS, ROWS, PREVIEW_CELLS,
)


@lru_cache(maxsize=512)
def lighten(hex_color: str, amount: float = 0.3) -> str:
    """Éclaircit une couleur hex."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = min(255, int(r + (255 - r) * amount))
    g = min(255, int(g + (255 - g) * amount))
    b = min(255, int(b + (255 - b) * amount))
    return f"#{r:02x}{g:02x}{b:02x}"


@lru_cache(maxsize=512)
def darken(hex_color: str, amount: float = 0.3) -> str:
    """Assombrit une couleur hex."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = max(0, int(r * (1 - amount)))
    g = max(0, int(g * (1 - amount)))
    b = max(0, int(b * (1 - amount)))
    return f"#{r:02x}{g:02x}{b:02x}"


def draw_cell(canvas: tk.Canvas, col: float, row: float, color_idx: int,
              ghost: bool = False, cell_size: int = CELL):
    """Dessine une cellule avec effet biseauté."""
    if ghost:
        color = GHOST_COLOR
        outline = GHOST_COLOR
    else:
        color = PIECE_COLORS.get(color_idx, BG)
        outline = darken(color, 0.4)

    x1 = col * cell_size
    y1 = row * cell_size
    x2 = x1 + cell_size
    y2 = y1 + cell_size

    canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=outline, width=1)

    if not ghost:
        # Effet biseauté (bord lumineux)
        m = max(2, cell_size // 10)
        light = PIECE_COLORS_LIGHT.get(color_idx, lighten(color, 0.3))
        canvas.create_line(x1 + m, y1 + m, x2 - m, y1 + m, fill=light, width=1)
        canvas.create_line(x1 + m, y1 + m, x1 + m, y2 - m, fill=light, width=1)
        dark = darken(color, 0.3)
        canvas.create_line(x2 - m, y1 + m, x2 - m, y2 - m, fill=dark, width=1)
        canvas.create_line(x1 + m, y2 - m, x2 - m, y2 - m, fill=dark, width=1)
    else:
        # Ghost : juste un contour pointillé
        m = 3
        canvas.create_rectangle(x1 + m, y1 + m, x2 - m, y2 - m,
                                fill="", outline="#505070", width=1, dash=(2, 2))


def draw_grid_lines(canvas: tk.Canvas, cols: int, rows: int, cell_size: int = CELL):
    """Dessine les lignes de la grille."""
    w = cols * cell_size
    h = rows * cell_size
    for c in range(cols + 1):
        x = c * cell_size
        canvas.create_line(x, 0, x, h, fill=GRID_LINE, width=1)
    for r in range(rows + 1):
        y = r * cell_size
        canvas.create_line(0, y, w, y, fill=GRID_LINE, width=1)


def draw_preview_piece(canvas: tk.Canvas, shape: list, color_idx: int,
                       cell_size: int = None):
    """Dessine une pièce centrée dans un canvas d'aperçu.

    Ne redessine que si la pièce a changé (l'aperçu ne change qu'au spawn,
    inutile de le recréer 60 fois par seconde).
    """
    key = (tuple(map(tuple, shape)) if shape else None, color_idx, cell_size)
    if getattr(canvas, "_preview_key", None) == key:
        return
    canvas._preview_key = key

    canvas.delete("all")
    if not shape:
        return

    # Taille configurée (et non winfo_width, qui vaut 1 avant l'affichage)
    cw = int(canvas["width"])
    ch = int(canvas["height"])
    cs = cell_size or min(cw, ch) // PREVIEW_CELLS

    ph = len(shape)
    pw = len(shape[0]) if ph > 0 else 0
    ox = (cw - pw * cs) / 2
    oy = (ch - ph * cs) / 2

    for ry, row in enumerate(shape):
        for rx, cell in enumerate(row):
            if cell:
                x1 = ox + rx * cs
                y1 = oy + ry * cs
                color = PIECE_COLORS.get(color_idx, "#fff")
                light = PIECE_COLORS_LIGHT.get(color_idx, lighten(color))
                canvas.create_rectangle(x1, y1, x1 + cs, y1 + cs,
                                        fill=color, outline=darken(color, 0.4))
                m = max(2, cs // 10)
                canvas.create_line(x1 + m, y1 + m, x1 + cs - m, y1 + m,
                                   fill=light, width=1)
                canvas.create_line(x1 + m, y1 + m, x1 + m, y1 + cs - m,
                                   fill=light, width=1)


def clear_preview(canvas: tk.Canvas):
    """Vide un canvas d'aperçu (une seule fois)."""
    if getattr(canvas, "_preview_key", None) is not None or \
            not hasattr(canvas, "_preview_key"):
        canvas.delete("all")
        canvas._preview_key = None


class Cached:
    """Enveloppe un appel Tk (StringVar.set, widget.config…) et ne le
    transmet que si les arguments ont changé depuis le dernier appel.

        set_score = Cached(score_var.set)
        set_score("1,200")   # appel Tk
        set_score("1,200")   # ignoré
    """

    __slots__ = ("_fn", "_last")

    def __init__(self, fn):
        self._fn = fn
        self._last = None

    def __call__(self, *args, **kw):
        key = (args, tuple(sorted(kw.items())))
        if key != self._last:
            self._last = key
            self._fn(*args, **kw)


class KeyBindings:
    """Liaisons clavier sur la fenêtre principale, libérables proprement.

    Piège tkinter : root.bind() enregistre le callback Python comme commande
    Tcl. root.unbind(seq) SANS funcid retire la liaison mais laisse la
    commande (et donc le callback, et tout l'objet jeu qu'il référence)
    en mémoire → fuite à chaque partie. On garde donc chaque funcid.
    """

    def __init__(self, widget):
        self.widget = widget
        self._ids: list[tuple[str, str]] = []

    def bind(self, key: str, callback):
        """Lie `key` (et sa majuscule pour une lettre seule)."""
        keys = [key]
        if len(key) == 1 and key.isalpha():
            keys.append(key.upper())
        for k in keys:
            self._ids.append((k, self.widget.bind(k, callback)))

    def release(self):
        """Retire toutes les liaisons ET libère les commandes Tcl."""
        for seq, funcid in self._ids:
            try:
                self.widget.unbind(seq, funcid)
            except tk.TclError:
                pass
        self._ids.clear()


def make_board_canvas(parent: tk.Frame, cols: int = COLS, rows: int = ROWS,
                      cell_size: int = CELL) -> tk.Canvas:
    """Crée un canvas de grille de jeu."""
    return tk.Canvas(parent,
                     width=cols * cell_size,
                     height=rows * cell_size,
                     bg=BG, highlightthickness=2,
                     highlightbackground=BORDER_COLOR)


def make_preview_canvas(parent: tk.Frame, size: int = PREVIEW_CELLS,
                        cell_size: int = None) -> tk.Canvas:
    """Crée un petit canvas pour l'aperçu d'une pièce."""
    cs = cell_size or CELL
    dim = size * cs
    return tk.Canvas(parent, width=dim, height=dim, bg=BG,
                     highlightthickness=1, highlightbackground=BORDER_COLOR)


def make_label(parent: tk.Frame, text: str, size: int = 10,
               color: str = TEXT_COLOR, bold: bool = False, **kw) -> tk.Label:
    """Crée un label stylisé."""
    weight = "bold" if bold else "normal"
    return tk.Label(parent, text=text, font=("Consolas", size, weight),
                    fg=color, bg=PANEL_BG, **kw)


def make_value_label(parent: tk.Frame, textvariable: tk.StringVar,
                     size: int = 16, color: str = TEXT_COLOR) -> tk.Label:
    """Crée un label de valeur dynamique."""
    return tk.Label(parent, textvariable=textvariable,
                    font=("Consolas", size, "bold"),
                    fg=color, bg=PANEL_BG)


def center_message(canvas: tk.Canvas, text: str, sub: str = None,
                   color: str = ACCENT, tags: str = None):
    """Affiche un message centré sur le canvas."""
    w = int(canvas["width"])
    h = int(canvas["height"])
    # Boîte de fond
    bw, bh = 180, 60 if sub else 44
    canvas.create_rectangle(w // 2 - bw, h // 2 - bh,
                            w // 2 + bw, h // 2 + bh,
                            fill=PANEL_BG, outline=color, width=2, tags=tags)
    canvas.create_text(w // 2, h // 2 - (12 if sub else 0),
                       text=text, fill=color,
                       font=("Consolas", 22, "bold"), tags=tags)
    if sub:
        canvas.create_text(w // 2, h // 2 + 20,
                           text=sub, fill=DIM_TEXT,
                           font=("Consolas", 11), tags=tags)
