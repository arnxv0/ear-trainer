"""Chord quality mapping and HookTheory Raw function parsing."""

import unittest

from pipeline.chords import OTHER, QUALITIES, chord_tones, quality
from pipeline.function import diatonic_triads, raw_function, resolve_function


class QualityTest(unittest.TestCase):
    def test_spec_starting_table(self):
        expected = {
            (4, 3): ("maj", ""), (3, 4): ("min", "m"), (3, 3): ("dim", "dim"), (4, 4): ("aug", "aug"),
            (2, 5): ("sus2", "sus2"), (5, 2): ("sus4", "sus4"), (4, 3, 3): ("dom7", "7"),
            (4, 3, 4): ("maj7", "maj7"), (3, 4, 3): ("min7", "m7"), (3, 3, 4): ("m7b5", "m7b5"),
            (3, 3, 3): ("dim7", "dim7"), (3, 4, 4): ("minmaj7", "m(maj7)"), (5, 2, 3): ("7sus4", "7sus4"),
            (4, 3, 3, 4): ("dom9", "9"), (4, 3, 4, 3): ("maj9", "maj9"), (3, 4, 3, 4): ("min9", "m9"),
        }
        for ivs, (qid, sym) in expected.items():
            with self.subTest(ivs=ivs):
                self.assertEqual((quality(ivs).id, quality(ivs).symbol), (qid, sym))

    def test_empirical_encodings(self):
        # Confirmed against HookTheory's own descriptors (type/adds) in the Raw file.
        self.assertEqual(quality([4, 3, 14]).id, "6")
        self.assertEqual(quality([3, 4, 14]).id, "m6")
        self.assertEqual(quality([4, 3, 7]).id, "add9")
        self.assertEqual(quality([4, 3, 7, 7]).id, "6/9")

    def test_every_table_entry_has_distinct_chord_tones(self):
        for ivs, q in QUALITIES.items():
            tones = chord_tones(0, ivs)
            self.assertEqual(len(tones), len(set(tones)), q.id)

    def test_unknown_and_empty_are_other(self):
        self.assertIs(quality([1, 5, 4]), OTHER)
        self.assertIs(quality([]), OTHER)

    def test_ids_are_unique(self):
        ids = [q.id for q in QUALITIES.values()]
        self.assertEqual(len(ids), len(set(ids)))


class DiatonicTriadTest(unittest.TestCase):
    def test_major_and_minor(self):
        self.assertEqual(diatonic_triads("major"), {0: "maj", 2: "min", 4: "min", 5: "maj", 7: "maj", 9: "min", 11: "dim"})
        self.assertEqual(diatonic_triads("minor"), {0: "min", 2: "dim", 3: "maj", 5: "min", 7: "min", 8: "maj", 10: "maj"})


def raw(**fields):
    return {"root": 1, "applied": 0, "borrowed": None, **fields}


class RawFunctionTest(unittest.TestCase):
    def test_applied_chord_root_is_the_target(self):
        # A major, B major chord written as root=5 applied=5: V/V.
        got = raw_function(raw(root=5, applied=5), 11, [4, 3], 9, "major")
        self.assertEqual(got, {"function": "secondary", "label": "V/V", "borrowed_from": None})

    def test_applied_seventh_to_vi(self):
        # Ab major, C7 written as root=6 applied=5 type 7: V7/vi.
        self.assertEqual(raw_function(raw(root=6, applied=5), 0, [4, 3, 3], 8, "major")["label"], "V7/vi")

    def test_applied_leading_tone(self):
        self.assertEqual(raw_function(raw(root=5, applied=7), 6, [3, 3], 0, "major")["label"], "vii°/V")

    def test_borrowed_mode_name(self):
        got = raw_function(raw(root=7, borrowed="mixolydian"), 7, [4, 3], 9, "major")
        self.assertEqual(got["function"], "borrowed")
        self.assertEqual(got["borrowed_from"], ["mixolydian"])
        self.assertEqual(got["label"], "bVII (borrowed from Mixolydian)")

    def test_unreadable_or_absent_labels(self):
        self.assertIsNone(raw_function(raw(borrowed=[-1, 1, 3, 4, 6, 8, 9]), 0, [4, 3], 0, "major"))
        self.assertIsNone(raw_function(raw(borrowed=""), 0, [4, 3], 0, "major"))
        self.assertIsNone(raw_function(raw(), 0, [4, 3], 0, "major"))
        # Borrowing from the key's own mode is no borrowing.
        self.assertIsNone(raw_function(raw(borrowed="major"), 0, [4, 3], 0, "major"))


class ResolveTest(unittest.TestCase):
    def test_hooktheory_label_wins_when_explicit(self):
        func, source, disagreement = resolve_function(raw(root=4, applied=4), 10, [4, 3], 0, "major")
        self.assertEqual((func["label"], source), ("IV/IV", "hooktheory"))
        self.assertEqual(disagreement, "secondary->borrowed")

    def test_minor_key_dominant_stays_diatonic(self):
        func, source, disagreement = resolve_function(raw(root=5, borrowed="major"), 4, [4, 3], 9, "minor")
        self.assertEqual((func["function"], func["label"], source), ("diatonic", "V (harmonic minor)", "rules"))
        self.assertEqual(disagreement, "override:borrowed_but_in_key")

    def test_applied_to_tonic_is_ignored(self):
        func, source, disagreement = resolve_function(raw(root=1, applied=5), 4, [4, 3], 9, "minor")
        self.assertEqual((func["label"], source, disagreement), ("V (harmonic minor)", "rules", "override:applied_to_tonic"))

    def test_rules_without_raw(self):
        func, source, disagreement = resolve_function(None, 2, [4, 3], 0, "major")
        self.assertEqual((func["label"], source, disagreement), ("V/V", "rules", None))


if __name__ == "__main__":
    unittest.main()
