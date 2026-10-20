"""Print random segments as readable text to check the corpus by ear.

    python -m pipeline.spot_check               # 10 random TRAIN segments
    python -m pipeline.spot_check -n 20 --seed 7 --split VALID
    python -m pipeline.spot_check --id qveoYyGGodn

Open the YouTube link (it starts 2 s before the segment), then compare what you
hear with the key, chords and melody degrees printed bar by bar.
"""

from __future__ import annotations

import argparse
import json
import random

from .common import OUT_DIR

LEAD_IN = 2.0


def clock(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def in_bar(items, bar):
    return [x for x in items if bar["t0"] - 1e-3 <= x["t0"] < bar["t1"] - 1e-3]


def chord_text(c) -> str:
    label = c["roman"] if c["function"] == "diatonic" else c["function_label"]
    return f"{c['symbol']} ({label})"


def render(seg: dict) -> str:
    key = seg["key"]
    start = max(0, int(seg["start"] - LEAD_IN))
    lines = [
        f"{seg['artist'].replace('-', ' ').title()} - {seg['song'].replace('-', ' ').title()}   [{seg['split']}, {seg['id']}]",
        f"Key: {key['name']}   Tempo: {seg['bpm']:.0f} bpm   {seg['meter']} beats per bar   Difficulty: {seg['difficulty'].get('overall')}",
        f"YouTube: https://www.youtube.com/watch?v={seg['yt']}&t={start}s   (segment {clock(seg['start'])} to {clock(seg['end'])})",
    ]
    for kc in seg["key_changes"]:
        lines.append(f"Key change at {clock(kc['t'])}: {kc['name']}")
    lines.append("")
    for i, bar in enumerate(seg["bars"], 1):
        held = [c for c in seg["chords"] if c["t0"] < bar["t0"] - 1e-3 and c["t1"] > bar["t0"] + 1e-3]
        chords = " | ".join([f"({chord_text(c)} held)" for c in held] + [chord_text(c) for c in in_bar(seg["chords"], bar)]) or "-"
        melody = " ".join(f"{n['deg']}" for n in in_bar(seg["notes"], bar)) or "-"
        lines.append(f"  bar {i:2}  {clock(bar['t0']):>7}   {chords:44}  melody: {melody}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", type=int, default=10, help="number of segments")
    parser.add_argument("--split", default="TRAIN", choices=["TRAIN", "VALID", "TEST", "KEYCHANGES"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--id", help="show one segment by HookTheory id (searches every split)")
    args = parser.parse_args()

    if args.id:
        for path in sorted(OUT_DIR.glob("corpus_*.json")):
            for seg in json.loads(path.read_text())["segments"]:
                if seg["id"] == args.id:
                    print(render(seg))
                    return
        raise SystemExit(f"No segment {args.id}")

    path = OUT_DIR / f"corpus_{args.split.lower()}.json"
    if not path.exists():
        raise SystemExit(f"{path} not found. Run `python -m pipeline.build_corpus` first.")
    segments = json.loads(path.read_text())["segments"]
    picks = random.Random(args.seed).sample(segments, min(args.n, len(segments)))
    for i, seg in enumerate(picks, 1):
        print(f"[{i}/{len(picks)}] " + render(seg) + "\n")


if __name__ == "__main__":
    main()
