# ══════════════════════════════════════════════════════════════
#  Makefile — Tetris Deluxe
#  make help  pour la liste des commandes
#  Windows : installer make une fois avec
#      winget install ezwinports.make
#  puis fermer et rouvrir le terminal.
# ══════════════════════════════════════════════════════════════

ifeq ($(OS),Windows_NT)
    PYTHON ?= python
else
    PYTHON ?= python3
endif

BUILD   := build
DIST    := dist
PROF    := $(BUILD)/tetris.prof
PYINST  := $(PYTHON) -m PyInstaller packaging/tetris.spec --noconfirm --clean \
           --distpath $(DIST) --workpath $(BUILD)/pyinstaller
FRAMES  ?= 3000

.DEFAULT_GOAL := help
.PHONY: help install install-dev run assets assets-force lint test bench \
        profile profile-auto profile-view profile-live memory check clean \
        icon exe exe-onefile dist-zip

help:            ## Affiche cette aide
	@$(PYTHON) tools/tasks.py help

# ── Installation ──────────────────────────────────────────────
install:         ## Installe les dépendances du jeu
	$(PYTHON) -m pip install -r requirements.txt

install-dev:     ## Installe aussi les outils (ruff, snakeviz, py-spy)
	$(PYTHON) -m pip install -r requirements-dev.txt

# ── Jeu ───────────────────────────────────────────────────────
run:             ## Lance le jeu
	$(PYTHON) main.py

assets:          ## Pré-calcule les sons manquants dans assets/audio
	$(PYTHON) audio.py --export

assets-force:    ## Régénère tous les sons (après modif. de audio.py)
	$(PYTHON) audio.py --export --force

# ── Qualité (≈ gcc -Wall) ─────────────────────────────────────
lint:            ## Analyse statique avec ruff
	$(PYTHON) -m ruff check .

test:            ## Test de fumée : joue FRAMES=3000 frames aléatoires
	$(PYTHON) tools/smoke_test.py --frames $(FRAMES)

check: lint test ## lint + test

# ── Performance (≈ gprof / valgrind) ──────────────────────────
bench:           ## Mesure temps de frame + démarrage (solo et multi)
	$(PYTHON) tools/bench.py --mode solo
	$(PYTHON) tools/bench.py --mode multi

profile:         ## Profile une vraie partie (jouer puis quitter)
	@$(PYTHON) tools/tasks.py mkdir $(BUILD)
	$(PYTHON) -m cProfile -o $(PROF) main.py
	$(PYTHON) tools/profile_report.py $(PROF)

profile-auto:    ## Profile une partie automatique (reproductible)
	@$(PYTHON) tools/tasks.py mkdir $(BUILD)
	$(PYTHON) -m cProfile -o $(PROF) tools/smoke_test.py --frames $(FRAMES)
	$(PYTHON) tools/profile_report.py $(PROF)

profile-view:    ## Ouvre le dernier profil dans le navigateur (snakeviz)
	$(PYTHON) -m snakeviz $(PROF)

profile-live:    ## Vue « top » en direct pendant que tu joues (py-spy)
	py-spy top -- $(PYTHON) main.py

memory:          ## Pic mémoire, plus gros allocateurs, fuites (tracemalloc)
	$(PYTHON) tools/mem_report.py

# ── Distribution ──────────────────────────────────────────────
icon:            ## Régénère assets/icon.ico et icon.png
	$(PYTHON) tools/make_icon.py

exe: assets      ## Crée dist/TetrisDeluxe/TetrisDeluxe.exe (dossier, comme Steam)
	$(PYINST)

exe-onefile: assets ## Crée dist/TetrisDeluxe.exe (un seul fichier à partager)
	$(PYINST) -- --onefile

dist-zip: exe    ## Crée le ZIP prêt à partager dans dist/
	$(PYTHON) tools/tasks.py zip

# ── Nettoyage ─────────────────────────────────────────────────
clean:           ## Supprime build/, dist/ et les caches Python
	@$(PYTHON) tools/tasks.py clean