"""
pieces.py — Gestion des pièces (Tetrominos) avec système 7-Bag.
"""

import random
from constants import SHAPES


class PieceBag:
    """Sac 7-Bag individuel pour distribution équitable des pièces."""

    def __init__(self):
        self._bag: list[int] = []

    def _refill(self):
        self._bag = list(range(len(SHAPES)))
        random.shuffle(self._bag)

    def next_index(self) -> int:
        if not self._bag:
            self._refill()
        return self._bag.pop()

    def reset(self):
        self._bag = []


class Piece:
    """Représente une pièce en jeu (forme, position, couleur)."""

    def __init__(self, grid_width: int, bag: PieceBag):
        idx = bag.next_index()
        shape_data = SHAPES[idx]
        self.shape: list[list[int]] = [row[:] for row in shape_data[0]]
        self.color: int = shape_data[1]
        self.x: int = grid_width // 2 - len(self.shape[0]) // 2
        self.y: int = 0

    def rotate_cw(self):
        """Rotation 90° sens horaire."""
        self.shape = [list(row) for row in zip(*self.shape[::-1])]

    def rotate_ccw(self):
        """Rotation 90° sens anti-horaire."""
        for _ in range(3):
            self.rotate_cw()

    @property
    def width(self) -> int:
        return len(self.shape[0]) if self.shape else 0

    @property
    def height(self) -> int:
        return len(self.shape)

    def cells(self) -> list[tuple[int, int]]:
        """Retourne la liste des coordonnées absolues (col, row) des blocs."""
        result = []
        for ry, row in enumerate(self.shape):
            for rx, cell in enumerate(row):
                if cell:
                    result.append((self.x + rx, self.y + ry))
        return result
