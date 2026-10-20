"""Difficulty prior for segments, notes and chords.

Surface features plus surprisal from an order-3 interpolated n-gram model
(Witten-Bell smoothing) trained on TRAIN only. This is only a prior; the live
Elo ratings in the backend correct it.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import Counter, defaultdict
from statistics import mean, pstdev

from .tagging import merge_repeats

ORDER = 3

MELODY_WEIGHTS = {
    "range": 1.0,
    "mean_interval": 1.0,
    "max_interval": 0.5,
    "leap_ratio": 1.0,
    "chromatic_fraction": 1.5,
    "notes_per_second": 1.0,
    "distinct_degrees": 0.75,
    "melody_surprisal": 2.0,
}
HARMONY_WEIGHTS = {
    "chords_per_bar": 1.0,
    "non_diatonic_fraction": 1.5,
    "extended_fraction": 1.0,
    "has_inversions": 0.5,
    "harmony_surprisal": 2.0,
}


class NGramModel:
    """Interpolated Witten-Bell n-gram model over string tokens."""

    def __init__(self, order: int = ORDER):
        self.order = order
        self.counts: dict[tuple, Counter] = defaultdict(Counter)
        self.vocab: set[str] = set()

    @staticmethod
    def start(mode: str) -> str:
        return f"<{mode}>"

    def fit(self, sequences) -> "NGramModel":
        for start, seq in sequences:
            padded = [start] * self.order + list(seq)
            self.vocab.update(seq)
            for i in range(self.order, len(padded)):
                for k in range(self.order + 1):
                    self.counts[tuple(padded[i - k : i])][padded[i]] += 1
        self._totals = {h: sum(c.values()) for h, c in self.counts.items()}
        return self

    def prob(self, history: tuple, token: str) -> float:
        p = 1.0 / (len(self.vocab) + 1)  # uniform base, +1 for unseen tokens
        for k in range(self.order + 1):
            h = tuple(history[len(history) - k :]) if k else ()
            c = self.counts.get(h)
            if not c:
                break
            total, types = self._totals[h], len(c)
            p = (c[token] + types * p) / (total + types)
        return p

    def surprisals(self, start: str, seq) -> list[float]:
        padded = [start] * self.order + list(seq)
        return [-math.log2(self.prob(tuple(padded[i - self.order : i]), padded[i])) for i in range(self.order, len(padded))]


def melody_tokens(seg):
    return [n["deg"] for n in seg["notes"]]


def harmony_tokens(seg):
    return [c["roman"] for c in merge_repeats(seg["chords"])]


def fit_models(train_segments):
    start = lambda s: NGramModel.start(s["key"]["mode"])  # noqa: E731
    melody = NGramModel().fit((start(s), melody_tokens(s)) for s in train_segments)
    harmony = NGramModel().fit((start(s), harmony_tokens(s)) for s in train_segments if s["chords"])
    return melody, harmony


def features(seg, melody_model, harmony_model) -> dict:
    notes, chords = seg["notes"], seg["chords"]
    duration = max(seg["end"] - seg["start"], 1e-6)
    midis = [n["midi"] for n in notes]
    ints = [abs(b - a) for a, b in zip(midis, midis[1:])]
    moves = [i for i in ints if i]
    start = NGramModel.start(seg["key"]["mode"])

    mel_s = melody_model.surprisals(start, melody_tokens(seg)) if notes else []
    for n, s in zip(notes, mel_s):
        n["s"] = round(s, 2)
    merged = harmony_tokens(seg)
    har_s = harmony_model.surprisals(start, merged) if merged else []
    # Map surprisal of each merged chord back onto every chord instance it covers.
    i = -1
    prev = None
    for c in chords:
        if c["roman"] != prev:
            i += 1
            prev = c["roman"]
        c["s"] = round(har_s[i], 2) if i < len(har_s) else None

    feats = {
        "range": (max(midis) - min(midis)) if midis else 0,
        "mean_interval": mean(ints) if ints else 0.0,
        "max_interval": max(ints) if ints else 0,
        "leap_ratio": sum(i >= 7 for i in moves) / len(moves) if moves else 0.0,
        "chromatic_fraction": sum(n["deg"] in seg["tags"]["chromatic_degrees"] for n in notes) / len(notes) if notes else 0.0,
        "notes_per_second": len(notes) / duration,
        "distinct_degrees": len({n["deg"] for n in notes}),
        "melody_surprisal": mean(mel_s) if mel_s else 0.0,
    }
    if chords:
        bars = max(len(seg["bars"]), 1)
        feats.update(
            {
                "chords_per_bar": len(merge_repeats(chords)) / bars,
                "non_diatonic_fraction": sum(c["function"] != "diatonic" for c in chords) / len(chords),
                "extended_fraction": sum(c["extended"] for c in chords) / len(chords),
                "has_inversions": float(any(c["inversion"] for c in chords)),
                "harmony_surprisal": mean(har_s) if har_s else 0.0,
            }
        )
    return feats


class Scorer:
    """Weighted z-score sums, mapped to 0..1 by percentile within TRAIN."""

    def __init__(self, train_features):
        keys = set(MELODY_WEIGHTS) | set(HARMONY_WEIGHTS)
        self.stats = {}
        for k in keys:
            vals = [f[k] for f in train_features if k in f]
            self.stats[k] = (mean(vals), pstdev(vals) or 1.0) if vals else (0.0, 1.0)
        self.melody_ref = sorted(self._raw(f, MELODY_WEIGHTS) for f in train_features)
        self.harmony_ref = sorted(self._raw(f, HARMONY_WEIGHTS) for f in train_features if "harmony_surprisal" in f)
        self.overall_ref = sorted(self._overall_raw(f) for f in train_features)

    def _z(self, f, k):
        mu, sd = self.stats[k]
        return (f[k] - mu) / sd

    def _raw(self, f, weights):
        return sum(w * self._z(f, k) for k, w in weights.items() if k in f) / sum(weights.values())

    def _overall_raw(self, f):
        mel = self._raw(f, MELODY_WEIGHTS)
        if "harmony_surprisal" not in f:
            return mel
        return 0.6 * mel + 0.4 * self._raw(f, HARMONY_WEIGHTS)

    @staticmethod
    def _pct(ref, x):
        return round(bisect_left(ref, x) / len(ref), 3) if ref else None

    def score(self, f) -> dict:
        return {
            "overall": self._pct(self.overall_ref, self._overall_raw(f)),
            "melody": self._pct(self.melody_ref, self._raw(f, MELODY_WEIGHTS)),
            "harmony": self._pct(self.harmony_ref, self._raw(f, HARMONY_WEIGHTS)) if "harmony_surprisal" in f else None,
            "components": {k: round(v, 3) for k, v in sorted(f.items())},
        }


def add_difficulty(segments) -> None:
    """Fill `difficulty` on each segment and `s` (surprisal, bits) on each note and chord."""
    train = [s for s in segments if s["split"] == "TRAIN"]
    melody_model, harmony_model = fit_models(train)
    feats = [features(s, melody_model, harmony_model) for s in segments]
    scorer = Scorer([f for s, f in zip(segments, feats) if s["split"] == "TRAIN"])
    for seg, f in zip(segments, feats):
        seg["difficulty"] = scorer.score(f)
