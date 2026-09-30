"""
audio.py — Génération et lecture de sons rétro pour le Tetris.

Tous les sons sont générés programmatiquement (chiptune 8-bit).
Nécessite pygame pour la lecture : pip install pygame
Si pygame n'est pas installé, le jeu fonctionne sans son.

Optimisation : la génération de la musique coûte ~1 s en Python pur.
Les sons sont donc pré-calculés UNE fois dans assets/audio/*.wav
(`python audio.py --export` ou `make assets`) puis simplement chargés.
Si un fichier manque, il est généré à la volée puis mis en cache.
"""

import math
import struct
import io
import os
import sys
import wave
import random

from paths import asset, is_frozen

# ─── Tentative d'import pygame ────────────────────────────────
_AUDIO_AVAILABLE = False
_mixer = None

try:
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame.mixer as _mixer
    _AUDIO_AVAILABLE = True
except ImportError:
    pass

# ─── Constantes audio ────────────────────────────────────────
SAMPLE_RATE = 22050
MAX_AMP = 12000   # amplitude (int16 max = 32767, on reste modéré)

# Notes (fréquences en Hz)
NOTE = {
    "E2": 82, "A2": 110, "B2": 123,
    "C3": 131, "D3": 147, "E3": 165, "F3": 175, "G3": 196, "A3": 220, "B3": 247,
    "C4": 262, "D4": 294, "E4": 330, "F4": 349, "G4": 392, "A4": 440, "B4": 494,
    "C5": 523, "D5": 587, "E5": 659, "F5": 698, "G5": 784, "A5": 880, "B5": 988,
    "C6": 1047,
}


# ══════════════════════════════════════════════════════════════
#  Générateurs de formes d'onde
# ══════════════════════════════════════════════════════════════

def _sine(freq: float, duration: float, amp: int = MAX_AMP, fade: float = 0.02) -> list[int]:
    """Génère une onde sinusoïdale."""
    n = int(SAMPLE_RATE * duration)
    fade_n = int(SAMPLE_RATE * fade)
    samples = []
    for i in range(n):
        val = amp * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)
        # Fade in/out pour éviter les clics
        if i < fade_n:
            val *= i / fade_n
        elif i > n - fade_n:
            val *= (n - i) / fade_n
        samples.append(int(val))
    return samples


def _square(freq: float, duration: float, amp: int = MAX_AMP // 2, fade: float = 0.01) -> list[int]:
    """Génère une onde carrée (son 8-bit classique)."""
    n = int(SAMPLE_RATE * duration)
    fade_n = int(SAMPLE_RATE * fade)
    period = SAMPLE_RATE / freq if freq > 0 else SAMPLE_RATE
    samples = []
    for i in range(n):
        val = amp if (i % period) < (period / 2) else -amp
        if i < fade_n:
            val *= i / fade_n
        elif i > n - fade_n:
            val *= (n - i) / fade_n
        samples.append(int(val))
    return samples


def _noise(duration: float, amp: int = MAX_AMP // 3, fade: float = 0.01) -> list[int]:
    """Génère du bruit blanc (pour percussions)."""
    n = int(SAMPLE_RATE * duration)
    fade_n = int(SAMPLE_RATE * fade)
    samples = []
    for i in range(n):
        val = random.randint(-amp, amp)
        if i < fade_n:
            val = int(val * i / fade_n)
        elif i > n - fade_n:
            val = int(val * (n - i) / fade_n)
        samples.append(val)
    return samples


def _silence(duration: float) -> list[int]:
    return [0] * int(SAMPLE_RATE * duration)


def _mix(*tracks) -> list[int]:
    """Mixe plusieurs pistes ensemble."""
    max_len = max(len(t) for t in tracks)
    result = [0] * max_len
    for track in tracks:
        for i, val in enumerate(track):
            result[i] += val
    # Clamp
    for i in range(len(result)):
        result[i] = max(-32000, min(32000, result[i]))
    return result


def _concat(*parts) -> list[int]:
    """Concatène plusieurs segments audio."""
    result = []
    for p in parts:
        result.extend(p)
    return result


def _samples_to_wav_bytes(samples: list[int]) -> bytes:
    """Convertit des échantillons int16 en données WAV en mémoire."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        raw = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(raw)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
#  Création des effets sonores
# ══════════════════════════════════════════════════════════════

def _make_move_sfx() -> bytes:
    """Court 'blip' pour un déplacement latéral."""
    s = _square(600, 0.03, amp=4000)
    return _samples_to_wav_bytes(s)


def _make_rotate_sfx() -> bytes:
    """Blip montant pour rotation."""
    s = _concat(_square(400, 0.025, amp=5000), _square(700, 0.025, amp=5000))
    return _samples_to_wav_bytes(s)


def _make_drop_sfx() -> bytes:
    """Son sourd pour le hard drop / verrouillage."""
    bass = _sine(80, 0.12, amp=10000)
    click = _noise(0.04, amp=6000)
    return _samples_to_wav_bytes(_mix(bass, click))


def _make_soft_drop_sfx() -> bytes:
    """Petit tick pour la descente."""
    s = _square(300, 0.015, amp=3000)
    return _samples_to_wav_bytes(s)


def _make_line_clear_sfx() -> bytes:
    """Son ascendant joyeux pour 1-3 lignes."""
    s = _concat(
        _square(NOTE["C5"], 0.06, amp=6000),
        _square(NOTE["E5"], 0.06, amp=6000),
        _square(NOTE["G5"], 0.08, amp=7000),
    )
    return _samples_to_wav_bytes(s)


def _make_tetris_sfx() -> bytes:
    """Fanfare pour un Tetris (4 lignes)."""
    melody = _concat(
        _square(NOTE["C5"], 0.07, amp=7000),
        _square(NOTE["E5"], 0.07, amp=7000),
        _square(NOTE["G5"], 0.07, amp=7000),
        _square(NOTE["C6"], 0.15, amp=8000),
    )
    bass = _concat(
        _sine(NOTE["C4"], 0.07, amp=5000),
        _sine(NOTE["C4"], 0.07, amp=5000),
        _sine(NOTE["E4"], 0.07, amp=5000),
        _sine(NOTE["G4"], 0.15, amp=6000),
    )
    return _samples_to_wav_bytes(_mix(melody, bass))


def _make_combo_sfx() -> bytes:
    """Son montant rapide pour combo."""
    s = _concat(
        _square(NOTE["E5"], 0.04, amp=5000),
        _square(NOTE["G5"], 0.04, amp=6000),
        _square(NOTE["B5"], 0.04, amp=6000),
        _square(NOTE["C6"], 0.06, amp=7000),
    )
    return _samples_to_wav_bytes(s)


def _make_level_up_sfx() -> bytes:
    """Arpège pour changement de niveau."""
    s = _concat(
        _square(NOTE["C4"], 0.05, amp=5000),
        _square(NOTE["E4"], 0.05, amp=5000),
        _square(NOTE["G4"], 0.05, amp=5000),
        _square(NOTE["C5"], 0.05, amp=6000),
        _square(NOTE["E5"], 0.05, amp=6000),
        _square(NOTE["G5"], 0.05, amp=6000),
        _square(NOTE["C6"], 0.10, amp=7000),
    )
    return _samples_to_wav_bytes(s)


def _make_hold_sfx() -> bytes:
    """Petit 'woosh' pour le hold."""
    s = _concat(
        _square(NOTE["A4"], 0.03, amp=4000),
        _square(NOTE["E4"], 0.03, amp=4000),
        _square(NOTE["A4"], 0.04, amp=5000),
    )
    return _samples_to_wav_bytes(s)


def _make_game_over_sfx() -> bytes:
    """Son descendant triste pour game over."""
    s = _concat(
        _square(NOTE["E4"], 0.15, amp=7000),
        _square(NOTE["D4"], 0.15, amp=6000),
        _square(NOTE["C4"], 0.15, amp=5000),
        _silence(0.05),
        _sine(NOTE["C3"], 0.40, amp=8000),
    )
    return _samples_to_wav_bytes(s)


def _make_tspin_sfx() -> bytes:
    """Son percutant pour T-Spin — montée dramatique + impact."""
    melody = _concat(
        _square(NOTE["C5"], 0.04, amp=6000),
        _square(NOTE["E5"], 0.04, amp=6500),
        _square(NOTE["G5"], 0.04, amp=7000),
        _square(NOTE["B5"], 0.04, amp=7500),
        _square(NOTE["C6"], 0.10, amp=8500),
    )
    impact = _noise(0.06, amp=5000)
    bass = _sine(NOTE["C3"], 0.26, amp=7000)
    return _samples_to_wav_bytes(_mix(melody, bass, _concat(_silence(0.16), impact)))


# ── Musique de fond (boucle) ─────────────────────────────────

def _make_bgm() -> bytes:
    """Vollständige Chiptune-Fassung von Korobeiniki (russ. Volkslied, 1861).

    Struktur: Intro → A → A' → B → A → Bridge → B → A → Outro
    """
    bpm = 150
    beat = 60.0 / bpm

    # Notenlängen
    h = beat * 2        # Halbe
    dq = beat * 1.5     # Punktierte Viertel
    q = beat            # Viertel
    e = beat / 2        # Achtel

    amp_m = 5500    # Melodie
    amp_h = 3000    # Harmonie / Gegenstimme
    amp_b = 4000    # Bass

    def msq(note, dur):
        """Melodie-Ton (Square, Staccato)."""
        gap = dur * 0.08
        return _concat(_square(NOTE.get(note, 0), dur - gap, amp=amp_m),
                        _silence(gap))

    def hsq(note, dur):
        """Harmonie-Ton (Square, leiser)."""
        gap = dur * 0.08
        return _concat(_square(NOTE.get(note, 0), dur - gap, amp=amp_h),
                        _silence(gap))

    def bs(note, dur):
        """Bass-Ton (Sinus)."""
        return _sine(NOTE.get(note, 0), dur, amp=amp_b)

    def rest(dur):
        return _silence(dur)

    # ══════════════════════════════════════════════════════════
    #  SECTION A — Thème principal (8 mesures)
    # ══════════════════════════════════════════════════════════
    # Mesure 1-2
    mel_a1 = _concat(
        msq("E5", q), msq("B4", e), msq("C5", e),
        msq("D5", q), msq("C5", e), msq("B4", e),
    )
    # Mesure 3-4
    mel_a2 = _concat(
        msq("A4", q), msq("A4", e), msq("C5", e),
        msq("E5", q), msq("D5", e), msq("C5", e),
    )
    # Mesure 5-6
    mel_a3 = _concat(
        msq("B4", dq), msq("C5", e),
        msq("D5", q), msq("E5", q),
    )
    # Mesure 7-8
    mel_a4 = _concat(
        msq("C5", q), msq("A4", q),
        msq("A4", h),
    )

    melody_a = _concat(mel_a1, mel_a2, mel_a3, mel_a4)

    # ── Bass Section A ────────────────────────────────────
    bass_a = _concat(
        # Mes 1-2: Am
        bs("A2", e), bs("E3", e), bs("A3", e), bs("E3", e),
        bs("A2", e), bs("E3", e), bs("A3", e), bs("E3", e),
        # Mes 3-4: Am → C
        bs("A2", e), bs("E3", e), bs("A3", e), bs("E3", e),
        bs("C3", e), bs("G3", e), bs("C3", e), bs("G3", e),
        # Mes 5-6: G → Em
        bs("G3", e), bs("D3", e), bs("G3", e), bs("D3", e),
        bs("E2", e), bs("B2", e), bs("E3", e), bs("B2", e),
        # Mes 7-8: Am
        bs("A2", e), bs("E3", e), bs("A3", e), bs("E3", e),
        bs("A2", e), bs("E3", e), bs("A2", q),
    )

    # ══════════════════════════════════════════════════════════
    #  SECTION A' — Thème avec variations (8 mesures)
    # ══════════════════════════════════════════════════════════
    mel_a1v = _concat(
        msq("E5", q), msq("B4", e), msq("C5", e),
        msq("D5", e), msq("E5", e), msq("C5", e), msq("B4", e),
    )
    mel_a2v = _concat(
        msq("A4", q), msq("A4", e), msq("C5", e),
        msq("E5", e), msq("G5", e), msq("D5", e), msq("C5", e),
    )
    mel_a3v = _concat(
        msq("B4", dq), msq("C5", e),
        msq("D5", q), msq("E5", q),
    )
    mel_a4v = _concat(
        msq("C5", q), msq("A4", q),
        msq("A4", q), rest(q),
    )

    melody_av = _concat(mel_a1v, mel_a2v, mel_a3v, mel_a4v)

    # ══════════════════════════════════════════════════════════
    #  SECTION B — Deuxième thème (8 mesures)
    # ══════════════════════════════════════════════════════════
    # Mesure 1-2
    mel_b1 = _concat(
        msq("D5", q), msq("F5", e), msq("A5", q),
        msq("G5", e),
    )
    # Mesure 3-4
    mel_b2 = _concat(
        msq("F5", q), msq("E5", e), msq("C5", e),
        msq("E5", q), msq("D5", e), msq("C5", e),
    )
    # Mesure 5-6
    mel_b3 = _concat(
        msq("B4", dq), msq("C5", e),
        msq("D5", q), msq("E5", q),
    )
    # Mesure 7-8
    mel_b4 = _concat(
        msq("C5", q), msq("A4", q),
        msq("A4", h),
    )

    melody_b = _concat(mel_b1, mel_b2, mel_b3, mel_b4)

    # ── Bass Section B ────────────────────────────────────
    bass_b = _concat(
        # Mes 1-2: Dm → F
        bs("D3", e), bs("A3", e), bs("D3", e), bs("A3", e),
        bs("F3", e), bs("C3", e), bs("F3", e), bs("C3", e),
        # Mes 3-4: C → Am
        bs("C3", e), bs("G3", e), bs("C3", e), bs("G3", e),
        bs("A2", e), bs("E3", e), bs("A2", e), bs("E3", e),
        # Mes 5-6: G → Em
        bs("G3", e), bs("D3", e), bs("G3", e), bs("D3", e),
        bs("E2", e), bs("B2", e), bs("E3", e), bs("B2", e),
        # Mes 7-8: Am
        bs("A2", e), bs("E3", e), bs("A3", e), bs("E3", e),
        bs("A2", e), bs("E3", e), bs("A2", q),
    )

    # ══════════════════════════════════════════════════════════
    #  BRIDGE — Pont musical (4 mesures)
    # ══════════════════════════════════════════════════════════
    mel_br = _concat(
        msq("E5", e), msq("C5", e), msq("D5", e), msq("B4", e),
        msq("C5", e), msq("A4", e), msq("B4", e), msq("G4", e),
        msq("A4", q), msq("A4", e), msq("B4", e),
        msq("C5", q), msq("D5", q),
        msq("E5", q), msq("C5", q),
        msq("B4", q), rest(q),
    )

    bass_br = _concat(
        bs("A2", e), bs("E3", e), bs("A2", e), bs("E3", e),
        bs("E2", e), bs("B2", e), bs("E2", e), bs("B2", e),
        bs("A2", e), bs("E3", e), bs("A3", e), bs("E3", e),
        bs("D3", e), bs("A3", e), bs("D3", q),
        bs("C3", e), bs("G3", e), bs("C3", q),
        bs("E2", e), bs("B2", e), bs("E2", q),
    )

    # ══════════════════════════════════════════════════════════
    #  HARMONIE — Gegenstimme für Section A (Terzen/Sexten)
    # ══════════════════════════════════════════════════════════
    harm_a = _concat(
        hsq("C5", q), hsq("G4", e), hsq("A4", e),
        hsq("B4", q), hsq("A4", e), hsq("G4", e),
        hsq("E4", q), hsq("E4", e), hsq("A4", e),
        hsq("C5", q), hsq("B4", e), hsq("A4", e),
        hsq("G4", dq), hsq("A4", e),
        hsq("B4", q), hsq("C5", q),
        hsq("A4", q), hsq("E4", q),
        hsq("E4", h),
    )

    # ══════════════════════════════════════════════════════════
    #  ASSEMBLAGE — Structure complète
    # ══════════════════════════════════════════════════════════
    def mix_section(mel, bas, har=None):
        """Mixe mélodie + basse (+ harmonie optionnelle)."""
        max_len = max(len(mel), len(bas))
        mel_pad = mel + [0] * (max_len - len(mel))
        bas_pad = bas + [0] * (max_len - len(bas))
        if har:
            har_pad = har + [0] * (max_len - len(har))
            return _mix(mel_pad, bas_pad, har_pad)
        return _mix(mel_pad, bas_pad)

    sec_a      = mix_section(melody_a,  bass_a)
    sec_av     = mix_section(melody_av, bass_a)
    sec_a_harm = mix_section(melody_a,  bass_a, harm_a)
    sec_b      = mix_section(melody_b,  bass_b)
    sec_br     = mix_section(mel_br,    bass_br)

    # Structure : A → A' → B → A(+harm) → Bridge → B → A(+harm) → A
    full = _concat(
        sec_a,          # 1. Thème simple
        sec_av,         # 2. Thème varié
        sec_b,          # 3. Deuxième thème
        sec_a_harm,     # 4. Retour avec harmonie
        sec_br,         # 5. Pont
        sec_b,          # 6. Deuxième thème
        sec_a_harm,     # 7. Retour avec harmonie
        sec_a,          # 8. Conclusion simple
    )

    return _samples_to_wav_bytes(full)


# ══════════════════════════════════════════════════════════════
#  Cache disque des sons pré-calculés
# ══════════════════════════════════════════════════════════════

AUDIO_DIR = asset("audio")
BGM_NAME = "bgm"


def _asset_path(name: str) -> str:
    return os.path.join(AUDIO_DIR, f"{name}.wav")


def load_or_generate(name: str, generator) -> bytes:
    """Retourne les octets WAV d'un son : depuis le cache disque s'il existe,
    sinon en le générant (puis en l'écrivant sur disque si possible)."""
    path = _asset_path(name)
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        pass

    data = generator()
    if not is_frozen():                       # le dossier d'un .exe est en lecture seule
        try:
            os.makedirs(AUDIO_DIR, exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        except OSError:
            pass
    return data


def export_all(force: bool = False) -> list[str]:
    """Pré-calcule tous les sons dans assets/audio/. Retourne les fichiers écrits."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    generators = dict(AudioManager.SFX_GENERATORS)
    generators[BGM_NAME] = _make_bgm
    written = []
    for name, gen in generators.items():
        path = _asset_path(name)
        if force or not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(gen())
            written.append(path)
    return written


# ══════════════════════════════════════════════════════════════
#  Classe principale AudioManager
# ══════════════════════════════════════════════════════════════

class AudioManager:
    """Gestionnaire audio centralisé.

    Utilisation :
        audio = AudioManager()
        audio.play_sfx("drop")
        audio.play_bgm()
        audio.set_sfx_volume(0.5)
    """

    SFX_GENERATORS = {
        "move":       _make_move_sfx,
        "rotate":     _make_rotate_sfx,
        "drop":       _make_drop_sfx,
        "soft_drop":  _make_soft_drop_sfx,
        "line_clear": _make_line_clear_sfx,
        "tetris":     _make_tetris_sfx,
        "tspin":      _make_tspin_sfx,
        "combo":      _make_combo_sfx,
        "level_up":   _make_level_up_sfx,
        "hold":       _make_hold_sfx,
        "game_over":  _make_game_over_sfx,
    }

    def __init__(self):
        self.available = False
        self._sounds: dict = {}
        self._bgm_tmpfile: str | None = None
        self._sfx_volume: float = 0.6
        self._bgm_volume: float = 0.3
        self._bgm_playing = False

        if not _AUDIO_AVAILABLE:
            return

        try:
            _mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.available = True
        except Exception:
            return

        # Charger (ou générer) tous les SFX.
        # NB : file= (et non buffer=) pour que pygame lise l'en-tête WAV
        # au lieu de le jouer comme des échantillons (petit « clic »).
        for name, gen_func in self.SFX_GENERATORS.items():
            try:
                wav_bytes = load_or_generate(name, gen_func)
                self._sounds[name] = _mixer.Sound(file=io.BytesIO(wav_bytes))
                self._sounds[name].set_volume(self._sfx_volume)
            except Exception:
                pass

        # La BGM est chargée paresseusement au premier play_bgm()
        self._bgm_tmpfile = None

    # ── Lecture SFX ───────────────────────────────────────────
    def play_sfx(self, name: str):
        """Joue un effet sonore par nom."""
        if not self.available:
            return
        sound = self._sounds.get(name)
        if sound:
            sound.play()

    # ── Lecture BGM ───────────────────────────────────────────
    def _bgm_source(self) -> str | None:
        """Chemin d'un fichier WAV lisible par pygame.mixer.music.

        1. le fichier pré-calculé assets/audio/bgm.wav ;
        2. sinon génération + un SEUL fichier temporaire réutilisé
           (l'ancienne version en créait un nouveau à chaque partie).
        """
        path = _asset_path(BGM_NAME)
        if os.path.exists(path):
            return path
        if self._bgm_tmpfile and os.path.exists(self._bgm_tmpfile):
            return self._bgm_tmpfile
        data = load_or_generate(BGM_NAME, _make_bgm)
        if os.path.exists(path):              # le cache vient d'être écrit
            return path
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="tetris_bgm_")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        self._bgm_tmpfile = tmp
        return tmp

    def play_bgm(self):
        """Démarre la musique de fond en boucle."""
        if not self.available:
            return
        try:
            src = self._bgm_source()
            if not src:
                return
            _mixer.music.load(src)
            _mixer.music.set_volume(self._bgm_volume)
            _mixer.music.play(loops=-1)  # boucle infinie
            self._bgm_playing = True
        except Exception:
            pass

    def stop_bgm(self):
        """Arrête la musique de fond."""
        if not self.available:
            return
        try:
            _mixer.music.stop()
            self._bgm_playing = False
        except Exception:
            pass

    def pause_bgm(self):
        if not self.available:
            return
        try:
            _mixer.music.pause()
        except Exception:
            pass

    def unpause_bgm(self):
        if not self.available:
            return
        try:
            _mixer.music.unpause()
        except Exception:
            pass

    # ── Volume ────────────────────────────────────────────────
    def set_sfx_volume(self, vol: float):
        """Règle le volume des SFX (0.0 à 1.0)."""
        self._sfx_volume = max(0.0, min(1.0, vol))
        for sound in self._sounds.values():
            try:
                sound.set_volume(self._sfx_volume)
            except Exception:
                pass

    def set_bgm_volume(self, vol: float):
        """Règle le volume de la musique (0.0 à 1.0)."""
        self._bgm_volume = max(0.0, min(1.0, vol))
        if self.available:
            try:
                _mixer.music.set_volume(self._bgm_volume)
            except Exception:
                pass

    @property
    def sfx_volume(self) -> float:
        return self._sfx_volume

    @property
    def bgm_volume(self) -> float:
        return self._bgm_volume

    # ── Nettoyage ─────────────────────────────────────────────
    def cleanup(self):
        """Libère les ressources."""
        self.stop_bgm()
        try:
            if self._bgm_tmpfile and os.path.exists(self._bgm_tmpfile):
                _mixer.music.unload()
                os.unlink(self._bgm_tmpfile)
        except Exception:
            pass


# ── Instance globale (singleton) ──────────────────────────────
_audio_instance: AudioManager | None = None


def get_audio() -> AudioManager:
    """Retourne l'instance audio globale (créée au premier appel)."""
    global _audio_instance
    if _audio_instance is None:
        _audio_instance = AudioManager()
    return _audio_instance


# ── Ligne de commande : pré-calcul des sons ──────────────────
if __name__ == "__main__":
    force = "--force" in sys.argv
    if "--export" in sys.argv or force:
        files = export_all(force=force)
        print(f"{len(files)} fichier(s) écrit(s) dans {AUDIO_DIR}")
        for f in files:
            print("  ", os.path.relpath(f))
    else:
        print("Usage : python audio.py --export [--force]")
