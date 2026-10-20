"""Build the corpus in one command:

    python -m pipeline.build_corpus

Downloads the dataset if needed, then filters, converts, tags, scores
difficulty and writes pipeline/out/:

    corpus_train.json  corpus_valid.json  corpus_test.json   main pools by split
    corpus_keychanges.json                                    KEY_CHANGES pool (track P10 only)
    index_concepts.json                                       concept -> clip moments (TRAIN+VALID only)
    freq_tables.json                                          corpus frequencies (TRAIN+VALID only)
    function_disagreements.json                               HookTheory labels vs our rules
    build_report.txt                                          the summary printed below
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import download
from .chords import QUALITIES, SEVENTH_OR_EXTENDED, bass_pc, chord_tones, quality, symbol
from .common import ATTRIBUTION, DATASET_PATH, DEGREE_LABELS, MODE_INTERVALS, OUT_DIR, RAW_DATASET_PATH, mode_name, scale_semitones
from .difficulty import add_difficulty
from .function import classify, numeral, raw_function, resolve_function
from .spelling import key_label, spell, tonic_name
from .tagging import add_distinctive_ngrams, build_concept_index, build_freq_tables, tag_segment
from .timing import BeatClock

REQUIRED_TAGS = {"MELODY", "AUDIO_AVAILABLE", "REFINED_ALIGNMENT"}
DROP_TAGS = {"TEMPO_CHANGES"}
SPLITS = ("TRAIN", "VALID", "TEST")
CORPUS_VERSION = 1
EXAMPLES_PER_DISAGREEMENT = 25
# Build-time tag lists, too large to ship; the index and freq tables already use them.
BUILD_ONLY_TAGS = ("melody_ngrams", "chord_ngrams", "chord_ngrams_quality")


class Skip(Exception):
    """Entry excluded from the corpus; the message is the reason."""


def r3(x: float) -> float:
    return round(float(x), 3)


def num(x):
    """Beat counts as int when whole (4 not 4.0), else float."""
    return int(x) if float(x).is_integer() else x


def keys_of(ann) -> list[dict]:
    keys = []
    for k in sorted(ann["keys"], key=lambda k: k["beat"]):
        mode = mode_name(k["scale_degree_intervals"])
        if mode is None:
            raise Skip("unknown_mode")
        keys.append({"beat": k["beat"], "tonic_pc": k["tonic_pitch_class"] % 12, "mode": mode})
    if not keys:
        raise Skip("no_key")
    return keys


def key_at(keys, beat):
    current = keys[0]
    for k in keys:
        if k["beat"] <= beat + 1e-9:
            current = k
    return current


def build_bars(ann, clock: BeatClock):
    """Bars from the (possibly changing) meters, with start beat and seconds."""
    meters = sorted(ann["meters"], key=lambda m: m["beat"]) or [{"beat": 0, "beats_per_bar": 4}]
    num_beats = ann["num_beats"]
    bars, beat = [], 0.0
    while beat < num_beats - 1e-9:
        meter = [m for m in meters if m["beat"] <= beat + 1e-9] or meters[:1]
        length = meter[-1]["beats_per_bar"]
        nxt = [m["beat"] for m in meters if m["beat"] > beat + 1e-9]
        end = min(beat + length, num_beats, *(nxt[:1] or [num_beats]))
        bars.append({"beat": num(beat), "t0": r3(clock.seconds(beat)), "t1": r3(clock.seconds(end)), "beats": num(end - beat)})
        beat = end
    return bars


def is_strong(beat, bars):
    for bar in bars:
        if bar["beat"] - 1e-6 <= beat < bar["beat"] + bar["beats"] - 1e-6:
            pos = beat - bar["beat"]
            half = bar["beats"] / 2
            return abs(pos) < 1e-6 or (bar["beats"] % 2 == 0 and abs(pos - half) < 1e-6)
    return False


def aligned_raw_chords(raw_entry, harmony):
    """Raw chords matched 1:1 to the processed harmony, or None if they don't line up."""
    if not raw_entry or not raw_entry.get("json"):
        return None
    chords = [c for c in raw_entry["json"].get("chords") or [] if not c.get("isRest")]
    if len(chords) != len(harmony):
        return None
    if any(abs((c["beat"] - 1) - h["onset"]) > 1e-6 for c, h in zip(chords, harmony)):
        return None
    return chords


def build_chord(h, keys, clock, raw_chord, stats):
    k = key_at(keys, h["onset"])
    tonic, mode = k["tonic_pc"], k["mode"]
    ivs = h["root_position_intervals"]
    q = quality(ivs)
    root = h["root_pitch_class"] % 12
    inversion = h.get("inversion") or 0
    semis = (root - tonic) % 12
    bass = bass_pc(root, ivs, inversion)
    sym, slash = symbol(root, ivs, inversion, tonic, mode)

    func, source, disagreement = resolve_function(raw_chord, root, ivs, tonic, mode)
    if disagreement:
        stats["disagreements"][disagreement] += 1
        examples = stats["disagreement_examples"][disagreement]
        if len(examples) < EXAMPLES_PER_DISAGREEMENT:
            examples.append({"segment": stats["current_id"], "key": key_label(tonic, mode), "chord": sym, "hooktheory": raw_function(raw_chord, root, ivs, tonic, mode), "rules": classify(root, ivs, tonic, mode)})
    if raw_chord and isinstance(raw_chord.get("borrowed"), list):
        stats["raw_unparsed"] += 1

    stats["quality"][q.id] += 1
    stats["intervals"][tuple(ivs)] += 1
    stats["function"][func["function"]] += 1
    stats["function_source"][source] += 1
    return {
        "t0": r3(clock.seconds(h["onset"])),
        "t1": r3(clock.seconds(h["offset"])),
        "beat": h["onset"],
        "dur_beats": num(h["offset"] - h["onset"]),
        "root_pc": root,
        "root_name": spell(root, tonic, mode),
        "root_deg": DEGREE_LABELS[semis],
        "quality": q.id,
        "symbol": sym,
        "roman": numeral(semis, q),
        "roman_plain": numeral(semis, q, with_suffix=False),
        "inversion": inversion,
        "bass_pc": bass,
        "bass_deg": DEGREE_LABELS[(bass - tonic) % 12],
        "slash": slash,
        "function": func["function"],
        "function_label": func["label"],
        "borrowed_from": func["borrowed_from"],
        "function_source": source,
        "extended": q.id in SEVENTH_OR_EXTENDED,
        "pcs": chord_tones(root, ivs),
    }


def build_segment(hid, entry, raw_entry, stats) -> dict:
    tags = set(entry["tags"])
    missing = REQUIRED_TAGS - tags
    if missing:
        raise Skip("missing_" + "_".join(sorted(missing)).lower())
    if tags & DROP_TAGS:
        raise Skip("tempo_changes")
    ann = entry["annotations"]
    melody = sorted(ann.get("melody") or [], key=lambda n: n["onset"])
    if not melody:
        raise Skip("no_melody_notes")
    refined = entry["alignment"].get("refined") or {}
    try:
        clock = BeatClock(refined.get("beats") or [], refined.get("times") or [])
    except ValueError:
        raise Skip("bad_alignment")
    keys = keys_of(ann)
    bars = build_bars(ann, clock)
    harmony = sorted(ann.get("harmony") or [], key=lambda h: h["onset"]) if "HARMONY" in tags else []
    raw_chords = aligned_raw_chords(raw_entry, harmony) if harmony else None
    if harmony and raw_entry is not None and raw_chords is None:
        stats["raw_unaligned"] += 1

    stats["current_id"] = hid
    chords = [build_chord(h, keys, clock, raw_chords[i] if raw_chords else None, stats) for i, h in enumerate(harmony)]

    notes = []
    for n in melody:
        k = key_at(keys, n["onset"])
        pc = n["pitch_class"] % 12
        semis = (pc - k["tonic_pc"]) % 12
        active = next((c for c in chords if c["beat"] - 1e-6 <= n["onset"] < c["beat"] + c["dur_beats"] - 1e-6), None)
        notes.append(
            {
                "t0": r3(clock.seconds(n["onset"])),
                "t1": r3(clock.seconds(n["offset"])),
                "beat": n["onset"],
                "dur_beats": num(n["offset"] - n["onset"]),
                "midi": pc + (5 + n["octave"]) * 12,
                "pc": pc,
                "name": spell(pc, k["tonic_pc"], k["mode"]),
                "deg": DEGREE_LABELS[semis],
                "deg_semi": semis,
                "strong_beat": is_strong(n["onset"], bars),
                "chord_tone": (pc in active["pcs"]) if active else None,
            }
        )

    def key_obj(k):
        return {
            "tonic_pc": k["tonic_pc"],
            "tonic_name": tonic_name(k["tonic_pc"], k["mode"]),
            "mode": k["mode"],
            "intervals": list(MODE_INTERVALS[k["mode"]]),
            "name": key_label(k["tonic_pc"], k["mode"]),
        }

    ht = entry["hooktheory"]
    return {
        "id": hid,
        "yt": entry["youtube"]["id"],
        "split": entry["split"],
        "artist": ht.get("artist", ""),
        "song": ht.get("song", ""),
        "hooktheory_url": (ht.get("urls") or {}).get("song", ""),
        "start": r3(clock.seconds(0)),
        "end": r3(clock.seconds(ann["num_beats"])),
        "bpm": round(clock.bpm(), 2),
        "meter": bars[0]["beats"] if bars else 4,
        "key": key_obj(keys[0]),
        "key_changes": [{"beat": k["beat"], "t": r3(clock.seconds(k["beat"])), **key_obj(k)} for k in keys[1:]],
        "notes": notes,
        "chords": chords,
        "bars": [{"t0": b["t0"], "t1": b["t1"], "beat": b["beat"]} for b in bars],
        "tags": [],
        "difficulty": {},
        "yt_ok": None,
    }


def load_yt_status(out_dir: Path) -> dict:
    path = out_dir / "yt_status.json"
    if not path.exists():
        return {}
    return {vid: v.get("ok") for vid, v in json.loads(path.read_text()).items()}


def build(data: dict, raw: dict | None) -> tuple[list, list, dict, Counter]:
    """Convert every entry. Returns (main segments, key-change pool, stats, drop reasons)."""
    stats = {
        "quality": Counter(),
        "intervals": Counter(),
        "function": Counter(),
        "function_source": Counter(),
        "disagreements": Counter(),
        "disagreement_examples": defaultdict(list),
        "raw_unaligned": 0,
        "raw_unparsed": 0,
        "current_id": None,
    }
    main, key_changes, dropped = [], [], Counter()
    for hid, entry in data.items():
        try:
            seg = build_segment(hid, entry, raw.get(hid) if raw is not None else None, stats)
        except Skip as skip:
            dropped[str(skip)] += 1
            continue
        if seg["key_changes"] or "KEY_CHANGES" in entry["tags"]:
            key_changes.append(seg)
        else:
            main.append(seg)
    return main, key_changes, stats, dropped


def enrich(segments: list) -> None:
    for seg in segments:
        seg["tags"] = tag_segment(seg, set(scale_semitones(seg["key"]["mode"])))
    add_distinctive_ngrams(segments)
    add_difficulty(segments)


def write_json(path: Path, obj) -> tuple[int, int]:
    """Write compact JSON; returns (bytes, gzipped bytes) since the app ships it gzipped."""
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
    path.write_bytes(data)
    return len(data), len(gzip.compress(data, 6))


def report(main, key_changes, stats, dropped, sizes, elapsed) -> str:
    lines = []
    p = lines.append
    total_in = len(main) + len(key_changes) + sum(dropped.values())
    p(f"Ear trainer corpus v{CORPUS_VERSION}  ({elapsed:.0f} s)")
    p("")
    p(f"Entries in dataset: {total_in}")
    p(f"  main corpus:       {len(main)}  ({len({s['yt'] for s in main})} unique videos)")
    p(f"  KEY_CHANGES pool:  {len(key_changes)}")
    for reason, n in dropped.most_common():
        p(f"  dropped {reason}: {n}")

    p("\nSegments per split (main corpus)")
    by_split = Counter(s["split"] for s in main)
    for sp in SPLITS:
        p(f"  {sp:6} {by_split[sp]:6}")

    p("\nSegments per mode and split")
    by_mode = defaultdict(Counter)
    for s in main:
        by_mode[s["key"]["mode"]][s["split"]] += 1
    p(f"  {'mode':18} {'TRAIN':>6} {'VALID':>6} {'TEST':>6} {'total':>7}")
    for mode, c in sorted(by_mode.items(), key=lambda kv: -sum(kv[1].values())):
        p(f"  {mode:18} {c['TRAIN']:6} {c['VALID']:6} {c['TEST']:6} {sum(c.values()):7}")
    p(f"  melody-only segments (no HARMONY): {sum(1 for s in main if not s['chords'])}")

    total_chords = sum(stats["quality"].values())
    known = total_chords - stats["quality"]["other"]
    p(f"\nChord instances (all pools): {total_chords}")
    p(f"  known quality: {known / total_chords:.2%}   (target > 98%)")
    p(f"  distinct interval tuples: {len(stats['intervals'])}; mapped: {sum(1 for k in stats['intervals'] if k in QUALITIES)}")
    unmapped = [(k, n) for k, n in stats["intervals"].most_common() if k not in QUALITIES]
    p("  most common unmapped tuples: " + ", ".join(f"{list(k)} x{n}" for k, n in unmapped[:8]))
    p("  full list: python -m pipeline.chords")

    p("\nChord qualities")
    for q, n in stats["quality"].most_common():
        p(f"  {q:12} {n:8}  {n / total_chords:6.2%}")

    p("\nChord functions")
    for f, n in stats["function"].most_common():
        p(f"  {f:12} {n:8}  {n / total_chords:6.2%}")
    p("  source: " + ", ".join(f"{k} {v}" for k, v in stats["function_source"].most_common()))
    p(f"  Raw chords not aligned to processed harmony (segments): {stats['raw_unaligned']}")
    p(f"  Raw 'borrowed' given as an unreadable scale array (chords): {stats['raw_unparsed']}")
    if stats["disagreements"]:
        p("  HookTheory label vs rules (hooktheory->rules, or override): " + ", ".join(f"{k} x{n}" for k, n in stats["disagreements"].most_common()))

    p("\nOutput                              JSON   gzipped")
    for name, (size, gz) in sizes.items():
        p(f"  {name:28} {size / 1e6:7.1f} MB {gz / 1e6:6.1f} MB")
    total, total_gz = (sum(v[i] for v in sizes.values()) for i in (0, 1))
    p(f"  {'total':28} {total / 1e6:7.1f} MB {total_gz / 1e6:6.1f} MB  ({'under' if total_gz < 50e6 else 'OVER'} the 50 MB budget, gzipped)")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-raw", action="store_true", help="ignore the Raw file; use rule-based chord functions only")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    started = time.time()
    download.ensure(raw=not args.no_raw)
    print("Loading dataset ...", flush=True)
    data = json.load(gzip.open(DATASET_PATH))
    raw = None
    if not args.no_raw and RAW_DATASET_PATH.exists():
        raw = json.load(gzip.open(RAW_DATASET_PATH))

    print("Converting ...", flush=True)
    main_segments, kc_segments, stats, dropped = build(data, raw)
    del data, raw
    print("Tagging and scoring ...", flush=True)
    enrich(main_segments + kc_segments)

    yt = load_yt_status(args.out)
    for seg in main_segments + kc_segments:
        seg["yt_ok"] = yt.get(seg["yt"])

    shown = [s for s in main_segments if s["split"] in ("TRAIN", "VALID")]
    index = build_concept_index(shown)
    freq = build_freq_tables(shown)
    for seg in main_segments + kc_segments:
        for tag in BUILD_ONLY_TAGS:
            seg["tags"].pop(tag, None)

    args.out.mkdir(parents=True, exist_ok=True)
    meta = {"version": CORPUS_VERSION, "attribution": ATTRIBUTION}
    sizes = {}
    for split in SPLITS:
        segs = [s for s in main_segments if s["split"] == split]
        sizes[f"corpus_{split.lower()}.json"] = write_json(args.out / f"corpus_{split.lower()}.json", {**meta, "split": split, "segments": segs})
    sizes["corpus_keychanges.json"] = write_json(args.out / "corpus_keychanges.json", {**meta, "segments": kc_segments})
    sizes["index_concepts.json"] = write_json(args.out / "index_concepts.json", {**meta, "concepts": index})
    sizes["freq_tables.json"] = write_json(args.out / "freq_tables.json", {**meta, **freq})
    write_json(
        args.out / "function_disagreements.json",
        {"counts": dict(stats["disagreements"].most_common()), "examples": stats["disagreement_examples"]},
    )

    text = report(main_segments, kc_segments, stats, dropped, sizes, time.time() - started)
    (args.out / "build_report.txt").write_text(text + "\n")
    print("\n" + text)


if __name__ == "__main__":
    main()
