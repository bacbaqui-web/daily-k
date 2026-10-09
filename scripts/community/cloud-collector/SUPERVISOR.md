# Supervised cloud collector integration — 0.3.0

## What this actually runs

This is executable agent-mediated integration, not a Node daemon, browser service,
or installed schedule. A parent invokes one bounded tick in the enabled Functions
runtime; it claims a GitHub-backed state using an injected transport, runs one
listing page or reviewed post slice, checkpoints, and releases the claim. Existing
hourly topic/news publishers remain separate. No credentials, remote writes, or
schedules are embedded in the package.

The offline integration test runs real local Python state, local file persistence,
and checkpoint logic with a fake browser and CAS store. Real GitHub transport and
browser compatibility still require the parent's authorized first live test.

## Required components

- Approved source package, verified against source-manifest.json.
- Supported cloud browser/CUA initialized as described in RUNNER.md.
- Private fixed-window run directory and private runtime state.
- A private journal path that remains available between invocations.
- One injected GitHub transport implementing the contract below.
- A parent/supervisor who reviews titles and pauses, verifies current CAPTCHA
  permission before solving normally, and never bypasses an access denial.

Only `supervisor_state.py inspect` creates the public allowlisted projection.
It serializes inspection under the private runtime lock, rejects unresolved local execution, checks the actual source and entire raw evidence map, then reruns the
approved offline checkpoint code, so counts/coverage do not come from a stale
summary file. Projection contains opaque run/source/evidence digests, exact fixed
window, local revision, nullable aggregate counts, coverage flags and checkpoint
time. It excludes local paths, titles, native comment IDs/text, source lists,
media, held-content details and private review references.

## Required GitHub transport contract

The parent supplies one object `remote`:

- `read()` returns `{mainSha, state}` for the current main commit. `state` is null
  only when the explicitly authorized state file truly does not exist. A read
  failure is an error, never an empty state. Verify any mirrored state files
  agree before returning. Return no truncated content.
- `compareAndSwap({expectedMainSha, expectedState, nextState, force:false})`
  changes only the approved state path(s), preserving all other files. It must
  first verify main/previous state and atomically CAS main with expected SHA and
  force=false. It returns `{status:'committed'|'conflict'|'unknown', mainSha?}`.
  `conflict` means a verified competing change and no uncertain write. A timeout
  or ambiguous response is `unknown`, never `conflict`.

For the existing connector: read current commit/tree, compare exact state,
serialize only allowlisted JSON, create blobs when needed, create_tree serially
with UTF-8 requests about 40KB or less, preserve its base tree, verify resulting
path/blob SHAs, create_commit, then update_ref(expected_sha, force=false). Keep
successful checkpoints privately. Never force push or use a stale entire tree.

`confirmedCas` journals before attempting CAS and after each result, reads back
exact state, and accepts an uncertain result only when exact readback proves the
intended write. It rebases a verified repository-only conflict up to three times
only when the collector state itself is unchanged. It never repeats a browser
read to recover a CAS ambiguity. Other authors may modify unrelated website data.
The parent must implement this real connector adapter; it is intentionally not
hardcoded to unverified connector names or credentials.

Remote claim success is a concurrency fact, not a claim that Pages/UI is already
updated. Any user-visible status publication must still follow the parent’s
exact-commit Pages and public JSON verification requirements.

## First setup, before a repeating schedule is connected

1. Verify the clean package and actual `source_digest()` from runtime_state.py.
2. Explicitly initialize one run from an actual first listing observation;
   fixed end comes from that observation, never the next wake's clock.
3. Persist that exact first observation using the reviewed one-time setup
   procedure. Keep posts/listings directories and run.json private.
4. Initialize private runtime state and `start-run`. There is no automatic
   replacement/migration of existing state. Preserve previous evidence.
5. Initialize the real remote adapter against the parent's approved path(s).
6. Use one new operationId for the bounded tick and a unique per-invocation
   claimNonce. Generate the latter with `python -c
   "import uuid; print(uuid.uuid4().hex)"` and retain it privately. Separate
   duplicate invocations must generate DIFFERENT nonces even when their scheduled
   operationId is identical. Retrying the same uncertain CAS retains its nonce.
7. Run one tick, independently verify remote state and actual browser result,
   then connect the existing authorized wake mechanism. Do not promise continuous
   activity or production success before that live test.

## Executable Functions integration

Read complete, verified source files with the workspace tool. Load
`supported_tool_runner.js` and `supervised_tick.js` into the SAME Functions cell,
then append this invocation, supplying actual values and the real remote adapter:

```javascript
const privateContext = {
  tools, rootDir, runDir, statePath, journalPath, owner,
  action: 'slice', detailBinding: 'detailTab', sliceSize: 6,
  reviewedIds: specificallyReviewedIds
};
const result = await runSupervisedCollectorTick({
  operationId, claimNonce, owner, remote,
  local: createCollectorLocalAdapter(privateContext)
});
text(result);
```

For one listing page use action:'listing', listingBinding, phase:'initial' or
'resweep', pageNumber, url, previousPage. The next link must be present in the
actual previousPage evidence. Never synthesize pagination URLs. The initial page
is the documented aagag listing. The managed adapter additionally applies the
private runtime fence around every browser/persistence call, while the wrapper
checks the remote claim. The state and source digest are obtained through the
private inspector; callers cannot substitute a remote cursor for local evidence.

An empty reviewedIds list returns title_review_required without post navigation.
The supervisor reviews those actual titles and invokes a NEW tick operationId
with only eligible IDs. Never mark every title approved automatically. Parent
context—not regex alone—handles ambiguous titles and safety holds.

## Result handling and next wake

- checkpointed: verified evidence is stored. Continue one bounded action at a
  time while the current supervisor is active; a later wake resumes the same
  fixed run after checking remote/private state. Do not create overlapping workers.
- already_completed: identical immediate tick delivery was already committed;
  no new browser call is made.
- active_or_uncertain_previous_execution: do not steal the lease, including
  after its clock expiry. Establish whether the previous external call ended.
- title_review_required: review actual titles before another slice.
- queue_exhausted with resweep still required: traverse actual next links and
  perform the final first-page resweep; no fixed page cap establishes coverage.
- verified_complete or closed_with_gaps: the local adapter validates and records
  the terminal outcome. Remote status becomes terminal; stop continuation of
  this window. Holds remain holds and are not successful verification.
- paused/reconciliation_required: do not automatically retry, reset browser,
  replace environment, approve CAPTCHA, or infer user cancellation intent.
- evidence_missing: preserve old fixed window and remote status; no browser
  navigation follows. Unknown counts are not converted to zero.

A repeating parent wake may inspect whether useful bounded work can begin, but
this package does nothing when the agent/tool runtime is inactive. Timing and
throughput must be measured in production; this is not a 24/7 daemon guarantee.

## Explicit recovery and new cycles

`reconcileSupervisedCollector(ctx, review)` is a separate supervisor-only entry
point. It is NEVER called automatically by a tick. It requires an actual private
ready run, `priorExecutionEnded:true`, a private review reference, new operationId
and nonce, and no unexpired remote lease. The reference stays only in the private
journal. This argument is a record of the supervisor’s real review, not authority
for the package to invent approval.

Modes:
- `resume`: source, run, fixed window and private evidence digest must match; local revision cannot regress. A remote-ready/local-revision mismatch after a reviewed local pause/resume can also use this explicit path.
  First resolve local pause using runtime_state.py's explicit review procedure.
- `restart_fixed_window`: only after evidence_missing/paused review, recreate
  the SAME exact window in a new private directory from page one. Reobserve
  evidence; old counts/cursors are not restored as truth. Inspecting from page
  one may no longer recover vanished historical listings; report gaps honestly.
- `advance_cycle`: prior remote state must be terminal; fresh private runKey and
  later exact window end are required. Initialize from a new actual listing
  observation and re-read all current IDs, including previous below-11 posts.

After reconciliation use a NEW tick operationId. Old snapshots and publication
records are untouched. Confirmed source upgrades need separate review, not silent
migration. A partially written private checkpoint can fail exact evidence hashes;
this version deliberately requires supervised reconciliation/reobservation rather
than automatically blessing it.

## Remaining boundary

A preflight check cannot atomically cancel a remote tool call already dispatched.
Unique claim nonces prevent duplicate claim adoption, local+remote fences prevent
new work after detected changes, and no automatic takeover is allowed. The
supervisor must genuinely verify in-flight completion before recovery. Raw
private data must be preserved by the current environment or reobserved; the
public projection is not a private backup. Item publication and its separate
safety/rights/media review are not part of this collector tick.
