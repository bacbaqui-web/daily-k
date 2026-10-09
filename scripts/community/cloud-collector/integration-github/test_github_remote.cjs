const {test}=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {createCollectorGitHubRemote}=require('./github_remote.js');
const hashBlob=s=>crypto.createHash('sha1').update('blob '+Buffer.byteLength(s)+'\0'+s).digest('hex');
const H=c=>c.repeat(40),response=x=>({structuredContent:{content:JSON.stringify(x)},isError:false});
function fixture({present=false,sideChange=false,uncertain=false,wrongCommitTree=false,wrongCommitParent=false,extraCommitParent=false,wrongCommitSha=false}={}){
 let main=H('a'),state=present?{x:1}:null,blob=null,trees={},commits={},calls=[],log=[];
 const entry=(path,sha,type='tree')=>({path,sha,type,mode:type==='tree'?'040000':'100644'});
 function makeRoot(root,leaf){trees[root]=[entry('ops',H('c')),entry('docs',H('d'))];trees[H('c')]=leaf?[entry('state',H('e'))]:[];trees[H('e')]=leaf?[entry('aagag-collector.json',leaf,'blob')]:[];}
 makeRoot(H('b'),state?hashBlob(JSON.stringify(state)+'\n'):null);commits[main]=H('b');
 const tools={
 mcp__codex_apps__github_fetch:async({url})=>{
  calls.push(url);
  if(url.includes('raw.githubusercontent'))return {structuredContent:{content:blob??JSON.stringify(state)+'\n'}};
  if(url.endsWith('/git/ref/heads/main'))return response({ref:'refs/heads/main',object:{type:'commit',sha:main}});
  if(url.includes('/git/commits/')){const id=url.split('/').pop();return response({sha:wrongCommitSha&&id===H('3')?H('9'):id,tree:{sha:wrongCommitTree&&id===H('3')?H('9'):commits[id]},parents:[{sha:wrongCommitParent&&id===H('3')?H('9'):H('a')},...(extraCommitParent&&id===H('3')?[{sha:H('8')}]:[])]});}
  const id=url.split('/').pop();return response({sha:id,truncated:false,tree:trees[id]});
 },
 mcp__codex_apps__github_create_blob:async({content})=>{blob=content;return response({sha:hashBlob(content)});},
 mcp__codex_apps__github_create_tree:async r=>{
  assert.equal(r.base_tree_sha,H('b'));assert.equal(r.tree_elements.length,1);
  trees[H('f')]=[entry('ops',H('1')),entry('docs',sideChange?H('9'):H('d'))];
  trees[H('1')]=[entry('state',H('2'))];trees[H('2')]=[entry('aagag-collector.json',r.tree_elements[0].sha,'blob')];
  return response({sha:H('f')});
 },
 mcp__codex_apps__github_create_commit:async r=>{assert.equal(r.parent_sha,main);commits[H('3')]=r.tree_sha;return response({sha:H('3')});},
 mcp__codex_apps__github_update_ref:async r=>{calls.push('UPDATE_REF');assert.equal(r.force,false);assert.equal(r.expected_sha,main);main=r.sha;state=JSON.parse(blob);if(uncertain)throw Error('timeout');return response({object:{sha:main}});}
 };
 const config={tools,journal:async e=>log.push(e),hashBlob:async s=>hashBlob(s),validateState:s=>{if(s!==null&&typeof s.x!=='number')throw Error('bad');},writeEnabled:true};
 return {config,calls,log};
}
test('missing state proven by nonrecursive trees',async()=>{const f=fixture();assert.deepEqual(await createCollectorGitHubRemote(f.config).read(),{mainSha:H('a'),state:null});});
test('pinned raw state verified against Git blob',async()=>{const f=fixture({present:true});assert.equal((await createCollectorGitHubRemote(f.config).read()).state.x,1);});
test('CAS writes state only and confirms',async()=>{const f=fixture(),r=createCollectorGitHubRemote(f.config);assert.equal((await r.compareAndSwap({expectedMainSha:H('a'),expectedState:null,nextState:{x:2},force:false})).status,'committed');assert.equal((await r.read()).state.x,2);assert.equal(f.log.at(-1).stage,'github_ref_confirmed');});
test('repository conflict does not write',async()=>{const f=fixture();assert.equal((await createCollectorGitHubRemote(f.config).compareAndSwap({expectedMainSha:H('9'),expectedState:null,nextState:{x:2},force:false})).status,'conflict');assert.equal(f.log.length,0);});
test('state conflict does not write',async()=>{const f=fixture({present:true});assert.equal((await createCollectorGitHubRemote(f.config).compareAndSwap({expectedMainSha:H('a'),expectedState:null,nextState:{x:2},force:false})).status,'conflict');});
test('unrelated tree mutation rejected before commit',async()=>{const f=fixture({sideChange:true});await assert.rejects(()=>createCollectorGitHubRemote(f.config).compareAndSwap({expectedMainSha:H('a'),expectedState:null,nextState:{x:2},force:false}),/Unrelated/);assert.equal(f.log.at(-1).stage,'github_tree');});
test('uncertain update never retried and exact readback works',async()=>{const f=fixture({uncertain:true}),r=createCollectorGitHubRemote(f.config);assert.equal((await r.compareAndSwap({expectedMainSha:H('a'),expectedState:null,nextState:{x:2},force:false})).status,'unknown');assert.equal((await r.read()).state.x,2);});
test('write disabled by default',async()=>{const f=fixture();delete f.config.writeEnabled;await assert.rejects(()=>createCollectorGitHubRemote(f.config).compareAndSwap({}),/disabled/);});
test('truncated tree is not missing state',async()=>{const f=fixture(),orig=f.config.tools.mcp__codex_apps__github_fetch;f.config.tools.mcp__codex_apps__github_fetch=async a=>a.url.includes('/git/trees/')?response({sha:a.url.split('/').pop(),truncated:true,tree:[]}):orig(a);await assert.rejects(()=>createCollectorGitHubRemote(f.config).read(),/Incomplete/);});
test('wrong state hash is rejected',async()=>{const f=fixture({present:true});f.config.hashBlob=async()=>H('0');await assert.rejects(()=>createCollectorGitHubRemote(f.config).read(),/hash mismatch/);});

for(const flag of ['wrongCommitTree','wrongCommitParent','extraCommitParent','wrongCommitSha'])test(flag+' stops before updating ref',async()=>{const f=fixture({[flag]:true});await assert.rejects(()=>createCollectorGitHubRemote(f.config).compareAndSwap({expectedMainSha:H('a'),expectedState:null,nextState:{x:2},force:false}),/commit tree\/parent mismatch/);assert.equal(f.calls.filter(x=>x==='UPDATE_REF').length,0);});
