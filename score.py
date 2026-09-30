"""
score.py — Système de score avec combos et gestion de la vitesse.
"""

import time
from constants import BASE_FALL_SPEED, MIN_FALL_SPEED


class ScoreSystem:
    """Système de points avec combo et T-Spin : (Lignes * 10) * Multiplicateur * Combo."""

    def __init__(self):
        self.score = 0
        self.level = 1
        self.total_lines = 0
        self.combo = 0
        self.max_combo = 0
        self.last_combo_time = 0.0
        self.last_combo_value = 0

        # Statistiques détaillées
        self.singles = 0
        self.doubles = 0
        self.triples = 0
        self.tetrises = 0
        self.pieces_placed = 0
        self.total_combos = 0
        self.game_start_time = time.monotonic()
        self.game_end_time = None

        # T-Spin stats
        self.tspins = 0
        self.tspin_singles = 0
        self.tspin_doubles = 0
        self.tspin_triples = 0
        self.last_tspin_time = 0.0
        self.last_tspin_type = ""   # "T-SPIN", "T-SPIN SINGLE", etc.

    def update_score(self, lines: int, is_tspin: bool = False) -> int:
        """Met à jour le score. Retourne les points bonus du combo."""
        from constants import TSPIN_POINTS

        combo_bonus = 0

        # ── T-Spin bonus ──────────────────────────────────
        if is_tspin:
            tspin_pts = TSPIN_POINTS.get(lines, 0)
            self.score += tspin_pts
            self.tspins += 1
            self.last_tspin_time = time.monotonic()

            if lines == 0:
                self.last_tspin_type = "T-SPIN"
            elif lines == 1:
                self.tspin_singles += 1
                self.last_tspin_type = "T-SPIN SINGLE"
            elif lines == 2:
                self.tspin_doubles += 1
                self.last_tspin_type = "T-SPIN DOUBLE"
            elif lines >= 3:
                self.tspin_triples += 1
                self.last_tspin_type = "T-SPIN TRIPLE"

        # ── Score normal des lignes ───────────────────────
        if lines > 0:
            self.combo += 1
            base_points = (lines * 10) * lines

            if lines == 1:
                self.singles += 1
            elif lines == 2:
                self.doubles += 1
            elif lines == 3:
                self.triples += 1
            elif lines >= 4:
                self.tetrises += 1

            if self.combo > 1:
                multiplier = 1 + (self.combo - 1) * 0.5
                combo_bonus = int(base_points * multiplier) - base_points
                self.score += int(base_points * multiplier)
                self.total_combos += 1
            else:
                self.score += base_points

            self.total_lines += lines
            self.level = (self.total_lines // 10) + 1

            if self.combo > 1:
                self.last_combo_time = time.monotonic()
                self.last_combo_value = self.combo
            if self.combo > self.max_combo:
                self.max_combo = self.combo
        else:
            self.combo = 0
        return combo_bonus

    def get_game_duration(self) -> float:
        end = self.game_end_time if self.game_end_time else time.monotonic()
        return end - self.game_start_time

    def freeze_time(self):
        self.game_end_time = time.monotonic()

    def get_pieces_per_minute(self) -> float:
        d = self.get_game_duration()
        return (self.pieces_placed / d) * 60 if d > 0 else 0.0

    def reset(self):
        self.__init__()


class SpeedManager:
    """Gère la vitesse de chute basée sur le score et le niveau."""

    def __init__(self, base: float = BASE_FALL_SPEED, minimum: float = MIN_FALL_SPEED,
                 level_factor: float = 0.05, score_factor: float = 0.02):
        self.base = base
        self.minimum = minimum
        self.level_factor = level_factor
        self.score_factor = score_factor

    def fall_speed(self, score: int, level: int) -> float:
        reduction = (level - 1) * self.level_factor + (score // 500) * self.score_factor
        return max(self.minimum, self.base - reduction)
