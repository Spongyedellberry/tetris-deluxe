"""
name_panel.py — Panneau de saisie des noms, intégré au menu animé.

Remplace simpledialog.askstring (petite fenêtre système grise) par un
panneau aux couleurs du jeu :
  * solo : un champ ; multi : deux champs côte à côte dans le même panneau ;
  * dernier nom utilisé pré-rempli (sauvegardé dans les paramètres) ;
  * 12 caractères max. (longueur affichée dans le classement) + compteur ;
  * Entrée = jouer, Échap = retour, Tab = champ suivant ;
  * sons : frappe, validation, retour.
"""

import tkinter as tk

from constants import BG, PANEL_BG, TEXT_COLOR, ACCENT, ACCENT2, DIM_TEXT, BORDER_COLOR
from settings import key_display
from ui_components import lighten

MAX_LEN = 12
P2_COLOR = "#d500f9"            # couleur du joueur 2 (identique à game_multi)

BTN_BG, BTN_HOVER = "#1e1e40", "#2a2a5a"


class NamePanel(tk.Frame):
    """Panneau modal posé sur le canvas du menu.

    on_confirm(names: list[str]) est appelé avec 1 (solo) ou 2 (multi) noms
    déjà nettoyés ; on_cancel() quand le joueur revient au menu.
    """

    def __init__(self, parent, mode: str, settings, ui, on_confirm, on_cancel):
        self.solo = mode == "solo"
        border = ACCENT if self.solo else ACCENT2
        # highlightcolor aussi : sinon Tk dessine un bord noir dès que le
        # focus est dans le panneau (dans un champ de saisie)
        super().__init__(parent, bg=PANEL_BG, padx=40 if self.solo else 26, pady=26,
                         highlightthickness=2, highlightbackground=border,
                         highlightcolor=border)
        self.settings = settings
        self.ui = ui
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._entries: list[tuple[str, tk.Entry, str]] = []   # (clé, champ, défaut)
        self._vcmd = (self.register(lambda p: len(p) <= MAX_LEN), "%P")
        self._build()

    # ── Construction ──────────────────────────────────────────
    def _build(self):
        title = "🎮  MODE SOLO" if self.solo else "👥  MULTIJOUEUR"
        subtitle = "── Qui va jouer ? ──" if self.solo else "── Qui s'affronte ? ──"
        tk.Label(self, text=title, font=("Consolas", 24, "bold"),
                 fg=ACCENT, bg=PANEL_BG).pack()
        tk.Label(self, text=subtitle, font=("Consolas", 11),
                 fg=ACCENT2, bg=PANEL_BG).pack(pady=(2, 22))

        last = self.settings.data.get("last_names", {})
        if self.solo:
            sk = self.settings.data["solo_keys"]
            hint = (f"{key_display(sk['move_left'])} {key_display(sk['move_right'])} "
                    f"{key_display(sk['rotate_cw'])} {key_display(sk['soft_drop'])}   "
                    f"Drop {key_display(sk['hard_drop'])}   Hold {key_display(sk['hold'])}")
            self._field(self, "NOM DU JOUEUR", "solo", ACCENT2, last.get("solo", ""),
                        "Joueur", hint).pack()
        else:
            row = tk.Frame(self, bg=PANEL_BG)
            row.pack()
            for i, (key, color) in enumerate([("p1", ACCENT2), ("p2", P2_COLOR)]):
                keys = self.settings.data[f"multi_{key}_keys"]
                hint = (f"{key_display(keys['move_left'])} {key_display(keys['move_right'])} "
                        f"{key_display(keys['rotate_cw'])} {key_display(keys['soft_drop'])}"
                        f"   Drop {key_display(keys['hard_drop'])}")
                self._field(row, f"JOUEUR {i + 1}", key, color, last.get(key, ""),
                            f"Joueur {i + 1}", hint, width=14
                            ).pack(side=tk.LEFT, padx=(0, 16) if i == 0 else 0)
                if i == 0:
                    tk.Label(row, text="VS", font=("Consolas", 16, "bold"),
                             fg=ACCENT, bg=PANEL_BG).pack(side=tk.LEFT, padx=(0, 16))

        # ── Boutons ───────────────────────────────────────────
        btns = tk.Frame(self, bg=PANEL_BG)
        btns.pack(pady=(26, 10))
        back = self._button(btns, "←  Retour", self._cancel, BTN_BG, BTN_HOVER, TEXT_COLOR)
        back.ui_sound = "ui_back"
        back.pack(side=tk.LEFT, padx=8)
        play = self._button(btns, "▶  JOUER", self._confirm, ACCENT,
                            lighten(ACCENT, 0.2), "#ffffff", bold=True)
        play.ui_sound = "ui_start"
        play.pack(side=tk.LEFT, padx=8)

        keys = "Entrée = jouer   ·   Échap = retour"
        if not self.solo:
            keys += "   ·   Tab = joueur suivant"
        tk.Label(self, text=keys, font=("Consolas", 9), fg=DIM_TEXT,
                 bg=PANEL_BG).pack()

        # Focus sur le premier champ, texte sélectionné (taper = remplacer)
        first = self._entries[0][1]
        self.after_idle(lambda: (first.focus_set(), first.select_range(0, tk.END),
                                 first.icursor(tk.END)))

    def _field(self, parent, label: str, key: str, color: str, value: str,
               default: str, hint: str, width: int = 20) -> tk.Frame:
        box = tk.Frame(parent, bg=PANEL_BG)

        head = tk.Frame(box, bg=PANEL_BG)
        head.pack(fill=tk.X)
        tk.Label(head, text=label, font=("Consolas", 10, "bold"),
                 fg=color, bg=PANEL_BG).pack(side=tk.LEFT)
        counter = tk.Label(head, text="", font=("Consolas", 9),
                           fg=DIM_TEXT, bg=PANEL_BG)
        counter.pack(side=tk.RIGHT)

        var = tk.StringVar(value=value[:MAX_LEN])
        entry = tk.Entry(
            box, textvariable=var, width=width, justify="center",
            font=("Consolas", 18, "bold"), fg=TEXT_COLOR, bg=BG,
            insertbackground=color, insertwidth=3, relief="flat",
            highlightthickness=2, highlightbackground=BORDER_COLOR,
            highlightcolor=color, selectbackground=color, selectforeground=BG,
            validate="key", validatecommand=self._vcmd,
        )
        entry.pack(pady=(4, 4), ipady=8)
        entry.var = var        # garder une référence (sinon la variable est libérée)

        def update_counter(*_):
            n = len(var.get())
            counter.config(text=f"{n}/{MAX_LEN}",
                           fg=ACCENT if n >= MAX_LEN else DIM_TEXT)
        var.trace_add("write", update_counter)
        update_counter()

        tk.Label(box, text=hint, font=("Consolas", 8), fg=DIM_TEXT,
                 bg=PANEL_BG).pack()

        entry.bind("<Return>", lambda e: self._confirm(from_key=True))
        entry.bind("<KP_Enter>", lambda e: self._confirm(from_key=True))
        entry.bind("<Escape>", lambda e: self._cancel(from_key=True))
        entry.bind("<KeyPress>", self._on_key, add="+")
        self._entries.append((key, entry, default))
        return box

    def _button(self, parent, text, command, bg, hover, fg, bold=False) -> tk.Button:
        b = tk.Button(parent, text=text, command=command,
                      font=("Consolas", 13, "bold" if bold else "normal"),
                      fg=fg, bg=bg, activeforeground=fg, activebackground=hover,
                      relief="flat", cursor="hand2", width=14, pady=8,
                      borderwidth=0, highlightthickness=0)
        b.bind("<Enter>", lambda e: b.config(bg=hover))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        return b

    # ── Événements ────────────────────────────────────────────
    def _on_key(self, event):
        entry = event.widget
        if event.keysym == "BackSpace" and entry.get():
            self.ui.sfx("ui_type")
        elif event.char and event.char.isprintable() and (
                len(entry.get()) < MAX_LEN or entry.selection_present()):
            self.ui.sfx("ui_type")

    def _confirm(self, from_key: bool = False):
        # Au clic, le bouton joue déjà son son (UISounds) ; au clavier non.
        if from_key:
            self.ui.sfx("ui_start")
        names, last = [], self.settings.data.setdefault("last_names", {})
        for key, entry, default in self._entries:
            name = " ".join(entry.get().split())      # espaces multiples → un seul
            if name:
                last[key] = name
            names.append(name or default)
        self.settings.save()
        self.on_confirm(names)

    def _cancel(self, from_key: bool = False):
        if from_key:
            self.ui.sfx("ui_back")
        self.on_cancel()
