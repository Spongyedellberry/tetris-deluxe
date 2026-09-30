"""
game_multi.py — Mode Multijoueur local (split-screen) avec lignes garbage.

Optimisations (v3) : même moteur de rendu que le mode solo (BoardRenderer),
labels/aperçus mis à jour seulement au changement, cadence compensée,
horloge monotone.
"""

import time
import tkinter as tk

from constants import (
    COLS, ROWS, TICK_MS,
    BG, PANEL_BG, TEXT_COLOR, ACCENT, ACCENT2, DIM_TEXT,
    WALL_KICK_OFFSETS, GARBAGE_TABLE, TSPIN_GARBAGE,
)
from pieces import PieceBag, Piece
from board import Board, LineManager, detect_tspin
from score import ScoreSystem, SpeedManager
from renderer import BoardRenderer
from ui_components import (
    draw_preview_piece, make_label, make_value_label, center_message, Cached,
    KeyBindings,
)

# Taille réduite pour que les deux grilles tiennent à l'écran
MULTI_CELL = 22


class PlayerState:
    """État complet d'un joueur avec détection T-Spin."""

    def __init__(self, name: str, board_width: int = COLS, speed_manager=None):
        self.name = name
        self.bag = PieceBag()
        self.board = Board(width=board_width)
        self.score = ScoreSystem()
        self.speed = speed_manager if speed_manager else SpeedManager()
        self.next_pieces = [Piece(board_width, self.bag) for _ in range(2)]
        self.current = self._spawn()
        self.last_fall = time.monotonic()
        self.game_over = False
        self.pending_garbage = 0
        self.last_was_rotate = False
        self.last_tspin = False  # résultat du dernier lock

    def _spawn(self) -> Piece:
        p = self.next_pieces.pop(0)
        self.next_pieces.append(Piece(self.board.width, self.bag))
        self.last_was_rotate = False
        if self.board.is_collision(p):
            self.game_over = True
        return p

    def move(self, dx, dy) -> bool:
        if self.game_over:
            return False
        if not self.board.is_collision(self.current, dx=dx, dy=dy):
            self.current.x += dx
            self.current.y += dy
            self.last_was_rotate = False
            return True
        return False

    def rotate(self) -> bool:
        if self.game_over:
            return False
        orig_shape = [row[:] for row in self.current.shape]
        orig_x, orig_y = self.current.x, self.current.y
        self.current.rotate_cw()
        for kx, ky in WALL_KICK_OFFSETS:
            if not self.board.is_collision(self.current, dx=kx, dy=ky):
                self.current.x += kx
                self.current.y += ky
                self.last_was_rotate = True
                return True
        self.current.shape = orig_shape
        self.current.x, self.current.y = orig_x, orig_y
        return False

    def hard_drop(self) -> tuple[int, bool]:
        """Hard drop. Retourne (lignes effacées, is_tspin)."""
        if self.game_over:
            return 0, False
        while not self.board.is_collision(self.current, dy=1):
            self.current.y += 1
        return self.lock_piece()

    def ghost_y(self) -> int:
        gy = self.current.y
        while not self.board.is_collision(self.current, dy=(gy - self.current.y + 1)):
            gy += 1
        return gy

    def lock_piece(self) -> tuple[int, bool]:
        """Verrouille la pièce. Retourne (lignes effacées, is_tspin)."""
        # T-Spin Erkennung VOR dem Verrouillage
        is_tspin = detect_tspin(self.board, self.current, self.last_was_rotate)
        self.last_tspin = is_tspin

        self.board.lock_piece(self.current)
        self.score.pieces_placed += 1
        self.last_was_rotate = False

        # Appliquer le garbage en attente
        if self.pending_garbage > 0:
            self.board.add_garbage_lines(self.pending_garbage)
            self.pending_garbage = 0

        full = LineManager.find_full_lines(self.board)
        lines = LineManager.remove_lines(self.board, full)
        self.score.update_score(lines, is_tspin=is_tspin)

        self.current = self._spawn()
        self.last_fall = time.monotonic()

        if self.board.is_game_over():
            self.game_over = True

        return lines, is_tspin

    def reset(self):
        self.bag = PieceBag()
        self.board.reset()
        self.score.reset()
        self.next_pieces = [Piece(self.board.width, self.bag) for _ in range(2)]
        self.current = self._spawn()
        self.last_fall = time.monotonic()
        self.game_over = False
        self.pending_garbage = 0
        self.last_was_rotate = False
        self.last_tspin = False


class MultiplayerGame(tk.Frame):
    """Jeu Tetris multijoueur split-screen avec audio et animations."""

    def __init__(self, master: tk.Tk, name1: str, name2: str, settings=None,
                 on_quit=None):
        super().__init__(master, bg=PANEL_BG)
        self.master = master
        self.on_quit = on_quit
        self.cs = MULTI_CELL  # cell size

        # Paramètres
        from settings import Settings
        self.settings = settings if settings else Settings()

        # Audio
        try:
            from audio import get_audio
            self.audio = get_audio()
            self.audio.set_sfx_volume(self.settings.sfx_volume)
            self.audio.set_bgm_volume(self.settings.bgm_volume)
        except Exception:
            self.audio = None

        self.p1 = PlayerState(name1, speed_manager=self.settings.make_speed_manager())
        self.p2 = PlayerState(name2, speed_manager=self.settings.make_speed_manager())
        self.show_ghost = self.settings.ghost_piece
        self.winner = None
        self.game_over = False

        # Animation states per player
        self._anim = {1: {"lines": [], "frame": 0, "active": False},
                      2: {"lines": [], "frame": 0, "active": False}}
        self._anim_max_frames = 6

        self._build_ui()
        self._bind_keys()
        self._tick_id = None
        self.p1.score.game_start_time = time.monotonic()
        self.p2.score.game_start_time = time.monotonic()

        # Démarrer la musique
        if self.audio and self.settings.music_enabled:
            self.audio.play_bgm()

        self._tick()

    # ── SFX helper ────────────────────────────────────────────
    def _sfx(self, name: str):
        if self.audio and self.settings.sfx_enabled:
            self.audio.play_sfx(name)

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self):
        self.pack(fill=tk.BOTH, expand=True)
        cs = self.cs

        # Titre
        title_frame = tk.Frame(self, bg=PANEL_BG)
        title_frame.pack(pady=(8, 4))
        make_label(title_frame, "TETRIS BATTLE — MULTIJOUEUR", size=14,
                   bold=True, color=ACCENT).pack()

        main = tk.Frame(self, bg=PANEL_BG)
        main.pack(padx=8, pady=4)

        # ── Joueur 1 ──
        p1_frame = tk.Frame(main, bg=PANEL_BG)
        p1_frame.pack(side=tk.LEFT, padx=(0, 12))
        from settings import key_display as kd
        p1k = self.settings.data["multi_p1_keys"]
        p1_keys_txt = (f"{kd(p1k['move_left'])}{kd(p1k['move_right'])}"
                       f"{kd(p1k['rotate_cw'])}{kd(p1k['soft_drop'])}"
                       f"+{kd(p1k['hard_drop'])}")
        make_label(p1_frame, f"{self.p1.name}  ({p1_keys_txt})",
                   size=10, bold=True, color=ACCENT2).pack()
        self.canvas1 = tk.Canvas(p1_frame, width=COLS * cs, height=ROWS * cs,
                                 bg=BG, highlightthickness=2,
                                 highlightbackground="#2a5a9a")
        self.canvas1.pack()
        self.renderer1 = BoardRenderer(self.canvas1, COLS, ROWS, cs)
        stats1 = tk.Frame(p1_frame, bg=PANEL_BG)
        stats1.pack(fill=tk.X, pady=4)
        self.p1_score_var = tk.StringVar(value="0")
        self.p1_lines_var = tk.StringVar(value="0")
        self.p1_combo_var = tk.StringVar(value="")
        for txt, var in [("Score", self.p1_score_var), ("Lignes", self.p1_lines_var)]:
            f = tk.Frame(stats1, bg=PANEL_BG)
            f.pack(side=tk.LEFT, padx=8)
            make_label(f, txt, size=8, color=DIM_TEXT).pack()
            make_value_label(f, var, size=13, color=TEXT_COLOR).pack()
        self.p1_combo_label = make_label(stats1, "", size=10, bold=True, color=ACCENT)
        self.p1_combo_label.pack(side=tk.LEFT, padx=8)

        # Preview J1
        pv1 = tk.Frame(p1_frame, bg=PANEL_BG)
        pv1.pack(pady=2)
        make_label(pv1, "Suivant", size=8, color=DIM_TEXT).pack(side=tk.LEFT)
        self.next1_canvas = tk.Canvas(pv1, width=4 * cs, height=3 * cs, bg=BG,
                                      highlightthickness=1,
                                      highlightbackground="#2a2a5a")
        self.next1_canvas.pack(side=tk.LEFT, padx=6)

        # ── Séparateur central ──
        sep = tk.Frame(main, width=3, bg=ACCENT)
        sep.pack(side=tk.LEFT, fill=tk.Y, padx=4)

        # ── Joueur 2 ──
        p2_frame = tk.Frame(main, bg=PANEL_BG)
        p2_frame.pack(side=tk.LEFT, padx=(12, 0))
        p2k = self.settings.data["multi_p2_keys"]
        p2_keys_txt = (f"{kd(p2k['move_left'])}{kd(p2k['move_right'])}"
                       f"{kd(p2k['rotate_cw'])}{kd(p2k['soft_drop'])}"
                       f"+{kd(p2k['hard_drop'])}")
        make_label(p2_frame, f"{self.p2.name}  ({p2_keys_txt})",
                   size=10, bold=True, color="#d500f9").pack()
        self.canvas2 = tk.Canvas(p2_frame, width=COLS * cs, height=ROWS * cs,
                                 bg=BG, highlightthickness=2,
                                 highlightbackground="#5a2a9a")
        self.canvas2.pack()
        self.renderer2 = BoardRenderer(self.canvas2, COLS, ROWS, cs)
        stats2 = tk.Frame(p2_frame, bg=PANEL_BG)
        stats2.pack(fill=tk.X, pady=4)
        self.p2_score_var = tk.StringVar(value="0")
        self.p2_lines_var = tk.StringVar(value="0")
        self.p2_combo_var = tk.StringVar(value="")
        for txt, var in [("Score", self.p2_score_var), ("Lignes", self.p2_lines_var)]:
            f = tk.Frame(stats2, bg=PANEL_BG)
            f.pack(side=tk.LEFT, padx=8)
            make_label(f, txt, size=8, color=DIM_TEXT).pack()
            make_value_label(f, var, size=13, color=TEXT_COLOR).pack()
        self.p2_combo_label = make_label(stats2, "", size=10, bold=True, color=ACCENT)
        self.p2_combo_label.pack(side=tk.LEFT, padx=8)

        # Preview J2
        pv2 = tk.Frame(p2_frame, bg=PANEL_BG)
        pv2.pack(pady=2)
        make_label(pv2, "Suivant", size=8, color=DIM_TEXT).pack(side=tk.LEFT)
        self.next2_canvas = tk.Canvas(pv2, width=4 * cs, height=3 * cs, bg=BG,
                                      highlightthickness=1,
                                      highlightbackground="#2a2a5a")
        self.next2_canvas.pack(side=tk.LEFT, padx=6)

        # Mises à jour paresseuses des labels
        self._set_p1_score = Cached(self.p1_score_var.set)
        self._set_p1_lines = Cached(self.p1_lines_var.set)
        self._set_p2_score = Cached(self.p2_score_var.set)
        self._set_p2_lines = Cached(self.p2_lines_var.set)
        self._cfg_p1_combo = Cached(self.p1_combo_label.config)
        self._cfg_p2_combo = Cached(self.p2_combo_label.config)

        # Contrôles en bas
        bot = tk.Frame(self, bg=PANEL_BG)
        bot.pack(pady=4)
        diff_name = self.settings.difficulty
        make_label(bot, f"Échap = Quitter  |  Difficulté : {diff_name}  |  "
                        f"Les lignes effacées envoient du garbage !",
                   size=9, color=DIM_TEXT).pack()

    # ── Contrôles ─────────────────────────────────────────────
    def _bind_keys(self):
        p1k = self.settings.data["multi_p1_keys"]
        p2k = self.settings.data["multi_p2_keys"]
        self._keys = KeyBindings(self.master)
        bind = self._keys.bind

        # Joueur 1
        bind(p1k["move_left"],  lambda e: self._p1_action("left"))
        bind(p1k["move_right"], lambda e: self._p1_action("right"))
        bind(p1k["rotate_cw"],  lambda e: self._p1_action("rotate"))
        bind(p1k["soft_drop"],  lambda e: self._p1_action("down"))
        bind(p1k["hard_drop"],  lambda e: self._p1_action("drop"))

        # Joueur 2
        bind(p2k["move_left"],  lambda e: self._p2_action("left"))
        bind(p2k["move_right"], lambda e: self._p2_action("right"))
        bind(p2k["rotate_cw"],  lambda e: self._p2_action("rotate"))
        bind(p2k["soft_drop"],  lambda e: self._p2_action("down"))
        bind(p2k["hard_drop"],  lambda e: self._p2_action("drop"))

        bind("<Escape>", lambda e: self._quit())

    def _p1_action(self, action):
        if self.game_over or self.p1.game_over:
            return
        lines, is_tspin = 0, False
        if action == "left":
            if self.p1.move(-1, 0):
                self._sfx("move")
        elif action == "right":
            if self.p1.move(1, 0):
                self._sfx("move")
        elif action == "down":
            if self.p1.move(0, 1):
                self.p1.last_fall = time.monotonic()
        elif action == "rotate":
            if self.p1.rotate():
                self._sfx("rotate")
        elif action == "drop":
            lines, is_tspin = self.p1.hard_drop()
            self._sfx("drop")
        if lines > 0 or is_tspin:
            self._start_line_anim(1, lines, is_tspin)
        self._send_garbage(lines, is_tspin, from_player=1)
        self._check_game_over()

    def _p2_action(self, action):
        if self.game_over or self.p2.game_over:
            return
        lines, is_tspin = 0, False
        if action == "left":
            if self.p2.move(-1, 0):
                self._sfx("move")
        elif action == "right":
            if self.p2.move(1, 0):
                self._sfx("move")
        elif action == "down":
            if self.p2.move(0, 1):
                self.p2.last_fall = time.monotonic()
        elif action == "rotate":
            if self.p2.rotate():
                self._sfx("rotate")
        elif action == "drop":
            lines, is_tspin = self.p2.hard_drop()
            self._sfx("drop")
        if lines > 0 or is_tspin:
            self._start_line_anim(2, lines, is_tspin)
        self._send_garbage(lines, is_tspin, from_player=2)
        self._check_game_over()

    def _send_garbage(self, lines: int, is_tspin: bool, from_player: int):
        """Envoie du garbage à l'adversaire basé sur les lignes effacées."""
        if lines <= 0 and not is_tspin:
            return

        # T-Spin envoie plus de garbage
        if is_tspin:
            garbage = TSPIN_GARBAGE.get(lines, 4)
        else:
            garbage = GARBAGE_TABLE.get(lines, 4)

        # Bonus combo
        src = self.p1 if from_player == 1 else self.p2
        if src.score.combo >= 3:
            garbage += src.score.combo - 2
        if garbage > 0:
            target = self.p2 if from_player == 1 else self.p1
            target.pending_garbage += garbage

    def _check_game_over(self):
        if self.p1.game_over and not self.game_over:
            self.p1.score.freeze_time()
            self.p2.score.freeze_time()
            self.winner = self.p2.name
            self.game_over = True
            self._sfx("game_over")
            if self.audio:
                self.audio.stop_bgm()
        elif self.p2.game_over and not self.game_over:
            self.p1.score.freeze_time()
            self.p2.score.freeze_time()
            self.winner = self.p1.name
            self.game_over = True
            self._sfx("game_over")
            if self.audio:
                self.audio.stop_bgm()

    def _start_line_anim(self, player_num: int, lines: int, is_tspin: bool = False):
        """Déclenche le SFX approprié quand des lignes sont effacées."""
        if is_tspin:
            self._sfx("tspin")
        elif lines >= 4:
            self._sfx("tetris")
        elif lines > 0:
            self._sfx("line_clear")
        # Combo SFX
        ps = self.p1 if player_num == 1 else self.p2
        if ps.score.combo > 1:
            self._sfx("combo")

    def _quit(self):
        if self._tick_id:
            self.after_cancel(self._tick_id)
        if self.audio:
            self.audio.stop_bgm()
        self._keys.release()          # libère aussi les callbacks (voir KeyBindings)
        self.destroy()
        if self.on_quit:
            self.on_quit()

    # ── Boucle ────────────────────────────────────────────────
    def _tick(self):
        start = time.monotonic()
        now = start
        if not self.game_over:
            for ps in (self.p1, self.p2):
                if ps.game_over:
                    continue
                spd = ps.speed.fall_speed(ps.score.score, ps.score.level)
                if now - ps.last_fall >= spd:
                    if not ps.board.is_collision(ps.current, dy=1):
                        ps.current.y += 1
                    else:
                        lines, is_tspin = ps.lock_piece()
                        src_num = 1 if ps is self.p1 else 2
                        if lines > 0 or is_tspin:
                            self._start_line_anim(src_num, lines, is_tspin)
                        else:
                            self._sfx("soft_drop")
                        self._send_garbage(lines, is_tspin, from_player=src_num)
                        self._check_game_over()
                    ps.last_fall = now

        self._update_stats()
        self._draw_board(self.renderer1, self.p1)
        self._draw_board(self.renderer2, self.p2)
        self._draw_previews()

        # Cadence compensée (voir game_solo._tick)
        spent_ms = (time.monotonic() - start) * 1000
        self._tick_id = self.after(max(1, int(TICK_MS - spent_ms)), self._tick)

    def _update_stats(self):
        now = time.monotonic()
        self._set_p1_score(f"{self.p1.score.score:,}")
        self._set_p1_lines(str(self.p1.score.total_lines))
        self._set_p2_score(f"{self.p2.score.score:,}")
        self._set_p2_lines(str(self.p2.score.total_lines))

        for ps, cfg in [(self.p1, self._cfg_p1_combo), (self.p2, self._cfg_p2_combo)]:
            if (ps.score.last_combo_time > 0 and
                    now - ps.score.last_combo_time < 2.0):
                cfg(text=f"★ COMBO x{ps.score.last_combo_value}! ★")
            else:
                cfg(text="")

    # ── Dessin ────────────────────────────────────────────────
    def _draw_board(self, r: BoardRenderer, ps: PlayerState):
        frame = r.frame_from_grid(ps.board.grid)

        cur = ps.current
        if not ps.game_over and cur:
            # Ghost (si activé)
            if self.show_ghost:
                gy = ps.ghost_y()
                if gy > cur.y:
                    ghost = ("g",)
                    for ry, srow in enumerate(cur.shape):
                        for rx, cell in enumerate(srow):
                            if cell:
                                r.put(frame, cur.x + rx, gy + ry, ghost)
            # Pièce active
            key = ("n", cur.color)
            for ry, srow in enumerate(cur.shape):
                for rx, cell in enumerate(srow):
                    if cell:
                        r.put(frame, cur.x + rx, cur.y + ry, key)

        r.render(frame)

        if ps.game_over:
            r.static_overlay("lost", lambda cv, tag: center_message(
                cv, "PERDU!", color="#ff1744", tags=tag))
        elif self.game_over:
            r.static_overlay("won", lambda cv, tag: center_message(
                cv, "VICTOIRE!", color="#00e676", tags=tag))
        else:
            r.static_overlay(None)

    def _draw_previews(self):
        cs = self.cs
        for cv, ps in [(self.next1_canvas, self.p1), (self.next2_canvas, self.p2)]:
            if ps.next_pieces:
                p = ps.next_pieces[0]
                draw_preview_piece(cv, p.shape, p.color, cell_size=cs - 4)
