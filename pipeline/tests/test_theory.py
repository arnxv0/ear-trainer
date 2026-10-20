"""Spelling, numerals, function classification and beat timing against the shared fixtures."""

import json
import unittest
from pathlib import Path

from pipeline.chords import bass_pc, symbol
from pipeline.chords import quality as chord_quality
from pipeline.function import classify, numeral
from pipeline.spelling import scale_names, spell, tonic_name
from pipeline.timing import BeatClock

FIXTURES = json.loads((Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "theory.json").read_text())


class SpellingTest(unittest.TestCase):
    def test_tonic_names(self):
        for case in FIXTURES["tonic_names"]:
            with self.subTest(case=case):
                self.assertEqual(tonic_name(case["tonic_pc"], case["mode"]), case["name"])

    def test_scales_use_each_letter_once(self):
        for case in FIXTURES["scales"]:
            with self.subTest(case=case):
                names = list(scale_names(case["tonic_pc"], case["mode"]))
                self.assertEqual(names, case["notes"])
                self.assertEqual(len({n[0] for n in names}), 7)

    def test_spell(self):
        for case in FIXTURES["spell"]:
            with self.subTest(case=case):
                self.assertEqual(spell(case["pc"], case["tonic_pc"], case["mode"]), case["name"])

    def test_every_key_spells_every_pitch_class(self):
        from pipeline.common import MODE_INTERVALS

        for mode in MODE_INTERVALS:
            for tonic in range(12):
                names = [spell(pc, tonic, mode) for pc in range(12)]
                for pc, name in enumerate(names):
                    self.assertLessEqual(len(name), 2, (mode, tonic, pc, name))


class NumeralTest(unittest.TestCase):
    def test_numerals(self):
        for case in FIXTURES["numerals"]:
            with self.subTest(case=case):
                self.assertEqual(numeral(case["semitones"], chord_quality(case["intervals"])), case["roman"])

    def test_plain_numeral_drops_suffix(self):
        self.assertEqual(numeral(7, chord_quality([4, 3, 3]), with_suffix=False), "V")
        self.assertEqual(numeral(11, chord_quality([3, 3]), with_suffix=False), "vii")


class FunctionTest(unittest.TestCase):
    def test_progressions(self):
        for prog in FIXTURES["progressions"]:
            for chord in prog["chords"]:
                with self.subTest(progression=prog["name"], chord=chord["symbol"]):
                    sym, _ = symbol(chord["root_pc"], chord["intervals"], 0, prog["tonic_pc"], prog["mode"])
                    got = classify(chord["root_pc"], chord["intervals"], prog["tonic_pc"], prog["mode"])
                    self.assertEqual(sym, chord["symbol"])
                    self.assertEqual(got["label"], chord["label"])
                    self.assertEqual(got["function"], chord["function"])

    def test_slash_chords(self):
        for case in FIXTURES["slash_chords"]:
            with self.subTest(case=case):
                sym, slash = symbol(case["root_pc"], case["intervals"], case["inversion"], case["tonic_pc"], case["mode"])
                self.assertEqual(sym, case["symbol"])
                self.assertEqual(slash, case["symbol"].split("/")[1])
                self.assertEqual(bass_pc(case["root_pc"], case["intervals"], case["inversion"]), case["bass_pc"])


class BeatClockTest(unittest.TestCase):
    def test_fixture_queries(self):
        for case in FIXTURES["beat_to_seconds"]:
            clock = BeatClock(case["beats"], case["times"])
            for beat, seconds in case["queries"]:
                self.assertAlmostEqual(clock.seconds(beat), seconds, places=6, msg=f"beat {beat}")

    def test_bpm_uses_median_beat_length(self):
        clock = BeatClock([0, 1, 2, 3, 4], [0, 0.5, 1.0, 1.5, 3.0])
        self.assertAlmostEqual(clock.bpm(), 120)

    def test_unsorted_input_is_sorted(self):
        clock = BeatClock([2, 0, 1], [2.0, 0.0, 1.0])
        self.assertAlmostEqual(clock.seconds(1.5), 1.5)

    def test_rejects_bad_alignment(self):
        with self.assertRaises(ValueError):
            BeatClock([0], [1.0])
        with self.assertRaises(ValueError):
            BeatClock([0, 0], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
