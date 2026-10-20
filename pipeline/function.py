"""Roman numerals and harmonic function of chords within a key.

Numerals are do-based: the numeral comes from the root's semitone distance to
the tonic, so a minor key reads i, ii°, bIII, iv, v, bVI, bVII and modal keys
read relative to the modal tonic (Mixolydian: I, ii, iii°, IV, v, vi, bVII).

Function classes: diatonic, borrowed, secondary, chromatic. When the HookTheory
Raw file is available its explicit `applied` / `borrowed` fields win (see
`raw_function`) and this classifier is the fallback.
"""

from __future__ import annotations

from functools import lru_cache

from .chords import DIMINISHED_QUALITIES, DOMINANT_QUALITIES, Quality, chord_tones, quality
from .common import DEGREE_LABELS, RAW_MODE_NAMES, scale_pcs, scale_semitones

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]

# Parallel modes a key may borrow from, in preference order.
PARALLEL_MODES = {
    "major": ["minor", "mixolydian", "dorian"],
    "minor": ["major"],
    "harmonic_minor": ["major"],
}
DEFAULT_PARALLEL = ["major", "minor"]
MODE_TEXT = {"minor": "minor", "major": "major", "harmonic_minor": "harmonic minor", "phrygian_dominant": "Phrygian dominant"}


def mode_text(mode: str) -> str:
    return MODE_TEXT.get(mode, mode.capitalize())


def numeral(semitones: int, q: Quality, with_suffix: bool = True) -> str:
    """Roman numeral for a chord whose root is `semitones` above the tonic."""
    label = DEGREE_LABELS[semitones % 12]
    prefix = label.rstrip("1234567")
    base = ROMAN[int(label[len(prefix):]) - 1]
    base = base if q.upper else base.lower()
    return prefix + base + (q.numeral if with_suffix and q.id != "other" else "")


@lru_cache(maxsize=None)
def diatonic_triads(mode: str) -> dict[int, str]:
    """Semitone above tonic -> triad quality id for each scale degree."""
    semis = scale_semitones(mode)
    out = {}
    for i, root in enumerate(semis):
        third = (semis[(i + 2) % 7] - root) % 12
        fifth = (semis[(i + 4) % 7] - root) % 12
        out[root] = {(4, 7): "maj", (3, 7): "min", (3, 6): "dim", (4, 8): "aug"}.get((third, fifth), "other")
    return out


def _target_numeral(target_semis: int, mode: str) -> str | None:
    """Numeral of the diatonic triad a secondary chord points at (major/minor only, not I)."""
    triad = diatonic_triads(mode).get(target_semis % 12)
    if target_semis % 12 == 0 or triad not in ("maj", "min"):
        return None
    return numeral(target_semis, quality((4, 3) if triad == "maj" else (3, 4)))


def _borrowed_sources(pcs: set[int], tonic_pc: int, mode: str) -> list[str]:
    return [m for m in PARALLEL_MODES.get(mode, [m for m in DEFAULT_PARALLEL if m != mode]) if pcs <= scale_pcs(tonic_pc, m)]


def classify(root_pc: int, intervals, tonic_pc: int, mode: str) -> dict:
    """Return {"function", "label", "borrowed_from"} for a chord in a key."""
    q = quality(intervals)
    pcs = set(chord_tones(root_pc, intervals))
    semis = (root_pc - tonic_pc) % 12
    rn = numeral(semis, q)

    def result(function, label=rn, borrowed_from=None):
        return {"function": function, "label": label, "borrowed_from": borrowed_from}

    if pcs <= scale_pcs(tonic_pc, mode):
        return result("diatonic")
    if mode == "minor" and pcs <= scale_pcs(tonic_pc, "harmonic_minor"):
        # V, V7 and vii° with the raised leading tone are part of minor-key harmony.
        return result("diatonic", f"{rn} (harmonic minor)")

    secondary_target = _target_numeral(semis + 5, mode)
    if q.id in DOMINANT_QUALITIES and secondary_target:
        return result("secondary", f"V{q.numeral}/{secondary_target}")

    sources = _borrowed_sources(pcs, tonic_pc, mode)
    if sources:
        return result("borrowed", f"{rn} (borrowed from {'/'.join(mode_text(s) for s in sources)})", sources)

    if q.id == "maj" and secondary_target:
        return result("secondary", f"V/{secondary_target}")
    leading_target = _target_numeral(semis + 1, mode)
    if q.id in DIMINISHED_QUALITIES and leading_target:
        return result("secondary", f"vii{q.numeral}/{leading_target}")
    return result("chromatic")


def raw_function(raw_chord: dict, root_pc: int, intervals, tonic_pc: int, mode: str) -> dict | None:
    """HookTheory's own label for a chord, or None when it gives no explicit one.

    In the Raw file an applied chord stores the *target* degree in `root` and its
    function relative to that target in `applied` (root=5, applied=5 is V/V).
    `borrowed` is a mode name, or an opaque scale array we cannot interpret.
    """
    q = quality(intervals)
    semis = (root_pc - tonic_pc) % 12
    applied = raw_chord.get("applied") or 0
    if applied:
        target_degree = raw_chord.get("root")
        if not isinstance(target_degree, int) or not 1 <= target_degree <= 7:
            return None
        target_semis = scale_semitones(mode)[target_degree - 1]
        triad = diatonic_triads(mode).get(target_semis, "maj")
        target = numeral(target_semis, quality((3, 4) if triad in ("min", "dim") else (4, 3)))
        if triad == "dim":
            target += "°"
        own = numeral((root_pc - tonic_pc - target_semis) % 12, q)
        return {"function": "secondary", "label": f"{own}/{target}", "borrowed_from": None}

    borrowed = raw_chord.get("borrowed")
    if isinstance(borrowed, str) and borrowed in RAW_MODE_NAMES:
        source = RAW_MODE_NAMES[borrowed]
        if source == mode:
            return None
        rn = numeral(semis, q)
        return {"function": "borrowed", "label": f"{rn} (borrowed from {mode_text(source)})", "borrowed_from": [source]}
    return None


def resolve_function(raw_chord: dict | None, root_pc: int, intervals, tonic_pc: int, mode: str):
    """Pick the chord's function: HookTheory's explicit label, else our rules.

    Returns (function dict, source, disagreement) where disagreement is None or
    a short tag naming how the two labels differ. Two HookTheory conventions are
    overridden because they would file chords under the wrong curriculum level:
    an applied chord aimed at the tonic (its "V/i" is just V), and a "borrowed"
    chord whose notes all sit in the home key, which includes the harmonic-minor
    V and vii° that level P5 teaches as minor-key diatonic.
    """
    rules = classify(root_pc, intervals, tonic_pc, mode)
    explicit = raw_function(raw_chord, root_pc, intervals, tonic_pc, mode) if raw_chord else None
    if explicit is None:
        return rules, "rules", None
    if explicit["function"] == "secondary" and raw_chord.get("root") == 1:
        return rules, "rules", "override:applied_to_tonic"
    if explicit["function"] == "borrowed" and rules["function"] == "diatonic":
        return rules, "rules", "override:borrowed_but_in_key"
    if explicit["function"] != rules["function"]:
        return explicit, "hooktheory", f"{explicit['function']}->{rules['function']}"
    return explicit, "hooktheory", None
