# GitHub state adapter, awaiting first-write handoff

This adapter binds reviewed runtime 0.3.0 to the already-connected GitHub tools.
It uses no token, environment secret, browser network client, or extra service.

## Fixed publication boundaries

- Repository: `bacbaqui-web/daily-k`, branch `main`.
- Minimal public checkpoint: `ops/state/aagag-collector.json` only. This is not a
  Pages data path and must not contain candidate titles, raw comments, native
  comment IDs, raw media/source lists, private paths, or review references.
- Clean package destination proposed: `scripts/community/cloud-collector/`.
  Publish the 0.3.0 source-manifest allowlist only, plus separately reviewed
  `integration-github/github_remote.js` and this integration procedure. Never copy
  the cloud working directory, runs, history, private journals, or deliverables.
- Other community/news/live code and all existing data remain unchanged.
- The package SHA is cfa6de729637cb197e18c0e04838f03c08ce7aebc61da5513f0ab6354013538b.
  Adapter has its own manifest. After publishing, record the exact returned commit
  as the supervisor's fixed code pin. Do not invent a pin before the commit exists.

## Transport injection

Load `src/supervised_tick.js` and `github_remote.js` into the same Functions cell.
Call `createCollectorGitHubRemote({tools,journal,hashBlob,validateState:validateRemote,
writeEnabled:false})` for inspection. Enable writes only during the parent's
explicit serialized writer handoff.

`journal(event)` must append using `src/supervisor_state.py journal` to the private
per-run transport journal with fsync. Do not use an in-memory-only function for
writes. `hashBlob(content)` must compute SHA-1 over the exact UTF-8 Git blob frame:
`b'blob '+str(len(bytes)).encode()+b'\0'+bytes`. Use the existing Python execution
tool; no networking or credentials are needed. Verify its stdout is exactly a
40-character lowercase SHA. Both callbacks must fail closed on tool errors.

Read uses a pinned main commit and complete non-recursive trees to prove whether
the state exists. A failed state read is never null. Existing JSON is checked
against its exact blob hash before schema validation. Writes validate the public
allowlist, re-read expected main and state, create a checked blob, create one
small path-only tree against the latest base, and independently walk all changed
ancestors. Every unrelated sibling's name/mode/type/SHA must remain identical.
Then create a single-parent commit, independently re-read its SHA/tree/only parent,
and update main with expected_sha and
force=false. Every successful stage is privately checkpointed. Ref-update
ambiguity returns unknown; the existing confirmedCas performs exact readback.
No retry, replacement environment, or stale ref overwrite is hidden here.

## First real tick and repeatability

1. Parent grants one writer turn after independent adapter review.
2. Fresh cloud listing anchor, package manifest check, private run initialization,
   one-time exact observation persistence, runtime init and start-run follow
   RUNNER.md. Old test runs are not silently adopted or migrated.
3. Use a unique operation ID and UUID4 claimNonce, journal both before invocation.
4. Run one bounded listing or reviewed slice through runSupervisedCollectorTick.
   Read state back and independently verify its SHA, final revision, actual local
   evidence, and browser observation time. The initial listing/bootstrap is not
   proof of complete collection or publication.
5. Only after that live smoke test succeeds may the authorized repeating wake
   call this supervisor. The supervisor reads the fixed pinned package and state
   before each tick. It does not need another agent's memory to resume: local
   run manifest/evidence/runtime state and the public projection are the inputs.
6. Missing private evidence pauses. Active or uncertain calls never have their
   lease stolen. Real supervisor review and the explicit recovery command are
   required for pause/denial/timeout/source upgrades; no automatic browser resets.
7. CAPTCHA may be solved normally only with verified current permission. This
   adapter does not approve or solve challenges. Do not assume a pending custom
   rule form was accepted. Blocked sites are not bypassed.
8. Candidate qualification, safety/rights/media verification, duplicate checking,
   and live homepage publication remain a separate verified gate. The state
   checkpoint is not a claim that new public content exists.

A wake runs bounded work while tools are active. It is not an unattended daemon,
a browser running 24/7, or a throughput guarantee. Never convert an unknown or
held count to zero or report partial coverage as all-post completion.

## Verified so far

- Fourteen local transport tests passed: missing/existing state, exact blob hash,
  CAS success, main conflict, state conflict, unrelated changes, uncertain ref
  readback, write-disabled default, truncation, corrupt state bytes, and wrong commit SHA/tree/parent/extra parent.
- Actual connected GitHub read succeeded at 2026-10-09T13:17Z:
  main `60cad9f2235c984aa15a34bf4010175b571ff168`, state truly absent.
- No remote write, real collector tick, or recurring supervisor setup has run
  from this integration yet.
