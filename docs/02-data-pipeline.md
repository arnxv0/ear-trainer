# 02. Data pipeline

All song data comes from the HookTheory dataset released with Sheet Sage. One 20 MB file. No manual annotation needed for modes 2 and 3.

## Source

- File: `https://github.com/chrisdonahue/sheetsage-data/raw/refs/heads/main/hooktheory/Hooktheory.json.gz`
- Optional: `Hooktheory_Raw.json.gz` in the same folder (HookTheory's native format, chords already in functional form with `applied` and `borrowed` fields). Inspect its schema before using; it was only partly verified.
- License: CC BY-NC-SA 3.0. Personal, non-commercial use. Show attribution in the app footer: "Song analyses from HookTheory TheoryTab via the Sheet Sage dataset (CC BY-NC-SA 3.0)."
- Reference parsing code: `notebooks/Dataset.ipynb` in `github.com/chrisdonahue/sheetsage`.

## Verified schema (one entry, keyed by HookTheory ID)

```json
{
 "tags": ["NO_SWING","AUDIO_AVAILABLE","USER_ALIGNMENT","REFINED_ALIGNMENT","MELODY","HARMONY"],
 "split": "TRAIN",
 "hooktheory": {"id": "...", "artist": "...", "song": "...", "annotators": [], "urls": {"artist": "", "song": "", "clip": ""}},
 "youtube": {"id": "X1Fqn9du7xo", "url": "https://www.youtube.com/watch?v=X1Fqn9du7xo", "duration": 225.36},
 "alignment": {
   "swing": "STRAIGHT",
   "user":    {"beats": [0, 44], "times": [51.85, 80.21]},
   "refined": {"beats": [0, 1, 2, "...", 44], "times": [51.8487, 52.4887, "...", 80.2387]}
 },
 "annotations": {
   "num_beats": 44,
   "meters":  [{"beat": 0, "beats_per_bar": 4, "beat_unit": 4}],
   "keys":    [{"beat": 0, "tonic_pitch_class": 2, "scale_degree_intervals": [2,2,1,2,2,2]}],
   "melody":  [{"onset": 1, "offset": 2, "octave": 0, "pitch_class": 11}],
   "harmony": [{"onset": 0, "offset": 2, "root_pitch_class": 7, "root_position_intervals": [4,3], "inversion": 0}]
 }
}
```

Key facts:
- `onset`/`offset` are in beats (can be fractional). Convert to seconds by linear interpolation of `alignment.refined.beats` against `alignment.refined.times` (extrapolate at edges).
- Melody is absolute pitch class plus relative octave. MIDI = `pitch_class + (5 + octave) * 12`.
- Scale degree semitone = `(pitch_class - tonic_pitch_class) mod 12`.
- `scale_degree_intervals` encodes the mode: `[2,2,1,2,2,2]` major, `[2,1,2,2,1,2]` natural minor, `[2,2,1,2,2,1]` Mixolydian, `[2,1,2,2,2,1]` Dorian, `[2,2,2,1,2,2]` Lydian, `[1,2,2,2,1,2]` Phrygian, `[1,2,2,1,2,2]` Locrian.
- `harmony.root_position_intervals` is the stacked intervals above the root in root position. `inversion` is 0, 1, 2, 3.
- `split` is TRAIN / VALID / TEST, 8:1:1, stratified by artist.

## Filtering

Keep: `MELODY`, `AUDIO_AVAILABLE`, `REFINED_ALIGNMENT`.
Separately keep `HARMONY` for chord tracks (check the tag exists; if a segment lacks harmony, it is melody-only).
Drop: `TEMPO_CHANGES`. Keep `KEY_CHANGES` entries in a separate pool used only for track P10.

Expected after filtering: about 16k segments, about 10k songs, about 101 hours. Roughly 8k major, 6.7k minor, a few hundred each Mixolydian and Dorian, small tail of Lydian, Phrygian, Locrian.

## Pipeline scripts (`pipeline/`)

### 1. `download.py`
Fetch the gz file(s) into `pipeline/raw/`. Idempotent.

### 2. `build_corpus.py`
For each kept entry produce:

```json
{
  "id": "hooktheory id",
  "yt": "video id",
  "split": "TRAIN|VALID|TEST",
  "artist": "", "song": "",
  "start": 51.85, "end": 80.24,
  "bpm": 93.75,
  "meter": 4,
  "key": {"tonic_pc": 2, "tonic_name": "D", "mode": "major", "intervals": [2,2,1,2,2,2]},
  "key_changes": [],
  "notes": [{"t0": 52.49, "t1": 53.13, "beat": 1, "dur_beats": 1, "midi": 71, "pc": 11, "deg": "6", "deg_semi": 9, "strong_beat": false}],
  "chords": [{"t0": 51.85, "t1": 53.13, "beat": 0, "dur_beats": 2,
              "root_pc": 7, "root_name": "G", "root_deg": "4",
              "quality": "maj", "symbol": "G", "roman": "IV",
              "inversion": 0, "bass_pc": 7, "bass_deg": "4", "slash": null,
              "function": "diatonic", "pcs": [7, 11, 2]}],
  "bars": [{"t0": 51.85, "t1": 54.41}],
  "tags": [],
  "difficulty": {}
}
```

Degree labels (semitones from tonic, do-based, so minor tonic is 1):
`0:"1", 1:"b2", 2:"2", 3:"b3", 4:"3", 5:"4", 6:"#4", 7:"5", 8:"b6", 9:"6", 10:"b7", 11:"7"`

**Spelling note names.** Use the key to spell. Tonic names: prefer the conventional key spelling (Db major not C# major, F# minor not Gb minor, Bb, Eb, Ab, etc.). Spell scale tones from the tonic letter upward so each letter appears once; spell chromatic notes with flats in flat keys and sharps in sharp keys. Write a unit-tested `spelling.py`.

### 3. Chord quality mapping (`chords.py`)

Map `root_position_intervals` to quality. Start with this table, then print every distinct interval tuple with its count across the corpus and extend the table so nothing important is unmapped:

| intervals | quality | symbol suffix |
|---|---|---|
| [4,3] | maj | "" |
| [3,4] | min | m |
| [3,3] | dim | dim |
| [4,4] | aug | aug |
| [2,5] | sus2 | sus2 |
| [5,2] | sus4 | sus4 |
| [4,3,3] | dom7 | 7 |
| [4,3,4] | maj7 | maj7 |
| [3,4,3] | min7 | m7 |
| [3,3,4] | m7b5 | m7b5 |
| [3,3,3] | dim7 | dim7 |
| [3,4,4] | minmaj7 | m(maj7) |
| [5,2,3] | 7sus4 | 7sus4 |
| [4,3,3,4] | dom9 | 9 |
| [4,3,4,3] | maj9 | maj9 |
| [3,4,3,4] | min9 | m9 |
| [4,3,2] (6th as stacked) | 6 | 6 |
| add9 forms | add9 | add9 |

Verify 6, add9 and 11/13 encodings empirically from the printed tuples. Unmapped tuples go into `quality: "other"` and are excluded from quality questions.

Bass: `bass_pc` is the chord tone at position `inversion` (0 root, 1 third, 2 fifth, 3 seventh). If bass differs from root, `slash = bass name`.

### 4. Roman numerals and function (`function.py`)

For each chord in the song's key:
1. `root_deg` from root pc relative to tonic.
2. Roman numeral case from quality (upper for maj/aug/dom, lower for min/dim), plus suffix (°, +, 7, maj7, ø7, sus4).
3. Function classification:
   - **diatonic**: all chord pcs in the key's scale.
   - **borrowed**: not diatonic, but all pcs fit the parallel mode (major key borrowing from natural minor, Mixolydian, Dorian; minor key borrowing from major). Label with source, e.g. `bVII (borrowed from minor/Mixolydian)`.
   - **secondary dominant**: major or dom7 chord whose root is a perfect fifth above a diatonic chord's root (excluding I), label `V/x`. Also `vii°/x` for dim chords a half step below a diatonic root.
   - **chromatic other**: anything else.
   - If the Raw file's `applied` / `borrowed` fields are available and parse cleanly, prefer them and use this logic as a fallback. Log disagreements.
4. In modal keys, numerals are relative to the modal tonic (Mixolydian: I, ii, iii°, IV, v, vi, bVII).

Unit test against hand-checked progressions: I-V-vi-IV in C, i-bVI-bIII-bVII in A minor, I-bVII-IV in D Mixolydian, I-II-IV in Lydian, V/V in a ii-V/V-V-I.

### 5. Tagging (`tagging.py`)

Per segment:
- Melody n-grams of degrees (2, 3, 4 grams). Keep distinctive ones per song by TF-IDF across the corpus.
- Degree on strong beats and phrase ends ("lands on 3"). Phrase end = note followed by a rest of 1 beat or more, or segment end.
- Step/leap ratio (step <= 2 semitones, leap >= 7).
- Chromatic melody degrees present.
- Chord n-grams of Roman numerals (2, 3, 4 grams), with and without quality suffixes.
- Chord qualities present, functions present (borrowed, secondary, modal).
- Mode.
- Chord-tone vs non-chord-tone for each melody note.

Build inverted indexes: `concept -> [(segment_id, t0, t1)]` so any Lab item can link to real clip moments where it occurs. For melody concepts, store the exact note window. For chord concepts, store the exact chord window.

Global frequency tables: chord numeral frequency, progression n-gram frequency, chromatic degree frequency, quality frequency. These order levels P4, M5, Q7.

### 6. Difficulty (`difficulty.py`)

Per segment and per question window, compute a prior:
- Melody: range, mean and max interval, leap ratio, chromatic fraction, notes per second, distinct degrees, surprisal from an order-3 smoothed n-gram model of degrees trained on TRAIN only.
- Harmony: chords per bar, fraction non-diatonic, fraction 7th/extended, presence of inversions, numeral n-gram surprisal.
- Combine as z-scored weighted sum into 0 to 1. Store components too.

This is only a prior. The live Elo rating (see 04) corrects it.

### 7. Availability check (`check_youtube.py`)

Run from the user's machine (region matters, user is in India). For every unique video ID, call `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<id>&format=json`. 200 means public and embeddable metadata exists; 401/403/404 means drop. Rate-limit politely, cache results in `pipeline/out/yt_status.json`, rerun monthly. Also record in-app playback errors (IFrame `onError` codes 100, 101, 150) and auto-mark those segments dead.

### 8. Export

- `out/corpus_train.json`, `out/corpus_test.json` (TEST split only, never shown in Lab or Bridge), `out/corpus_valid.json` (use as extra Bridge material).
- `out/index_concepts.json`, `out/freq_tables.json`.
- Load into SQLite at backend start, or ship as static gzipped JSON fetched by the frontend. Total should stay well under 50 MB.

## Known data issues

- About 5% of refined alignments are off by a whole bar (wrong downbeat). Provide a per-segment user fix: "shift by -1 bar / +1 bar", stored as an override.
- Note offsets are heuristic (about 89% match).
- About 2% of entries have multiple keys.
- Link rot is unmeasured. Expect some loss.
- Almost no Indian songs. Track 12 in the build plan adds a self-annotation editor that writes the same schema.
