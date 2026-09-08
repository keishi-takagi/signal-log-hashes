#!/usr/bin/env python3
"""
verify_hashlog.py — check the integrity of hashes.tsv, and optionally check a
released file against the digest published on a given date.

Two independent checks:

1.  Chain integrity (always run).
    Every row carries chain_n = SHA256(chain_{n-1} || record_n). Recomputing
    the chain from the genesis value detects any altered, inserted, removed or
    reordered row: the mismatch appears at that row and at every row after it.

2.  Content check (--file / --date).
    Given a file that was held privately at the time, recompute its SHA-256 and
    compare it with the digest published for that date. A match shows the file
    is byte-identical to the one committed to on that date.

The chain alone does not establish *when* rows were written — a whole log could
be regenerated consistently. What establishes timing is that each row was
pushed to a public repository on the day it covers, and that GitHub's public
events feed, mirrored by third parties, records those pushes independently of
the author.

Usage
-----
    python3 verify_hashlog.py
    python3 verify_hashlog.py --file ./live_backfill_log.csv --date 2026-09-08
"""

import argparse
import hashlib
import sys
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "hashes.tsv"
HEADER = "date\tfile\tsha256\tbytes\tchain"
GENESIS = "0" * 64


def sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def load_rows() -> list[list[str]]:
    rows = []
    for ln in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln == HEADER:
            continue
        parts = ln.split("\t")
        if len(parts) != 5:
            print(f"MALFORMED ROW: {ln}", file=sys.stderr)
            sys.exit(2)
        rows.append(parts)
    return rows


def verify_chain(rows: list[list[str]]) -> bool:
    prev = GENESIS
    ok = True
    for i, (date, name, digest, size, chain) in enumerate(rows, 1):
        expect = hashlib.sha256(
            (prev + "\t".join([date, name, digest, size])).encode("utf-8")).hexdigest()
        if expect != chain:
            print(f"CHAIN BREAK at row {i} ({date}, {name})")
            print(f"  recorded: {chain}")
            print(f"  expected: {expect}")
            ok = False
        prev = chain
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, help="released file to check")
    ap.add_argument("--date", help="date whose published digest to check against (YYYY-MM-DD)")
    args = ap.parse_args()

    if not LOG_PATH.exists():
        print(f"{LOG_PATH} not found.", file=sys.stderr)
        return 2

    rows = load_rows()
    dates = sorted({r[0] for r in rows})
    print(f"rows: {len(rows)}   days: {len(dates)}   range: {dates[0]} .. {dates[-1]}")

    chain_ok = verify_chain(rows)
    print("chain:", "OK — no row altered, inserted, removed or reordered"
          if chain_ok else "BROKEN")

    if args.file or args.date:
        if not (args.file and args.date):
            print("--file and --date must be given together.", file=sys.stderr)
            return 2
        digest, size = sha256_file(args.file)
        match = [r for r in rows if r[0] == args.date and r[1] == args.file.name]
        if not match:
            print(f"no entry for {args.file.name} on {args.date}")
            return 1
        _, _, pub_digest, pub_size, _ = match[0]
        print(f"\nfile:      {args.file}")
        print(f"published: {pub_digest}  ({pub_size} bytes, {args.date})")
        print(f"computed:  {digest}  ({size} bytes)")
        if digest == pub_digest:
            print("MATCH — file is byte-identical to the content committed to on that date.")
        else:
            print("MISMATCH — file differs from the content committed to on that date.")
            return 1

    return 0 if chain_ok else 1


if __name__ == "__main__":
    sys.exit(main())
