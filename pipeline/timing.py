"""Beat to seconds conversion from the dataset's refined alignment."""

from __future__ import annotations

from bisect import bisect_right
from statistics import median


class BeatClock:
    """Linear interpolation of beats -> seconds, extrapolating past both ends.

    Mirrors Sheet Sage's `interp1d(beats, times, kind="linear", fill_value="extrapolate")`.
    """

    def __init__(self, beats, times):
        if len(beats) != len(times) or len(beats) < 2:
            raise ValueError("alignment needs at least two matching beats and times")
        pairs = sorted(zip(beats, times))
        self.beats = [float(b) for b, _ in pairs]
        self.times = [float(t) for _, t in pairs]
        if any(b2 <= b1 for b1, b2 in zip(self.beats, self.beats[1:])):
            raise ValueError("alignment beats must be strictly increasing")

    def seconds(self, beat: float) -> float:
        b, t = self.beats, self.times
        # Pick the segment containing `beat`, or the first/last one to extrapolate.
        i = min(max(bisect_right(b, beat) - 1, 0), len(b) - 2)
        frac = (beat - b[i]) / (b[i + 1] - b[i])
        return t[i] + frac * (t[i + 1] - t[i])

    def bpm(self) -> float:
        per_beat = [(t2 - t1) / (b2 - b1) for b1, b2, t1, t2 in zip(self.beats, self.beats[1:], self.times, self.times[1:])]
        return 60.0 / median(per_beat)
