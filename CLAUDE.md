# Ear Trainer: project brief for Claude Code

Read this file first, then the docs in order. Build in the phases from `docs/05-build-plan.md`. Do not skip ahead.

## What this is

A personal ear training web app for one user (Jayant). He plays guitar, has some music theory, and has used Perfect Ear. Built for daily personal use, hosted so he can open it on his phone and laptop.

## The end goal (this decides every tradeoff)

Listen to a real song and, without looking anything up:
1. Find the tonic and name the key (e.g. "E major", "A Dorian")
2. Identify the chord progression, including quality (maj, min, 7ths, sus, add9, dim, slash chords) and function (I, IV, V, vi, bVII, V/V, borrowed iv, etc.)
3. Identify the melody as scale degrees
4. Play those chords on guitar in the real key

If a feature does not move one of these four, it is low priority.

## Core principles (from research, see docs/07-research-report.md)

- **Transfer is the problem, not drills.** Drill accuracy does not carry over to real songs by itself. The headline metric is accuracy on held-out real songs, shown next to drill accuracy so drill scores can never hide a plateau.
- **Always in key context.** No isolated interval naming. Everything is relative to a tonic.
- **Note names plus degree numbers.** Buttons show the real note name AND the degree, e.g. `G# (3)`. Chords show the real name AND Roman numeral, e.g. `C#m (vi)`. Never note names alone. Rotate keys often.
- **Interleave, don't block.** Mix all unlocked items in every set. Weight sampling toward confusions.
- **Feedback on every practice trial. No feedback during tests.**
- **Fade the scaffolding.** Cadence every trial, then occasionally, then never. Real songs have no cadence.
- **Chunks, not single notes.** Progress from single degrees and single chords to 2 to 4 note patterns and 2 to 4 chord progressions mined from real songs.
- **Bass first for chords.** The bass usually plays the chord root. Train hearing the bass line as scale degrees before naming full progressions.
- **Log every trial from day one.** It is the data for adaptive difficulty and for proving progress.

## Stack

- Frontend: React + TypeScript + Vite. Mobile-first layout, works on desktop.
- Backend: FastAPI (Python 3.11+), SQLite via SQLModel. Single user, simple password or token auth via env var.
- Offline data pipeline: Python scripts in `pipeline/`.
- Audio: `smplr` (piano + General MIDI soundfonts for guitar and others), scheduled on AudioContext time.
- Real songs: YouTube IFrame Player API only. Never download audio.
- Mic (later phases): `pitchy` for sung pitch, `meyda` chroma for strummed guitar chords.
- Deploy: one container (FastAPI serves the built frontend). Fly.io, Render or Railway.

## Hard rules

- Never download, cache, or process YouTube audio. Player stays visible, at least 200x200, nothing overlaid on it. Our UI sits beside or below it.
- Data comes from the HookTheory dataset (CC BY-NC-SA 3.0, personal non-commercial use). Keep the attribution in the app footer.
- Do not invent music theory data. Every degree, chord and key in modes 2 and 3 comes from the corpus or from the user's own annotations.
- No leaderboards, coins or gamification beyond a simple streak and progress charts.
- No em dashes in any UI copy.

## Docs

1. `docs/01-curriculum.md`: the skill tree from first note to full song transcription. The heart of the app.
2. `docs/02-data-pipeline.md`: turning HookTheory data into the corpus, chord and key logic, tagging, difficulty.
3. `docs/03-modes-and-screens.md`: Lab, Bridge, Test, Play Along, Progress. Exact flows.
4. `docs/04-tech-and-constraints.md`: YouTube, audio, mic, adaptive engine, schema, gotchas.
5. `docs/05-build-plan.md`: phases with acceptance criteria.
6. `docs/06-guitar.md`: voicings, capo, fretboard, playing what you hear.
7. `docs/07-research-report.md`: the full research with sources. Reference only.
