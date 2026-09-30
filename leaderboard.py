"""
leaderboard.py — Classement des meilleurs scores (persistance JSON).
"""

import json
import os
from datetime import datetime

from paths import user_data_dir

SCORES_FILE = "tetris_scores.json"


class Leaderboard:
    """Gère le classement des meilleurs scores."""

    def __init__(self, filename: str | None = None, max_entries: int = 10):
        # Chemin absolu : indépendant du dossier depuis lequel le jeu est lancé
        self.filename = filename or os.path.join(user_data_dir(), SCORES_FILE)
        self.max_entries = max_entries
        self.scores: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.scores, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def add_score(self, name: str, score: int, lines: int, level: int):
        entry = {
            "name": name,
            "score": score,
            "lines": lines,
            "level": level,
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        self.scores.append(entry)
        self.scores.sort(key=lambda x: x["score"], reverse=True)
        self.scores = self.scores[: self.max_entries]
        self._save()

    def is_high_score(self, score: int) -> bool:
        if len(self.scores) < self.max_entries:
            return True
        return score > self.scores[-1]["score"]

    def get_rank(self, score: int) -> int:
        for i, entry in enumerate(self.scores):
            if score >= entry["score"]:
                return i + 1
        return len(self.scores) + 1
