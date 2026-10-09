# Supervised integration status (0.3.0)

SUPERVISOR.md is the current integration contract. New executable bounded ticks combine private checkpoints and an injected GitHub CAS adapter. No live remote adapter, recurring schedule or daemon was started by this package. Older upgrade sections below document earlier development stages.

# Runtime upgrade status (0.2.0)

Local code and offline tests have been upgraded. Existing live observations remain unchanged. This is still an agent-mediated collector; no daemon or recurring production connection has been started. See RUNNER.md section 7. Older 0.1.0 deliverables are historical and must not be substituted for the new source-only runtime-upgrade package.

# Cloud-native aagag collector

Created independently on the dot cloud computer on 2026-10-09. No transferred Mac package was read or reused. This is a reusable **agent-mediated macro for the supported cloud-browser tool**, not an unattended daemon. It does not install packages or use credentials, direct HTTP, browser internals, private APIs, browser fingerprint changes, proxy changes, image downloads, or production publishing.

Source version: `0.1.0` (`VERSION`). Start with [RUNNER.md](RUNNER.md) for executable supported-tool orchestration.

## Files

- `src/browser-macro.js`: sequential documented browser operations and read-only DOM extraction; native-comment expansion, numeric-load readiness, ID-deduplicated literal `ㅋ` threshold, source expansion, body-only media metadata, bounded recoverable retry, and stop-on-block behavior
- `src/supported_tool_runner.js`: reviewed-slice and discovered-pagination adapter with verified, fsynced atomic persistence
- `src/core.py`: deterministic normalization, exclusions, dates, and coverage gates
- `src/checkpoint.py`: atomic derived reports and pending queue; retains raw per-post/per-page checkpoints
- `tests/`: standard-library Python and Node mock regression tests; see its README
- `runs/20261009T020332Z/`: actual observed evidence, candidates, unresolved records, and summary

## Fixed observed window

2026-10-08 11:03:32.390 KST through 2026-10-09 11:03:32.390 KST, inclusive. The basis is the exact latest listing/relisting timestamp rendered by aagag, not an original content publication date. Native aagag comments are cumulative as of each actual observation; older comments and comments after the fixed cutoff are counted separately. External-source comment totals are never added to literal `ㅋ` counts.

## Procedure

1. Initialize the supported cloud browser, read its current instructions, and create listing/detail tabs.
2. Load the macro definitions into the same tool runtime.
3. Start at the issue listing; capture only the actual listing container. Follow the next numbered link returned by the current page, preserving page observations. Continue beyond the actual 24-hour boundary; do not stop at a fixed number of pages/posts.
4. For every unique post, wait for the native numeric comment count, select all comments, deduplicate native IDs, and verify unique count against the rendered total. Only literal Unicode `ㅋ` characters in native comment bodies count.
5. Verified totals or trustworthy observed lower bounds of at least 11 retain every eligible threshold qualifier. Lower-bound candidates remain verification-held and never acquire invented exact counts. Below-threshold posts get a verified-count exclusion. Qualifiers expand all visible source titles for marker checks and extract every body image in DOM order with natural dimensions, plus actual video/embed URLs and posters. No full body/comment text or image files are retained.
6. Persist each returned slice before continuing. `python src/checkpoint.py pending 12` regenerates an initial-work queue from the raw files. This queue intentionally excludes already observed records; incomplete/failed records are separately exposed for a bounded repair pass, never silently skipped as completed.
7. Repair recoverable incomplete observations without overriding reported totals. A source list displaying fewer rows than its stated total remains a gap.
8. Resweep from the first listing page to the same fixed boundary for pagination movement, inspect newly found IDs, and confirm exact boundary dates. Only then can listing coverage be complete. Candidate source/media gaps and blocked/failed records remain explicit; they prevent an unqualified full-completion claim.

The macro uses one detail reader and a 3-second politeness interval. This does not guarantee site acceptance: the live run reached an explicit CAPTCHA. The first challenge was solved with explicit user approval, and normal page return was verified. Future challenges require separate approval. Do not switch network, identity, or browser to evade the block.

## Safety and delivery

Known listing-title markers and existing sexual/graphic/private-allegation rules exclude posts before opening them. Ambiguous titles use explicit unresolved verification holds. Automatic title rules alone do not guarantee semantic filtering. Counts alone do not certify that content is suitable to publish: visual/context review is still required. Every eligible observed threshold qualifier is retained in `all-threshold-qualifiers.json`; previously observed source-title exclusions remain audit qualifiers, while known listing exclusions/manual title holds are handled separately. Lower-bound and temporally uncertain eligible qualifiers remain explicitly verification-held candidates. `candidates.json` is never an arbitrary editorial sample.

Final user-facing exports should contain original links, short titles/quotes within 25 words per source, and media URLs/metadata only. Full source lists and per-comment count/date evidence are audit data, not a republication feed. No production/GitHub/schedule changes have been made.

## Current status

The current user-facing result is `deliverables/public-run-report.json`. Its separate listing, native-comment, and full-completion flags are authoritative for that export. Traversal accounting can finish while explicit title/temporal holds or source/native-count gaps remain unresolved. Raw run files are local audit evidence and are not included in the clean ZIP.

## Offline public export and reusable ZIP

After the latest checkpoint has finished writing, run from this directory:

```sh
python history/compare_history.py --run-dir runs/20261009T020332Z
python src/export_public.py --run-dir runs/20261009T020332Z
```

Repeat both commands after the final scan or any repair. They use only existing local
evidence and do not browse, upload, publish, or modify the source run. The exporter
supports `--output-dir` and `--comparison-dir`. It creates:

- `deliverables/public-run-report.json`: every retained candidate in the current
  `candidates.json`, in the same order, with coverage and publication-history annotations
- `deliverables/candidates.csv`: the same candidate rows, with JSON-encoded media,
  captured original links, and publication annotations in individual cells
- `deliverables/source-manifest.json`: version 0.1.0 source inventory, SHA-256/size for every allowlisted code/test/doc file, and deterministic source-tree digest
- `deliverables/dailyk-cloud-macro.zip`: collector/exporter code, offline tests,
  documentation, and the two public exports

The package deliberately excludes raw run files, per-comment records, full source-title
lists, live audit logs, publication-history snapshots, images, and videos. Those local
inputs are needed to recompute an existing scan; the ZIP does not reconstruct missing
evidence. New runs use the manifest-backed initialization procedure in `tests/README.md`.
The published-history snapshot must be separately captured/refreshed before a new
publication-history comparison. No transferred Mac package is used.

Each exported title is capped at 25 whitespace-separated words, with a truncation flag.
Body/comment quotations and alternate source titles are never exported. Media entries
preserve captured DOM order, exact body image URLs and natural dimensions, and video
URLs/posters; no media files are downloaded. The observed aagag post URL is preserved
only when its identity matches. External original URLs come only from separately
captured `original-source-links.json` evidence, never from guessed source IDs. A source
list being expanded/checked does not mean an original host's body was verified.

Exact native counts remain null unless the observation explicitly verifies them. A separately validated `knownLiteralKMinimum` may prove the >=11 threshold while exact totals stay null and verification remains held. Temporal relisting holds preserve the latest actual timestamp and verified count while membership/original exact time remain uncertain. Supplemental source/media times never replace the original comment-observation time. Old,
in-window, and post-cutoff comment counts are published only when the verified total
reconciles with all three date groups. Exact source counts remain observed versus
reported, with a separate gap flag. Excluded, unresolved-held, failed/incomplete, and
unobserved rows use distinct statuses and expose only IDs and safe reasons.

`fullCompletion` stays false while required coverage or verification is unresolved.
Even a complete metadata scan is not visual/context safety approval for publication.
The window ends at 11:03:32.390 KST; cumulative comments reflect each later actual
observation. This differs from the original 08:30 KST edition. Publication identity
overlaps are flags and never remove candidates. The report distinguishes the total
number of stories in that edition from the number matching current candidates.
Unmatched or newly qualifying posts do not establish omissions in the original run.

The exporter rejects changing/inconsistent checkpoints. Missing or stale history
comparisons are labelled explicitly and overlap counts remain null; rerun the history
comparison, then the exporter. The JSON is the authoritative typed output. In the CSV,
null values are empty cells, and a leading apostrophe protects formula-like strings.

Run its focused regression tests with:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_export_public.py' -v
```

Metadata readiness is separate from publication approval. `publicReady` is always false in this exporter. `readyForIndependentReview` requires complete captured metadata and a current unmatched identity comparison; confirmed duplicate IDs come only from captured comparison evidence. Independent safety and rights review is still required.
