#!/usr/bin/env python3
"""
tools/bench.py — Benchmark reproductible du Tetris (démarrage + rendu).

Mesure :
  * le temps d'initialisation de l'audio (génération / chargement des sons) ;
  * le temps moyen et le 99e percentile d'une frame (_tick + rendu Tk) ;
  * le nombre d'objets présents sur le canvas.

Usage :
    python tools/bench.py                 # mode solo, 600 frames
    python tools/bench.py --mode multi
    python tools/bench.py --frames 2000 --fill 12
"""

import argparse
import os
import random
import statistics
import sys
import time

# Le benchmark ne doit pas dépendre d'une carte son
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Sauvegardes dans un dossier temporaire : les tests ne touchent jamais
# aux paramètres ni au classement du joueur.
import tempfile  # noqa: E402
os.environ.setdefault("TETRIS_DATA_DIR", tempfile.mkdtemp(prefix="tetris_test_"))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import tkinter as tk  # noqa: E402


def fill_board(board, rows: int):
    """Remplit les `rows` lignes du bas avec des blocs (un trou par ligne)."""
    for y in range(board.height - rows, board.height):
        gap = random.randrange(board.width)
        board.grid[y] = [0 if x == gap else random.randint(1, 7)
                         for x in range(board.width)]


def run_frames(root, game, frames: int, actions) -> list[float]:
    times = []
    for i in range(frames):
        if i % 8 == 0:
            actions[(i // 8) % len(actions)]()
        t0 = time.perf_counter()
        game._tick()
        game.after_cancel(game._tick_id)
        root.update()                      # force le rendu Tk
        times.append(time.perf_counter() - t0)
    return times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["solo", "multi"], default="solo")
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--fill", type=int, default=10, help="lignes pré-remplies")
    args = ap.parse_args()
    random.seed(1234)

    from settings import Settings
    from leaderboard import Leaderboard

    # ── Démarrage audio ──────────────────────────────────────
    t0 = time.perf_counter()
    try:
        from audio import get_audio
        get_audio()
    except Exception as exc:              # pragma: no cover
        print("audio indisponible :", exc)
    audio_ms = (time.perf_counter() - t0) * 1000

    root = tk.Tk()
    settings = Settings()

    if args.mode == "solo":
        from game_solo import SoloGame
        game = SoloGame(root, "Bench", Leaderboard(), settings)
        game.after_cancel(game._tick_id)
        fill_board(game.board, args.fill)
        actions = [lambda: game._do_move(-1, 0), lambda: game._do_move(1, 0),
                   lambda: game._do_rotate()]
        canvases = [game.canvas]
    else:
        from game_multi import MultiplayerGame
        game = MultiplayerGame(root, "J1", "J2", settings)
        game.after_cancel(game._tick_id)
        fill_board(game.p1.board, args.fill)
        fill_board(game.p2.board, args.fill)
        actions = [lambda: game.p1.move(-1, 0), lambda: game.p2.move(1, 0),
                   lambda: game.p1.rotate(), lambda: game.p2.rotate()]
        canvases = [game.canvas1, game.canvas2]

    root.update()
    run_frames(root, game, 30, actions)          # échauffement

    def next_ids():
        """Les identifiants d'objets Tk croissent : on sonde le prochain id."""
        ids = []
        for c in canvases:
            i = c.create_line(0, 0, 0, 0)
            c.delete(i)
            ids.append(i)
        return ids

    ids_before = next_ids()
    times = run_frames(root, game, args.frames, actions)
    ids_after = next_ids()
    created = sum(a - b - 1 for a, b in zip(ids_after, ids_before)) / args.frames

    ms = sorted(t * 1000 for t in times)
    p99 = ms[int(len(ms) * 0.99) - 1]
    items = sum(len(c.find_all()) for c in canvases)

    print(f"mode            : {args.mode}")
    print(f"init audio      : {audio_ms:8.1f} ms")
    print(f"frame moyenne   : {statistics.mean(ms):8.3f} ms")
    print(f"frame médiane   : {statistics.median(ms):8.3f} ms")
    print(f"frame p99       : {p99:8.3f} ms")
    print(f"budget 60 FPS   : {16.667:8.3f} ms")
    print(f"objets créés    : {created:8.1f} par frame")
    print(f"objets canvas   : {items:8d} (dont cachés)")

    try:
        game.audio and game.audio.stop_bgm()
    except Exception:
        pass
    root.destroy()


if __name__ == "__main__":
    main()
