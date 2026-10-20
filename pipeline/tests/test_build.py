"""Building segments from dataset entries: filters, timing, notes, chords, tags, difficulty."""

import copy
import unittest
from collections import Counter, defaultdict

from pipeline.build_corpus import Skip, build, build_segment, enrich
from pipeline.difficulty import NGramModel
from pipeline.tagging import build_concept_index, merge_repeats, ngrams, phrase_end_flags

MAJOR = [2, 2, 1, 2, 2, 2]
MINOR = [2, 1, 2, 2, 1, 2]


def entry(split="TRAIN", tags=None, keys=None, melody=None, harmony=None, meters=None, num_beats=8):
    """A small entry in the dataset's schema: C major, 120 bpm, 8 beats from t=10 s."""
    return {
        "tags": tags or ["MELODY", "HARMONY", "AUDIO_AVAILABLE", "REFINED_ALIGNMENT", "NO_SWING"],
        "split": split,
        "hooktheory": {"id": "x", "artist": "artist", "song": "song", "urls": {"song": "https://example.invalid/song"}},
        "youtube": {"id": "vid123", "url": "", "duration": 100},
        "alignment": {"refined": {"beats": list(range(num_beats + 1)), "times": [10 + 0.5 * b for b in range(num_beats + 1)]}},
        "annotations": {
            "num_beats": num_beats,
            "meters": meters or [{"beat": 0, "beats_per_bar": 4, "beat_unit": 4}],
            "keys": keys or [{"beat": 0, "tonic_pitch_class": 0, "scale_degree_intervals": MAJOR}],
            "melody": melody
            if melody is not None
            else [
                {"onset": 0, "offset": 1, "octave": 0, "pitch_class": 4},  # E = 3
                {"onset": 1, "offset": 2, "octave": 0, "pitch_class": 2},  # D = 2
                {"onset": 2, "offset": 4, "octave": 0, "pitch_class": 0},  # C = 1, phrase end (rest follows)
                {"onset": 5, "offset": 6, "octave": -1, "pitch_class": 11},  # B below = 7
                {"onset": 6, "offset": 8, "octave": 0, "pitch_class": 3},  # Eb = b3
            ],
            "harmony": harmony
            if harmony is not None
            else [
                {"onset": 0, "offset": 4, "root_pitch_class": 0, "root_position_intervals": [4, 3], "inversion": 0},
                {"onset": 4, "offset": 6, "root_pitch_class": 7, "root_position_intervals": [4, 3, 3], "inversion": 1},
                {"onset": 6, "offset": 8, "root_pitch_class": 8, "root_position_intervals": [4, 3], "inversion": 0},
            ],
        },
    }


def new_stats():
    return {
        "quality": Counter(), "intervals": Counter(), "function": Counter(), "function_source": Counter(),
        "disagreements": Counter(), "disagreement_examples": defaultdict(list),
        "raw_unaligned": 0, "raw_unparsed": 0, "current_id": None,
    }


class BuildSegmentTest(unittest.TestCase):
    def setUp(self):
        self.seg = build_segment("seg1", entry(), None, new_stats())

    def test_timing_and_key(self):
        s = self.seg
        self.assertEqual((s["start"], s["end"], s["bpm"], s["meter"]), (10.0, 14.0, 120.0, 4))
        self.assertEqual(s["key"]["name"], "C major")
        self.assertEqual([(b["t0"], b["t1"]) for b in s["bars"]], [(10.0, 12.0), (12.0, 14.0)])

    def test_notes(self):
        notes = self.seg["notes"]
        self.assertEqual([n["deg"] for n in notes], ["3", "2", "1", "7", "b3"])
        self.assertEqual([n["name"] for n in notes], ["E", "D", "C", "B", "Eb"])
        self.assertEqual([n["midi"] for n in notes], [64, 62, 60, 59, 63])
        self.assertEqual([n["strong_beat"] for n in notes], [True, False, True, False, True])
        self.assertEqual([n["chord_tone"] for n in notes], [True, False, True, True, True])
        self.assertEqual((notes[1]["t0"], notes[1]["t1"]), (10.5, 11.0))

    def test_chords(self):
        c1, c2, c3 = self.seg["chords"]
        self.assertEqual((c1["symbol"], c1["roman"], c1["function"]), ("C", "I", "diatonic"))
        self.assertEqual((c2["symbol"], c2["roman"], c2["bass_deg"], c2["slash"]), ("G7/B", "V7", "7", "B"))
        self.assertEqual((c3["symbol"], c3["function"], c3["function_label"]), ("Ab", "borrowed", "bVI (borrowed from minor)"))
        self.assertEqual(c2["pcs"], [7, 11, 2, 5])

    def test_filters(self):
        cases = {
            "missing_refined_alignment": entry(tags=["MELODY", "HARMONY", "AUDIO_AVAILABLE"]),
            "tempo_changes": entry(tags=["MELODY", "AUDIO_AVAILABLE", "REFINED_ALIGNMENT", "TEMPO_CHANGES"]),
            "no_melody_notes": entry(melody=[]),
            "unknown_mode": entry(keys=[{"beat": 0, "tonic_pitch_class": 0, "scale_degree_intervals": [1, 1, 1, 1, 1, 1]}]),
        }
        for reason, e in cases.items():
            with self.subTest(reason=reason), self.assertRaises(Skip) as ctx:
                build_segment("x", e, None, new_stats())
            self.assertEqual(str(ctx.exception), reason)

    def test_melody_only_entry_has_no_chords(self):
        seg = build_segment("x", entry(tags=["MELODY", "AUDIO_AVAILABLE", "REFINED_ALIGNMENT"]), None, new_stats())
        self.assertEqual(seg["chords"], [])
        self.assertTrue(all(n["chord_tone"] is None for n in seg["notes"]))

    def test_key_change_uses_active_key_and_goes_to_pool(self):
        keys = [
            {"beat": 0, "tonic_pitch_class": 0, "scale_degree_intervals": MAJOR},
            {"beat": 4, "tonic_pitch_class": 9, "scale_degree_intervals": MINOR},
        ]
        e = entry(keys=keys, tags=["MELODY", "HARMONY", "AUDIO_AVAILABLE", "REFINED_ALIGNMENT", "KEY_CHANGES"])
        seg = build_segment("x", e, None, new_stats())
        self.assertEqual(seg["key_changes"][0]["name"], "A minor")
        self.assertEqual(seg["key_changes"][0]["t"], 12.0)
        self.assertEqual([n["deg"] for n in seg["notes"]], ["3", "2", "1", "2", "#4"])  # B and Eb heard in A minor
        main, pool, _, _ = build({"a": entry(), "b": e}, None)
        self.assertEqual(([s["id"] for s in main], [s["id"] for s in pool]), (["a"], ["b"]))

    def test_meter_change_bars(self):
        meters = [{"beat": 0, "beats_per_bar": 4, "beat_unit": 4}, {"beat": 4, "beats_per_bar": 2, "beat_unit": 4}]
        seg = build_segment("x", entry(meters=meters), None, new_stats())
        self.assertEqual([b["beat"] for b in seg["bars"]], [0, 4, 6])

    def test_raw_labels_are_used_when_aligned(self):
        raw_chords = [
            {"beat": 1, "isRest": False, "root": 1, "applied": 0, "borrowed": None},
            {"beat": 3, "isRest": True},
            {"beat": 5, "isRest": False, "root": 5, "applied": 0, "borrowed": None},
            {"beat": 7, "isRest": False, "root": 6, "applied": 0, "borrowed": "minor"},
        ]
        stats = new_stats()
        seg = build_segment("x", entry(), {"json": {"chords": raw_chords}}, stats)
        self.assertEqual([c["function_source"] for c in seg["chords"]], ["rules", "rules", "hooktheory"])
        misaligned = copy.deepcopy(raw_chords)
        misaligned[0]["beat"] = 2
        build_segment("x", entry(), {"json": {"chords": misaligned}}, stats)
        self.assertEqual(stats["raw_unaligned"], 1)


class EnrichTest(unittest.TestCase):
    def setUp(self):
        self.segs = [build_segment(f"s{i}", entry(split=split), None, new_stats()) for i, split in enumerate(["TRAIN", "TRAIN", "VALID"])]
        enrich(self.segs)

    def test_tags(self):
        tags = self.segs[0]["tags"]
        self.assertEqual(tags["phrase_end_degrees"], ["1", "b3"])
        self.assertEqual(tags["chromatic_degrees"], ["b3"])
        self.assertIn("I-V-bVI", tags["chord_ngrams"]["3"])
        self.assertEqual(tags["non_diatonic"], ["borrowed:bVI (borrowed from minor)"])

    def test_difficulty_and_surprisal(self):
        d = self.segs[0]["difficulty"]
        self.assertTrue(0 <= d["overall"] <= 1 and 0 <= d["melody"] <= 1 and 0 <= d["harmony"] <= 1)
        self.assertIn("melody_surprisal", d["components"])
        self.assertTrue(all("s" in n for n in self.segs[0]["notes"]))
        self.assertTrue(all(c["s"] is not None for c in self.segs[0]["chords"]))

    def test_concept_index(self):
        index = build_concept_index(self.segs, top_ngrams=100)
        self.assertEqual(index["M:deg:3:major"][0][1:], [10.0, 10.5])
        self.assertEqual(index["P:numeral:V7:major"][0][1:], [12.0, 13.0])
        self.assertIn("F:borrowed:bVI (borrowed from minor)", index)
        self.assertEqual(len(index["T:mode:major"]), 3)
        capped = build_concept_index(self.segs, max_per_concept=2)
        self.assertEqual(len(capped["T:mode:major"]), 2)


class HelpersTest(unittest.TestCase):
    def test_ngrams_and_merge(self):
        self.assertEqual(ngrams(["5", "6", "5"], 2), [("5", "6"), ("6", "5")])
        chords = [{"roman": "I", "t1": 1}, {"roman": "I", "t1": 2}, {"roman": "V", "t1": 3}]
        self.assertEqual([(c["roman"], c["t1"]) for c in merge_repeats(chords)], [("I", 2), ("V", 3)])

    def test_phrase_ends(self):
        notes = [{"beat": 0, "dur_beats": 1}, {"beat": 1, "dur_beats": 1}, {"beat": 3, "dur_beats": 1}]
        self.assertEqual(phrase_end_flags(notes), [False, True, True])

    def test_ngram_model_is_a_distribution(self):
        model = NGramModel().fit([("<major>", ["1", "2", "3", "1", "2", "3"]), ("<major>", ["5", "6", "5"])])
        history = ("1", "2")
        total = sum(model.prob(history, t) for t in model.vocab) + model.prob(history, "<unseen>")
        self.assertAlmostEqual(total, 1.0, places=9)
        self.assertGreater(model.prob(history, "3"), model.prob(history, "6"))


if __name__ == "__main__":
    unittest.main()
