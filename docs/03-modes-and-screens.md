# 03. Modes and screens

Five screens: **Today**, **Lab**, **Bridge**, **Test**, **Play Along**, plus **Progress** and **Settings**. Mobile-first. Keyboard shortcuts on desktop for every answer.

## Shared components

- **Answer pad.** Buttons labelled with real note name plus degree, e.g. `F# (3)`. For chords: `Bm (ii)`. Only unlocked items appear. Keyboard: number keys for degrees, letters for chords as configured.
- **Piano roll.** Horizontal time axis, vertical pitch. Left edge shows note names for the current key, with in-key rows tinted and the tonic row highlighted. Chord blocks render in a lane under the melody with symbol plus numeral. During playback a playhead moves. On reveal, notes light up with degree labels.
- **Fretboard.** 12 to 15 frets, standard tuning. Shows a chord voicing, or highlights where a note/tonic is. Tappable to play notes (useful for T6 and G2).
- **Context control.** Shows current scaffold level: Cadence every trial / Tonic only / Every N trials / None.
- **Replay buttons.** Replay, replay context, "resolve to tonic" (plays the target then walks stepwise to 1), "compare" (plays your answer then the correct one).

## Today (home)

- One button: **Start today's session** (the 20 minute plan from 01).
- Two numbers side by side, same size: **Lab accuracy (7 days)** and **Real song accuracy (7 days)**. Real song accuracy is the headline.
- Streak, minutes this week.
- Shortcuts to each mode.

## Lab

Synthesized drills for all tracks.

Flow per trial:
1. Context: cadence (I-IV-V-I with guitar or piano voicing) or tonic note or drone or nothing, based on scaffold level. Random key each trial or each set (setting).
2. Stimulus: note / interval-in-key / bass note / chord / progression / phrase.
3. User answers.
4. Feedback immediately: correct or not, the right answer on the piano roll, "compare" plays theirs vs correct, "resolve to tonic" option. For chords, show guitar voicing in the real key.
5. Every 5 to 8 trials, a **"Hear it in a song"** card: a Bridge clip from the concept index that contains the item just practiced. One tap plays it, piano roll highlights the moment. No question, just exposure.

Set composition: interleave all unlocked items across the selected tracks, sampling weighted by (low rating, high confusion, time since last seen). New level items appear at 30 to 40% of trials when first unlocked.

Stimulus variety: random octave including below tonic, timbre rotates (piano, nylon or steel guitar, one more GM sound), tempo varies slightly. Chords in guitar voicings by default.

## Bridge

Real song clips from TRAIN and VALID splits only.

Clip selection: from the concept index for the current focus track and level, filtered by available videos, ordered by difficulty near the user's current rating.

Flow per clip:
1. **Play** button (user gesture, required on mobile). Player visible. Clip starts 1 to 2 s before the segment start.
2. **Find the tonic** (always first, scored on track T). Candidate pad or 12-note keyboard depending on T level. Tap a candidate to hear it on top of the paused song.
3. Then 1 to 3 focus questions on the same clip. Examples:
   - "What degree does the melody land on at the end of this phrase?" (segment loops the phrase)
   - "Bass degree on this chord?" (chord windows shown as blocks on the timeline, current one highlighted)
   - "Which numeral is the 3rd chord?"
   - "Quality of the highlighted chord?"
   - "Name the 4-chord loop" (P4+)
4. Reveal with piano roll synced to the video: notes and chords light up in time. Corpus answer is shown with real names and numerals and guitar voicings.
5. Controls: loop current window, 0.75x speed, shift alignment -1 / +1 bar (saves override), report bad clip.

Grading against the user's tonic: if the user's tonic is a relative major/minor or modal reinterpretation of the corpus tonic, accept and grade later answers relative to the user's choice, flag "alternate reading".

## Listen-through

After the Bridge block, auto-play the session's clips back to back with the piano roll and chord lane in sync, degrees and numerals visible. No questions. Skip button. This is passive exposure tied to practice.

## Test

TEST split only. These songs never appear in Lab, Bridge, Listen-through or Play Along until the user has tested on them. After a test the song moves to a "reviewed" pool and can appear elsewhere.

Flow: one song section, the full transcription task from 01 (tonic, mode, key name, bass degrees, qualities, numerals, optional melody). No feedback until done. Then a step-by-step report: each answer vs corpus, with the clip replayable at each step. Per-step scores are stored and charted.

Unlimited replays and looping are allowed (real transcription works that way). Speed control allowed. Time to answer is recorded.

Default cadence: once a week from the Today plan. Can be run any time.

## Play Along

Pick any clip already practiced in Bridge or reviewed in Test (or any TRAIN clip).

- Video plays with a chord lane showing current and next chord, symbol, numeral, and voicing on a fretboard.
- Loop, speed (0.75x, 1x), count-in.
- Capo selector: shows the capo position that makes the most chords open shapes, and the shape names to play.
- "Hide chords" toggle: play along by ear, reveal per bar.
- Optional mic check (later phase): after each bar, shows whether the strummed pitch classes matched the chord.

## Progress

- Real song accuracy vs Lab accuracy over time, per track. The gap between them is the transfer gap.
- Per-item rating table and a confusion heatmap (degrees: 12x12, chords: by numeral).
- Test history: per-step scores over time.
- Average response time per track (faster recognition is real progress even at the same accuracy).
- Levels unlocked per track.

## Settings

- Label style: note names + degrees (default), degrees only.
- Key rotation: every trial / every set / fixed.
- Timbres enabled.
- Scaffold override.
- Daily session length.
- Auth token.
- Data: export trial log as CSV.
