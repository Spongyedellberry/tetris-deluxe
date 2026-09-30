#!/usr/bin/env python3
"""
tools/profile_report.py — Résumé lisible d'un profil cProfile (≈ gprof).

Usage :
    python -m cProfile -o build/tetris.prof main.py    # jouer puis quitter
    python tools/profile_report.py build/tetris.prof [--top 25] [--all]

Par défaut, seules les fonctions du projet sont affichées (pas celles de
tkinter / de la bibliothèque standard). --all affiche tout.
"""

import argparse
import os
import pstats
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", nargs="?", default=os.path.join(ROOT, "build", "tetris.prof"))
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--all", action="store_true", help="inclure les bibliothèques")
    args = ap.parse_args()

    stats = pstats.Stats(args.profile)
    # Filtre regex appliqué au chemin complet « fichier:ligne(fonction) »
    restrict = [] if args.all else [re.escape(ROOT)]

    print("=" * 78)
    print(" TEMPS CUMULÉ (fonction + tout ce qu'elle appelle)  → où chercher")
    print("=" * 78)
    stats.sort_stats("cumulative").print_stats(*restrict, args.top)

    print("=" * 78)
    print(" TEMPS PROPRE (hors sous-appels)  → la ligne de code réellement lente")
    print("=" * 78)
    stats.sort_stats("tottime").print_stats(*restrict, args.top)


if __name__ == "__main__":
    main()
