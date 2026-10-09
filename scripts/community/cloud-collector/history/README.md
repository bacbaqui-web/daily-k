# Offline published-history comparison

This tool is an annotation step. It does not edit the source run, filter candidates,
publish anything, or contact a network. Every normalized observed record is retained;
every input candidate and threshold qualifier must appear in the corresponding output.

## Captured publication authority

`published-history.snapshot.json` contains only comparison metadata:

- 171 story records from all 13 indexed community editions, October 3–9 AM
- 108 records from the publicly deployed legacy `feed.json` (86 regular, 22 tagged)
- 279 records total, representing 275 canonical aagag IDs

Legacy feed entries are labelled separately. They are public stored history, not a
claim that they are currently rendered by the community-edition UI. The snapshot
covers current public files, not every removed record in all historical Git commits.

Authority is the read-only GitHub connector snapshot of commit
`8bc40f1cd2a68e76fd22d9b32ecef9f1adbbdc94`, committed October 8 at 23:49:54 UTC.
The Pages build and deployment for that exact commit succeeded at 23:51:21 UTC:
https://github.com/bacbaqui-web/daily-k/actions/runs/37861615522

The deployed community index explicitly contains October 9 AM:
https://github.com/bacbaqui-web/daily-k/blob/8bc40f1cd2a68e76fd22d9b32ecef9f1adbbdc94/docs/data/community/index.json

`published-history.evidence.json` records immutable URLs, blob hashes, index and tree
coverage, deployment identity, and capture time. The local October 9 AM draft was
only a supplemental check: its Git blob hash exactly matches the independently
verified deployed file. The draft's existence alone was not publication evidence.

No complete post bodies, comment text, media binaries, credentials, or Mac-package
files were saved or consumed for this comparison.

## Recompute after another scan checkpoint

From `cloud-native`:

```sh
python history/compare_history.py --run-dir runs/20261009T020332Z
python -m unittest discover -s history -p 'test_compare_history.py' -v
```

Or use an absolute run path. Optional flags: `--snapshot PATH` and `--output-dir PATH`.
Default output is `history/comparisons/<run-directory-name>/`:

- `comparison-summary.json`: counts, hashes, coverage state, and interpretation limits
- `all-observed-comparison.json`: every normalized input row
- `all-threshold-comparison.json`: every retained source threshold qualifier
- `candidate-comparison.json`: every source candidate

The source checkpoint is read-only. Separately read files must agree in row counts,
IDs, row values, and hashes. A changing/torn checkpoint causes bounded read retries
and then an explicit failure without writing a new comparison. Once source writes
finish, rerun. A comparison's source timestamp is recorded so a stale result is clear.

An offline rerun does **not** refresh publication history. To refresh that snapshot,
use the approved read-only GitHub connector to obtain current main, its Pages
completion status, immutable `/docs/data/community/index.json`, every indexed
edition at the same SHA, and `/docs/data/feed.json`. Retain only comparison metadata
in the same schema and update the evidence file. Never assume a local draft is public.

## Identity and review flags

- Canonical aagag ID matches ignore the numeric relisting suffix, including `_1`
  and `-1` (and `_2`/`-2`), whether found in native IDs, prefixed IDs, or aagag URLs.
- Exact normalized original/source URLs establish an overlap too. Normalization
  removes fragments and known tracking parameters and sorts query parameters.
  Other sites retain scheme, host, and all nontracking parameters to avoid broad
  false-positive matches. Aagag links canonicalize to the same issue ID.
- Media URL and normalized title overlaps are separate review flags. Neither alone
  means an already-published identity. Title matching is NFC/case/whitespace exact,
  not fuzzy. Alternate source titles may also produce a flag.
- `original-source-links.json` is used when present; unavailable source URLs remain
  unavailable. Missing identity matches are not proof that similar content is new.
- Published overlaps are never silently removed or decremented from the all-qualifier
  count. Unresolved verification gaps remain the source scan's responsibility.

## Timing distinctions

The current fixed listing/relisting window is October 8, 2026 02:03:32.390 UTC through
October 9, 2026 02:03:32.390 UTC (11:03:32.390 KST to 11:03:32.390 KST). It is not an
original publication window. Native literal `ㅋ` counts are cumulative as of each
actual observation, including older and post-cutoff comments; observation timestamps
and the old/window/post-window count fields are preserved.

The previous October 9 AM edition uses an 08:30 KST cutoff, or October 8 23:30 UTC.
Its five published stories were observed later, around 23:35–23:39 UTC. The later
macro scan has a different fixed window and later actual observations. A newly
qualifying or unmatched post cannot automatically be called a miss in the original
smaller run. Partial-scan counts are provisional. Use the source coverage status
and rerun this comparison when the full scan finishes.

## Verification

`test_compare_history.py` contains 12 standard-library regression tests covering
suffix aliases, URL normalization, external numeric IDs, title/media-only flags,
legacy scope, source-link enrichment, row retention and held qualifiers, source
immutability, and rejection of inconsistent checkpoints. See `tests-result.txt`.
