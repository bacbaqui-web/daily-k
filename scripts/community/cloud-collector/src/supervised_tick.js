/* Agent-mediated bounded tick. Dependency-injected GitHub CAS contract only.
   No network client, credentials, timer, daemon, or platform writes in this file. */
function stable(v){if(Array.isArray(v))return '['+v.map(stable).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stable(v[k])).join(',')+'}';return JSON.stringify(v);}
function same(a,b){return stable(a)===stable(b);}
function exactKeys(obj,keys){if(!obj||typeof obj!=='object'||Array.isArray(obj)||(Object.keys(obj).some(k=>!keys.includes(k))||keys.some(k=>!Object.prototype.hasOwnProperty.call(obj,k))))throw new Error('Unexpected public state field');}
function validateProjection(p){
 exactKeys(p,['runKey','window','sourceSha256','privateEvidenceDigest','localRevision','progress','coverage','checkpointAt']);
 for(const k of ['runKey','sourceSha256','privateEvidenceDigest'])if(!/^[a-f0-9]{64}$/.test(p[k]))throw new Error('Invalid digest');
 exactKeys(p.window,['start','end']);for(const t of [p.window.start,p.window.end,p.checkpointAt])if(typeof t!=='string'||!/(Z|[+-]\d\d:\d\d)$/.test(t)||!Number.isFinite(Date.parse(t)))throw new Error('Timestamp required');
 if(Date.parse(p.window.start)>=Date.parse(p.window.end)||!Number.isInteger(p.localRevision)||p.localRevision<0)throw new Error('Invalid window/revision');
 exactKeys(p.progress,['observedRecords','qualifiers','candidates']);for(const v of Object.values(p.progress))if(v!==null&&(!Number.isInteger(v)||v<0))throw new Error('Unknown count must be null');
 exactKeys(p.coverage,['listing','resweep','nativeComments','complete']);for(const v of Object.values(p.coverage))if(typeof v!=='boolean')throw new Error('Invalid coverage');
 return p;
}
function validateRemote(s){
 if(s===null)return;
 exactKeys(s,['schemaVersion','revision','fence','operationId','claimNonce','status','lease','projection','updatedAt','lastOutcome']);
 if(!/^[a-f0-9]{32}$/.test(s.claimNonce))throw new Error('Unique invocation nonce required');
 if(s.schemaVersion!==1||!Number.isInteger(s.revision)||s.revision<1||!Number.isInteger(s.fence)||s.fence<1)throw new Error('Invalid remote revision');
 if(!/^[A-Za-z0-9_.-]{1,150}$/.test(s.operationId)||!['ready','running','paused_requires_review','evidence_missing','terminal'].includes(s.status))throw new Error('Invalid operation/status');
 validateProjection(s.projection);
 if(!Number.isFinite(Date.parse(s.updatedAt)))throw new Error('Invalid time');
 if(s.lease!==null){exactKeys(s.lease,['owner','expiresAt']);if(!/^[A-Za-z0-9_.-]{1,100}$/.test(s.lease.owner)||!Number.isFinite(Date.parse(s.lease.expiresAt)))throw new Error('Invalid lease');}
 if((s.status==='running')!==(s.lease!==null))throw new Error('Lease/status mismatch');
 if(s.lastOutcome!==null&&!['checkpointed','queue_exhausted','title_review_required','paused','failed','evidence_missing'].includes(s.lastOutcome))throw new Error('Invalid outcome');
}
async function confirmedCas(remote,local,before,next){
 validateRemote(next);await local.journal({stage:'before_cas',expectedMainSha:before.mainSha,next});
 let base=before;
 for(let n=0;n<3;n++){
  let result;try{result=await remote.compareAndSwap({expectedMainSha:base.mainSha,expectedState:base.state,nextState:next,force:false});}catch{result={status:'unknown'};}
  await local.journal({stage:'cas_result',status:result.status,mainSha:result.mainSha??null});
  const read=await remote.read();validateRemote(read.state);
  if(same(read.state,next)){await local.journal({stage:'confirmed',mainSha:read.mainSha,revision:next.revision});return read;}
  if(result.status==='conflict'&&same(read.state,before.state)){base=read;continue;}
  throw new Error('Remote outcome unconfirmed or state changed; stop without retry');
 }
 throw new Error('Concurrent repository updates; no collection started');
}
async function runSupervisedCollectorTick(ctx){
 const {remote,local}=ctx;
 if(!/^[a-f0-9]{32}$/.test(ctx.claimNonce))throw new Error('Create and privately journal a unique UUID4 hex per invocation');
 if(!/^[A-Za-z0-9_.-]{1,150}$/.test(ctx.operationId)||!/^[A-Za-z0-9_.-]{1,100}$/.test(ctx.owner))throw new Error('Opaque operation/owner required');
 const now=()=>new Date().toISOString();
 const before=await remote.read();validateRemote(before.state);
 if(before.state&&before.state.status!=='ready')return {status:'not_started',reason:before.state.status==='running'?'active_or_uncertain_previous_execution':'review_or_new_cycle_required',remoteRevision:before.state.revision};
 if(before.state?.operationId===ctx.operationId)return {status:'already_completed',remoteRevision:before.state.revision};
 const initial=await local.inspect();
 if(!initial.available){
  if(before.state){const next={...before.state,revision:before.state.revision+1,status:'evidence_missing',lease:null,updatedAt:now(),lastOutcome:'evidence_missing'};await confirmedCas(remote,local,before,next);}
  return {status:'not_started',reason:'private_evidence_unavailable',restartPolicy:'review_then_reobserve_same_fixed_window_from_first_page'};
 }
 validateProjection(initial.projection);
 if(initial.runtimeStatus!=='ready')return {status:'not_started',reason:'local_runtime_not_ready'};
 if(before.state&&(!same(before.state.projection,initial.projection)))return {status:'not_started',reason:'remote_private_checkpoint_mismatch'};
 const claim={schemaVersion:1,revision:(before.state?.revision??0)+1,fence:(before.state?.fence??0)+1,operationId:ctx.operationId,claimNonce:ctx.claimNonce,status:'running',lease:{owner:ctx.owner,expiresAt:new Date(Date.now()+600000).toISOString()},projection:initial.projection,updatedAt:now(),lastOutcome:null};
 let held=await confirmedCas(remote,local,before,claim);
 const guard=async()=>{const fresh=await remote.read();validateRemote(fresh.state);if(!same(fresh.state,claim)||Date.now()>=Date.parse(claim.lease.expiresAt))throw new Error('Remote fence changed/expired');};
 let result;
 try{await guard();result=await local.execute({guard,runtimeRevision:initial.runtimeRevision,sourceSha256:initial.sourceSha256});}
 catch{result={status:'tool_stopped'};}
 const final=await local.inspect();
 const sameRun=final.available&&final.projection.localRevision>=claim.projection.localRevision&&final.projection.runKey===claim.projection.runKey&&same(final.projection.window,claim.projection.window)&&final.projection.sourceSha256===claim.projection.sourceSha256;
 const terminal=sameRun&&['verified_complete','closed_with_gaps'].includes(final.runtimeStatus)&&result.status==='queue_exhausted';
 const safe=sameRun&&['checkpointed','queue_exhausted','title_review_required'].includes(result.status)&&final.available&&(final.runtimeStatus==='ready'||terminal);
 const projection=sameRun?validateProjection(final.projection):claim.projection;
 const outcome=safe?result.status:final.available?'paused':'evidence_missing';
 const next={...claim,revision:claim.revision+1,status:terminal?'terminal':safe?'ready':final.available?'paused_requires_review':'evidence_missing',lease:null,projection,updatedAt:now(),lastOutcome:outcome};
 try{await guard();await confirmedCas(remote,local,held,next);}catch{return {status:'reconciliation_required',reason:'final_remote_outcome_unknown',automaticRetry:false};}
 return {status:safe?'checkpointed':'paused',outcome,runtimeResult:result,remoteRevision:next.revision,nextWake:terminal?'new_cycle_review_required':safe?'continue_bounded_work':'supervisor_review_required'};
}
// Adapter around the existing documented tool runtime. Load supported_tool_runner.js first.
function createCollectorLocalAdapter(ctx){
 const exec=async(command,path,event)=>{const r=await ctx.tools.exec_command({cmd:`python ${collectorShellQuote(ctx.rootDir+'/src/supervisor_state.py')} ${collectorShellArg(command)} ${collectorShellQuote(path)}${event?' --event '+collectorShellArg(JSON.stringify(event)):''}`,max_output_tokens:12000});if(r.exit_code!==0)throw new Error('Local supervisor state unavailable');return JSON.parse(r.output.trim());};
 return {inspect:()=>exec('inspect',ctx.statePath),journal:e=>exec('journal',ctx.journalPath,e),execute:async({guard,runtimeRevision,sourceSha256})=>{
  const base=ctx.tools;const tools={...base,mcp__cua_repl__js:async a=>{await guard();return base.mcp__cua_repl__js(a);},apply_patch:async a=>{await guard();return base.apply_patch(a);},exec_command:async a=>{await guard();return base.exec_command(a);}};
  const managed={...ctx,tools,runtimeRevision,sourceSha256};
  if(ctx.action==='slice'){
    const result=await runManagedCollectorSlice(managed);
    if(result.status==='queue_exhausted'&&result.summary?.listingCoverageComplete===true&&result.summary?.passes?.resweep===true){
      const call=async(command,args)=>{await guard();const r=await tools.exec_command({cmd:`python ${collectorShellQuote(ctx.rootDir+'/src/runtime_state.py')} ${collectorShellQuote(ctx.statePath)} ${collectorShellArg(command)} --args ${collectorShellArg(JSON.stringify(args))}`,max_output_tokens:12000});if(r.exit_code!==0)throw new Error('Terminal state could not be verified');return JSON.parse(r.output.trim());};
      const begin=await call('begin',{revision:result.runtimeRevision,sourceSha256,runDir:ctx.runDir,owner:ctx.owner,leaseSeconds:600});
      const done=await call('finish',{revision:begin.revision,sourceSha256,owner:ctx.owner,fence:begin.lease.fence,outcome:result.summary.complete?'verified_complete':'closed_with_gaps'});
      return {...result,runtimeRevision:done.revision,runtimeStatus:done.status};
    }
    return result;
  }
  if(ctx.action==='listing')return captureManagedCollectorListingPage(managed);
  throw new Error('Explicit bounded action slice/listing required');
 }};
}
if(typeof module!=='undefined')module.exports={runSupervisedCollectorTick,createCollectorLocalAdapter,validateProjection,validateRemote,confirmedCas};

// Explicit supervisor-only recovery. Never invoked automatically by a tick.
async function reconcileSupervisedCollector(ctx,review){
 if(review?.priorExecutionEnded!==true||typeof review.reference!=='string'||!review.reference.trim())throw new Error('Verified prior tool completion and review reference required');
 if(!/^[a-f0-9]{32}$/.test(ctx.claimNonce)||!/^[A-Za-z0-9_.-]{1,150}$/.test(ctx.operationId))throw new Error('New recovery identity required');
 const before=await ctx.remote.read();validateRemote(before.state);
 if(!before.state)throw new Error('No remote run to reconcile');
 if(before.state.lease&&Date.now()<Date.parse(before.state.lease.expiresAt))throw new Error('Active lease must not be overridden');
 const local=await ctx.local.inspect();
 if(!local.available||local.runtimeStatus!=='ready')throw new Error('Verified ready private run required');
 validateProjection(local.projection);
 const old=before.state.projection,p=local.projection;
 if(review.mode==='advance_cycle'){
  if(before.state.status!=='terminal'||p.runKey===old.runKey||Date.parse(p.window.end)<=Date.parse(old.window.end))throw new Error('Previous cycle must be terminal and fresh window later');
 }else if(review.mode==='restart_fixed_window'){
  if(!['evidence_missing','paused_requires_review'].includes(before.state.status)||!same(p.window,old.window))throw new Error('Lost run must restart its exact fixed window');
 }else if(review.mode==='resume'){
  if(!['ready','running','paused_requires_review'].includes(before.state.status)||p.localRevision<old.localRevision||p.runKey!==old.runKey||!same(p.window,old.window)||p.sourceSha256!==old.sourceSha256||p.privateEvidenceDigest!==old.privateEvidenceDigest)throw new Error('Resume requires matching source, run, and actual evidence');
 }else throw new Error('Unknown review mode');
 await ctx.local.journal({stage:'supervisor_review',mode:review.mode,reference:review.reference,priorExecutionEnded:true});
 const next={...before.state,revision:before.state.revision+1,fence:before.state.fence+1,operationId:ctx.operationId,claimNonce:ctx.claimNonce,status:'ready',lease:null,projection:p,updatedAt:new Date().toISOString(),lastOutcome:null};
 await confirmedCas(ctx.remote,ctx.local,before,next);
 return {status:'ready',remoteRevision:next.revision,nextWake:'new_tick_operation_id_required'};
}
if(typeof module!=='undefined')module.exports.reconcileSupervisedCollector=reconcileSupervisedCollector;
