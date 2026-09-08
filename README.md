# Signal log — daily hash commitments

This repository publishes daily SHA-256 digests of files that are held
privately. It contains no market data, no positions, no returns and no
algorithm — only digests.

## What this is for

A private repository proves nothing about *when* its contents were fixed. Git
commit dates are author-settable metadata, and history can be rebuilt and
force-pushed, so a verifier opening a private repository later cannot tell a
record accumulated over years from one constructed the night before.

Publishing a digest fixes the content it commits to. Once a digest is public,
the file it stands for cannot be substituted: any different content produces a
different digest. The files themselves stay private and may be released later,
at which point each day's content is checkable against the digest published on
that day.

What establishes the timing is not this repository's own commit dates — those
are as settable as any other. It is that each row was pushed to a **public**
repository on the day it covers, and that GitHub's public events feed, mirrored
by third parties such as GH Archive, records those pushes independently of the
author.

## Format

`hashes.tsv` is append-only:

```
date	file	sha256	bytes	chain
```

- **date** — UTC date of the commitment
- **file** — basename only; the private repository's structure is not disclosed
- **sha256** — digest of the file as it stood on that date
- **bytes** — file size
- **chain** — `SHA256(chain_previous || record)`, with a genesis value of 64 zeros

The chain means no row can be altered, inserted, removed or reordered without
breaking that row and every row after it.

## Verifying

Chain integrity, at any time:

```
python3 verify_hashlog.py
```

Once a file has been released, check it against the digest published on a given
date:

```
python3 verify_hashlog.py --file ./live_backfill_log.csv --date 2026-09-08
```

A match shows the released file is byte-identical to the content committed to
on that date.

## What this does not claim

- It does not disclose or attest to the *contents* of the private files.
- It does not attest to trading results, and nothing here is a performance
  record or an offer of any kind.
- Chain integrity alone does not establish timing; a whole log could be
  regenerated consistently. Timing rests on the public push record described
  above.

## Related

Pre-registered detection protocol, published in full:
https://github.com/keishi-takagi/tda-monitoring

That repository is a separate project with a separate purpose and is not
covered by the commitments in this one.

## License

MIT.
