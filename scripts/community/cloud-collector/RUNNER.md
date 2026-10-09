# Supported-tool runner (version 0.3.0)

This package is an agent-mediated collector for the dot cloud browser. It is not a standalone Node browser program, daemon, scheduled scraper, or publication feed. Node is used only for offline tests. The live adapter runs inside the enabled Functions/tools runtime; browser operations run through `tools.mcp__cua_repl__js` and the initialized CUA session. Python handles local checkpoints and exports.

Prerequisites: the enabled `cua_repl.js`, `exec_command`, and `apply_patch` tools; a cloud workspace containing this package; Python 3; and explicit task authorization. If the current tool documentation or API differs, stop and adapt to the documented contract. Do not use HTTP clients, private browser APIs, direct CDP commands, new identities, proxies, or alternative environments to bypass a denial.

## 1. Verify the package

After extracting the ZIP, run from its root:

```sh
python - <<'PY'
import hashlib,json
from pathlib import Path
manifest=json.loads(Path('source-manifest.json').read_text())
assert Path('VERSION').read_text().strip()==manifest['version']
for entry in manifest['files']:
    data=Path(entry['path']).read_bytes()
    assert len(data)==entry['byteSize'],entry['path']
    assert hashlib.sha256(data).hexdigest()==entry['sha256'],entry['path']
print('Verified source package',manifest['version'])
PY
```

The manifest covers the allowlisted source, offline tests, and documentation. It excludes run evidence, screenshots, images, video files, private history snapshots, and raw native-comment/source-title data.

## 2. Initialize the documented cloud browser

Read the current `cua_repl` instructions. Its first call, or the first call after a JavaScript-only reset, must contain only one documented entry-point call. For a newly requested cloud listing tab, the current entry point is:

```javascript
var listingTab = await cua.createBrowserTab("cdp", "https://aagag.com/issue/");
```

Read the returned browser documentation and state before continuing. If reusing an existing task, refresh its documentation and select only a verified existing tab. Do not reset, close, replace, or operate tabs belonging to other tasks or the user. This procedure does not authorize recovery from access denial or CAPTCHA.

In a later CUA call, create the single detail reader if needed:

```javascript
var detailTab = await cua.createBrowserTab("cdp", "about:blank");
```

Load the exact reviewed contents of `src/browser-macro.js` as the code of a subsequent CUA call. File reading occurs through the workspace tool, not browser filesystem access. One executable Functions example is:

```javascript
const rootDir = "/absolute/path/to/cloud-native";
const source = await tools.exec_command({cmd:"cat src/browser-macro.js",workdir:rootDir,max_output_tokens:20000});
if (source.exit_code !== 0) throw new Error("Collector source unavailable");
text(await tools.mcp__cua_repl__js({code:source.output,title:"Load reviewed cloud collector definitions"}));
```

Replace the absolute path with the actual verified package location. Read the complete source; never execute a truncated tool result.

## 3. Capture the actual anchor, then initialize the run

In CUA, capture the first listing observation after bounded list readiness:

```javascript
await listingTab.playwright.locator('#listIssue a.article').first().waitFor({state:'attached',timeoutMs:12000});
var initialListing = await collectListing(listingTab);
nodeRepl.write(JSON.stringify(initialListing));
```

Retain this exact JSON observation. Use its actual `observedAt` value, not the current time on a later attempt:

```sh
python src/checkpoint.py init --end '<initialListing.observedAt>' --run-dir /absolute/path/to/run
```

The command returns the selected run directory and fixed `run.json` window. Reinitializing that directory with a different cutoff is rejected. Normal resume never moves the anchor.

Load the exact contents of `src/supported_tool_runner.js` at the beginning of a Functions cell, then append:

```javascript
const ctx={tools,rootDir:"/absolute/path/to/cloud-native",runDir:"/absolute/path/to/run",phase:"initial",pageNumber:1};
// captured must be the exact serialized JSON returned by initialListing.
const captured = /* insert that JSON object as data */ {};
const result=await persistCollectorListingObservation(ctx,captured);
text(result);
if(result.status==="checkpointed") store("collector.previousPage",result.page);
```

The `{}` placeholder deliberately fails verification; it is not usable listing evidence. Replace it with the actual returned JSON. Never interpolate title/source text as executable code. This persistence step preserves the original anchor observation without a second browser request.

Functions cells have fresh JavaScript scopes. Include the adapter source in each cell that invokes its functions. CUA browser bindings live in the separate persistent browser session. Do not run the adapter with `node src/supported_tool_runner.js` expecting a live browser.

## 4. Review, collect, and verify one bounded slice

First ask the adapter for the current queue with no approved IDs. Append this invocation after the adapter definitions in Functions:

```javascript
const result=await runApprovedCollectorSlice({tools,rootDir:"/absolute/path/to/cloud-native",runDir:"/absolute/path/to/run",detailBinding:"detailTab",sliceSize:6,reviewedIds:[]});
text(result);
```

Review every returned title semantically. Regex rules alone do not guarantee suitability. Do not approve all IDs programmatically. Uncertain or denied items require explicit `verification-holds.json` records and remain unresolved. Known title-rule exclusions are removed before navigation.

After review, call the same function with only the specifically reviewed eligible IDs:

```javascript
const result=await runApprovedCollectorSlice({tools,rootDir:"/absolute/path/to/cloud-native",runDir:"/absolute/path/to/run",detailBinding:"detailTab",sliceSize:6,reviewedIds:["ACTUAL_REVIEWED_ID"]});
text(result);
```

The adapter recomputes pending work, refuses unreviewed rows, collects one slice, stages the exact returned JSON, verifies it, fsyncs and atomically promotes it, rereads it, and only then rebuilds the summary. `checkpointed` requires a persistence proof with SHA-256, byte count, and file/parent-directory fsync. A patch acknowledgment alone is insufficient.

Stop the outer loop on `paused`, `tool_stopped`, `listing_unverified`, `persistence_unverified`, or `checkpoint_update_failed`. Preserve/review available evidence before any retry. `checkpoint_update_failed` may already have durable raw evidence: repair the local checkpoint without repeating browser reads. Never automatically retry a denied action or infer CAPTCHA approval. Runtime failures marked `stopBatch` require a pause and supported runtime-health review; the runner does not reset browsers or create recovery tabs.

A generic record failure is not complete coverage. Native-count discrepancies stay unverified. A trustworthy observed minimum of at least 11 may retain a verification-held lower-bound qualifier while exact totals stay null.

## 5. Continue only through discovered pagination links

Load the adapter in Functions and use the previous verified observation:

```javascript
const previousPage=load("collector.previousPage");
const link=previousPage.pages.find(p=>p.number===previousPage.page+1);
if(!link) throw new Error("No observed next-page link; review coverage rather than guessing a URL");
const result=await captureCollectorListingPage({tools,rootDir:"/absolute/path/to/cloud-native",runDir:"/absolute/path/to/run",listingBinding:"listingTab",phase:"initial",pageNumber:link.number,url:link.url,previousPage});
text(result);
if(result.status==="checkpointed") store("collector.previousPage",result.page);
```

Do not synthesize page URLs or stop after a fixed page/post count. A page size or slice size is not a full-run cap. Confirm the fixed-window boundary with exact eligible header dates and at least one eligible older witness. Held dates stay explicitly unverified; they are not older witnesses.

Perform the final `resweep` from the first listing page, using the same fixed manifest cutoff and newly observed pagination links. Queue exhaustion alone does not prove a completed resweep or full verification. The returned `resweepStillRequired` uses the verified resweep pass and listing-coverage flag; completed traversal with unresolved holds does not trigger endless resweeps.

For newly discovered IDs, actual header-only `outside_window` evidence can resolve records definitively outside the window without comment collection. Unknown/inside timestamps cannot use that shortcut. Temporal relisting ambiguity requires an explicit `temporal-holds.json` record: retain qualifying evidence with uncertain membership, never invent an earlier exact date.

## 6. Export locally after checkpointing

```sh
DAILYK_RUN_DIR=/absolute/path/to/run python src/checkpoint.py summary
python history/compare_history.py --run-dir /absolute/path/to/run
python src/export_public.py --run-dir /absolute/path/to/run --output-dir /absolute/path/to/output
```

Refresh publication history through an authorized separate task when needed. The comparison is not a new network crawl. Re-run comparison/export after changed evidence; stale comparisons are explicitly labelled. Exports include every current retained candidate with evidence/verification status, capped titles, and metadata only. They do not publish, create schedules, make GitHub changes, or provide visual/context safety clearance.

See `tests/README.md` for the full offline verification suite and the distinct listing, native-comment, source/media, manual-hold, lower-bound, and temporal-hold semantics.

## 7. Version 0.2.0: fenced repeat execution (offline-tested)

This upgrade is **not installed in production and does not start any process**.
It adds a private local state coordinator, not an unattended daemon or durable
remote hosting service. The browser still requires the active, authorized tool
runtime and semantic title review. No timer, credentials, remote state, GitHub
writes, or publication approval are created by this package.

For repeated invocations use `runManagedCollectorSlice` and
`captureManagedCollectorListingPage`, never the legacy unguarded primitives.
The managed context additionally needs `statePath`, `runtimeRevision`,
`sourceSha256`, and an opaque `owner` string. Compute the actual source digest:

```sh
python -c "import sys;sys.path.insert(0,'src');from runtime_state import source_digest;print(source_digest())"
```

Initialize a **new private state file** with `runtime_state.py STATE init --args
'{"sourceSha256":"ACTUAL_DIGEST"}'`. Existing state is never reset. Initialize
the fixed-window run using section 3, and create its empty posts/listings
subdirectories before `start-run`. State commands accept JSON `--args` containing
the last returned revision and sourceSha256. `start-run` additionally takes
runDir; every run directory is one-use across all cycles. Do not initialize a
new state to evade a stopped run.

The managed wrapper acquires one 600-second lease, checks its owner/fence,
revision, actual source digest, fixed run directory and manifest before browser
calls and evidence persistence, then records the outcome. Use only the returned
revision on the next call. Lease expiry never authorizes automatic takeover.
No automatic resume is permitted after tool denial, cancellation, CAPTCHA,
unknown outcome, corrupted persistence or runtime pause. A cancellation-looking
error is an operational outcome, not proof the user intentionally cancelled.

`pause` revokes the execution fence and retains any in-flight lease. `resume`
requires expiry of any retained lease, an explicit reviewReference and
inFlightResolved=true. The operator must establish the old browser/tool call
has actually ended, not merely wait for a clock. A preflight guard cannot abort
an external tool already in flight; therefore these checks provide **supervised
single-writer safety, not daemon-grade fencing**. Do not run overlapping agents.

At begin/resume, the complete private posts/listings filename+SHA map must match
the last checkpoint. Missing, changed or extra files fail closed. Interrupted
writes may therefore require explicit evidence reconciliation; this version
deliberately does not automatically bless an uncertain interrupted checkpoint.
Keep raw evidence private. If it is lost, preserved aggregate counts or cursors
are not proof: stop, review the old operation, and rebuild a verified fixed-window
run from page one rather than claiming a resume.

Terminal outcomes are `verified_complete` (requires complete=true in the actual
summary) or `closed_with_gaps` (requires verified listing traversal and final
resweep). Never call held posts verified. After a terminal cycle, initialize a
fresh 24-hour run and traverse from page one. All current IDs, including previous
below-11 items, must be read anew; old counts cannot suppress a threshold crossing.
Moving pagination still requires the final resweep. Closed-with-gaps is a partial
result and does not erase unresolved holds.

`record-batch` stores only an operationId and payload SHA to detect conflicting
retries. It does not publish or establish that a batch was published. Publication
must independently recheck current remote history, safety/rights review, the
live validator and compare-and-swap before reporting success.

The reviewed production connection remains an external step. Recommended usage
is one agent-mediated worker per bounded slice, preserving private state and
passing the returned revision; any scheduler must first verify active browser,
retained evidence and absence of another worker. This package alone cannot
promise collection while no tool invocation is running.


## 8. Supervised remote-state integration

Version 0.3.0 adds the executable bounded tick, allowlisted projection and injected GitHub CAS contract in SUPERVISOR.md. Use that integration for repeated invocations. Real transport setup, first live verification and scheduling remain the parent’s separate authorized actions.
