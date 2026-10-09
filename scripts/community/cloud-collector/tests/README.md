# Offline collector checks

Run from `cloud-native/`:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
node --test tests/test_browser_macro.cjs tests/test_supported_tool_runner.cjs
```

Only Python and Node standard libraries are used. Tests create temporary fixtures inside `tests/`, mock browser APIs, and do not browse, access the network, install packages, or touch live run files.

## Covered

- Literal native `ㅋ` threshold: 10 excludes, 11 qualifies; native comment-ID deduplication and conflicting/missing IDs
- Canonical post suffixes across listing passes, pending queues, and raw alias files
- Canonical observation selection: newest comments-complete observation, otherwise newest incomplete; newer threshold crossings survive source/media gaps, and raw aliases plus newer-incomplete-attempt metadata are retained
- Inclusive window bounds, KST-to-UTC conversion, exact-date requirements, and cumulative old/in-window/post-window comment counts
- NSFW markers in aggregator and individual source titles; safety-held qualifiers remain in the qualifier export
- Full-coverage rejection for missing listing rows/passes/pages/boundaries, incomplete comments/sources/images/videos, and absent media evidence
- Comments-only verification for complete native counts below 11, including legacy records without a scope flag; it cannot bypass source/media verification at 11 or more, native comment completeness, exact timestamps, or observed status
- Immutable manifest-backed run initialization/resume, environment/CLI selection, and distinct listing/native/strict coverage
- Explicit unresolved verification holds: pending/retry/export suppression, canonical alias matching, unchanged reasons, no invented classification/counts, and incomplete coverage
- Listing-title policy exclusion before any visit, with exact evidence, null counts, canonical alias handling, and eligible-only boundary checks
- Atomic checkpoint replacement and regeneration after interrupted output; failed browser records containing only `requestedId`
- Bounded browser retry, recovery errors, bot-denial stop, one reload per retry, source expansion, optional source-range headings, and slice stop/3-second throttle
- The stable all-comments control is activated even when already selected, before numeric readiness, to trigger viewport-dependent comment loading
- Numeric comment-count readiness before threshold classification; real zero is distinct from a loading placeholder/null, incomplete row counts retry once, and readiness timeout remains bounded
- Exact counts remain null when incomplete. Trustworthy captured native rows may prove a >=11 lower bound, with a separate minimum/evidence and verification-held status; a partial minimum below 11 remains unknown, never a below-threshold exclusion

## Fixed-window run interface

Initialize a fresh run using the actual timestamp captured at its initial observation. Never substitute a later resume time:

```sh
python src/checkpoint.py init --end '<actual_initial_observation_utc>' --run-dir /path/to/run
DAILYK_RUN_DIR=/path/to/run python src/checkpoint.py pending 12
DAILYK_RUN_DIR=/path/to/run python src/checkpoint.py summary
```

- `--end` is mandatory for `init` and requires an explicit UTC timestamp (`Z` or `+00:00`). The fixed start is exactly 24 hours earlier.
- `run.json` persists the window. Resuming never computes a new cutoff from the current clock. Re-initializing with the identical anchor is idempotent; a different anchor is rejected.
- `--run-dir` overrides `DAILYK_RUN_DIR` and works before or after the subcommand. Without either during initialization, the directory is `runs/<UTC-anchor>/`; the init response returns its absolute path.
- Normal summary/pending invocations without a selected directory retain the original active run `20261009T020332Z` and its exact `2026-10-09T02:03:32.390Z` cutoff.
- Custom runs must have a valid manifest. Initialization refuses to assign a new anchor to preexisting raw evidence without a manifest. An initialization lock prevents competing initializers; an interrupted initialization may leave `.initializing` requiring review before retrying.

## Policy exclusions and coverage meanings

Known listing titles matching any existing explicit title safety rule are excluded before visiting: standalone `ㅇㅎ`, `ㅎㅂ`, or `ㅇㅎㅂ` markers, `sexual_title`, `graphic_or_death_title`, and `private_allegation_title`. No additional topical or editorial filters were introduced. Python and JavaScript share the classifier contract and are tested for exact rule-definition and fixture parity. `listing-exclusions.json` retains the exact title, URL, ID, matched rule/text, any marker, page, phase, and listing observation time. Comment counts, `ㅋ` counts, threshold classification, and exact dates stay null/unverified. Canonical aliases are excluded together. Previously retained raw evidence is preserved but excluded from qualifier exports and retry-facing incomplete lists.

The browser macro independently returns `policy_excluded` for supplied listing titles matching these safety rules before reading any browser property or calling any browser API. Tests use a throwing proxy to verify zero access.

- `policyExcludedCount` / `policyExcludedIDs`: separately evidenced listing-title exclusions
- `listingCoverageComplete`: both contiguous listing passes have exact older dates for all non-policy-excluded, non-held boundary rows and at least one such eligible witness
- `nativeCommentCoverageComplete`: listing coverage plus actual verified native counts and exact listing dates for every nonexcluded discovered row
- `complete`: the existing strict result, also requiring the applicable source/media checks for eligible threshold qualifiers

A source/media gap may leave native-comment coverage true while strict completeness stays false. An all-excluded/all-held final page does not itself establish an older boundary. Excluded and held dates are never represented as inspected. `boundaryHeldDatesUnverified`, `boundaryHeldIDs`, and `boundaryHeldIDsByPass` disclose held rows left outside the boundary proof; their unresolved status still prevents native-comment and overall completeness.

## Manual unresolved verification holds

An optional run-local `verification-holds.json` is an array of explicit records containing nonempty string fields `id`, `title`, `url`, `reason`, and `heldAt`. The collector never populates holds or infers their meaning. The parent/operator supplies the actual listing evidence and authorized reason.

- Held canonical IDs and aliases are omitted from `pending.json`, retry-facing `incompleteIDs`, and candidate/qualifier exports.
- `verificationHeldIDs`, `verificationHeldCount`, and `verificationHolds` expose the current holds and their supplied reasons.
- Holds remain unresolved. Missing raw records remain in `missingIds`, and native-comment/overall completeness stays false while a hold exists. A hold is not a confirmed sexual-content classification or a resolved policy exclusion.
- An explicit hold takes precedence over automatic policy resolution. Held rows are omitted from boundary-date proof and explicitly reported as unverified there. Boundary proof still requires exact older dates for every remaining eligible row and at least one eligible older witness. A held row is never used as that witness, and its raw record may remain missing.
- Raw evidence and the hold file are preserved. Invalid hold files stop checkpoint generation rather than silently dropping protection. Once an authorized decision removes a hold, the next checkpoint uses the current file and may return the row to pending.

Automatic title rules alone cannot guarantee semantic filtering or determine the meaning of ambiguous titles. Uncertain or denied items require explicit review/holds; passing a title regex check is not evidence that content is safe.

## Systemic browser-runtime circuit breaker

Terminal failure chains explicitly identifying a timed-out `Page.enable`, `Runtime.evaluate`, CDP attach/connect, protocol transport operation, or the exact “CDP operation exceeded its deadline before command dispatch” error receive `pauseReason: "browser_runtime_failure"` and `stopBatch: true`. The existing single bounded retry remains; recovery failures can end it early. If the retry succeeds, collection proceeds normally.

`collectSlice` returns immediately after this pause flag, before another throttle/browser call or post. Callers must also stop their outer collection loop on any `stopBatch` result and preserve the checkpoint before reviewing runtime health. Generic record failures and ordinary count/source completeness gaps do not trigger this circuit breaker. The macro does not reset the runtime, create tabs, or alter browser connections.

## Document readiness

Every attempted post read first uses a bounded supported body-attached wait. The diagnostic body-text read is null-safe if the document changes immediately afterward. `documentReadiness` distinguishes `document_not_ready`, `body_attached`, and `loaded_missing_content`; per-attempt header observations retain body presence and ready state when available.

An absent/loading body never becomes a successful empty post or numeric zero count. Earlier exact header and partial-count evidence survive a later readiness failure. Numeric zero comments still require the separate visible numeric-counter and exact native-row checks.

## Partial extraction evidence

A count mismatch or readiness failure retains the header title, exact listing timestamp when observed, and per-attempt header observations. Any available preliminary native comments retain only ID, date, and literal `ㅋ` count, alongside the reported expected count and observation time. Comment text is never retained. This enriches existing browser evaluations without adding reads or requests.

Failed-count records can therefore have known window membership while exact totals remain null/unverified. Conflict-free, all-selected native rows with nonnegative integer counts and real capture context may prove an observed lower-bound qualifier; source/media and exact-total verification remain held. A later missing header does not erase a previously observed exact date; separate header observations preserve what was and was not seen at each attempt.

## Lower bounds, outside-window headers, and temporal uncertainty

- `thresholdEvidence: observed_lower_bound` and `knownLiteralKMinimum` retain a proven threshold without claiming an exact total. Provisional candidates stay `candidateVerificationHeld`; exact count/date partitions remain null in public output. The exporter independently checks native-ID deduplication, conflicts, counts, capture context, and the declared minimum.
- Explicit `outside_window` header records require an actual title, matching observed aagag ID/URL, aware observation time, and an exact timestamp strictly outside the inclusive fixed window. They resolve only header-scoped traversal. Native counts, minima, and qualification remain null; inside/unknown dates cannot use this shortcut.
- Optional `temporal-holds.json` records use `reason: relisted_after_cutoff_original_exact_time_unknown`, `id`, `heldAt`, and initial page/observation-time/displayed-age evidence. That proof must match a stored initial listing. The latest actual header stays unchanged, `originalExactListedAt` stays null, and `inWindow` becomes uncertain. A verified threshold qualifier is retained as verification-held, never silently dropped or represented as definitely in-window. Temporal holds keep native/overall coverage incomplete.
- Supplemental source/media observations use their own `sourceListObservedAt` and `mediaObservedAt`. The original `commentEvidenceObservedAt` is preserved. Missing explicit field timestamps are not replaced with invented times.

## Durable supported-tool adapter and clean package

`src/supported_tool_runner.js` executes only inside the enabled Functions/tools runtime. Its offline Node tests mock browser calls. It requires explicit reviewed IDs, accepts only discovered pagination URLs, and stops on denials, CAPTCHA/runtime pauses, or unverified persistence. Raw evidence is first staged, compared to the actual returned JSON, fsynced, atomically promoted, and reread. `apply_patch` returning by itself never establishes a checkpoint.

See `RUNNER.md` for executable tool-runtime initialization, immutable anchoring, verified first-page persistence, review/slice calls, discovered pagination, resweep, and local export steps. The adapter is not a standalone Node scraper or daemon.

The clean ZIP contains `VERSION` 0.1.0 and `source-manifest.json`. The manifest lists SHA-256 and byte size for every allowlisted code/test/doc file and a deterministic source-tree digest. The same captured bytes are packaged; a concurrent source edit aborts export before artifact commit. Raw runs, private evidence, image/video files, and history snapshots are excluded.

## Read-only snapshot audit

```sh
PYTHONDONTWRITEBYTECODE=1 python tests/audit_snapshot.py runs/<run-id>
```

This independently compares raw native-comment counts and dates with saved normalized output. It does not import the collector implementation. A mismatched `observedAt` is skipped and reported because the live run may be updating. The audit reports when a cumulative qualifier has fewer than 11 `ㅋ` in in-window comments and includes older comments.

`python-results.txt`, `node-results.txt`, and `validation.json` contain the latest test evidence. `live-snapshot-audit.json` is a point-in-time audit, not an assertion that the live run is complete.

## Limits

- Browser mocks do not establish compatibility with the real browser, real site, pagination stability, asynchronous loading, or current selectors.
- Completion validates captured metadata. Image/video content safety, visual context, and resolving actual external source URLs require separate live review.
- `pending.json` intentionally contains never-observed posts only. Incomplete IDs stay visible separately; an explicit bounded retry stage is required to revisit them.
- Selecting an older comments-complete alias over a newer incomplete alias preserves usable evidence but does not claim it is the freshest attempt. Selection metadata identifies newer incomplete aliases, the latest known attempt, and unknown alias timestamps. All raw aliases remain available.
- Atomic rename tests verify interruption recovery at the file-replacement level, not power-loss durability or concurrent multi-writer safety.
