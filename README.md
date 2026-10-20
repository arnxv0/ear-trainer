# ear-trainer

A personal ear trainer that bridges drills and real songs: find the key, hear the chords and melody as degrees, play it on guitar.

The plan lives in [`CLAUDE.md`](CLAUDE.md) and [`docs/`](docs). Built in phases; **Phase 0, the data pipeline, is done.**

## Data pipeline

Python 3.11+, standard library only.

```sh
python3 -m pipeline.build_corpus     # download the dataset and build the corpus (~30 s)
python3 -m pipeline.spot_check       # print 10 random songs to check by ear
python3 -m pipeline.chords           # every chord interval tuple with its count
python3 -m pipeline.check_youtube    # video availability; run where the app is used
python3 -m unittest discover -s pipeline/tests -t .
```

Output goes to `pipeline/out/`: corpus per split (TRAIN, VALID, held-out TEST), a key-change pool, a concept index linking drill items to song moments, frequency tables and a build report.

## Data

Song analyses from HookTheory TheoryTab via the [Sheet Sage dataset](https://github.com/chrisdonahue/sheetsage) (CC BY-NC-SA 3.0). Personal, non-commercial use.
