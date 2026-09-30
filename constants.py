"""
constants.py — Constantes du jeu Tetris (dimensions, couleurs, formes).
"""

# ─── Dimensions de la grille ──────────────────────────────────
COLS = 10
ROWS = 20
CELL = 30                        # taille d'une cellule en pixels
PREVIEW_CELLS = 5                # taille grille aperçu

# ─── Vitesse / Timing ────────────────────────────────────────
TICK_MS = 16                     # ~60 FPS
LOCK_DELAY_MS = 500
BASE_FALL_SPEED = 0.5            # secondes
MIN_FALL_SPEED = 0.05

# ─── Couleurs ─────────────────────────────────────────────────
BG           = "#0f0f1a"
GRID_LINE    = "#1e1e3a"
PANEL_BG     = "#151530"
BORDER_COLOR = "#2a2a5a"
TEXT_COLOR    = "#d0d0e0"
ACCENT       = "#e94560"
ACCENT2      = "#0ea5e9"
DIM_TEXT     = "#606080"
GHOST_COLOR  = "#303050"

# Index couleur → couleur hex (correspondance avec les indices curses)
# 0 = vide, 1-7 = pièces
PIECE_COLORS = {
    0: BG,
    1: "#00e5ff",   # I - Cyan
    2: "#ffe600",   # O - Jaune
    3: "#d500f9",   # T - Magenta
    4: "#00e676",   # S - Vert
    5: "#ff1744",   # Z - Rouge
    6: "#2979ff",   # J - Bleu
    7: "#ff9100",   # L - Orange
}

PIECE_COLORS_LIGHT = {
    1: "#66f0ff",
    2: "#fff176",
    3: "#ea80fc",
    4: "#69f0ae",
    5: "#ff5252",
    6: "#82b1ff",
    7: "#ffb74d",
}

GARBAGE_COLOR = "#555577"

# ─── Définition des formes (mêmes matrices que la version curses) ─
SHAPES = [
    ([[1, 1, 1, 1]], 1),         # I
    ([[1, 1], [1, 1]], 2),       # O
    ([[0, 1, 0], [1, 1, 1]], 3), # T
    ([[0, 1, 1], [1, 1, 0]], 4), # S
    ([[1, 1, 0], [0, 1, 1]], 5), # Z
    ([[1, 0, 0], [1, 1, 1]], 6), # J
    ([[0, 0, 1], [1, 1, 1]], 7), # L
]

# ─── Noms des pièces pour l'affichage ────────────────────────
PIECE_NAMES = {1: "I", 2: "O", 3: "T", 4: "S", 5: "Z", 6: "J", 7: "L"}

# ─── Wall Kick offsets ────────────────────────────────────────
WALL_KICK_OFFSETS = [
    (0, 0), (-1, 0), (1, 0), (0, -1), (-1, -1), (1, -1), (-2, 0), (2, 0),
]

# ─── Scoring ──────────────────────────────────────────────────
GARBAGE_TABLE = {1: 0, 2: 1, 3: 2, 4: 4}

# T-Spin bonus points (ajoutés au score normal des lignes)
TSPIN_POINTS = {
    0: 400,     # T-Spin Zero (pas de ligne)
    1: 800,     # T-Spin Single
    2: 1200,    # T-Spin Double
    3: 1600,    # T-Spin Triple
}

# Garbage envoyé pour T-Spin en multi (remplace GARBAGE_TABLE)
TSPIN_GARBAGE = {
    0: 0,       # T-Spin Zero
    1: 2,       # T-Spin Single
    2: 4,       # T-Spin Double
    3: 6,       # T-Spin Triple
}

# Index couleur de la pièce T
T_PIECE_COLOR = 3
