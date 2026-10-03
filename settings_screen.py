"""
settings_screen.py — Écran de paramètres complet avec tkinter.

Contient :
  - Plein écran (toggle)
  - Difficulté (sélection avec description)
  - Ghost piece (toggle)
  - Remappage des touches (solo + multi) avec capture interactive
  - Réinitialisation aux valeurs par défaut
"""

import tkinter as tk

from constants import PANEL_BG, TEXT_COLOR, ACCENT, ACCENT2, DIM_TEXT
from ui_components import make_label
from settings import (
    Settings, DIFFICULTY_PRESETS,
    SOLO_ACTIONS, MULTI_P1_ACTIONS, MULTI_P2_ACTIONS,
    key_display,
)

# Styles réutilisables
BTN_NORMAL = dict(
    font=("Consolas", 11), fg=TEXT_COLOR, bg="#1e1e40",
    activeforeground=ACCENT, activebackground="#2a2a5a",
    relief="flat", cursor="hand2", borderwidth=0,
    highlightthickness=1, highlightbackground="#3a3a6a",
)
TOGGLE_ON  = dict(font=("Consolas", 11, "bold"), fg="#0f0f1a", bg="#00e676",
                   activeforeground="#0f0f1a", activebackground="#69f0ae",
                   relief="flat", cursor="hand2", width=8)
TOGGLE_OFF = dict(font=("Consolas", 11, "bold"), fg=TEXT_COLOR, bg="#5a2020",
                   activeforeground=TEXT_COLOR, activebackground="#7a3030",
                   relief="flat", cursor="hand2", width=8)


class SettingsScreen(tk.Frame):
    """Écran de paramètres du jeu."""

    def __init__(self, master: tk.Tk, settings: Settings, on_back=None):
        super().__init__(master, bg=PANEL_BG)
        self.master = master
        self.settings = settings
        self.on_back = on_back
        self._capture_target = None   # (action, group, button) en cours de capture
        self._capture_bind_id = None

        self.pack(fill=tk.BOTH, expand=True)
        self._build()

    # ══════════════════════════════════════════════════════════
    #  Construction de l'interface
    # ══════════════════════════════════════════════════════════
    def _build(self):
        # Canvas + scrollbar pour tout contenir
        outer = tk.Frame(self, bg=PANEL_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer, bg=PANEL_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=PANEL_BG)

        self.scroll_frame.bind("<Configure>",
                               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Scroll molette
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))

        f = self.scroll_frame

        # ── Titre ─────────────────────────────────────────────
        make_label(f, "⚙  PARAMÈTRES", size=16, bold=True, color=ACCENT).pack(pady=(16, 12))

        # ── Section 1 : Affichage ─────────────────────────────
        self._section(f, "AFFICHAGE")
        row_fs = self._row(f)
        make_label(row_fs, "Plein écran", size=11).pack(side=tk.LEFT)
        self.btn_fullscreen = tk.Button(row_fs, **self._toggle_style(self.settings.fullscreen),
                                        command=self._toggle_fullscreen)
        self.btn_fullscreen.pack(side=tk.RIGHT)

        row_ghost = self._row(f)
        make_label(row_ghost, "Ghost piece (ombre)", size=11).pack(side=tk.LEFT)
        self.btn_ghost = tk.Button(row_ghost, **self._toggle_style(self.settings.ghost_piece),
                                   command=self._toggle_ghost)
        self.btn_ghost.pack(side=tk.RIGHT)

        # ── Section 2 : Audio ─────────────────────────────────
        self._section(f, "AUDIO")

        # Musique on/off
        row_music = self._row(f)
        make_label(row_music, "Musique de fond", size=11).pack(side=tk.LEFT)
        self.btn_music = tk.Button(row_music, **self._toggle_style(self.settings.music_enabled),
                                   command=self._toggle_music)
        self.btn_music.pack(side=tk.RIGHT)

        # SFX on/off
        row_sfx = self._row(f)
        make_label(row_sfx, "Effets sonores", size=11).pack(side=tk.LEFT)
        self.btn_sfx = tk.Button(row_sfx, **self._toggle_style(self.settings.sfx_enabled),
                                 command=self._toggle_sfx)
        self.btn_sfx.pack(side=tk.RIGHT)

        # Volume musique (slider)
        row_bgm_vol = self._row(f)
        make_label(row_bgm_vol, "Volume musique", size=10).pack(side=tk.LEFT)
        self.bgm_vol_var = tk.IntVar(value=int(self.settings.bgm_volume * 100))
        self.bgm_slider = tk.Scale(
            row_bgm_vol, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.bgm_vol_var, command=self._on_bgm_vol_change,
            length=180, bg=PANEL_BG, fg=TEXT_COLOR, troughcolor="#1e1e40",
            highlightthickness=0, sliderrelief="flat",
            font=("Consolas", 8))
        self.bgm_slider.pack(side=tk.RIGHT)

        # Volume SFX (slider)
        row_sfx_vol = self._row(f)
        make_label(row_sfx_vol, "Volume effets", size=10).pack(side=tk.LEFT)
        self.sfx_vol_var = tk.IntVar(value=int(self.settings.sfx_volume * 100))
        self.sfx_slider = tk.Scale(
            row_sfx_vol, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.sfx_vol_var, command=self._on_sfx_vol_change,
            length=180, bg=PANEL_BG, fg=TEXT_COLOR, troughcolor="#1e1e40",
            highlightthickness=0, sliderrelief="flat",
            font=("Consolas", 8))
        self.sfx_slider.pack(side=tk.RIGHT)

        # Note si pygame non installé
        try:
            from audio import get_audio
            am = get_audio()
            if not am.available:
                make_label(f, "  ⚠ pygame non installé — pip install pygame",
                           size=9, color="#ff8a80").pack(anchor="w", padx=30)
        except Exception:
            make_label(f, "  ⚠ Module audio indisponible",
                       size=9, color="#ff8a80").pack(anchor="w", padx=30)

        # ── Section 3 : Difficulté ────────────────────────────
        self._section(f, "DIFFICULTÉ")
        self.diff_buttons: dict[str, tk.Button] = {}
        for name, preset in DIFFICULTY_PRESETS.items():
            row = self._row(f)
            is_selected = (name == self.settings.difficulty)
            btn = tk.Button(row, text=name, width=10,
                            font=("Consolas", 11, "bold" if is_selected else "normal"),
                            fg=("#0f0f1a" if is_selected else TEXT_COLOR),
                            bg=(ACCENT2 if is_selected else "#1e1e40"),
                            activeforeground=ACCENT, activebackground="#2a2a5a",
                            relief="flat", cursor="hand2",
                            command=lambda n=name: self._set_difficulty(n))
            btn.pack(side=tk.LEFT)
            desc = make_label(row, f"  {preset['description']}", size=9, color=DIM_TEXT)
            desc.pack(side=tk.LEFT, padx=(8, 0))
            # Afficher les valeurs de vitesse
            speed_txt = f"[base={preset['base_speed']:.2f}s  min={preset['min_speed']:.2f}s]"
            make_label(row, speed_txt, size=8, color="#505070").pack(side=tk.RIGHT)
            self.diff_buttons[name] = btn

        # ── Section 3 : Touches Solo ──────────────────────────
        self._section(f, "TOUCHES — MODE SOLO")
        self.solo_key_btns: dict[str, tk.Button] = {}
        for action, label in SOLO_ACTIONS.items():
            row = self._row(f)
            make_label(row, label, size=10).pack(side=tk.LEFT)
            current_key = self.settings.solo_key(action)
            btn = tk.Button(row, text=key_display(current_key), width=12,
                            **BTN_NORMAL,
                            command=lambda a=action: self._start_capture("solo_keys", a))
            btn.pack(side=tk.RIGHT)
            self.solo_key_btns[action] = btn

        # ── Section 4 : Touches Multi J1 ─────────────────────
        self._section(f, "TOUCHES — MULTIJOUEUR JOUEUR 1")
        self.p1_key_btns: dict[str, tk.Button] = {}
        for action, label in MULTI_P1_ACTIONS.items():
            row = self._row(f)
            make_label(row, label, size=10).pack(side=tk.LEFT)
            current_key = self.settings.multi_p1_key(action)
            btn = tk.Button(row, text=key_display(current_key), width=12,
                            **BTN_NORMAL,
                            command=lambda a=action: self._start_capture("multi_p1_keys", a))
            btn.pack(side=tk.RIGHT)
            self.p1_key_btns[action] = btn

        # ── Section 5 : Touches Multi J2 ─────────────────────
        self._section(f, "TOUCHES — MULTIJOUEUR JOUEUR 2")
        self.p2_key_btns: dict[str, tk.Button] = {}
        for action, label in MULTI_P2_ACTIONS.items():
            row = self._row(f)
            make_label(row, label, size=10).pack(side=tk.LEFT)
            current_key = self.settings.multi_p2_key(action)
            btn = tk.Button(row, text=key_display(current_key), width=12,
                            **BTN_NORMAL,
                            command=lambda a=action: self._start_capture("multi_p2_keys", a))
            btn.pack(side=tk.RIGHT)
            self.p2_key_btns[action] = btn

        # ── Boutons du bas ────────────────────────────────────
        tk.Frame(f, height=20, bg=PANEL_BG).pack()
        bottom = tk.Frame(f, bg=PANEL_BG)
        bottom.pack(pady=(0, 20))

        tk.Button(bottom, text="🔄  Réinitialiser par défaut",
                  command=self._reset_defaults,
                  font=("Consolas", 11), fg="#ff8a80", bg="#1e1e40",
                  activeforeground=ACCENT, activebackground="#2a2a5a",
                  relief="flat", cursor="hand2", padx=12, pady=6).pack(side=tk.LEFT, padx=6)

        back = tk.Button(bottom, text="← Retour au menu",
                         command=self._go_back,
                         font=("Consolas", 11), fg=TEXT_COLOR, bg="#1e1e40",
                         activeforeground=ACCENT, activebackground="#2a2a5a",
                         relief="flat", cursor="hand2", padx=12, pady=6)
        back.ui_sound = "ui_back"          # son « retour » (voir ui_sounds.py)
        back.pack(side=tk.LEFT, padx=6)

        # Label de capture (caché par défaut)
        self.capture_label = make_label(f, "", size=12, bold=True, color=ACCENT)
        self.capture_label.pack(pady=4)

    # ══════════════════════════════════════════════════════════
    #  Helpers UI
    # ══════════════════════════════════════════════════════════
    def _section(self, parent, title: str):
        """Ajoute un titre de section."""
        tk.Frame(parent, height=8, bg=PANEL_BG).pack()
        sep = tk.Frame(parent, height=1, bg="#3a3a6a")
        sep.pack(fill=tk.X, padx=20, pady=(8, 4))
        make_label(parent, title, size=10, bold=True, color=ACCENT2).pack(anchor="w", padx=24)

    def _row(self, parent) -> tk.Frame:
        """Crée une ligne de paramètre."""
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill=tk.X, padx=30, pady=3)
        return row

    def _toggle_style(self, state: bool) -> dict:
        style = dict(TOGGLE_ON if state else TOGGLE_OFF)
        style["text"] = "  OUI  " if state else "  NON  "
        return style

    def _refresh_toggle(self, btn: tk.Button, state: bool):
        style = self._toggle_style(state)
        btn.config(**style)

    # ══════════════════════════════════════════════════════════
    #  Actions
    # ══════════════════════════════════════════════════════════
    def _toggle_fullscreen(self):
        self.settings.fullscreen = not self.settings.fullscreen
        self._refresh_toggle(self.btn_fullscreen, self.settings.fullscreen)
        # Appliquer immédiatement
        self.master.attributes("-fullscreen", self.settings.fullscreen)
        self.settings.save()

    def _toggle_ghost(self):
        self.settings.ghost_piece = not self.settings.ghost_piece
        self._refresh_toggle(self.btn_ghost, self.settings.ghost_piece)
        self.settings.save()

    def _toggle_music(self):
        self.settings.music_enabled = not self.settings.music_enabled
        self._refresh_toggle(self.btn_music, self.settings.music_enabled)
        # Appliquer immédiatement
        try:
            from audio import get_audio
            am = get_audio()
            if self.settings.music_enabled:
                am.play_bgm("menu")        # on est dans les menus
            else:
                am.stop_bgm()
        except Exception:
            pass
        self.settings.save()

    def _toggle_sfx(self):
        self.settings.sfx_enabled = not self.settings.sfx_enabled
        self._refresh_toggle(self.btn_sfx, self.settings.sfx_enabled)
        self.settings.save()

    def _on_bgm_vol_change(self, val):
        vol = int(val) / 100.0
        self.settings.bgm_volume = vol
        try:
            from audio import get_audio
            get_audio().set_bgm_volume(vol)
        except Exception:
            pass
        self.settings.save()

    def _on_sfx_vol_change(self, val):
        vol = int(val) / 100.0
        self.settings.sfx_volume = vol
        try:
            from audio import get_audio
            am = get_audio()
            am.set_sfx_volume(vol)
            # Jouer un petit son test
            am.play_sfx("rotate")
        except Exception:
            pass
        self.settings.save()

    def _set_difficulty(self, name: str):
        self.settings.difficulty = name
        for n, btn in self.diff_buttons.items():
            is_sel = (n == name)
            btn.config(
                font=("Consolas", 11, "bold" if is_sel else "normal"),
                fg="#0f0f1a" if is_sel else TEXT_COLOR,
                bg=ACCENT2 if is_sel else "#1e1e40",
            )
        self.settings.save()

    # ── Capture de touche ─────────────────────────────────────
    def _start_capture(self, group: str, action: str):
        """Lance la capture d'une touche pour un action donnée."""
        # Annuler une éventuelle capture en cours
        self._cancel_capture()

        # Trouver le bon bouton
        if group == "solo_keys":
            btn = self.solo_key_btns[action]
        elif group == "multi_p1_keys":
            btn = self.p1_key_btns[action]
        else:
            btn = self.p2_key_btns[action]

        self._capture_target = (action, group, btn)
        btn.config(text="⏎ Appuyez...", bg=ACCENT, fg="#0f0f1a")
        self.capture_label.config(
            text="Appuyez sur la touche souhaitée  (Échap pour annuler)")

        # Écouter la prochaine touche
        self._capture_bind_id = self.master.bind("<Key>", self._on_key_captured)

    def _on_key_captured(self, event):
        """Callback appelé quand l'utilisateur presse une touche pendant la capture."""
        if self._capture_target is None:
            return

        action, group, btn = self._capture_target

        # Échap → annuler
        if event.keysym == "Escape":
            self._cancel_capture()
            return

        # Construire la chaîne de touche tkinter
        tk_key = self._event_to_tk_key(event)

        # Appliquer
        if group == "solo_keys":
            self.settings.set_solo_key(action, tk_key)
        elif group == "multi_p1_keys":
            self.settings.set_multi_p1_key(action, tk_key)
        else:
            self.settings.set_multi_p2_key(action, tk_key)

        btn.config(text=key_display(tk_key), bg="#1e1e40", fg=TEXT_COLOR)
        self.settings.save()
        self._finish_capture()

    def _event_to_tk_key(self, event) -> str:
        """Convertit un événement tkinter en chaîne de bind utilisable."""
        # Touches spéciales
        special = {
            "Left": "<Left>", "Right": "<Right>",
            "Up": "<Up>", "Down": "<Down>",
            "space": "<space>", "Return": "<Return>",
            "Tab": "<Tab>", "Escape": "<Escape>",
            "Shift_L": "<Shift_L>", "Shift_R": "<Shift_R>",
            "Control_L": "<Control_L>", "Control_R": "<Control_R>",
            "BackSpace": "<BackSpace>", "Delete": "<Delete>",
        }
        if event.keysym in special:
            return special[event.keysym]
        # Touche simple (lettre, chiffre, symbole)
        if event.char and len(event.char) == 1 and event.char.isprintable():
            return event.char.lower()
        # Fallback
        return f"<{event.keysym}>"

    def _cancel_capture(self):
        """Annule la capture en cours et remet le bouton à son état normal."""
        if self._capture_target:
            action, group, btn = self._capture_target
            if group == "solo_keys":
                current = self.settings.solo_key(action)
            elif group == "multi_p1_keys":
                current = self.settings.multi_p1_key(action)
            else:
                current = self.settings.multi_p2_key(action)
            btn.config(text=key_display(current), bg="#1e1e40", fg=TEXT_COLOR)
        self._finish_capture()

    def _finish_capture(self):
        if self._capture_bind_id:
            self.master.unbind("<Key>", self._capture_bind_id)
            self._capture_bind_id = None
        self._capture_target = None
        self.capture_label.config(text="")

    # ── Reset ─────────────────────────────────────────────────
    def _reset_defaults(self):
        self.settings.reset_to_defaults()
        self.settings.save()
        # Reconstruire l'écran
        self.destroy()
        SettingsScreen(self.master, self.settings, on_back=self.on_back)

    # ── Retour ────────────────────────────────────────────────
    def _go_back(self):
        self._cancel_capture()
        # Appliquer le plein écran au cas où
        self.master.attributes("-fullscreen", self.settings.fullscreen)
        self.destroy()
        if self.on_back:
            self.on_back()
