#!/usr/bin/env python3
"""
tools/mem_report.py — Analyse mémoire avec tracemalloc (≈ valgrind massif/memcheck).

1. Joue N frames (solo + multi) via le test de fumée.
2. Affiche le pic mémoire et les lignes qui allouent le plus.
3. Compare deux instantanés (après l'échauffement / à la fin) :
   une croissance continue entre les deux = fuite mémoire probable.

Usage : python tools/mem_report.py [--frames 2000] [--top 12]
"""

import argparse
import gc
import os
import sys
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=2000)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    tracemalloc.start(10)
    import smoke_test as st
    import tkinter as tk
    from settings import Settings

    root = tk.Tk()
    settings = Settings()

    st.test_solo(root, settings, 200)                 # échauffement
    gc.collect()        # sinon les cycles pas encore collectés passent pour des fuites
    snap_warm = tracemalloc.take_snapshot()
    print(st.test_solo(root, settings, args.frames))
    print(st.test_multi(root, settings, args.frames))
    gc.collect()
    snap_end = tracemalloc.take_snapshot()
    current, peak = tracemalloc.get_traced_memory()
    root.destroy()

    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    only_project = [tracemalloc.Filter(True, os.path.join(project, "*"))]

    print(f"\nMémoire Python actuelle : {current / 1024:8.1f} Kio")
    print(f"Pic mémoire Python      : {peak / 1024:8.1f} Kio\n")

    print(f"── Top {args.top} des lignes qui allouent (code du projet) ──")
    for s in snap_end.filter_traces(only_project).statistics("lineno")[:args.top]:
        print("  ", s)

    print("\n── Croissance entre échauffement et fin (fuites ?) ──")
    diff = snap_end.filter_traces(only_project).compare_to(
        snap_warm.filter_traces(only_project), "lineno")
    growing = [d for d in diff if d.size_diff > 0][:args.top]
    if not growing:
        print("   aucune croissance détectée ✔")
    for d in growing:
        print("  ", d)


if __name__ == "__main__":
    main()
