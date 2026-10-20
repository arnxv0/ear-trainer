"""Chord quality from `root_position_intervals`, plus bass, pitch classes and symbols.

The table is keyed by the dataset's stacked intervals (each relative to the
previous chord tone). Entries beyond the spec's starting table were confirmed
against HookTheory's own chord descriptors in the Raw file (type, adds,
suspensions, alterations). Tuples not listed map to quality "other" and are
excluded from quality questions.

Run `python -m pipeline.chords` to print every distinct tuple with its count.
"""

from __future__ import annotations

from dataclasses import dataclass

from .spelling import spell


@dataclass(frozen=True)
class Quality:
    id: str
    symbol: str  # suffix after the root name, e.g. "m7"
    numeral: str  # suffix after the Roman numeral, e.g. "ø7"
    upper: bool  # Roman numeral case: upper for major/dominant/aug/sus


def _q(id, symbol, numeral, upper):
    return Quality(id, symbol, numeral, upper)


QUALITIES: dict[tuple[int, ...], Quality] = {
    # Triads, dyads and suspensions
    (4, 3): _q("maj", "", "", True),
    (3, 4): _q("min", "m", "", False),
    (3, 3): _q("dim", "dim", "°", False),
    (4, 4): _q("aug", "aug", "+", True),
    (2, 5): _q("sus2", "sus2", "sus2", True),
    (5, 2): _q("sus4", "sus4", "sus4", True),
    (2, 3, 2): _q("sus2sus4", "sus2sus4", "sus2sus4", True),
    (6, 1): _q("sus#4", "sus#4", "sus#4", True),  # diatonic sus4 on IV
    (7,): _q("power", "5", "5", True),
    # Sevenths
    (4, 3, 3): _q("dom7", "7", "7", True),
    (4, 3, 4): _q("maj7", "maj7", "maj7", True),
    (3, 4, 3): _q("min7", "m7", "7", False),
    (3, 3, 4): _q("m7b5", "m7b5", "ø7", False),
    (3, 3, 3): _q("dim7", "dim7", "°7", False),
    (3, 4, 4): _q("minmaj7", "m(maj7)", "(maj7)", False),
    (5, 2, 3): _q("7sus4", "7sus4", "7sus4", True),
    (2, 5, 3): _q("7sus2", "7sus2", "7sus2", True),
    (5, 2, 4): _q("maj7sus4", "maj7sus4", "maj7sus4", True),
    (2, 5, 4): _q("maj7sus2", "maj7sus2", "maj7sus2", True),
    (4, 4, 2): _q("aug7", "7#5", "+7", True),
    (4, 4, 3): _q("augmaj7", "maj7#5", "+maj7", True),
    (4, 2, 4): _q("7b5", "7b5", "7b5", True),
    # Added tones
    (4, 3, 7): _q("add9", "add9", "add9", True),
    (3, 4, 7): _q("madd9", "m(add9)", "add9", False),
    (4, 3, 10): _q("add11", "add11", "add11", True),
    (3, 4, 10): _q("madd11", "m(add11)", "add11", False),
    (4, 3, 14): _q("6", "6", "6", True),  # HookTheory voices the added 6th above the octave
    (3, 4, 14): _q("m6", "m6", "6", False),
    (4, 3, 7, 7): _q("6/9", "6/9", "6/9", True),
    (3, 4, 3, 7): _q("min7add11", "m7(add11)", "7(add11)", False),
    # Extended and altered dominants
    (4, 3, 3, 4): _q("dom9", "9", "9", True),
    (4, 3, 4, 3): _q("maj9", "maj9", "maj9", True),
    (3, 4, 3, 4): _q("min9", "m9", "9", False),
    (4, 3, 3, 4, 3): _q("dom11", "11", "11", True),
    (3, 4, 3, 4, 3): _q("min11", "m11", "11", False),
    (4, 3, 4, 3, 4): _q("maj9#11", "maj9(#11)", "maj9(#11)", True),
    (4, 3, 3, 4, 3, 4): _q("dom13", "13", "13", True),
    (4, 3, 3, 3): _q("7b9", "7b9", "7b9", True),
    (4, 3, 3, 5): _q("7#9", "7#9", "7#9", True),
    (4, 3, 3, 10): _q("7b13", "7b13", "7b13", True),
}
OTHER = Quality("other", "?", "?", True)

# Qualities whose chord carries a dominant function (major 3rd + minor 7th).
DOMINANT_QUALITIES = {"dom7", "dom9", "dom11", "dom13", "7b9", "7#9", "7b13", "7b5"}
DIMINISHED_QUALITIES = {"dim", "dim7", "m7b5"}
SEVENTH_OR_EXTENDED = {
    "dom7", "maj7", "min7", "m7b5", "dim7", "minmaj7", "7sus4", "7sus2", "maj7sus4", "maj7sus2",
    "aug7", "augmaj7", "7b5", "add9", "madd9", "add11", "madd11", "6", "m6", "6/9", "min7add11",
    "dom9", "maj9", "min9", "dom11", "min11", "maj9#11", "dom13", "7b9", "7#9", "7b13",
}


def quality(intervals) -> Quality:
    return QUALITIES.get(tuple(intervals), OTHER)


def chord_tones(root_pc: int, intervals) -> list[int]:
    """Absolute pitch classes in root-position order (root, 3rd, 5th, ...)."""
    tones, acc = [root_pc % 12], 0
    for step in intervals:
        acc += step
        tones.append((root_pc + acc) % 12)
    return tones


def bass_pc(root_pc: int, intervals, inversion: int) -> int:
    tones = chord_tones(root_pc, intervals)
    return tones[inversion] if 0 <= inversion < len(tones) else tones[0]


def symbol(root_pc: int, intervals, inversion: int, tonic_pc: int, mode: str) -> tuple[str, str | None]:
    """Chord symbol spelled in the key, plus the slash bass name (or None)."""
    q = quality(intervals)
    name = spell(root_pc, tonic_pc, mode) + (q.symbol if q is not OTHER else "")
    bass = bass_pc(root_pc, intervals, inversion)
    if bass == root_pc % 12:
        return name, None
    slash = spell(bass, tonic_pc, mode)
    return f"{name}/{slash}", slash


def main() -> None:
    import collections
    import gzip
    import itertools
    import json

    from .common import DATASET_PATH

    data = json.load(gzip.open(DATASET_PATH))
    counts = collections.Counter(
        tuple(h["root_position_intervals"]) for e in data.values() for h in (e["annotations"]["harmony"] or [])
    )
    total = sum(counts.values())
    known = sum(n for k, n in counts.items() if k in QUALITIES)
    print(f"{len(counts)} distinct interval tuples, {total} chord instances")
    print(f"Mapped to a known quality: {known / total:.2%}\n")
    for tup, n in counts.most_common():
        semis = list(itertools.accumulate((0, *tup)))
        print(f"{str(list(tup)):24} {n:8}  semitones {semis!s:28} {quality(tup).id}")


if __name__ == "__main__":
    main()
