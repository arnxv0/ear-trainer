# 05. Build plan

Build in phases. Each phase ends with something Jayant can use daily. Do not start a phase until the previous one meets its acceptance criteria. After each phase, stop and summarise what was built and what to test.

## Phase 0: Data pipeline (do this first)

Build `pipeline/` per doc 02: download, build_corpus, chords, function, spelling, tagging, difficulty, export. Leave `check_youtube.py` written but note it must be run from the user's machine.

Acceptance:
- Corpus builds in one command. Prints counts per split, mode, quality, function.
- Prints all distinct `root_position_intervals` tuples with counts; mapping table extended so >98% of chord instances have a known quality.
- Unit tests pass for spelling, numerals, function classification, beat-to-second conversion.
- A script prints 10 random segments as human-readable text (song, key, chords with numerals and names, melody degrees, YouTube URL with timestamp) so Jayant can spot-check by ear.

## Phase 1: Lab, tracks T1, M1 to M3, P1 to P3, Q1

- Frontend shell, auth, Today screen (simple).
- Audio engine with smplr, iOS unlock, cadences, guitar-voiced chords.
- Answer pad with note name + degree labels, piano roll (static reveal), fretboard (voicing display).
- Backend: Trial logging, ratings, interleaved sampling, level unlock, confusion matrix.
- Deploy.

Acceptance:
- Works on iPhone Safari with ringer off and on Android Chrome.
- 20-trial set interleaves unlocked items, random keys, random octaves, rotating timbres.
- Every trial logged. Progress screen shows accuracy and a confusion heatmap.

## Phase 2: Clip engine and Bridge

- ClipPlayer with lead-in, polling loop, speed, playsinline, error handling, debug panel for time jitter.
- Synced piano roll and chord lane on video playback.
- Bridge flow: find tonic (T2, T3), then melody and chord questions from the concept index.
- Bar-shift override and report bad clip.
- "Hear it in a song" cards in Lab.
- Listen-through after Bridge.

Acceptance:
- 50 random TRAIN clips play at the right place on mobile within about 0.5 s of the intended note after the lead-in.
- Highlight stays in sync through a loop.
- Dead videos are auto-marked and skipped.

## Phase 3: Bass and chords in depth

- Tracks B1 to B5, Q2 to Q6, P4 to P7 in Lab and Bridge.
- Progression questions on real clips (name the loop).
- Voicings for every chord answer, capo suggestion.
- Play Along screen.

Acceptance:
- In Bridge, a 4-chord loop question shows chord windows, accepts numerals, reveals names + numerals + voicings + capo suggestion.
- Play Along loops a bar range with current/next chord and fretboard.

## Phase 4: Test mode and transfer metrics

- TEST split pool, full transcription flow (tonic, mode, key name via fretboard, bass, quality, numerals, optional melody).
- No answers sent before submission. Step-by-step graded report.
- Progress: Lab vs real-song accuracy per track, test per-step history, response times.
- Today plan builds the 20 minute session automatically with a weekly Test.

Acceptance:
- A test song never appeared anywhere in the app before its test.
- Headline real-song accuracy shown on Today.

## Phase 5: Modes, advanced harmony, key changes

- Tracks T4, T5, M4, M5, P5, P8 to P10, Q7, Q8.
- Modal reveal screen with characteristic chord and note on fretboard.
- Key change detection questions from KEY_CHANGES pool.

## Phase 6: Mic

- Sing-back practice step (pitchy) for M and T tracks.
- Strum check (meyda chroma) with a calibration screen for G4.

## Phase 7: Own songs

- Annotation editor: paste YouTube link, set start/end, tap tonic, tap bar lines, enter chords per bar (numeral or name), optional melody by tapping degrees while looping at 0.5x. Saves in corpus schema.
- Use for Bollywood and any song missing from the dataset.
- Optional: Claude API helper that drafts a chord chart from the user's partial input, always marked "unverified" until the user confirms by ear.

## Phase 8: Polish

- Settings, CSV export, streaks, monthly YouTube availability recheck job.

## Definition of success (track in Progress)

- Real song accuracy on TEST songs rising month over month on tonic, numerals and quality.
- Gap between Lab and real-song accuracy shrinking.
- Average time to name a 4-chord loop in a new song dropping.
- Jayant can take a pop song he has never analysed, find the key on guitar, and play the progression along with the recording.
