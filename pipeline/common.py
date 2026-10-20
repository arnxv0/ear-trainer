"""Constants shared by every pipeline step: paths, degree labels and modes."""

from __future__ import annotations

from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
RAW_DIR = PIPELINE_DIR / "raw"
OUT_DIR = PIPELINE_DIR / "out"

DATASET_URL = "https://github.com/chrisdonahue/sheetsage-data/raw/refs/heads/main/hooktheory/Hooktheory.json.gz"
RAW_DATASET_URL = "https://github.com/chrisdonahue/sheetsage-data/raw/refs/heads/main/hooktheory/Hooktheory_Raw.json.gz"
DATASET_PATH = RAW_DIR / "Hooktheory.json.gz"
RAW_DATASET_PATH = RAW_DIR / "Hooktheory_Raw.json.gz"

ATTRIBUTION = "Song analyses from HookTheory TheoryTab via the Sheet Sage dataset (CC BY-NC-SA 3.0)."

# Do-based degree labels: semitones above the tonic, so a minor tonic is still 1.
DEGREE_LABELS = {0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "#4", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7"}

# `scale_degree_intervals` from the dataset (6 steps; the 7th closes the octave).
MODE_INTERVALS: dict[str, tuple[int, ...]] = {
    "major": (2, 2, 1, 2, 2, 2),
    "dorian": (2, 1, 2, 2, 2, 1),
    "phrygian": (1, 2, 2, 2, 1, 2),
    "lydian": (2, 2, 2, 1, 2, 2),
    "mixolydian": (2, 2, 1, 2, 2, 1),
    "minor": (2, 1, 2, 2, 1, 2),
    "locrian": (1, 2, 2, 1, 2, 2),
    "harmonic_minor": (2, 1, 2, 2, 1, 3),
    "phrygian_dominant": (1, 3, 1, 2, 1, 2),
}
INTERVALS_TO_MODE = {v: k for k, v in MODE_INTERVALS.items()}

# HookTheory Raw file names for the same scales.
RAW_MODE_NAMES = {
    "major": "major",
    "minor": "minor",
    "dorian": "dorian",
    "phrygian": "phrygian",
    "lydian": "lydian",
    "mixolydian": "mixolydian",
    "locrian": "locrian",
    "harmonicMinor": "harmonic_minor",
    "phrygianDominant": "phrygian_dominant",
}


def mode_name(intervals) -> str | None:
    return INTERVALS_TO_MODE.get(tuple(intervals))


def scale_semitones(mode: str) -> list[int]:
    """Semitones above the tonic for the 7 scale tones of `mode`."""
    out = [0]
    for step in MODE_INTERVALS[mode]:
        out.append(out[-1] + step)
    return out


def scale_pcs(tonic_pc: int, mode: str) -> set[int]:
    return {(tonic_pc + s) % 12 for s in scale_semitones(mode)}


def degree_label(pc: int, tonic_pc: int) -> str:
    return DEGREE_LABELS[(pc - tonic_pc) % 12]
