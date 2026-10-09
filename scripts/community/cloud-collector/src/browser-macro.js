/* Agent-mediated macro for documented cua_repl browser tabs. No fetch, CDP, sockets,
   browser internals, package imports, downloads, or DOM mutations. Load into the
   same initialized CUA REPL as listingTab/detailTab. Each returned slice must be
   checkpointed by the caller before starting the next slice. */
// Keep these existing title rules in parity with core.TITLE_SAFETY_RULES.
var listingTitleSafetyRules = [
  {
    "code": "source_title_nsfw_marker",
    "pattern": "(?<![ㄱ-ㅎ])(?:ㅇㅎㅂ|ㅇㅎ|ㅎㅂ)(?![ㄱ-ㅎ])"
  },
  {
    "code": "sexual_title",
    "pattern": "비키니|ㅂㅋㄴ|섹스|성관계|야동|젖꼭지|알몸|성인물"
  },
  {
    "code": "graphic_or_death_title",
    "pattern": "총살|처형|참수|시신|시체|자살|고문|성폭행"
  },
  {
    "code": "private_allegation_title",
    "pattern": "불륜|성추행|몰카|강간"
  }
];
var classifyListingTitle = function(title) {
  return listingTitleSafetyRules.flatMap(rule=>{
    const match=String(title||'').match(new RegExp(rule.pattern));
    return match?[{code:rule.code,matchedText:match[0]}]:[];
  });
};
var collectListing = async function(tab) {
  return await tab.playwright.evaluate(() => ({
    url: location.href, observedAt: new Date().toISOString(),
    items: [...document.querySelectorAll('#listIssue a.article')].map((a,order)=>({
      order, id: new URL(a.href).searchParams.get('idx'), url:a.href,
      title:[...(a.querySelector('.title')?.childNodes||[])].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim(),
      age:a.querySelector('.time')?.innerText.trim()||null
    })),
    pages:[...document.querySelectorAll('a[href]')].filter(a=>/^\?page=\d+$/.test(a.getAttribute('href'))).map(a=>({number:Number(a.textContent),url:a.href}))
  }));
};
// Pause only terminal failures whose recorded chain identifies the browser runtime.
var finalizeCollectorFailure = function(result,error) {
  result.status='failed';result.error=String(error);
  if(collectorDenied(error))return {...result,status:'blocked',stopBatch:true,pauseReason:'authorization_or_access_block'};
  const errors=[result.error,...result.attempts.map(entry=>entry.error||'')];
  const runtimeOperation=/Page\.enable|Runtime\.evaluate|\bCDP\b[\s\S]{0,80}(?:attach|connect)|(?:attach|connect)[\s\S]{0,80}\bCDP\b|protocol[\s\S]{0,40}transport/i;
  if(errors.some(message=>/\bCDP operation exceeded its deadline before command dispatch\b/i.test(message)||(runtimeOperation.test(message)&&/timed?\s*out|timeout/i.test(message)))) {
    result.pauseReason='browser_runtime_failure';result.stopBatch=true;
  }
  return result;
};
var collectorIdentity = function(id,url) {
  try { const u=new URL(url); if(u.origin!=='https://aagag.com'||u.pathname!=='/issue/'||!/^\d+(?:[_-]\d+)?$/.test(String(id))||u.searchParams.get('idx')!==String(id))return null; return String(id).split(/[_-]/)[0]; } catch { return null; }
};
var collectorDenied = function(error) { return /approval.?checker|not authorized|permission denied|access denied|action denied|user.?cancel|cancelled by|canceled by|requires.?approval|captcha|verify you are human/i.test(String(error)); };
var collectPost = async function(tab,item) {
  // Known title-policy exclusions never open or read the post.
  const matchedRules=classifyListingTitle(item.title);
  if(matchedRules.length) {
    const marker=matchedRules.find(rule=>rule.code==='source_title_nsfw_marker')?.matchedText||null;
    const reason=marker?'known_listing_nsfw_marker':'known_listing_title_safety_exclusion';
    const evidence={id:item.id,title:item.title,url:item.url,marker,matchedRules,sourceListingPage:item.sourceListingPage??item.page??null,sourceListingObservedAt:item.sourceListingObservedAt??item.listingObservedAt??null,sourceListingPhase:item.sourceListingPhase??item.phase??null};
    return {requestedId:item.id,requestedUrl:item.url,id:item.id,url:item.url,title:item.title,status:'policy_excluded',reason,matchedRules,attempts:[],commentCount:null,kCount:null,thresholdQualified:null,candidate:false,listedAt:null,dateVerified:false,listingEvidence:[evidence]};
  }
  const result={requestedId:item.id, requestedUrl:item.url, attempts:[], headerObservations:[], status:'pending'};
  const requestedIdentity=collectorIdentity(item.id,item.url);
  if(!requestedIdentity)return {...result,status:'failed',stopBatch:true,pauseReason:'invalid_requested_identity'};
  for(let attempt=1;attempt<=2;attempt++) {
    try {
      if(await tab.url()!==item.url) await tab.goto(item.url);
      else if(attempt>1) await tab.reload();
      try {
        await tab.playwright.locator('body').waitFor({state:'attached',timeoutMs:12000});
      } catch(readinessError) {
        result.documentReadiness={state:'document_not_ready',reason:'body_attachment_wait_failed',attempt,at:new Date().toISOString(),error:String(readinessError)};
        throw readinessError;
      }
      const presence=await tab.playwright.evaluate(()=>({documentBodyPresent:!!document.body,documentReadyState:document.readyState||null,id:new URL(location.href).searchParams.get('idx'),url:location.href,listedAtRaw:document.querySelector('#header .odate')?.textContent||null,observedAt:new Date().toISOString(),title:document.querySelector('h1.title')?.innerText||null,all:!!document.querySelector('#comment_sort [sort=all]'),allSelected:!!document.querySelector('#comment_sort [sort=all].on'),commentLoader:!!document.querySelector('#comment .cmt_memo'),history:!!document.querySelector('#history_bar'),historyExpanded:!!document.querySelector('#history_list')&&document.querySelector('#history_list').getBoundingClientRect().height>0,body:!!document.querySelector('#vContent'),error:document.querySelector('h1.title')?null:(document.body?.innerText?.slice(0,1000)??null)}));
      const header={id:presence.id||item.id,url:presence.url||item.url,title:presence.title||null,listedAtRaw:presence.listedAtRaw||null,observedAt:presence.observedAt};
      result.headerObservations.push({attempt,...header,documentBodyPresent:presence.documentBodyPresent,documentReadyState:presence.documentReadyState});
      result.documentReadiness={state:presence.documentBodyPresent===false?'document_not_ready':'body_attached',readyState:presence.documentReadyState??null,attempt,at:presence.observedAt};
      if(header.title&&header.listedAtRaw||!result.listedAtRaw) Object.assign(result,header,{headerEvidenceObservedAt:presence.observedAt});
      if(presence.documentBodyPresent===false||presence.documentReadyState==='loading'&&(!presence.title||!presence.body)) {
        result.documentReadiness.state='document_not_ready';
        result.documentReadiness.reason=presence.documentBodyPresent===false?'body_absent_after_wait':'document_loading';
        throw new Error('Document not ready: '+result.documentReadiness.reason);
      }
      if(!presence.title||!presence.body) {
        result.documentReadiness.state='loaded_missing_content';
        result.status='blocked_or_missing';result.error=presence.error;result.attempts.push({attempt,at:new Date().toISOString(),error:presence.error});return result;
      }
      if(collectorIdentity(presence.id,presence.url)!==requestedIdentity)return {...result,status:'failed',stopBatch:true,pauseReason:'observed_identity_mismatch'};
      // Stable filter also scrolls native comments into view, triggering lazy loading.
      if(presence.all) await tab.playwright.locator('#comment_sort [sort=all]').click();
      await tab.playwright.locator('#comment_cnt strong').filter({hasText:/^\d+$/}).waitFor({state:'visible',timeoutMs:12000});
      const preliminary=await tab.playwright.evaluate(()=>({expectedRaw:document.querySelector('#comment_cnt strong')?.textContent||null,expected:(()=>{const raw=document.querySelector('#comment_cnt strong')?.textContent?.trim();return /^\d+$/.test(raw||'')?Number(raw):null;})(),commentsAllSelected:!!document.querySelector('#comment_sort [sort=all].on'),observedAt:new Date().toISOString(),comments:[...document.querySelectorAll('#comment .cmt[w_idx]')].map(e=>({id:e.getAttribute('w_idx'),date:e.querySelector('.ago')?.getAttribute('date')||null,kCount:(()=>{const text=e.querySelector('.content')?.innerText;return typeof text==='string'?(text.match(/ㅋ/g)||[]).length:null;})()}))}));
      // Preserve actual partial evidence before validation can fail; never retain comment text.
      Object.assign(result,{commentsExpected:Number.isInteger(preliminary.expected)?preliminary.expected:null,commentsExpectedRaw:preliminary.expectedRaw??null,commentsAllSelected:preliminary.commentsAllSelected??false,commentCounts:preliminary.comments,commentEvidenceObservedAt:preliminary.observedAt});
      const uniquePre=new Map(preliminary.comments.map(c=>[c.id,c.kCount]));
      if(preliminary.comments.some(c=>!c.id||!Number.isInteger(c.kCount)||c.kCount<0)||preliminary.comments.some(c=>uniquePre.get(c.id)!==c.kCount)||!Number.isInteger(preliminary.expected)||uniquePre.size!==preliminary.expected) throw new Error('Native comment count not ready or incomplete: '+uniquePre.size+'/'+preliminary.expected);
      const qualifies=[...uniquePre.values()].reduce((a,b)=>a+b,0)>=11;
      if(qualifies&&presence.history&&!presence.historyExpanded) await tab.playwright.locator('#history_bar').click();
      if(qualifies&&presence.history) await tab.playwright.locator('#history_list .hsite').first().waitFor({state:'attached',timeoutMs:12000});
      const data=await tab.playwright.evaluate(()=>{
        const comments=[...document.querySelectorAll('#comment .cmt[w_idx]')].map(e=>({id:e.getAttribute('w_idx'),date:e.querySelector('.ago')?.getAttribute('date')||null,kCount:(()=>{const text=e.querySelector('.content')?.innerText;return typeof text==='string'?(text.match(/ㅋ/g)||[]).length:null;})()}));
        const sources=[...document.querySelectorAll('#history_list .hsite')].map(e=>({id:e.getAttribute('alt'),site:e.querySelector('.sitename')?.textContent||null,title:e.querySelector('a')?.textContent||'',url:e.querySelector('a')?.getAttribute('href')||null,age:e.querySelector('.ago:last-child')?.textContent||null}));
        const media=[...document.querySelectorAll('#vContent img,#vContent video,#vContent iframe')].map((e,order)=>e.tagName==='IMG'?{type:'image',order,url:e.currentSrc||e.src,width:e.naturalWidth,height:e.naturalHeight,complete:e.complete}:e.tagName==='VIDEO'?{type:'video',order,url:e.currentSrc||e.src,poster:e.poster||null,width:e.videoWidth,height:e.videoHeight}:{type:'embed',order,url:e.src});
        return {id:new URL(location.href).searchParams.get('idx'),url:location.href,title:document.querySelector('h1.title')?.innerText,listedAtRaw:document.querySelector('#header .odate')?.textContent||null,observedAt:new Date().toISOString(),commentsExpected:(()=>{const raw=document.querySelector('#comment_cnt strong')?.textContent?.trim();return /^\d+$/.test(raw||'')?Number(raw):null;})(),commentsAllSelected:!!document.querySelector('#comment_sort [sort=all].on'),commentCounts:comments,sourcesExpected:(()=>{const raw=document.querySelector('#history_bar')?.innerText.match(/총\s*(\d+)/)?.[1];return raw===undefined?null:Number(raw);})(),sourcesExpanded:!!document.querySelector('#history_list')&&document.querySelector('#history_list').getBoundingClientRect().height>0,sources,sourceRange:document.querySelector('h4.other')?.innerText.match(/S:[^\n]+/)?.[0]||null,media};
      });
      if(collectorIdentity(data.id,data.url)!==requestedIdentity)return {...result,status:'failed',stopBatch:true,pauseReason:'observed_identity_mismatch'};
      result.attempts.push({attempt,at:data.observedAt});
      return {...result,...data,status:'observed',headerEvidenceObservedAt:data.observedAt,commentEvidenceObservedAt:data.observedAt,verificationScope:qualifies?'full_candidate':'comments_only_below_threshold',mediaInspectionSkipped:!qualifies};
    } catch(error) {
      result.attempts.push({attempt,at:new Date().toISOString(),error:String(error)});
      if(collectorDenied(error))return {...result,status:'blocked',error:String(error),stopBatch:true,pauseReason:'authorization_or_access_block'};
      if(attempt===2)return finalizeCollectorFailure(result,error);
      // One bounded retry for transient tool/navigation errors, never bot denials.
      try {
        const state=await tab.playwright.domSnapshot();
        if(/verify you are human|checking your browser|unusual traffic|access denied|captcha/i.test(state)){result.status='blocked';result.stopBatch=true;result.pauseReason='authorization_or_access_block';result.error=state.slice(0,1000);return result;}
      } catch(recoveryError) {result.attempts.push({attempt,stage:'recovery',error:String(recoveryError),at:new Date().toISOString()});return finalizeCollectorFailure(result,recoveryError);}
    }
  }
};
var collectSlice = async function(tab,items) {
  const data=[];
  for(const item of items){
    data.push(await collectPost(tab,item));
    if(data[data.length-1].stopBatch)break;
    // Explicit politeness throttle, not a page-readiness wait. Only one tab reads posts.
    await tab.playwright.waitForTimeout(3000);
    if(['blocked','blocked_or_missing'].includes(data[data.length-1].status))break;
  }
  return data;
};
