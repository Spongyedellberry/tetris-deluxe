"""
game_solo.py — Mode Solo du Tetris avec tkinter.
Inclut : audio (SFX + BGM) et animations visuelles.

Optimisations (v3) :
  * rendu de la grille via BoardRenderer (objets persistants, mise à jour
    différentielle) au lieu de delete("all") + recréation à chaque frame ;
  * labels et aperçus mis à jour uniquement quand leur valeur change ;
  * boucle à cadence compensée (le temps de calcul est déduit du délai) ;
  * horloge monotone (time.monotonic) insensible aux changements d'heure.
"""

import time
import math
import tkinter as tk

from constants import (
    COLS, ROWS, CELL, TICK_MS,
    PANEL_BG, TEXT_COLOR, ACCENT, ACCENT2, DIM_TEXT,
    WALL_KICK_OFFSETS,
)
from pieces import PieceBag, Piece
from board import Board, LineManager, detect_tspin
from score import ScoreSystem
from leaderboard import Leaderboard
from renderer import BoardRenderer
from ui_components import (
    draw_preview_piece, clear_preview,
    make_board_canvas, make_preview_canvas,
    make_label, make_value_label, center_message,
    lighten, Cached, KeyBindings,
)


class SoloGame(tk.Frame):
    """Jeu Tetris mode solo complet avec audio et animations."""

    def __init__(self, master: tk.Tk, player_name: str, leaderboard: Leaderboard,
                 settings=None, on_quit=None):
        super().__init__(master, bg=PANEL_BG)
        self.master = master
        self.player_name = player_name
        self.leaderboard = leaderboard
        self.on_quit = on_quit

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

        self._build_ui()
        self._bind_keys()
        self._reset_game()
        self._tick_id = None

        # Démarrer la musique
        if self.audio and self.settings.music_enabled:
            self.audio.play_bgm()

        self._start_tick()

    # ── SFX helper ────────────────────────────────────────────
    def _sfx(self, name: str):
        """Joue un SFX si activé."""
        if self.audio and self.settings.sfx_enabled:
            self.audio.play_sfx(name)

    # ── Construction de l'interface ───────────────────────────
    def _build_ui(self):
        self.pack(fill=tk.BOTH, expand=True)
        container = tk.Frame(self, bg=PANEL_BG)
        container.pack(padx=12, pady=12)

        # --- Panneau gauche : Hold ---
        left = tk.Frame(container, bg=PANEL_BG)
        left.pack(side=tk.LEFT, padx=(0, 10), anchor="n")
        make_label(left, "HOLD", size=11, bold=True, color=ACCENT2).pack()
        self.hold_canvas = make_preview_canvas(left)
        self.hold_canvas.pack(pady=4)
        tk.Frame(left, height=20, bg=PANEL_BG).pack()
        make_label(left, "Joueur", size=9, color=DIM_TEXT).pack()
        make_label(left, self.player_name, size=12, bold=True, color=ACCENT2).pack()

        # --- Grille centrale ---
        self.canvas = make_board_canvas(container)
        self.canvas.pack(side=tk.LEFT)
        self.renderer = BoardRenderer(self.canvas, COLS, ROWS, CELL)

        # --- Panneau droit : Next + Stats ---
        right = tk.Frame(container, bg=PANEL_BG)
        right.pack(side=tk.LEFT, padx=(10, 0), anchor="n")

        make_label(right, "SUIVANT", size=11, bold=True, color=ACCENT2).pack()
        self.next_canvases = []
        for _ in range(3):
            c = make_preview_canvas(right)
            c.pack(pady=2)
            self.next_canvases.append(c)

        tk.Frame(right, height=14, bg=PANEL_BG).pack()

        # Score / Level / Lines
        self.score_var = tk.StringVar(value="0")
        self.level_var = tk.StringVar(value="1")
        self.lines_var = tk.StringVar(value="0")
        self.speed_var = tk.StringVar(value="0.50s")
        self.combo_var = tk.StringVar(value="")

        for label_text, var, color in [
            ("SCORE", self.score_var, ACCENT),
            ("NIVEAU", self.level_var, TEXT_COLOR),
            ("LIGNES", self.lines_var, TEXT_COLOR),
            ("TEMPO", self.speed_var, ACCENT2),
        ]:
            make_label(right, label_text, size=9, color=DIM_TEXT).pack(anchor="w")
            make_value_label(right, var, size=15, color=color).pack(anchor="w", pady=(0, 6))

        # Combo
        self.combo_label = make_label(right, "", size=12, bold=True, color=ACCENT)
        self.combo_label.pack(anchor="w", pady=(6, 0))

        # T-Spin
        self.tspin_label = make_label(right, "", size=12, bold=True, color="#d500f9")
        self.tspin_label.pack(anchor="w", pady=(2, 0))

        # Mises à jour paresseuses : un appel Tk seulement si la valeur change
        self._set_score = Cached(self.score_var.set)
        self._set_level = Cached(self.level_var.set)
        self._set_lines = Cached(self.lines_var.set)
        self._set_speed = Cached(self.speed_var.set)
        self._cfg_combo = Cached(self.combo_label.config)
        self._cfg_tspin = Cached(self.tspin_label.config)

        # Contrôles (affichés selon les paramètres)
        tk.Frame(right, height=10, bg=PANEL_BG).pack()
        from settings import key_display as kd
        sk = self.settings.data["solo_keys"]
        controls = [
            f"{kd(sk['move_left'])} {kd(sk['move_right'])}  Déplacer",
            f"{kd(sk['rotate_cw'])}    Rotation",
            f"{kd(sk['soft_drop'])}    Descente",
            f"{kd(sk['hard_drop'])}  Hard Drop",
            f"{kd(sk['hold'])}     Hold",
            f"{kd(sk['pause'])}     Pause",
            f"{kd(sk['quit'])}     Quitter",
        ]
        for c in controls:
            make_label(right, c, size=8, color=DIM_TEXT).pack(anchor="w")

    # ── Raccourcis clavier ────────────────────────────────────
    def _bind_keys(self):
        sk = self.settings.data["solo_keys"]
        self._keys = KeyBindings(self.master)
        bind = self._keys.bind

        bind(sk["move_left"],  lambda e: self._do_move(-1, 0))
        bind(sk["move_right"], lambda e: self._do_move(1, 0))
        bind(sk["soft_drop"],  lambda e: self._soft_drop())
        bind(sk["rotate_cw"],  lambda e: self._do_rotate())
        bind(sk["rotate_ccw"], lambda e: self._do_rotate(-1))
        bind(sk["hard_drop"],  lambda e: self._hard_drop())
        bind(sk["hold"],       lambda e: self._do_hold())
        bind(sk["pause"],      lambda e: self._toggle_pause())
        bind(sk["quit"],       lambda e: self._quit_game())
        bind(sk["restart"],    lambda e: self._try_restart())

    # ── État du jeu ───────────────────────────────────────────
    def _reset_game(self):
        self.bag = PieceBag()
        self.board = Board()
        self.score_sys = ScoreSystem()
        self.speed_mgr = self.settings.make_speed_manager()

        self.next_pieces = [Piece(self.board.width, self.bag) for _ in range(3)]
        self.current = self._spawn_piece()
        self.held_piece_data = None
        self.can_hold = True

        self.show_ghost = self.settings.ghost_piece
        self.paused = False
        self.game_over = False
        self.last_fall = time.monotonic()
        self._prev_level = 1

        # ── T-Spin tracking ───────────────────────────────────
        self._last_was_rotate = False   # dernière action = rotation ?
        self._pending_tspin = False     # T-Spin détecté, en attente d'anim

        # ── État des animations ───────────────────────────────
        self._anim_lines: list[int] = []
        self._anim_frame: int = 0
        self._anim_max_frames: int = 6
        self._animating: bool = False

        self._impact_flash: float = 0.0
        self._impact_rows: list[int] = []

        self._go_anim_frame: int = 0
        self._go_animating: bool = False

        self._combo_anim_size: int = 12
        self._combo_anim_time: float = 0.0

        self._tspin_anim_time: float = 0.0  # quand afficher le texte T-Spin

        self._update_labels()

    def _spawn_piece(self) -> Piece:
        p = self.next_pieces.pop(0)
        self.next_pieces.append(Piece(self.board.width, self.bag))
        self.can_hold = True
        if self.board.is_collision(p):
            self.game_over = True
        return p

    # ── Actions du joueur (avec SFX) ──────────────────────────
    def _move(self, dx, dy) -> bool:
        if self.game_over or self.paused or self._animating:
            return False
        if not self.board.is_collision(self.current, dx=dx, dy=dy):
            self.current.x += dx
            self.current.y += dy
            self._last_was_rotate = False
            return True
        return False

    def _do_move(self, dx, dy):
        if self._move(dx, dy):
            self._sfx("move")

    def _rotate(self, direction=1):
        if self.game_over or self.paused or self._animating:
            return
        original_shape = [row[:] for row in self.current.shape]
        original_x, original_y = self.current.x, self.current.y

        if direction == 1:
            self.current.rotate_cw()
        else:
            self.current.rotate_ccw()

        for kx, ky in WALL_KICK_OFFSETS:
            if not self.board.is_collision(self.current, dx=kx, dy=ky):
                self.current.x += kx
                self.current.y += ky
                self._last_was_rotate = True
                return True

        self.current.shape = original_shape
        self.current.x = original_x
        self.current.y = original_y
        return False

    def _do_rotate(self, direction=1):
        if self._rotate(direction):
            self._sfx("rotate")

    def _soft_drop(self):
        if self._move(0, 1):
            self.last_fall = time.monotonic()

    def _hard_drop(self):
        if self.game_over or self.paused or self._animating:
            return
        while not self.board.is_collision(self.current, dy=1):
            self.current.y += 1

        # Flash d'impact
        self._impact_flash = time.monotonic()
        self._impact_rows = sorted({self.current.y + ry
                                    for ry, srow in enumerate(self.current.shape)
                                    if any(srow)})

        self._sfx("drop")
        self._lock_piece()

    def _do_hold(self):
        if self.game_over or self.paused or not self.can_hold or self._animating:
            return
        self.can_hold = False
        self._last_was_rotate = False
        saved_shape = [row[:] for row in self.current.shape]
        saved_color = self.current.color

        if self.held_piece_data is None:
            self.held_piece_data = (saved_shape, saved_color)
            self.current = self._spawn_piece()
        else:
            old_shape, old_color = self.held_piece_data
            self.held_piece_data = (saved_shape, saved_color)
            self.current.shape = old_shape
            self.current.color = old_color
            self.current.x = self.board.width // 2 - len(old_shape[0]) // 2
            self.current.y = 0

        self._sfx("hold")

    def _ghost_y(self) -> int:
        gy = self.current.y
        while not self.board.is_collision(self.current, dy=(gy - self.current.y + 1)):
            gy += 1
        return gy

    def _lock_piece(self):
        # ── T-Spin Erkennung VOR dem Verrouillage ────────────
        is_tspin = detect_tspin(self.board, self.current, self._last_was_rotate)

        self.board.lock_piece(self.current)
        self.score_sys.pieces_placed += 1
        self._last_was_rotate = False

        # Détection des lignes complètes
        full = LineManager.find_full_lines(self.board)

        if full or is_tspin:
            # Lancer l'animation de suppression
            self._anim_lines = full if full else []
            self._anim_frame = 0
            self._animating = True
            self._pending_tspin = is_tspin

            # SFX selon le type
            if is_tspin:
                self._sfx("tspin")
                self._tspin_anim_time = time.monotonic()
            elif len(full) >= 4:
                self._sfx("tetris")
            else:
                self._sfx("line_clear")

            # Si T-Spin sans ligne → résoudre immédiatement
            if is_tspin and not full:
                self._finish_line_clear_anim()
        else:
            self.score_sys.update_score(0, is_tspin=False)
            self._sfx("soft_drop")

        self.current = self._spawn_piece()
        self.last_fall = time.monotonic()

        if self.game_over:
            self._on_game_over()

    def _finish_line_clear_anim(self):
        """Appelée quand l'animation de suppression est terminée."""
        lines = LineManager.remove_lines(self.board, self._anim_lines)
        old_level = self.score_sys.level
        self.score_sys.update_score(lines, is_tspin=self._pending_tspin)
        self._update_labels()

        # Combo SFX
        if self.score_sys.combo > 1:
            self._sfx("combo")
            self._combo_anim_size = 18
            self._combo_anim_time = time.monotonic()

        # Level up SFX
        if self.score_sys.level > old_level:
            self._sfx("level_up")

        self._anim_lines = []
        self._anim_frame = 0
        self._animating = False
        self._pending_tspin = False

    def _toggle_pause(self):
        if self.game_over:
            return
        self.paused = not self.paused
        if self.paused:
            if self.audio:
                self.audio.pause_bgm()
        else:
            self.last_fall = time.monotonic()
            if self.audio and self.settings.music_enabled:
                self.audio.unpause_bgm()

    def _try_restart(self):
        if self.game_over:
            self._reset_game()
            if self.audio and self.settings.music_enabled:
                self.audio.play_bgm()

    def _quit_game(self):
        if self._tick_id:
            self.after_cancel(self._tick_id)
        if self.audio:
            self.audio.stop_bgm()
        self._keys.release()          # libère aussi les callbacks (voir KeyBindings)
        self.destroy()
        if self.on_quit:
            self.on_quit()

    # ── Game Over ─────────────────────────────────────────────
    def _on_game_over(self):
        self.score_sys.freeze_time()
        self._sfx("game_over")
        if self.audio:
            self.audio.stop_bgm()
        self._go_animating = True
        self._go_anim_frame = 0
        if self.leaderboard.is_high_score(self.score_sys.score):
            self.leaderboard.add_score(
                self.player_name,
                self.score_sys.score,
                self.score_sys.total_lines,
                self.score_sys.level,
            )

    # ── Labels ────────────────────────────────────────────────
    def _update_labels(self):
        """Met à jour les labels. Grâce à Cached, aucun appel Tk n'est émis
        tant que les valeurs affichées ne changent pas."""
        now = time.monotonic()
        self._set_score(f"{self.score_sys.score:,}")
        self._set_level(str(self.score_sys.level))
        self._set_lines(str(self.score_sys.total_lines))
        spd = self.speed_mgr.fall_speed(self.score_sys.score, self.score_sys.level)
        self._set_speed(f"{spd:.2f}s")

        # Combo (texte animé avec taille qui diminue)
        if (self.score_sys.last_combo_time > 0 and
                now - self.score_sys.last_combo_time < 2.0):
            elapsed = now - self._combo_anim_time
            size = self._combo_anim_size if elapsed < 0.3 else 12
            txt = f"★ COMBO x{self.score_sys.last_combo_value}! ★"
            self._cfg_combo(text=txt, font=("Consolas", size, "bold"))
        else:
            self._cfg_combo(text="")

        # T-Spin (texte animé pendant 2.5 secondes)
        if (self.score_sys.last_tspin_time > 0 and
                now - self.score_sys.last_tspin_time < 2.5):
            elapsed = now - self.score_sys.last_tspin_time
            # Pulsation de taille
            if elapsed < 0.4:
                size = 16
            elif elapsed < 0.8:
                size = 14
            else:
                size = 12
            txt = f"🌀 {self.score_sys.last_tspin_type}!"
            self._cfg_tspin(text=txt, font=("Consolas", size, "bold"))
        else:
            self._cfg_tspin(text="")

    # ── Boucle principale ─────────────────────────────────────
    def _start_tick(self):
        self._tick()

    def _tick(self):
        start = time.monotonic()
        now = start

        # Animation de suppression de lignes
        if self._animating:
            self._anim_frame += 1
            if self._anim_frame >= self._anim_max_frames:
                self._finish_line_clear_anim()

        # Game over animation
        elif self._go_animating:
            self._go_anim_frame += 1
            if self._go_anim_frame > ROWS:
                self._go_animating = False

        # Chute normale
        elif not self.game_over and not self.paused:
            speed = self.speed_mgr.fall_speed(self.score_sys.score, self.score_sys.level)
            if now - self.last_fall >= speed:
                if not self.board.is_collision(self.current, dy=1):
                    self.current.y += 1
                else:
                    self._lock_piece()
                self.last_fall = now

        self._update_labels()
        self._draw()

        # Cadence compensée : on retire le temps déjà consommé par la frame,
        # sinon la période réelle vaut TICK_MS + durée de la frame.
        spent_ms = (time.monotonic() - start) * 1000
        self._tick_id = self.after(max(1, int(TICK_MS - spent_ms)), self._tick)

    # ── Dessin ────────────────────────────────────────────────
    def _draw(self):
        c = self.canvas
        r = self.renderer
        now = time.monotonic()

        # ── 1. État voulu des cellules ───────────────────────
        frame = r.frame_from_grid(self.board.grid)

        # Animation game over : remplissage progressif gris
        if self._go_animating:
            first = (ROWS - self._go_anim_frame) * COLS
            grey = ("x",)
            for i in range(max(0, first), len(frame)):
                if frame[i] is not None:
                    frame[i] = grey

        # Flash de suppression de lignes
        if self._animating and self._anim_lines:
            key = ("f", self._anim_frame % 3)
            for row_idx in self._anim_lines:
                for col in range(COLS):
                    r.put(frame, col, row_idx, key)

        # Pièce active + ghost
        cur = self.current
        if not self.game_over and cur and not self._animating:
            if self.show_ghost:
                gy = self._ghost_y()
                if gy > cur.y:
                    ghost = ("g",)
                    for ry, srow in enumerate(cur.shape):
                        for rx, cell in enumerate(srow):
                            if cell:
                                r.put(frame, cur.x + rx, gy + ry, ghost)
            key = ("n", cur.color)
            for ry, srow in enumerate(cur.shape):
                for rx, cell in enumerate(srow):
                    if cell:
                        r.put(frame, cur.x + rx, cur.y + ry, key)

        r.render(frame)          # ne touche que les cellules modifiées

        # ── 2. Messages fixes (redessinés seulement au changement) ──
        if self.paused:
            r.static_overlay("pause", lambda cv, tag: center_message(
                cv, "PAUSE", "P pour reprendre", tags=tag))
        elif self.game_over and not self._go_animating:
            r.static_overlay("game_over", lambda cv, tag: center_message(
                cv, "GAME OVER", "R = Rejouer  Q = Menu", tags=tag))
        else:
            r.static_overlay(None)

        # ── 3. Effets animés (quelques objets, recréés) ──────
        c.delete("fx")

        # Flash d'impact hard drop
        if self._impact_flash > 0 and (now - self._impact_flash) < 0.12:
            alpha = 1.0 - (now - self._impact_flash) / 0.12
            flash_color = lighten("#ffffff", round(1.0 - alpha * 0.5, 2))
            for row_idx in self._impact_rows:
                if 0 <= row_idx < ROWS:
                    y1 = row_idx * CELL
                    c.create_rectangle(0, y1, COLS * CELL, y1 + CELL,
                                       fill="", outline=flash_color, width=2,
                                       tags="fx")

        # T-Spin flash overlay
        if (self.score_sys.last_tspin_time > 0 and
                now - self.score_sys.last_tspin_time < 1.5):
            elapsed = now - self.score_sys.last_tspin_time
            # Pulse : taille oscille puis diminue
            pulse = abs(math.sin(elapsed * 6)) * max(0, 1.0 - elapsed / 1.5)
            font_size = int(18 + pulse * 10)
            # Couleur magenta qui s'estompe
            fade = max(0, 1.0 - elapsed / 1.5)
            if fade > 0.05:
                color = f"#{int(213 * fade):02x}00{int(249 * fade):02x}"
                cx = COLS * CELL // 2
                cy = ROWS * CELL // 3
                font = ("Consolas", font_size, "bold")
                text = self.score_sys.last_tspin_type
                # Ombre portée d'abord, texte ensuite (sinon l'ombre le recouvre)
                c.create_text(cx + 2, cy + 2, text=text, font=font,
                              fill="#1a001a", anchor="center", tags="fx")
                c.create_text(cx, cy, text=text, font=font,
                              fill=color, anchor="center", tags="fx")

        # ── 4. Aperçus (redessinés seulement si la pièce change) ──
        for i, cv in enumerate(self.next_canvases):
            if i < len(self.next_pieces):
                p = self.next_pieces[i]
                draw_preview_piece(cv, p.shape, p.color)

        # Hold
        if self.held_piece_data:
            draw_preview_piece(self.hold_canvas, self.held_piece_data[0],
                               self.held_piece_data[1])
        else:
            clear_preview(self.hold_canvas)
