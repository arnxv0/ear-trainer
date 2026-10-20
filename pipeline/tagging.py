"""Per-segment concept tags, the concept -> clip-moment index, and frequency tables."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

NGRAM_SIZES = (2, 3, 4)
DISTINCTIVE_PER_SEGMENT = 5
MIN_INDEX_DF = 10  # n-gram concepts need at least this many segments to be indexed
TOP_NGRAMS_PER_MODE = 100  # per mode and n-gram length
MAX_MOMENTS_PER_CONCEPT = 400
STEP_MAX, LEAP_MIN = 2, 7


def ngrams(seq, n):
    return [tuple(seq[i : i + n]) for i in range(len(seq) - n + 1)]


def ngram_key(gram) -> str:
    return "-".join(gram)


def merge_repeats(chords, key=lambda c: c["roman"]):
    """Collapse consecutive chords with the same label (a held or re-struck chord)."""
    out = []
    for c in chords:
        if out and key(out[-1]) == key(c):
            out[-1] = {**out[-1], "t1": c["t1"]}
        else:
            out.append(dict(c))
    return out


def phrase_end_flags(notes, rest_beats=1.0):
    """A note ends a phrase when followed by a rest of `rest_beats` or more, or at the end."""
    flags = []
    for i, n in enumerate(notes):
        nxt = notes[i + 1] if i + 1 < len(notes) else None
        flags.append(nxt is None or nxt["beat"] - (n["beat"] + n["dur_beats"]) >= rest_beats - 1e-6)
    return flags


def melody_stats(notes):
    intervals = [abs(b["midi"] - a["midi"]) for a, b in zip(notes, notes[1:])]
    moves = [i for i in intervals if i > 0]
    return {
        "step_ratio": round(sum(i <= STEP_MAX for i in moves) / len(moves), 3) if moves else 0.0,
        "leap_ratio": round(sum(i >= LEAP_MIN for i in moves) / len(moves), 3) if moves else 0.0,
    }


def tag_segment(seg, scale_semis) -> dict:
    """Concept tags for one built segment (notes and chords already in the corpus schema)."""
    notes, chords, mode = seg["notes"], seg["chords"], seg["key"]["mode"]
    degs = [n["deg"] for n in notes]
    ends = phrase_end_flags(notes)
    plain = [c["roman_plain"] for c in merge_repeats(chords, key=lambda c: c["roman_plain"])]
    full = [c["roman"] for c in merge_repeats(chords)]
    non_diatonic = sorted({f"{c['function']}:{c['function_label']}" for c in chords if c["function"] != "diatonic"})
    chord_tone_flags = [n["chord_tone"] for n in notes if n["chord_tone"] is not None]
    return {
        "mode": mode,
        "melody_ngrams": {str(n): sorted({ngram_key(g) for g in ngrams(degs, n)}) for n in NGRAM_SIZES},
        "strong_beat_degrees": sorted({n["deg"] for n in notes if n["strong_beat"]}),
        "phrase_end_degrees": [n["deg"] for n, end in zip(notes, ends) if end],
        "chromatic_degrees": sorted({n["deg"] for n in notes if n["deg_semi"] not in scale_semis}),
        **melody_stats(notes),
        "chord_ngrams": {str(n): sorted({ngram_key(g) for g in ngrams(plain, n)}) for n in NGRAM_SIZES},
        "chord_ngrams_quality": {str(n): sorted({ngram_key(g) for g in ngrams(full, n)}) for n in NGRAM_SIZES},
        "qualities": sorted({c["quality"] for c in chords}),
        "functions": sorted({c["function"] for c in chords}),
        "non_diatonic": non_diatonic,
        "has_inversions": any(c["inversion"] for c in chords),
        "chord_tone_ratio": round(sum(chord_tone_flags) / len(chord_tone_flags), 3) if chord_tone_flags else None,
    }


def add_distinctive_ngrams(segments) -> None:
    """Keep each segment's most distinctive melody n-grams by TF-IDF across the corpus."""
    df = Counter()
    tfs = []
    for seg in segments:
        degs = [n["deg"] for n in seg["notes"]]
        tf = Counter(ngram_key(g) for n in NGRAM_SIZES for g in ngrams(degs, n))
        tfs.append(tf)
        df.update(tf.keys())
    total = len(segments)
    for seg, tf in zip(segments, tfs):
        scored = sorted(((count * math.log(total / df[g]), g) for g, count in tf.items() if count >= 2), reverse=True)
        seg["tags"]["melody_distinctive"] = [g for _, g in scored[:DISTINCTIVE_PER_SEGMENT]]


def _spread(moments, k):
    """Up to k moments spread evenly across the difficulty range (moments sorted by difficulty)."""
    if len(moments) <= k:
        return moments
    step = len(moments) / k
    return [moments[int(i * step)] for i in range(k)]


def build_concept_index(segments, max_per_concept=MAX_MOMENTS_PER_CONCEPT, top_ngrams=TOP_NGRAMS_PER_MODE) -> dict[str, list]:
    """concept -> [[segment_id, t0, t1], ...], at most one moment per segment per concept.

    Concept names match the adaptive engine's item ids (doc 04), e.g.
    `M:deg:b7:major`, `P:numeral:bVII:major`, `Q:quality:min7`. Melody and
    progression n-grams are limited to the `top_ngrams` most widespread per
    mode and length, and every concept keeps at most `max_per_concept` moments
    spread across segment difficulty so Bridge can still pick clips near the
    user's rating. Only pass segments the app may show (never TEST).
    """
    seg_df = Counter()
    for seg in segments:
        tags = seg["tags"]
        for n in NGRAM_SIZES:
            seg_df.update(f"M:ngram:{g}:{tags['mode']}" for g in tags["melody_ngrams"][str(n)])
            seg_df.update(f"P:prog:{g}:{tags['mode']}" for g in tags["chord_ngrams"][str(n)])
    groups = defaultdict(list)
    for concept, df in seg_df.items():
        track, kind, gram, mode = concept.split(":")
        if df >= MIN_INDEX_DF:
            groups[(track, mode, gram.count("-"))].append((df, concept))
    kept_ngrams = {c for group in groups.values() for _, c in sorted(group, reverse=True)[:top_ngrams]}

    index: dict[str, list] = defaultdict(list)
    for seg in sorted(segments, key=lambda s: (s["difficulty"].get("overall") or 0, s["id"])):
        sid, mode, notes = seg["id"], seg["key"]["mode"], seg["notes"]
        seen = set()

        def add(concept, t0, t1):
            if concept not in seen:
                seen.add(concept)
                index[concept].append([sid, round(t0, 3), round(t1, 3)])

        add(f"T:mode:{mode}", seg["start"], seg["end"])
        # Prefer a strong-beat occurrence for single degrees: easier to hear.
        for n in sorted(notes, key=lambda n: not n["strong_beat"]):
            add(f"M:deg:{n['deg']}:{mode}", n["t0"], n["t1"])
        for n, end in zip(notes, phrase_end_flags(notes)):
            if end:
                add(f"M:land:{n['deg']}:{mode}", n["t0"], n["t1"])
        degs = [n["deg"] for n in notes]
        for size in NGRAM_SIZES:
            for i, g in enumerate(ngrams(degs, size)):
                concept = f"M:ngram:{ngram_key(g)}:{mode}"
                if concept in kept_ngrams:
                    add(concept, notes[i]["t0"], notes[i + size - 1]["t1"])

        for c in seg["chords"]:
            add(f"P:numeral:{c['roman']}:{mode}", c["t0"], c["t1"])
            add(f"B:bass:{c['bass_deg']}:{mode}", c["t0"], c["t1"])
            if c["quality"] != "other":
                add(f"Q:quality:{c['quality']}", c["t0"], c["t1"])
            if c["inversion"]:
                add(f"B:inversion:{mode}", c["t0"], c["t1"])
            if c["function"] != "diatonic":
                add(f"F:{c['function']}:{c['function_label']}", c["t0"], c["t1"])
        merged = merge_repeats(seg["chords"], key=lambda c: c["roman_plain"])
        for size in NGRAM_SIZES:
            for i in range(len(merged) - size + 1):
                window = merged[i : i + size]
                concept = f"P:prog:{ngram_key(c['roman_plain'] for c in window)}:{mode}"
                if concept in kept_ngrams:
                    add(concept, window[0]["t0"], window[-1]["t1"])
    return {k: _spread(v, max_per_concept) for k, v in sorted(index.items())}


def build_freq_tables(segments) -> dict:
    """Corpus frequencies that order curriculum levels (P4, M5, Q7). Pass TRAIN+VALID only."""
    by_mode = lambda: defaultdict(Counter)  # noqa: E731
    numerals, progressions, chromatic, melody, bass = by_mode(), by_mode(), by_mode(), by_mode(), by_mode()
    qualities, modes, functions = Counter(), Counter(), Counter()
    for seg in segments:
        mode = seg["key"]["mode"]
        modes[mode] += 1
        tags = seg["tags"]
        for c in seg["chords"]:
            numerals[mode][c["roman"]] += 1
            bass[mode][c["bass_deg"]] += 1
            qualities[c["quality"]] += 1
            functions[f"{c['function']}:{c['function_label']}" if c["function"] != "diatonic" else "diatonic"] += 1
        for n in NGRAM_SIZES:
            progressions[mode].update(tags["chord_ngrams"][str(n)])
            melody[mode].update(tags["melody_ngrams"][str(n)])
        chromatic[mode].update(tags["chromatic_degrees"])

    def top(counter_by_mode, k=None):
        return {m: dict(c.most_common(k)) for m, c in sorted(counter_by_mode.items())}

    return {
        "segments_by_mode": dict(modes.most_common()),
        "chord_numerals": top(numerals),
        "bass_degrees": top(bass),
        "chord_qualities": dict(qualities.most_common()),
        "chord_functions": dict(functions.most_common(300)),
        "progression_ngrams_segments": top(progressions, 300),
        "melody_ngrams_segments": top(melody, 300),
        "chromatic_degrees_segments": top(chromatic),
    }
