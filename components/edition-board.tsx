'use client';
import {useEffect,useRef,useState} from 'react';
import {CommunityBriefing} from './community-briefing';
import {NewsBriefing,NewsPrepared} from './news-briefing';
import {WindowContent} from './live-board';
import {isLiveState,isSnapshot,liveTime,snapshotHash,type LiveState,type Snapshot,type SnapshotRef} from '../lib/live';
import {containsItem,currentEdition,latestNewsEdition,editionBoundary,editionDates,editionHref,editionId,editionSource,parseEdition,requestedEdition,validDate,type ArchiveEdition,type Channel,type EditionSelection} from '../lib/edition-view';

const shortTime=(value:string|null|undefined)=>value?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value)):'아직 없음';
function archiveEntries(value:unknown):ArchiveEdition[] {
 if(!value||typeof value!=='object'||!('editions' in value)||!Array.isArray(value.editions))throw Error();
 return value.editions.map((entry:ArchiveEdition)=>{
  if(!entry||!validDate(entry.date)||!['am','pm'].includes(entry.edition)||typeof entry.id!=='string'||!new RegExp(`^(archive/)?${entry.date}/${entry.edition}\\.json$`).test(entry.path))throw Error();return entry;
 }).sort((a,b)=>editionId(b).localeCompare(editionId(a)));
}
async function readSnapshot(ref:SnapshotRef,cache:Map<string,Snapshot>,signal:AbortSignal):Promise<Snapshot> {
 const key=`${ref.id}:${ref.sha256}`,cached=cache.get(key);if(cached)return cached;
 const response=await fetch(`/daily-k/data/live/${ref.path}`,{cache:'no-store',signal});if(!response.ok)throw Error();
 const raw=await response.text();if(await snapshotHash(raw)!==ref.sha256)throw Error();
 const value:unknown=JSON.parse(raw);if(!isSnapshot(value)||value.id!==ref.id)throw Error();
 if(signal.aborted)throw Error();cache.set(key,value);return value;
}
export function EditionBoard({channel,search,onNavigate}:{channel:Channel;search:string;onNavigate:(href:string)=>void}) {
 const [now,setNow]=useState(0),[state,setState]=useState<LiveState|null>(null);
 const [archives,setArchives]=useState<Record<Channel,ArchiveEdition[]>>({humor:[],news:[]});
 const [loaded,setLoaded]=useState(false),[errors,setErrors]=useState<string[]>([]),[retry,setRetry]=useState(0);
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null),[snapshotError,setSnapshotError]=useState('');
 const cache=useRef(new Map<string,Snapshot>());
 const [lookup,setLookup]=useState<{key:string;selection:EditionSelection|null;error?:string}|null>(null);
 useEffect(()=>{setNow(Date.now());const tick=setInterval(()=>{const timestamp=Date.now();setNow(previous=>editionId(currentEdition(previous))===editionId(currentEdition(timestamp))?previous:timestamp)},1000);return()=>clearInterval(tick)},[]);
 useEffect(()=>{
  const controller=new AbortController();let running=false;
  async function load(){
   if(running)return;running=true;
   const sources=[['회차 상태','/daily-k/data/live/current.json'],['커뮤니티 기록','/daily-k/data/community/index.json'],['뉴스 기록','/daily-k/data/news/index.json']] as const;
   const results=await Promise.allSettled(sources.map(async([,url],index)=>{
    const response=await fetch(url,{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();
    const value:unknown=await response.json();
    if(index===0){if(!isLiveState(value))throw Error();if(!controller.signal.aborted)setState(value)}
    else {const entries=archiveEntries(value);if(!controller.signal.aborted)setArchives(current=>({...current,[index===1?'humor':'news']:entries}))}
   }));
   if(!controller.signal.aborted){setErrors(results.flatMap((r,i)=>r.status==='rejected'?[`${sources[i][0]}을 새로 확인하지 못했습니다. 표시된 내용이 이전 상태일 수 있습니다.`]:[]));setLoaded(true)}running=false;
  }
  void load();const timer=setInterval(load,60000);return()=>{controller.abort();clearInterval(timer)};
 },[retry]);
 const query=new URLSearchParams(search),entries=archives[channel];
 const item=query.get('item'),explicit=validDate(query.get('date'))||!!parseEdition(query.get('record'));
 const needsLookup=!!item&&!explicit&&(channel==='news'||!state?.windows.some(w=>containsItem(w,channel,item)));
 const lookupKey=`${channel}:${search}:${state?.snapshots.map(s=>`${s.id}:${s.sha256}`).join(',')}`;
 useEffect(()=>{
  if(!loaded||!state||!needsLookup||!item)return;
  const controller=new AbortController();
  void(async()=>{try{
   for(const ref of state.snapshots){const value=await readSnapshot(ref,cache.current,controller.signal);if(containsItem(value,channel,item)){if(!controller.signal.aborted)setLookup({key:lookupKey,selection:parseEdition(ref.id)});return}}
   if(!controller.signal.aborted)setLookup({key:lookupKey,selection:null});
  }catch{if(!controller.signal.aborted)setLookup({key:lookupKey,selection:null,error:'공유한 항목의 보관 회차를 확인하지 못했습니다.'})}})();
  return()=>controller.abort();
 },[loaded,state,needsLookup,item,channel,lookupKey,retry]);
 const selection=needsLookup&&lookup?.key===lookupKey&&lookup.selection?lookup.selection:requestedEdition(query,now,state,entries,channel);
 const id=editionId(selection),current=channel==='news'?latestNewsEdition(now,entries):currentEdition(now);
 const source=editionSource(selection,now,state,entries,query.get('view')==='archive'||query.get('archive')==='1',channel);
 const ref=source.kind==='snapshot'?source.ref:null;
 useEffect(()=>{
  setSnapshotError('');if(!ref){setSnapshot(null);return}
  const controller=new AbortController();
  void readSnapshot(ref,cache.current,controller.signal).then(value=>{if(!controller.signal.aborted)setSnapshot(value)}).catch(()=>{if(!controller.signal.aborted)setSnapshotError('확정 원본을 불러오거나 검증하지 못했습니다. 다시 시도해 주세요.')});
  return()=>controller.abort();
 },[ref?.id,ref?.sha256,retry]);
 const visible=source.kind==='window'?source.window:source.kind==='snapshot'&&snapshot?.id===id?snapshot:null;
 const corrections=state?.corrections.filter(c=>c.snapshotId===id)||[];
 const updated=channel==='news'?(source.kind==='snapshot'&&snapshot?.id===id?snapshot.finalizedAt:null):visible?.items.reduce<string|null>((latest,item)=>!latest||Date.parse(item.recordedAt)>Date.parse(latest)?item.recordedAt:latest,null);
 const dates=channel==='news'?[...new Set([current.date,...entries.map(e=>e.date)])].sort():editionDates(now,state,entries),previous=dates.filter(d=>d<selection.date).at(-1),next=dates.find(d=>d>selection.date);
 const incomplete=errors.some(message=>message.startsWith('회차 상태')||message.startsWith(channel==='news'?'뉴스 기록':'커뮤니티 기록'));
 const status=incomplete&&(source.kind==='missing'||source.kind==='current')?'확인 필요':source.kind==='snapshot'?'확정':source.kind==='archive'?'기존 기록':channel==='news'?'미발행':source.kind==='window'&&source.pending?'확정 대기':source.kind==='current'||source.kind==='window'?'진행 중':source.kind==='future'?'예정':'기록 없음';
 const isCurrent=id===editionId(current);
 const choose=(value:EditionSelection)=>{if(editionId(value)!==id)onNavigate(editionHref(value,channel))};
 const unresolved=needsLookup&&(!state||lookup?.key!==lookupKey);
 const missingLink=needsLookup&&!unresolved&&!lookup?.selection;
 if(!now)return <p className="news-message" role="status">회차를 불러오고 있습니다.</p>;
 return <section className="edition-board" aria-label={`${channel==='news'?'뉴스':'커뮤니티'} 회차`}>
  <div className="news-controls news-controls-inline edition-controls" role="group" aria-label="브리핑 날짜와 시간">
   <button className="news-date-arrow" disabled={!previous} onClick={()=>previous&&choose({...selection,date:previous})} aria-label="이전 브리핑 날짜">←</button>
   <button className="news-edition-button" aria-pressed={selection.edition==='am'} onClick={()=>choose({...selection,edition:'am'})}>오전</button>
   <label className="news-date-selection"><span className="sr-only">브리핑 날짜</span><input type="date" value={selection.date} onChange={e=>validDate(e.target.value)&&choose({...selection,date:e.target.value})}/></label>
   <button className="news-edition-button" aria-pressed={selection.edition==='pm'} onClick={()=>choose({...selection,edition:'pm'})}>오후</button>
   <button className="news-date-arrow" disabled={!next} onClick={()=>next&&choose({...selection,date:next})} aria-label="다음 브리핑 날짜">→</button>
  </div>
  <h1 className="sr-only">{selection.date} {selection.edition==='am'?'오전':'오후'} {channel==='news'?'뉴스':'커뮤니티'} 회차</h1>
  <div className="edition-status-row"><span><span className="live-status">{status}</span> {selection.edition==='am'?'오전':'오후'} 9시 회차{visible&&channel==='humor'?` · ${visible.items.length}건`:''}</span>{(!isCurrent||explicit)&&<button className="edition-current" onClick={()=>onNavigate(editionHref(null,channel))}>{channel==='news'?'최근 발행 ↗':'현재 회차 ↗'}</button>}</div>
  {source.kind!=='archive'&&<div className="edition-meta"><span>회차 기준 {shortTime(editionBoundary(selection))}</span><span>{channel==='news'?'실제 확정':'목록 반영'} {shortTime(updated)}</span><span>한국시간</span></div>}
  {errors.length>0&&<div className="live-alert" role="alert">{errors.map(message=><p key={message}>{message}</p>)}<button onClick={()=>setRetry(n=>n+1)}>다시 시도</button></div>}
  {!loaded||unresolved?<p className="news-message" role="status">회차를 불러오고 있습니다.</p>:missingLink?<div className="news-message" role="alert"><p>{lookup?.error||'공유한 항목이 등록된 회차를 찾지 못했습니다.'}</p>{lookup?.error&&<button onClick={()=>setRetry(n=>n+1)}>다시 시도</button>}</div>:source.kind==='archive'?(channel==='news'?<NewsBriefing key={`${id}:${search}`} selection={selection}/>:<CommunityBriefing key={`${id}:${search}`} selection={selection}/>):source.kind==='snapshot'&&!visible?(snapshotError?<div className="live-alert" role="alert"><p>{snapshotError}</p><button onClick={()=>setRetry(n=>n+1)}>다시 시도</button></div>:<p className="news-message" role="status">확정 기록을 불러오고 있습니다.</p>):visible?<>
   {source.kind==='window'&&source.pending&&<p className="edition-pending" role="status">확정 기준 시각이 지났습니다. 등록된 내용은 보존 중이며 실제 확정은 아직 확인되지 않았습니다.</p>}
   {channel==='news'&&visible.news?<NewsPrepared key={`${id}:${search}`} brief={visible.news.brief} record={id} corrections={corrections}/>:<WindowContent key={`${id}:${search}`} window={visible} channel={channel} corrections={corrections} record={source.kind==='snapshot'?id:undefined}/>}
  </>:incomplete?<div className="live-empty"><h2>이 회차의 등록 상태를 확인하지 못했습니다</h2><p>위의 다시 시도로 최신 데이터를 확인해 주세요.</p></div>:channel==='news'?<div className="live-empty"><h2>아직 발행된 브리핑이 없습니다</h2><p>매일 한국시간 09:00·21:00에 뉴스를 조사·검증하고 정리가 끝나면 게시합니다. 최근 발행 회차나 다른 날짜를 선택해 주세요.</p></div>:source.kind==='current'?<><div className="live-empty"><h2>아직 등록된 내용이 없습니다</h2><p>확인한 새 자료가 들어오면 이 회차에 표시됩니다.<br/>{selection.edition==='am'?'전날 오후 9시부터 이날 오전 9시까지':'이날 오전 9시부터 오후 9시까지'}의 수집 창입니다.</p></div><p className="live-disclaimer">등록된 수집 확인 기록이 없습니다. 수집기의 가동 상태나 수집 결과 0건을 의미하지 않습니다.</p></>:<div className="live-empty"><h2>{source.kind==='future'?'아직 시작하지 않은 회차입니다':'이 회차에 보관된 내용이 없습니다'}</h2><p>다른 날짜나 오전·오후를 선택해 주세요.</p></div>}
  <details className="edition-record-info"><summary>회차·확인 정보</summary>{channel==='news'?<p>매일 한국시간 09:00·21:00을 기사 기준으로 한 번 조사·검증한 뒤 최종 브리핑을 게시합니다. 새 발행 전에는 최근 발행 회차를 보여줍니다. 기사 기준·실제 작성·실제 확정 시각은 구분하며, 이전 회차의 시간과 원본은 보존합니다.</p>:<><p>오전 회차는 전날 21:00 이상~당일 09:00 미만, 오후 회차는 당일 09:00 이상~21:00 미만입니다. 같은 회차에 자료를 추가하고 확정 후에는 원본을 보존합니다. 이후 정정은 별도로 표시합니다.</p><p>‘진행 중’은 수집 창의 상태이며 수집기 정상 가동을 뜻하지 않습니다. 첫 발견·확인 시각·관측 이력은 각 항목에 남깁니다.</p></>}<p>전체 데이터 반영 {liveTime(state?.updatedAt)} · 실제 웹 배포 완료 시각과 다를 수 있습니다.</p>{source.kind==='snapshot'&&snapshot?.id===id&&<><p>실제 확정 {liveTime(snapshot.finalizedAt)}<br/>회차 기준 {liveTime(snapshot.scheduledFor)}</p><a href={`/daily-k/data/live/${source.ref.path}`} target="_blank" rel="noopener noreferrer">확정 원본 JSON ↗</a><p className="edition-hash">SHA-256 {source.ref.sha256}</p></>}</details>
 </section>;
}
