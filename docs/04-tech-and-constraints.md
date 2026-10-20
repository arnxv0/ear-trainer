# 04. Tech, engine and constraints

## Repo layout

```
ear-trainer/
  CLAUDE.md
  docs/
  pipeline/           # Python offline scripts (02)
    raw/  out/  tests/
  backend/            # FastAPI
    app/
      main.py  models.py  engine.py  routes/  data_loader.py
    tests/
  frontend/           # React + TS + Vite
    src/
      audio/          # smplr wrapper, scheduler, cadences, voicings playback
      youtube/        # ClipPlayer
      components/     # AnswerPad, PianoRoll, Fretboard, ChordLane
      screens/        # Today, Lab, Bridge, Test, PlayAlong, Progress, Settings
      theory/         # spelling, numerals, voicings (shared logic, unit tested)
  Dockerfile
```

## YouTube clip engine (`frontend/src/youtube/ClipPlayer`)

Facts from the IFrame API docs and developer policies:
- `seekTo` and `start` snap to the nearest keyframe. Playback can begin up to about 2 s early. So: seek to `segment.start - 1.5`, and run our own highlight timer from `getCurrentTime()`.
- `end` is whole seconds only. Implement looping ourselves: poll `getCurrentTime()` every 50 to 100 ms while playing; when past `window.end`, `seekTo(window.start - lead, true)`.
- `setPlaybackRate` is not guaranteed, rounds unsupported values, and resets on every load. Reapply after each load, listen to `onPlaybackRateChange`, show the actual rate.
- Mobile: `playerVars: { playsinline: 1, controls: 1, rel: 0 }`. Call `playVideo()` synchronously inside the tap handler. Handle `onAutoplayBlocked` by showing a tap-to-play button.
- Errors 100, 101, 150: mark segment unavailable via API.
- Policy: player visible, at least 200x200 (480x270 recommended), nothing overlaid on it, no audio-only, no background play, no download or storage of content. Our piano roll and answer pad sit beside or below it.
- Measure `getCurrentTime()` jitter on the user's devices in a debug panel during Phase 2, and tune the lead and poll interval.

Synchronized piano roll: map `getCurrentTime()` (plus alignment override offset) to note and chord windows. Use `requestAnimationFrame` interpolation between polls for smooth playhead.

## Audio engine (`frontend/src/audio`)

- Library: `smplr`. Piano: SplendidGrandPiano. Guitar and others: Soundfont instruments (acoustic_guitar_nylon, acoustic_guitar_steel, electric_guitar_clean, plus one non-guitar like string_ensemble_1 or electric_piano_1).
- Self-host or cache samples. smplr's default sample host is GitHub Pages, which rate-limits. Copy needed samples into `frontend/public/samples/` or cache with the browser Cache API on first load.
- Schedule everything against `AudioContext.currentTime`, never `setTimeout`.
- iOS: Web Audio is muted when the ringer switch is off. In the first user tap: `audioContext.resume()` and start a looping silent `<audio>` element. Also try `navigator.audioSession.type = "playback"` where supported.
- Cadences: I-IV-V-I with smooth voice leading, in guitar voicing for guitar timbres. Minor: i-iv-V-i. Modal contexts: I-bVII-IV-I (Mixolydian), i-IV-i (Dorian).
- Chord playback: block and arpeggiated options, using the voicing from `theory/voicings` so Lab chords sound like the guitar shape shown.

## Mic (later phases)

Sung pitch (`pitchy`):
- getUserMedia with `echoCancellation: false, noiseSuppression: false, autoGainControl: false`.
- Analyse 2048-sample frames, keep frames with clarity > 0.9, median over 300 to 500 ms.
- Fold to the target's octave and grade within ±40 cents.
- Do not use singing as a warm-up right before Test questions (a study found it lowered dictation scores). Offer it as its own practice step.

Strummed chord check (`meyda` chroma):
- Compute 12-bin chroma over about 1 s after onset.
- Cosine similarity to the binary template of the target chord's pitch classes. Accept above a threshold tuned on the user's guitar (calibration screen: strum 5 known chords).
- Show which pitch classes were strong vs expected. This is a confidence aid, not a strict grader.

## Adaptive engine (`backend/app/engine.py`)

Item = a specific question type and answer, e.g. `M:deg:b7:major`, `P:numeral:bVII:major`, `Q:quality:m7`, `T:tonic:bridge`, or a specific corpus question window.

- **Elo-style ratings** for the user per item and per track, and for each corpus question window (item difficulty). Initialize corpus items from the difficulty prior (02, step 6). Update after every scored trial. K factor higher for new items.
- **Level unlock**: when the user's track rating on the current level's items passes a threshold (start: expected accuracy 85% on those items), unlock the next level. Never re-lock.
- **Sampling** for a set: probability proportional to `w_weak * (1 - p_correct) + w_confuse * confusion_mass + w_spacing * f(time since last seen) + w_new * is_new`. Default weights 0.4, 0.3, 0.2, 0.1. Interleave across tracks in warm-up; focus track dominates in Bridge.
- **Confusion matrix** per track: answered vs correct. Feeds the heatmap and sampling.
- **Scaffold fading**: per track, scaffold level steps down when rating rises: cadence every trial, tonic note only, cadence every 4 trials, every 8, none, then occasional mid-set key change to train noticing a new key.
- **Bridge clip selection**: target clips with predicted accuracy 65 to 80% (the learning zone).
- **Test**: no adaptation during the test; results update ratings afterwards with a higher weight for transfer metrics.

## Data model (SQLite via SQLModel)

```
Trial(id, ts, session_id, mode[lab|bridge|test|listen|play], track, level,
      item_id, segment_id?, window_t0?, window_t1?, key_tonic, key_mode,
      scaffold_level, timbre, stimulus_json, answer, correct_answer,
      correct bool, response_ms, replays int, speed float, alt_reading bool)
Rating(subject[user|item], item_id, track, rating, n, last_seen)
Unlock(track, level, unlocked_at)
Session(id, started, ended, plan_json)
SegmentOverride(segment_id, bar_shift int, dead bool, note)
TestResult(id, segment_id, ts, step_scores_json, answers_json)
Annotation(id, yt_id, payload_json)    # self-annotated songs, same schema as corpus
Settings(key, value)
```

Log everything. Export CSV from Settings.

## API (FastAPI)

```
GET  /api/today                       -> session plan
POST /api/session/start|end
GET  /api/lab/next?track=&n=          -> list of stimuli (backend picks items, frontend synthesizes)
GET  /api/bridge/next?track=&n=       -> clip windows + questions
GET  /api/test/next                   -> one TEST segment, questions only, no answers
POST /api/test/{id}/submit            -> graded report
POST /api/trial                        -> log + rating update, returns feedback payload
GET  /api/concept/{concept}/clips      -> "hear it in a song" moments
GET  /api/progress                     -> charts data
POST /api/segment/{id}/override        -> bar shift / dead
POST /api/annotation                   -> self-annotated song
```

Test answers must not be sent to the frontend before submission.

## Theory module (shared, unit tested)

Implement once in Python (pipeline, backend) and mirror in TypeScript (frontend), with shared JSON test fixtures so both agree:
- Key spelling and note names.
- Degree labels and Roman numerals.
- Chord symbols from root + quality + inversion.
- Guitar voicing lookup and generation (06).
- Capo suggestion.

## Auth and deploy

- Single user. `APP_TOKEN` env var; frontend stores it after a one-time entry. All `/api` routes require it.
- One Docker image: build frontend, FastAPI serves `frontend/dist` and `/api`. SQLite on a persistent volume.
- HTTPS required (mic access needs it).

## Testing

- Pipeline: unit tests for spelling, quality mapping, numerals, function classification, beat-to-seconds conversion. Snapshot test on 20 hand-checked songs.
- Backend: engine tests (rating updates, unlock, sampling distribution).
- Frontend: theory module tests with the shared fixtures. Manual checklist for iOS Safari and Android Chrome audio and YouTube.
