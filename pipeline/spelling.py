"""Key-aware note spelling.

Every key is spelled from a parent major key so that each scale letter appears
once. The parent major names below match HookTheory annotators' own choices
(Db, Eb, Ab, Bb, F#, B), which also yields their conventional minor and modal
tonics (F# minor, D# minor, A# Phrygian, Gb Lydian, ...).
"""

from __future__ import annotations

from functools import lru_cache

from .common import DEGREE_LABELS, scale_semitones

LETTERS = "CDEFGAB"
NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJOR_KEY_NAMES = {0: "C", 1: "Db", 2: "D", 3: "Eb", 4: "E", 5: "F", 6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}

# Position of each mode's tonic in its parent major scale. Harmonic minor and
# Phrygian dominant borrow the key signature of natural minor and Phrygian.
MODE_ROTATION = {
    "major": 0,
    "dorian": 1,
    "phrygian": 2,
    "phrygian_dominant": 2,
    "lydian": 3,
    "mixolydian": 4,
    "minor": 5,
    "harmonic_minor": 5,
    "locrian": 6,
}
MAJOR_SEMITONES = scale_semitones("major")


def accidental(n: int) -> str:
    return "#" * n if n > 0 else "b" * -n


def name_for(letter: str, pc: int) -> tuple[str, int]:
    """Spell `pc` on `letter`; returns (name, accidental count, + sharp / - flat)."""
    diff = (pc - NATURAL_PC[letter]) % 12
    if diff > 6:
        diff -= 12
    return letter + accidental(diff), diff


def _spell_scale_from(tonic_name: str, semitones: list[int]) -> list[str]:
    letter_index = LETTERS.index(tonic_name[0])
    tonic_pc = pc_of(tonic_name)
    names = []
    for i, s in enumerate(semitones):
        names.append(name_for(LETTERS[(letter_index + i) % 7], (tonic_pc + s) % 12)[0])
    return names


def pc_of(name: str) -> int:
    pc = NATURAL_PC[name[0]]
    for ch in name[1:]:
        pc += 1 if ch == "#" else -1
    return pc % 12


@lru_cache(maxsize=None)
def tonic_name(tonic_pc: int, mode: str) -> str:
    rotation = MODE_ROTATION[mode]
    parent_pc = (tonic_pc - MAJOR_SEMITONES[rotation]) % 12
    parent_scale = _spell_scale_from(MAJOR_KEY_NAMES[parent_pc], MAJOR_SEMITONES)
    return parent_scale[rotation]


@lru_cache(maxsize=None)
def scale_names(tonic_pc: int, mode: str) -> tuple[str, ...]:
    """Spelled scale tones of the key, one letter each."""
    return tuple(_spell_scale_from(tonic_name(tonic_pc, mode), scale_semitones(mode)))


@lru_cache(maxsize=None)
def key_direction(tonic_pc: int, mode: str) -> int:
    """+1 for sharp keys, -1 for flat keys, 0 for C major and its modes."""
    total = sum(name_for(n[0], pc_of(n))[1] for n in scale_names(tonic_pc, mode))
    return (total > 0) - (total < 0)


def _simple_name(pc: int, direction: int) -> str:
    for letter, natural in NATURAL_PC.items():
        if natural == pc:
            return letter
    if direction > 0:
        return name_for(LETTERS[[NATURAL_PC[l] for l in LETTERS].index((pc - 1) % 12)], pc)[0]
    return name_for(LETTERS[[NATURAL_PC[l] for l in LETTERS].index((pc + 1) % 12)], pc)[0]


@lru_cache(maxsize=None)
def spell(pc: int, tonic_pc: int, mode: str) -> str:
    """Name for pitch class `pc` in the given key.

    Scale tones use the key's letters (E# in F# major) unless that needs a
    double accidental, which only happens in rare keys. Chromatic tones follow
    their do-based degree label (b7 of E is D, #4 of C is F#), falling back to
    a plain sharp or flat name per the key direction when that label would
    need a double accidental or an odd spelling like B# or Fb.
    """
    pc %= 12
    semis = (pc - tonic_pc) % 12
    scale = scale_semitones(mode)
    if semis in scale:
        name = scale_names(tonic_pc, mode)[scale.index(semis)]
        if len(name) <= 2:
            return name
        # Double accidental (C## in D# harmonic minor): use the plain name.
        return _simple_name(pc, key_direction(tonic_pc, mode))

    label = DEGREE_LABELS[semis]
    degree = int(label.lstrip("b#"))
    tonic = tonic_name(tonic_pc, mode)
    letter = LETTERS[(LETTERS.index(tonic[0]) + degree - 1) % 7]
    name, acc = name_for(letter, pc)
    if abs(acc) <= 1 and name not in ("B#", "Cb", "E#", "Fb"):
        return name
    direction = key_direction(tonic_pc, mode) or (1 if label.startswith("#") else -1)
    return _simple_name(pc, direction)


def key_label(tonic_pc: int, mode: str) -> str:
    pretty = {"harmonic_minor": "harmonic minor", "phrygian_dominant": "Phrygian dominant"}
    mode_text = pretty.get(mode, mode if mode in ("major", "minor") else mode.capitalize())
    return f"{tonic_name(tonic_pc, mode)} {mode_text}"
