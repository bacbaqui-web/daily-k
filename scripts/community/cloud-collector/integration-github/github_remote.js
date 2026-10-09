/* GitHub connector adapter. No credentials or raw collector evidence. Load
   supervised_tick.js first, or inject its validateRemote export. */
function collectorGitHubData(result) {
  if (!result || result.isError) throw new Error('GitHub connector failed');
  let value = result.structuredContent;
  for (let depth = 0; depth < 5; depth++) {
    if (typeof value === 'string') return JSON.parse(value);
    if (value && typeof value.content === 'string') return JSON.parse(value.content);
    if (value && value.structuredContent) { value = value.structuredContent; continue; }
    if (value && typeof value === 'object') return value;
    break;
  }
  throw new Error('Missing structured GitHub response');
}
function collectorCanonical(value) {
  if (Array.isArray(value)) return '[' + value.map(collectorCanonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k)+':'+collectorCanonical(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
function createCollectorGitHubRemote({tools, journal, hashBlob, validateState, writeEnabled=false}) {
  const repo='bacbaqui-web/daily-k', path='ops/state/aagag-collector.json';
  if (typeof journal!=='function' || typeof hashBlob!=='function' || typeof validateState!=='function') throw new Error('Durable journal, Git blob hash, state validator required');
  const api='https://api.github.com/repos/'+repo;
  const get=async suffix=>collectorGitHubData(await tools.mcp__codex_apps__github_fetch({url:api+suffix}));
  const sha=v=>{if(!/^[a-f0-9]{40}$/.test(v))throw new Error('Invalid Git SHA');return v;};
  const equal=(a,b)=>collectorCanonical(a)===collectorCanonical(b);
  async function tree(id) {
    const t=await get('/git/trees/'+sha(id));
    if(t.sha!==id || t.truncated!==false || !Array.isArray(t.tree))throw new Error('Incomplete tree');
    if(new Set(t.tree.map(x=>x.path)).size!==t.tree.length)throw new Error('Duplicate tree entry');
    return t.tree;
  }
  async function inspectTree(root) {
    const levels=[];let id=root;
    for(const segment of path.split('/')) {
      const entries=id ? await tree(id):[];levels.push(entries);
      const found=entries.find(x=>x.path===segment);
      if(segment!=='aagag-collector.json' && found && (found.type!=='tree'||found.mode!=='040000'))throw new Error('Unsafe state parent');
      id=found?.sha??null;
    }
    const leaf=levels[2].find(x=>x.path==='aagag-collector.json');
    if(leaf && (leaf.type!=='blob'||leaf.mode!=='100644'))throw new Error('Unsafe state file');
    return {levels,blobSha:leaf?.sha??null};
  }
  async function snapshot() {
    const ref=await get('/git/ref/heads/main');
    if(ref.ref!=='refs/heads/main'||ref.object?.type!=='commit')throw new Error('Unexpected main ref');
    const mainSha=sha(ref.object.sha), commit=await get('/git/commits/'+mainSha);
    if(commit.sha!==mainSha)throw new Error('Commit mismatch');
    const treeSha=sha(commit.tree.sha), branch=await inspectTree(treeSha);
    let state=null;
    if(branch.blobSha) {
      // Contents pinned to immutable commit; missing state is proven by tree,
      // never inferred from a failed or forbidden file request.
      const raw=await tools.mcp__codex_apps__github_fetch({url:'https://raw.githubusercontent.com/'+repo+'/'+mainSha+'/'+path});
      if(raw.isError)throw new Error('State content unavailable');
      let payload=raw.structuredContent;
      const content=typeof payload?.content==='string'?payload.content:payload?.structuredContent?.content;
      if(typeof content!=='string'||await hashBlob(content)!==branch.blobSha)throw new Error('State bytes/hash mismatch');
      state=JSON.parse(content);validateState(state);
    }
    return {mainSha,state,treeSha,branch};
  }
  async function read(){const s=await snapshot();return {mainSha:s.mainSha,state:s.state};}
  async function compareAndSwap({expectedMainSha,expectedState,nextState,force}) {
    if(!writeEnabled)throw new Error('Remote writes disabled until explicit writer handoff');
    if(force!==false)throw new Error('Force must be false');
    sha(expectedMainSha);validateState(expectedState);validateState(nextState);
    if(nextState===null)throw new Error('State deletion forbidden');
    const before=await snapshot();
    if(before.mainSha!==expectedMainSha||!equal(before.state,expectedState))return {status:'conflict',mainSha:before.mainSha};
    const content=JSON.stringify(nextState,null,2)+'\n', expectedBlob=sha(await hashBlob(content));
    await journal({stage:'github_intent',expectedMainSha,path,expectedBlob});
    const blob=collectorGitHubData(await tools.mcp__codex_apps__github_create_blob({repository_full_name:repo,content,encoding:'utf-8'}));
    if(blob.sha!==expectedBlob)throw new Error('Created blob mismatch');
    await journal({stage:'github_blob',sha:blob.sha});
    const request={repository_full_name:repo,base_tree_sha:before.treeSha,tree_elements:[{path,mode:'100644',type:'blob',sha:blob.sha}]};
    if(unescape(encodeURIComponent(JSON.stringify(request))).length>40000)throw new Error('Tree request too large');
    const created=collectorGitHubData(await tools.mcp__codex_apps__github_create_tree(request));sha(created.sha);
    await journal({stage:'github_tree',sha:created.sha});
    const after=await inspectTree(created.sha);
    if(after.blobSha!==expectedBlob)throw new Error('Final state blob mismatch');
    const segments=path.split('/');
    const trim=(entries,segment)=>entries.filter(x=>x.path!==segment).map(({path,mode,type,sha})=>({path,mode,type,sha})).sort((a,b)=>a.path.localeCompare(b.path));
    for(let i=0;i<3;i++)if(!equal(trim(before.branch.levels[i],segments[i]),trim(after.levels[i],segments[i])))throw new Error('Unrelated tree change');
    const commit=collectorGitHubData(await tools.mcp__codex_apps__github_create_commit({repository_full_name:repo,parent_sha:expectedMainSha,tree_sha:created.sha,message:'Checkpoint supervised aagag collector state'}));sha(commit.sha);
    await journal({stage:'github_commit',sha:commit.sha});
    const committed=await get('/git/commits/'+commit.sha);
    if(committed.sha!==commit.sha || committed.tree?.sha!==created.sha || !Array.isArray(committed.parents) || committed.parents.length!==1 || committed.parents[0]?.sha!==expectedMainSha)throw new Error('Created commit tree/parent mismatch');
    await journal({stage:'github_commit_verified',sha:commit.sha,treeSha:created.sha,parentSha:expectedMainSha});
    // Journal before dispatch. Any ambiguous update is unknown, not a verified
    // conflict. confirmedCas must read back before considering another action.
    await journal({stage:'github_ref_intent',sha:commit.sha,expectedMainSha});
    try {
      const updated=collectorGitHubData(await tools.mcp__codex_apps__github_update_ref({repository_full_name:repo,branch_name:'main',sha:commit.sha,expected_sha:expectedMainSha,force:false}));
      const actual=updated.object?.sha??updated.sha;
      if(actual!==commit.sha)return {status:'unknown'};
      await journal({stage:'github_ref_confirmed',sha:commit.sha});
      return {status:'committed',mainSha:commit.sha};
    } catch {return {status:'unknown'};}
  }
  return {read,compareAndSwap};
}
if(typeof module!=='undefined')module.exports={createCollectorGitHubRemote,collectorGitHubData};
