"""Check which corpus videos are still public and embeddable, via YouTube oEmbed.

Run this on the machine (and in the country) where the app will be used:
availability and region locks differ by location. Results are cached in
pipeline/out/yt_status.json and merged into the corpus (`yt_ok`) on the next
`python -m pipeline.build_corpus`. Rerun monthly.

    python -m pipeline.check_youtube                  # check everything not checked in 30 days
    python -m pipeline.check_youtube --limit 50       # a quick sample
    python -m pipeline.check_youtube --recheck-days 0 # force a full recheck
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .common import OUT_DIR

OEMBED = "https://www.youtube.com/oembed?url={url}&format=json"
STATUS_PATH = OUT_DIR / "yt_status.json"
DEAD_CODES = {401, 403, 404}


def video_ids() -> list[str]:
    ids = set()
    for path in sorted(OUT_DIR.glob("corpus_*.json")):
        ids.update(s["yt"] for s in json.loads(path.read_text())["segments"])
    if not ids:
        raise SystemExit("No corpus found. Run `python -m pipeline.build_corpus` first.")
    return sorted(ids)


def check(video_id: str, timeout: float = 15) -> tuple[bool | None, int | str]:
    """(ok, code): ok is True if embeddable, False if gone/blocked, None if unknown."""
    url = OEMBED.format(url=urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe=""))
    req = urllib.request.Request(url, headers={"User-Agent": "ear-trainer-availability-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status
    except urllib.error.HTTPError as err:
        return (False if err.code in DEAD_CODES else None), err.code
    except (urllib.error.URLError, TimeoutError) as err:
        return None, type(err).__name__


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="check at most this many videos")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between requests (be polite)")
    parser.add_argument("--recheck-days", type=int, default=30, help="skip videos checked more recently than this")
    args = parser.parse_args()

    cache = json.loads(STATUS_PATH.read_text()) if STATUS_PATH.exists() else {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.recheck_days)
    todo = [v for v in video_ids() if v not in cache or cache[v].get("ok") is None or datetime.fromisoformat(cache[v]["checked"]) < cutoff]
    if args.limit is not None:
        todo = todo[: args.limit]
    print(f"{len(todo)} videos to check ({len(cache)} cached). Ctrl+C stops safely.")

    done = 0
    try:
        for vid in todo:
            ok, code = check(vid)
            cache[vid] = {"ok": ok, "code": code, "checked": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            done += 1
            if done % 100 == 0:
                STATUS_PATH.write_text(json.dumps(cache, indent=0))
                print(f"  {done}/{len(todo)}", flush=True)
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nStopped early; progress saved.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(cache, indent=0))

    values = [v["ok"] for v in cache.values()]
    print(f"Checked {done} now. Cache: {values.count(True)} available, {values.count(False)} unavailable, {values.count(None)} unknown.")
    print("Run `python -m pipeline.build_corpus` to merge this into the corpus.")


if __name__ == "__main__":
    main()
