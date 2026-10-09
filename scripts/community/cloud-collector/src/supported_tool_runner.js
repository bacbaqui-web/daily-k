/* Executable adapter for the supported Functions/tools runtime, not standalone Node.
 * Read the current cua_repl browser documentation before loading browser-macro.js.
 * This adapter never signs in, solves CAPTCHA, resets browsers, or publishes.
 */
function collectorShellArg(value) {
  if (typeof value !== 'string' || value.includes('\0')) throw new Error('Invalid shell argument');
  return "'" + value.replace(/'/g, "'\\''") + "'";
}
function collectorShellQuote(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || /[\0\n\r]/.test(value)) throw new Error('Expected absolute local path');
  return collectorShellArg(value);
}
function collectorBinding(value) {
  if (!/^[A-Za-z_$][\w$]*$/.test(value || '')) throw new Error('Invalid initialized browser binding name');
  return value;
}
function collectorJSON(result, expectedArray) {
  if (result?.isError) throw new Error('Browser tool returned an error; no automatic retry');
  const text = (result?.content || []).filter(x => x.type === 'text').map(x => x.text).find(x => x.trim().startsWith(expectedArray ? '[' : '{'));
  if (!text) throw new Error('No JSON evidence returned; stop and inspect tool outcome');
  const data = JSON.parse(text);
  if (expectedArray ? !Array.isArray(data) : data === null || typeof data !== 'object' || Array.isArray(data)) throw new Error('Wrong evidence shape');
  return data;
}
const collectorEvidenceVerifier = `import hashlib,json,os,re,shutil,sys
from pathlib import Path
root=Path(sys.argv[1]);stage=Path(sys.argv[2]);expected=json.loads(sys.argv[3])
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
verified=[];prepared=[]
for entry in expected:
 relative=entry['relative']
 if not re.fullmatch(r'(?:posts/\\d+(?:[_-]\\d+)?|listings/(?:initial|resweep)-\\d{4,})\\.json',relative):raise RuntimeError('Unsafe evidence path')
 source=stage/relative;target=root/relative
 if not source.is_file() or source.is_symlink():raise RuntimeError('Staged evidence missing or symlinked: '+relative)
 with source.open('rb') as handle:
  data=handle.read()
  if canonical(json.loads(data))!=canonical(entry['data']):raise RuntimeError('Staged evidence differs from browser result: '+relative)
  os.fsync(handle.fileno())
 prepared.append((source,target,relative,data))
for source,target,relative,data in prepared:
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.is_symlink():raise RuntimeError('Refusing symlink evidence target: '+relative)
 os.replace(source,target)
 with target.open('rb') as handle:
  actual=handle.read()
  if actual!=data:raise RuntimeError('Promoted evidence changed during readback: '+relative)
  os.fsync(handle.fileno())
 directory=os.open(target.parent,os.O_RDONLY)
 try:os.fsync(directory)
 finally:os.close(directory)
 verified.append({'relative':relative,'sha256':hashlib.sha256(actual).hexdigest(),'byteSize':len(actual)})
shutil.rmtree(stage)
print(json.dumps({'verified':True,'durability':'file_and_parent_directory_fsync','files':verified}))`;
async function persistCollectorEvidence(ctx, entries) {
  collectorShellQuote(ctx.runDir);
  if (!Array.isArray(entries) || !entries.length) throw new Error('No evidence to persist');
  const seen = new Set();
  for (const entry of entries) {
    if (!/^(?:posts\/\d+(?:[_-]\d+)?|listings\/(?:initial|resweep)-\d{4,})\.json$/.test(entry.relative) || seen.has(entry.relative)) throw new Error('Unsafe or duplicate evidence path');
    seen.add(entry.relative);
  }
  const stage = ctx.runDir + '/.collector-staging/' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  let patch = '*** Begin Patch\n';
  for (const entry of entries) patch += '*** Add File: ' + stage + '/' + entry.relative + '\n+' + JSON.stringify(entry.data,null,2).split('\n').join('\n+') + '\n';
  const written = await ctx.tools.apply_patch(patch + '*** End Patch');
  if (written?.isError) throw new Error('Evidence staging tool reported an error; no automatic retry');
  const result = await ctx.tools.exec_command({cmd:'# DAILYK_VERIFY_EVIDENCE\npython -c ' + collectorShellArg(collectorEvidenceVerifier) + ' ' + collectorShellQuote(ctx.runDir) + ' ' + collectorShellQuote(stage) + ' ' + collectorShellArg(JSON.stringify(entries)),max_output_tokens:6000});
  if (result.exit_code !== 0) throw new Error('Evidence persistence not verified: ' + result.output);
  const proof = JSON.parse(result.output.trim());
  if (proof.verified !== true || proof.durability !== 'file_and_parent_directory_fsync' || !Array.isArray(proof.files) || proof.files.length !== entries.length || proof.files.some(file => !seen.has(file.relative) || !/^[a-f0-9]{64}$/.test(file.sha256) || !Number.isInteger(file.byteSize) || file.byteSize < 1) || new Set(proof.files.map(file=>file.relative)).size !== entries.length) throw new Error('Incomplete evidence verification proof');
  return proof;
}
async function collectorCheckpoint(ctx) {
  const r = await ctx.tools.exec_command({cmd: `python ${collectorShellQuote(ctx.rootDir + '/src/checkpoint.py')} summary --run-dir ${collectorShellQuote(ctx.runDir)}`, max_output_tokens: 15000});
  if (r.exit_code !== 0) throw new Error('Checkpoint command failed: ' + r.output);
  return JSON.parse(r.output.trim());
}
async function runApprovedCollectorSlice(ctx) {
  const { tools, rootDir, runDir } = ctx;
  const size = ctx.sliceSize ?? 6;
  if (!Number.isInteger(size) || size < 1 || size > 12) throw new Error('Slice size must be 1..12; this is not a full-run cap');
  const pending = await tools.exec_command({cmd: `python ${collectorShellQuote(rootDir + '/src/checkpoint.py')} pending ${size} --run-dir ${collectorShellQuote(runDir)}`, max_output_tokens: 12000});
  if (pending.exit_code !== 0) throw new Error('Pending queue failed: ' + pending.output);
  const items = JSON.parse(pending.output.trim());
  if (!Array.isArray(items)) throw new Error('Pending queue has an invalid shape');
  if (!items.length) {
    const summary=await collectorCheckpoint(ctx);
    const resweepComplete=summary.passes?.resweep===true && summary.listingCoverageComplete===true;
    return {status:'queue_exhausted',summary,resweepStillRequired:!resweepComplete};
  }
  const approved = new Set((ctx.reviewedIds || []).map(String));
  const unreviewed = items.filter(x => !approved.has(String(x.id)));
  if (unreviewed.length) return {status:'title_review_required', items, unreviewedIds:unreviewed.map(x=>x.id), browserCalled:false};
  const binding = collectorBinding(ctx.detailBinding || 'detailTab');
  const response = await tools.mcp__cua_repl__js({code:`nodeRepl.write(JSON.stringify(await collectSlice(${binding},${JSON.stringify(items)})));`, timeout_ms:240000, title:'Collect reviewed eligible posts and checkpoint results'});
  let rows;
  try { rows = collectorJSON(response, true); }
  catch (error) { return {status:'tool_stopped', reason:String(error), toolResult:response, browserRetryAllowed:false}; }
  if (!rows.length) return {status:'tool_stopped',reason:'Browser returned no post evidence',browserRetryAllowed:false};
  const wanted = new Set(items.map(x=>String(x.id))), seen = new Set();
  const entries = rows.map(row=>{
    const id = String(row?.requestedId || '');
    if (!/^\d+(?:[_-]\d+)?$/.test(id) || !wanted.has(id) || seen.has(id)) throw new Error('Unexpected, duplicate, or unsafe observed ID; evidence not persisted');
    seen.add(id);return {relative:'posts/'+id+'.json',data:row};
  });
  let persistence, summary;
  try { persistence = await persistCollectorEvidence(ctx,entries); }
  catch(error) { return {status:'persistence_unverified',reason:String(error),observedIds:rows.map(x=>x.requestedId),checkpointUpdated:false,browserRetryAllowed:false}; }
  try { summary = await collectorCheckpoint(ctx); }
  catch(error) { return {status:'checkpoint_update_failed',reason:String(error),persistence,observedIds:rows.map(x=>x.requestedId),browserRetryAllowed:false}; }
  const blocker = rows.find(x=>x.stopBatch || ['blocked','blocked_or_missing','document_not_ready'].includes(x.status));
  return {status:blocker?'paused':'checkpointed', observedIds:rows.map(x=>x.requestedId), blocker:blocker||null, persistence, summary, automaticCaptchaApproval:false};
}
async function persistCollectorListingObservation(ctx, observed) {
  const {pageNumber,phase} = ctx;
  if (!Number.isInteger(pageNumber) || pageNumber < 1 || !['initial','resweep'].includes(phase)) throw new Error('Invalid listing page or phase');
  if (!Array.isArray(observed?.items) || !observed.items.length || !Array.isArray(observed.pages) || typeof observed.observedAt !== 'string' || !Number.isFinite(Date.parse(observed.observedAt))) return {status:'listing_unverified',evidence:observed};
  const data = {...observed,page:pageNumber,phase};
  let persistence;
  try { persistence=await persistCollectorEvidence(ctx,[{relative:`listings/${phase}-${String(pageNumber).padStart(4,'0')}.json`,data}]); }
  catch(error) { return {status:'persistence_unverified',reason:String(error),checkpointUpdated:false,browserRetryAllowed:false}; }
  return {status:'checkpointed',page:data,persistence,nextLink:data.pages.find(x=>x.number===pageNumber+1)||null};
}
async function captureCollectorListingPage(ctx) {
  const { tools, pageNumber, url } = ctx;
  if (!Number.isInteger(pageNumber) || pageNumber < 1) throw new Error('Positive page number required');
  if (!['initial','resweep'].includes(ctx.phase)) throw new Error('Invalid traversal phase');
  const initial = pageNumber === 1 && ['https://aagag.com/issue/','https://aagag.com/issue/?page=1'].includes(url);
  if (!initial && !ctx.previousPage?.pages?.some(x=>x.number===pageNumber && x.url===url)) throw new Error('Next URL must come from the observed prior-page links');
  const binding = collectorBinding(ctx.listingBinding || 'listingTab');
  const response = await tools.mcp__cua_repl__js({code:`if(await ${binding}.url()===${JSON.stringify(url)})await ${binding}.reload();else await ${binding}.goto(${JSON.stringify(url)});nodeRepl.write(JSON.stringify(await collectListing(${binding})));`,timeout_ms:60000,title:'Capture observed listing links for fixed-window traversal'});
  let data;
  try { data = collectorJSON(response,false); }
  catch(error){return {status:'tool_stopped',reason:String(error),toolResult:response,browserRetryAllowed:false};}
  return persistCollectorListingObservation(ctx,data);
}
if (typeof module !== 'undefined') module.exports={runApprovedCollectorSlice,captureCollectorListingPage,persistCollectorListingObservation,persistCollectorEvidence,collectorJSON,collectorShellQuote};

// Required entry points for repeat execution. Legacy primitives above are for
// one explicitly supervised run, not concurrent or scheduled use.
async function managedCollectorOperation(ctx, operation) {
  const statePath=collectorShellQuote(ctx.statePath);
  const originalTools=ctx.tools;
  const invoke=async(command,args)=>{
    const r=await originalTools.exec_command({cmd:`python ${collectorShellQuote(ctx.rootDir+'/src/runtime_state.py')} ${statePath} ${collectorShellArg(command)} --args ${collectorShellArg(JSON.stringify(args))}`,max_output_tokens:12000});
    if(r.exit_code!==0)throw new Error('Execution fence rejected: '+r.output);
    return JSON.parse(r.output.trim());
  };
  let state=await invoke('begin',{revision:ctx.runtimeRevision,sourceSha256:ctx.sourceSha256,runDir:ctx.runDir,owner:ctx.owner,leaseSeconds:ctx.leaseSeconds??600});
  const guardArgs={revision:state.revision,sourceSha256:ctx.sourceSha256,owner:ctx.owner,fence:state.lease.fence};
  const guard=()=>invoke('guard',guardArgs);
  const tools={...originalTools,
    mcp__cua_repl__js:async a=>{await guard();return originalTools.mcp__cua_repl__js(a);},
    apply_patch:async a=>{await guard();return originalTools.apply_patch(a);},
    exec_command:async a=>{await guard();return originalTools.exec_command(a);}
  };
  let result;
  try { result=await operation({...ctx,tools}); }
  catch(error){result={status:'tool_stopped',reason:String(error),browserRetryAllowed:false};}
  // Unknown tool outcomes and explicit denial require review, never auto retry.
  const blocked=['paused','tool_stopped'].includes(result.status);
  const failed=['persistence_unverified','checkpoint_update_failed','listing_unverified'].includes(result.status);
  try {
    state=await invoke('finish',{...guardArgs,outcome:blocked?'paused_requires_user':failed?'paused_runtime':'ready'});
    return {...result,runtimeRevision:state.revision,runtimeStatus:state.status};
  } catch(error) {
    return {...result,status:'runtime_reconciliation_required',reason:String(error),browserRetryAllowed:false};
  }
}
async function runManagedCollectorSlice(ctx){return managedCollectorOperation(ctx,runApprovedCollectorSlice);}
async function captureManagedCollectorListingPage(ctx){return managedCollectorOperation(ctx,captureCollectorListingPage);}
if(typeof module!=='undefined')Object.assign(module.exports,{managedCollectorOperation,runManagedCollectorSlice,captureManagedCollectorListingPage});
