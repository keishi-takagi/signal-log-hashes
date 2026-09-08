#!/usr/bin/env python3
"""
hashlog.py — publish daily SHA-256 commitments for privately held files.

Purpose
-------
A private repository proves nothing about *when* its contents were fixed. Git
commit dates are author-settable metadata (GIT_AUTHOR_DATE / GIT_COMMITTER_DATE),
and history can be rebuilt wholesale and force-pushed, so a verifier opening a
private repo later cannot distinguish a record accumulated over years from one
constructed the night before.

This script closes that gap without disclosing anything. It writes the SHA-256
of each tracked file to an append-only log in a PUBLIC repository and pushes it
daily. GitHub's public events feed — mirrored by third parties such as GH
Archive — records each push, and that record is outside the author's control.
Once a hash is published, the file content it commits to is fixed: any later
substitution produces a different digest.

The files themselves stay private and can be released whenever it suits —
a year later, at a sale, or never. Whenever they are released, each day's
content is checkable against the digest published on that day.

Entries are additionally hash-chained: every line incorporates the chain value
of the line before it, so no line can be altered or removed without breaking
every line that follows.

Usage
-----
    python3 hashlog.py                 # hash, append, commit, push
    python3 hashlog.py --no-push       # local only
    python3 hashlog.py --dry-run       # print what would be appended

Cron (daily, after the signal run):
    30 9 * * 1-5 cd /root/hashlog && /usr/bin/python3 hashlog.py >> cron.log 2>&1
"""

import argparse
import hashlib
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# --- configuration ----------------------------------------------------------

# Where this script and the public log live.
REPO_DIR = Path(__file__).resolve().parent

# The append-only public log.
LOG_PATH = REPO_DIR / "hashes.tsv"

# Files to commit to. Resolved relative to this script's own location rather
# than the working directory, so cron and manual runs behave identically.
# Paths are recorded by basename only; the directory structure of the private
# repository is not disclosed.
SIGNAL_LOG_DIR = REPO_DIR.parent / "tda-signal-log"

TRACKED_FILES = [
    SIGNAL_LOG_DIR / "live_backfill_log.csv",
    SIGNAL_LOG_DIR / "live_backfill_log.html",
]

# Dates are stamped in JST, pinned here rather than taken from the environment
# so that manual runs and cron runs agree. The signal pipeline stamps its own
# output with the JST date; if this file used UTC, any run before 09:00 JST
# would record the previous day and the two records would disagree about which
# day a digest covers.
TZ = ZoneInfo("Asia/Tokyo")

HEADER = "date\tfile\tsha256\tbytes\tchain"
GENESIS = "0" * 64

# ----------------------------------------------------------------------------


def sha256_file(path: Path) -> tuple[str, int]:
    """Return (hex digest, byte size) for a file, read in chunks."""
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def read_log() -> list[str]:
    if not LOG_PATH.exists():
        return []
    return [ln for ln in LOG_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]


def last_chain(lines: list[str]) -> str:
    """Chain value of the final data row, or the genesis value if none."""
    for ln in reversed(lines):
        if ln == HEADER:
            continue
        return ln.split("\t")[-1]
    return GENESIS


def chain_next(prev: str, fields: list[str]) -> str:
    """chain_n = SHA256(chain_{n-1} || record_n)."""
    return hashlib.sha256((prev + "\t".join(fields)).encode("utf-8")).hexdigest()


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO_DIR)] + args,
                          capture_output=True, text=True, check=check)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-push", action="store_true", help="commit locally, do not push")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = ap.parse_args()

    stamp = datetime.now(TZ).strftime("%Y-%m-%d")
    lines = read_log()
    prev = last_chain(lines)

    # Refuse to append a second time for the same date: the log is a daily
    # commitment, and duplicate rows would make the chain ambiguous.
    existing_dates = {ln.split("\t")[0] for ln in lines if ln != HEADER}
    if stamp in existing_dates and not args.dry_run:
        print(f"{stamp} already recorded. Nothing to do.")
        return 0

    new_rows = []
    for path in TRACKED_FILES:
        if not path.exists():
            print(f"WARNING: {path} not found; recording as MISSING.", file=sys.stderr)
            digest, size = "MISSING", 0
        else:
            digest, size = sha256_file(path)
        fields = [stamp, path.name, digest, str(size)]
        prev = chain_next(prev, fields)
        new_rows.append("\t".join(fields + [prev]))

    if args.dry_run:
        for r in new_rows:
            print(r)
        return 0

    with LOG_PATH.open("a", encoding="utf-8") as f:
        if not lines:
            f.write(HEADER + "\n")
        for r in new_rows:
            f.write(r + "\n")

    for r in new_rows:
        print(r)

    # Commit and push.
    try:
        run_git(["add", "--", LOG_PATH.name])
        if run_git(["diff", "--staged", "--quiet"], check=False).returncode == 0:
            print("No change to commit.")
            return 0
        run_git(["commit", "-m", f"hashlog {stamp}"])
        if args.no_push:
            print("Committed. Push skipped (--no-push).")
            return 0
        run_git(["push", "origin", "HEAD"])
        print("Pushed.")
    except subprocess.CalledProcessError as e:
        print(f"git failed: {e.stderr.strip()}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
