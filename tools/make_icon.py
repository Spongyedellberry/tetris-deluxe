#!/usr/bin/env python3
"""
tools/make_icon.py — Génère l'icône du jeu (assets/icon.ico + assets/icon.png).

Une pièce T dans le style biseauté du jeu, sur fond sombre arrondi.
Dessinée en 1024 px puis réduite (anti-crénelage) pour chaque taille ICO.

Nécessite Pillow (requirements-dev.txt). Usage : python tools/make_icon.py
"""

import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from constants import PIECE_COLORS, PIECE_COLORS_LIGHT, PANEL_BG, BORDER_COLOR  # noqa: E402

S = 1024                                   # taille de travail
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _shade(rgb, f: float):
    return tuple(max(0, min(255, int(v * f))) for v in rgb)


def draw_block(d: ImageDraw.ImageDraw, x: int, y: int, size: int, color_idx: int):
    base = _hex(PIECE_COLORS[color_idx])
    light = _hex(PIECE_COLORS_LIGHT[color_idx])
    dark = _shade(base, 0.62)
    edge = max(4, size // 7)               # épaisseur du biseau
    # Corps + contour sombre
    d.rectangle([x, y, x + size - 1, y + size - 1], fill=_shade(base, 0.55))
    d.rectangle([x + 3, y + 3, x + size - 4, y + size - 4], fill=base)
    # Biseau : haut/gauche clairs, bas/droite sombres (trapèzes)
    x2, y2 = x + size - 4, y + size - 4
    x1, y1 = x + 3, y + 3
    d.polygon([(x1, y1), (x2, y1), (x2 - edge, y1 + edge), (x1 + edge, y1 + edge)], fill=light)
    d.polygon([(x1, y1), (x1 + edge, y1 + edge), (x1 + edge, y2 - edge), (x1, y2)], fill=light)
    d.polygon([(x2, y1), (x2, y2), (x2 - edge, y2 - edge), (x2 - edge, y1 + edge)], fill=dark)
    d.polygon([(x1, y2), (x1 + edge, y2 - edge), (x2 - edge, y2 - edge), (x2, y2)], fill=dark)


def make_icon() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Fond arrondi
    pad = S // 32
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=S // 5,
                        fill=_hex(PANEL_BG), outline=_hex(BORDER_COLOR), width=S // 40)
    # Pièce T centrée (3 × 2 blocs)
    b = int(S * 0.25)
    ox = (S - 3 * b) // 2
    oy = (S - 2 * b) // 2 + b // 12
    for cx, cy in [(1, 0), (0, 1), (1, 1), (2, 1)]:
        draw_block(d, ox + cx * b, oy + cy * b, b, 3)
    return img


def main():
    out_dir = os.path.join(ROOT, "assets")
    os.makedirs(out_dir, exist_ok=True)
    img = make_icon()
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(out_dir, "icon.png"))
    img.save(os.path.join(out_dir, "icon.ico"), sizes=[(s, s) for s in ICO_SIZES])
    print("assets/icon.ico et assets/icon.png générés")


if __name__ == "__main__":
    main()
