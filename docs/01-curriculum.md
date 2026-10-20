# 01. Curriculum: from one note to a full song

The app is organised as six skill tracks that run in parallel and feed one final skill: transcribing a song you have never heard. Each track has levels. Each level is a set of items (a degree, a chord, a pattern) with its own Elo rating. A level unlocks when the user's rating on the current level passes a threshold (see 04 for the engine). Unlocked items keep appearing in interleaved review forever.

Every track runs in three modes (see 03):
- **Lab**: synthesized audio, full control, feedback on every trial.
- **Bridge**: the same concept inside real song clips from the training split.
- **Test**: held-out songs, no feedback until the end.

A concept is not "done" when Lab accuracy is high. It is done when Bridge and Test accuracy on it are high.

---

## Track T: Tonic and key finding

The skill nobody trains and every real song needs. Comes first because every other answer is relative to it.

| Level | Task | Notes |
|---|---|---|
| T1 | Hear a cadence, then sing or pick the tonic from 3 candidate notes | Lab |
| T2 | Hear a 10 to 20 s real clip, pick the tonic from 4 candidate notes played on piano | Bridge. Candidates: true tonic, 5th, 4th, relative major/minor tonic |
| T3 | Same, but candidates are all 12 notes on a one-octave keyboard (tap to audition each against the clip) | Bridge |
| T4 | Major or minor? (after tonic is found) | Bridge |
| T5 | Which mode? Major, minor, Mixolydian, Dorian, then Lydian, Phrygian | Bridge. Use the `mode` field |
| T6 | Name the key with no candidates. User finds the tonic on the guitar fretboard UI or real guitar, then types the key | Test. This is how you get from relative pitch to an actual key name |

**Honest note to show in-app:** relative pitch tells you "this is I to V to vi to IV". To know it is in E, you need one reference: find the tonic on your guitar. T6 trains exactly that lookup until it is fast.

Ambiguous pop tonics exist (loop songs that sit on vi or IV). In Bridge and Test, if the corpus tonic and the user's tonic differ by a relative major/minor relationship, mark it "alternate reading" not "wrong", and still grade the degrees against the user's chosen tonic for the rest of that song.

---

## Track M: Melody as scale degrees

| Level | Items | Notes |
|---|---|---|
| M1 | 1, 3, 5 | Single notes after cadence. Major key |
| M2 | add 2, 6 | Pentatonic. Covers a huge share of pop melodies |
| M3 | add 4, 7 | Full major scale |
| M4 | minor: 1, b3, 4, 5, b7, then 2, b6 | Do-based minor. The minor tonic is still 1 |
| M5 | chromatics by corpus frequency: b7 in major, #4, b3 in major, b6, b2 | Add one at a time |
| M6 | 2 note patterns mined from the corpus (e.g. 5-6, 3-2, 7-1) | Chunks |
| M7 | 3 to 4 note patterns (5-6-5, 3-2-1, 1-7-6-5) | Chunks |
| M8 | Full short phrases (4 to 8 notes) from real songs, played on piano | Melodic dictation |
| M9 | Same phrases in the real recording | Bridge / Test |

Octave of the target is randomized, including below the tonic (descending is harder and needs practice). Timbre rotates between piano, guitar, and one more GM sound.

---

## Track B: Bass line and chord roots

Bass first is the practical shortcut to chords. If you can hear the bass note as a degree, you know the chord root in most pop songs.

| Level | Task |
|---|---|
| B1 | Synth bass note after cadence: which degree? Roots 1, 4, 5 |
| B2 | Add 6, 2, then 3, then b7, b6, b3 (borrowed roots) |
| B3 | Bass line of 2 to 4 notes, each a degree |
| B4 | Real song clip: what degree is the bass/root on each chord change? Use `harmony[].root_pitch_class` relative to tonic. Piano roll shows chord change points so the user knows when to listen |
| B5 | Inversions: bass is not the root. "Is this chord in root position?" then "what is the bass degree and the root degree?" (slash chords like C/E) |

---

## Track Q: Chord quality

| Level | Items |
|---|---|
| Q1 | major vs minor triad |
| Q2 | add diminished, augmented |
| Q3 | sus2, sus4 |
| Q4 | dominant 7, major 7, minor 7 |
| Q5 | m7b5 (half diminished), dim7, minor-major 7 |
| Q6 | add9, 6, m6, 9, maj9, m9 |
| Q7 | 11 and 13 colors, 7#9, 7b9, 7sus4 (only those that appear in the corpus with meaningful frequency) |
| Q8 | inversions of triads and 7ths |

Lab plays the chord as both a block chord and an arpeggio, in a guitar voicing (not just close piano voicing), because that is how it will sound on the user's instrument. In Bridge, only ask about quality on chords the corpus labels with that quality.

---

## Track P: Progressions and function (Roman numerals)

The core of "identify the chords".

| Level | Items | Notes |
|---|---|---|
| P1 | I, IV, V | After cadence. One chord at a time, which numeral? |
| P2 | add vi | The four chords of pop |
| P3 | add ii, iii | Full diatonic major |
| P4 | 2 to 4 chord progressions from corpus n-grams: I-V-vi-IV, vi-IV-I-V, I-vi-IV-V, ii-V-I, I-IV-V-I, etc. | Ordered by corpus frequency |
| P5 | Minor key diatonic: i, iv, v, V (harmonic), bVI, bVII, bIII, ii° | |
| P6 | Borrowed chords in major: bVII, iv, bVI, bIII, ii°/ii-half-dim | Modal interchange |
| P7 | Secondary dominants: V/V (II major), V/vi (III major), V/IV (I7), V/ii (VI major) | |
| P8 | Modal progressions: Mixolydian (I-bVII-IV), Dorian (i-IV, i-ii), Lydian (I-II), Phrygian (i-bII) | |
| P9 | 7th chords in progression (Imaj7, ii7, V7, vi7), sus resolutions (Vsus4-V) | Combines Q and P |
| P10 | Key changes: detect "the key just moved", common pop shifts (up a half step, up a whole step, relative major/minor) | Only songs with KEY_CHANGES tag |
| P11 | Full section: name every chord in a 4 to 8 bar real clip | Test |

Every chord answer shows: Roman numeral, real chord name in the song's key, and a guitar voicing (see 06).

---

## Track G: Guitar transfer

Knowing the chords is useless unless you can play them. This track turns answers into hands.

| Level | Task |
|---|---|
| G1 | After any correct chord answer, show the chord in the real key with 2 voicings (open if possible, barre otherwise) |
| G2 | Find the tonic on your guitar while the clip loops (no mic, self-confirm) |
| G3 | Play-along: loop a Bridge clip with the progression shown bar by bar, at 0.75x or 1x |
| G4 | Mic check (optional phase): strum the chord, app checks pitch classes via chroma |
| G5 | Capo thinking: "This song is in Ab. Capo 1, play G shapes." Show capo suggestions that turn the progression into open shapes |
| G6 | Full song section: user transcribes key and progression, then plays it along with the clip. App shows the corpus answer after |

---

## The final skill: Song Transcription (Test mode)

One held-out song section, no feedback until the end:
1. Find the tonic (T)
2. Major, minor, or mode (T)
3. Name the key using guitar (T6)
4. Bass/root degrees for each chord change (B)
5. Chord qualities (Q)
6. Roman numerals and chord names (P)
7. Melody of the hook as degrees (M), optional

Scored per step. The per-step score history over weeks is the real progress chart.

---

## Session shape (default, about 20 minutes)

Research (Meludia, perceptual learning studies) suggests about 20 minutes daily, not more than 30, with listening right after practice.

1. **Warm-up Lab, 5 min:** interleaved items from all unlocked levels across tracks, weighted to weakest and most-confused.
2. **Bridge, 8 min:** 3 to 4 real clips. Each clip: find tonic, then 2 to 3 questions on the current focus track.
3. **Listen-through, 2 min:** replay the Bridge clips with degrees and chords highlighted in sync, no questions. Passive exposure right after practice is what drove the biggest lab gains.
4. **Play Along, 5 min:** loop one clip with the chords shown, play it on guitar.
5. **Weekly:** one Test song (full transcription), replaces the Bridge block that day.

## Realistic expectations (show on first launch)

- Single degrees and I/IV/V/vi in Lab: weeks.
- Diatonic progressions in real songs: about 2 to 4 months of daily practice.
- Borrowed chords, secondary dominants, modes, 7ths in real songs: about 6 to 12 months.
- Full transcription of most pop songs: about a year of consistent practice. Dense jazz harmony is beyond this plan.

These are practitioner estimates, not study results. The app's own progress chart is the real measure.
