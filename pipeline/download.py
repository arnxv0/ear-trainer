"""Fetch the HookTheory dataset files into pipeline/raw/. Idempotent.

    python -m pipeline.download            # both files
    python -m pipeline.download --no-raw   # skip the optional 96 MB Raw file
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import sys
import urllib.request
from pathlib import Path

from .common import DATASET_PATH, DATASET_URL, RAW_DATASET_PATH, RAW_DATASET_URL


def _valid_gzip(path: Path) -> bool:
    try:
        with gzip.open(path) as f:
            f.read(1)
        return True
    except (OSError, EOFError):
        return False


def fetch(url: str, dest: Path, force: bool = False) -> Path:
    if dest.exists() and not force and _valid_gzip(dest):
        print(f"  have {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {dest.name} ...", flush=True)
    with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out)
    if not _valid_gzip(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{url} did not return a gzip file")
    tmp.replace(dest)
    print(f"  saved {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def ensure(raw: bool = True, force: bool = False) -> None:
    fetch(DATASET_URL, DATASET_PATH, force)
    if raw:
        try:
            fetch(RAW_DATASET_URL, RAW_DATASET_PATH, force)
        except Exception as err:  # optional file: the build falls back to rule-based functions
            print(f"  warning: Raw file unavailable ({err}); using rule-based chord functions", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-raw", action="store_true", help="skip Hooktheory_Raw.json.gz")
    parser.add_argument("--force", action="store_true", help="download again even if present")
    args = parser.parse_args()
    ensure(raw=not args.no_raw, force=args.force)


if __name__ == "__main__":
    main()
