"""
board.py — Grille de jeu, gestion des lignes et détection T-Spin.
"""

import random
from constants import COLS, ROWS, T_PIECE_COLOR


def detect_tspin(board, piece, last_was_rotate: bool) -> bool:
    """Détecte si le verrouillage actuel est un T-Spin.

    Règles (3-corner rule) :
      1. La pièce est un T (color == T_PIECE_COLOR)
      2. La dernière action avant le lock était une rotation
      3. Au moins 3 des 4 coins diagonaux autour du centre du T
         sont occupés (bloc ou mur/sol)
    """
    if not last_was_rotate:
        return False
    if piece.color != T_PIECE_COLOR:
        return False

    # Trouver le centre du T dans la matrice de la pièce.
    # Le centre est la cellule pleine qui a le plus de voisins pleins
    # (toujours 3 pour le T).
    cx, cy = _find_t_center(piece)
    if cx is None:
        return False

    # Coordonnées absolues du centre
    abs_cx = piece.x + cx
    abs_cy = piece.y + cy

    # Vérifier les 4 coins diagonaux
    corners = [
        (abs_cx - 1, abs_cy - 1),
        (abs_cx + 1, abs_cy - 1),
        (abs_cx - 1, abs_cy + 1),
        (abs_cx + 1, abs_cy + 1),
    ]

    filled = 0
    for x, y in corners:
        if _is_occupied(board, x, y):
            filled += 1

    return filled >= 3


def _find_t_center(piece) -> tuple:
    """Trouve la cellule centrale du T (celle avec 3 voisins orthogonaux)."""
    shape = piece.shape
    rows = len(shape)
    cols = len(shape[0]) if rows > 0 else 0

    best = (None, None)
    best_count = -1

    for ry in range(rows):
        for rx in range(cols):
            if not shape[ry][rx]:
                continue
            # Compter les voisins orthogonaux pleins dans la matrice
            count = 0
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = rx + dx, ry + dy
                if 0 <= nx < cols and 0 <= ny < rows and shape[ny][nx]:
                    count += 1
            if count > best_count:
                best_count = count
                best = (rx, ry)

    return best


def _is_occupied(board, x: int, y: int) -> bool:
    """Vérifie si une position est occupée (bloc, mur, ou sol)."""
    if x < 0 or x >= board.width:
        return True   # Mur
    if y >= board.height:
        return True   # Sol
    if y < 0:
        return False  # Au-dessus de la grille = vide
    return board.grid[y][x] != 0


class Board:
    """Grille de jeu Tetris."""

    def __init__(self, width: int = COLS, height: int = ROWS):
        self.width = width
        self.height = height
        self.grid: list[list[int]] = [[0] * width for _ in range(height)]

    def is_collision(self, piece, dx: int = 0, dy: int = 0) -> bool:
        """Vérifie collision avec bords et blocs existants."""
        for ry, row in enumerate(piece.shape):
            for rx, cell in enumerate(row):
                if cell:
                    nx = piece.x + rx + dx
                    ny = piece.y + ry + dy
                    if nx < 0 or nx >= self.width or ny >= self.height:
                        return True
                    if ny >= 0 and self.grid[ny][nx] != 0:
                        return True
        return False

    def lock_piece(self, piece):
        """Verrouille une pièce sur la grille."""
        for ry, row in enumerate(piece.shape):
            for rx, cell in enumerate(row):
                if cell:
                    py = piece.y + ry
                    px = piece.x + rx
                    if 0 <= py < self.height and 0 <= px < self.width:
                        self.grid[py][px] = piece.color

    def add_garbage_lines(self, num_lines: int):
        """Ajoute des lignes garbage en bas de la grille."""
        if num_lines <= 0:
            return
        for _ in range(num_lines):
            self.grid.pop(0)
        for _ in range(num_lines):
            line = [7] * self.width  # couleur garbage
            gap = random.randint(0, self.width - 1)
            line[gap] = 0
            self.grid.append(line)

    def is_game_over(self) -> bool:
        """Vérifie si des blocs sont présents dans la première ligne."""
        return any(cell != 0 for cell in self.grid[0])

    def reset(self):
        self.grid = [[0] * self.width for _ in range(self.height)]


class LineManager:
    """Détection et suppression des lignes complètes."""

    @staticmethod
    def find_full_lines(board: Board) -> list[int]:
        return [y for y in range(board.height)
                if all(cell != 0 for cell in board.grid[y])]

    @staticmethod
    def remove_lines(board: Board, indices: list[int]) -> int:
        if not indices:
            return 0
        new_grid = [row for y, row in enumerate(board.grid) if y not in indices]
        cleared = board.height - len(new_grid)
        for _ in range(cleared):
            new_grid.insert(0, [0] * board.width)
        board.grid = new_grid
        return cleared

    @staticmethod
    def clear_lines(board: Board) -> int:
        full = LineManager.find_full_lines(board)
        return LineManager.remove_lines(board, full)
