#!/usr/bin/env python3
"""
tools/smoke_test.py — Test de fumée : joue des milliers de frames avec des
entrées aléatoires (déplacements, rotations, hard drop, hold, pause,
game over, restart) en solo et en multi, puis anime le menu principal.

Toute exception fait échouer le test (code de sortie 1).

Usage : python tools/smoke_test.py [--frames 3000]
"""

import argparse
import os
import random
import sys
import time

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import tkinter as tk  # noqa: E402


class _MemoryLeaderboard:
    """Classement en mémoire : le test ne doit pas écrire de fichier."""

    def __init__(self):
        self.scores = []

    def is_high_score(self, score):
        return True

    def add_score(self, *a, **k):
        self.scores.append(a)


def step(root, game):
    game._tick()
    game.after_cancel(game._tick_id)
    root.update()


def test_solo(root, settings, frames):
    from game_solo import SoloGame
    g = SoloGame(root, "Smoke", _MemoryLeaderboard(), settings)
    g.after_cancel(g._tick_id)
    g.speed_mgr.base = g.speed_mgr.minimum = 0.0     # chute à chaque frame
    actions = [lambda: g._do_move(-1, 0), lambda: g._do_move(1, 0),
               g._do_rotate, lambda: g._do_rotate(-1), g._soft_drop,
               g._hard_drop, g._do_hold]
    games = 0
    for i in range(frames):
        random.choice(actions)()
        if i % 500 == 250:
            g._toggle_pause()
            step(root, g)
            g._toggle_pause()
        step(root, g)
        if g.game_over and not g._go_animating:
            games += 1
            g._try_restart()
            g.speed_mgr.base = g.speed_mgr.minimum = 0.0
    g._quit_game()
    return f"solo  : {frames} frames, {games} parties terminées"


def test_multi(root, settings, frames):
    from game_multi import MultiplayerGame
    g = MultiplayerGame(root, "A", "B", settings)
    g.after_cancel(g._tick_id)
    rounds = 0
    names = ["left", "right", "rotate", "down", "drop"]
    for _ in range(frames):
        g._p1_action(random.choice(names))
        g._p2_action(random.choice(names))
        step(root, g)
        if g.game_over:
            rounds += 1
            g.p1.reset()
            g.p2.reset()
            g.game_over = False
            g.winner = None
    g._quit()
    return f"multi : {frames} frames, {rounds} manches terminées"


def test_menu():
    import main
    app = main.App()
    t0 = time.monotonic()
    for _ in range(300):
        app._menu_tick()
        app.root.after_cancel(app._anim_id)
        app.root.update()
    app._show_settings()
    app.root.update()
    app._show_leaderboard()
    app.root.update()
    app._show_menu()
    app.root.update()
    app.root.destroy()
    return f"menu  : 300 frames en {time.monotonic() - t0:.2f} s"


def main_():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=3000)
    args = ap.parse_args()
    random.seed(42)

    from settings import Settings
    root = tk.Tk()
    settings = Settings()
    print(test_solo(root, settings, args.frames))
    print(test_multi(root, settings, args.frames))
    root.destroy()
    print(test_menu())
    print("OK")


if __name__ == "__main__":
    main_()
