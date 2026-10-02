'use client';
import {useEffect,useState} from 'react';
import {editionLabel,emphasisParts,isNewsBrief,isNewsIndex,koreaTime,newsLink,type Edition,type NewsBrief,type NewsIndex,type NewsSource} from '../lib/news';

function ArticleImage({item}:{item:NewsSource}){
 const [failed,setFailed]=useState(false);
 return <div className="news-link-image">{item.imageUrl&&!failed?<img src={item.imageUrl} alt="" loading="lazy" decoding="async" onError={()=>setFailed(true)}/>:<span>{item.name}</span>}</div>;
}
function Sources({items,related=[]}:{items:NewsSource[];related?:NewsSource[]}){
 const unique=[...new Map([...related,...items].map(s=>[s.url,s])).values()];
 // Related metadata includes thumbnails; retain it when the same URL is also a source.
 const cards=unique.slice(0,3).map(s=>related.find(r=>r.url===s.url)||s);
 const remaining=items.filter(s=>!cards.some(c=>c.url===s.url));
 return <div className="news-sources">
  <h3>확인 · 관련 뉴스</h3>
  <div className="news-related">{cards.map(s=><a className="news-link-card" href={s.url} target="_blank" rel="noopener noreferrer" key={s.url}>
   <ArticleImage item={s}/><div className="news-link-copy"><span className="news-publisher">{items.some(item=>item.url===s.url)?'확인: ':''}{s.name}</span><strong>{s.title}</strong>{s.publishedAt&&<time dateTime={s.publishedAt}>{koreaTime(s.publishedAt)}</time>}<span className="sr-only"> (새 탭)</span></div>
  </a>)}</div>
  {remaining.length>0&&<p className="news-extra-sources">추가 확인: {remaining.map((s,i)=><span key={s.url}>{i>0?' · ':''}<a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}<span className="sr-only"> · {s.title} (새 탭)</span></a></span>)}</p>}
 </div>;
}
function Emphasis({text,phrases}:{text:string;phrases?:string[]}){
 return <>{emphasisParts(text,phrases).map((part,i)=>part.bold?<strong key={i}>{part.text}</strong>:part.text)}</>;
}
export function NewsBriefing(){
 const [index,setIndex]=useState<NewsIndex|null>(null),[date,setDate]=useState(''),[edition,setEdition]=useState<Edition>('am');
 const [brief,setBrief]=useState<NewsBrief|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();let initialized=false;
  async function load(){try{
   const r=await fetch('/daily-k/data/news/index.json',{cache:'no-store',signal:controller.signal});
   if(!r.ok)throw Error();const v:unknown=await r.json();if(!isNewsIndex(v))throw Error();
   if(controller.signal.aborted)return;setIndex(v);
   if(!initialized){const q=new URLSearchParams(location.search);const latest=v.editions[0];const requested=q.get('date');setDate(requested&&/^\d{4}-\d{2}-\d{2}$/.test(requested)?requested:latest?.date||'');setEdition(q.get('edition')==='pm'?'pm':q.get('edition')==='am'?'am':latest?.edition||'am');initialized=true}setError('');
  }catch{if(!controller.signal.aborted){setError('브리핑 목록을 불러오지 못했습니다.');setLoading(false)}}}
  void load();const timer=window.setInterval(load,60000);return()=>{controller.abort();clearInterval(timer)};
 },[retry]);
 const entry=index?.editions.find(e=>e.date===date&&e.edition===edition);
 const path=entry?.path,version=index?.updatedAt||entry?.generatedAt;
 useEffect(()=>{
  if(!index)return;setBrief(null);setError('');
  if(!path){setLoading(false);return}setLoading(true);const controller=new AbortController();
  void (async()=>{try{const r=await fetch(`/daily-k/data/news/${path}`,{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error();const v:unknown=await r.json();if(!isNewsBrief(v)||v.date!==date||v.edition!==edition)throw Error();if(!controller.signal.aborted)setBrief(v)}catch{if(!controller.signal.aborted)setError('브리핑을 불러오지 못했습니다.')}finally{if(!controller.signal.aborted)setLoading(false)}})();return()=>controller.abort();
 },[path,version,date,edition,retry,!!index]);
 const dates=[...new Set(index?.editions.map(e=>e.date)||[])].sort().reverse();
 const previous=dates.find(d=>d<date),next=[...dates].reverse().find(d=>d>date);
 function choose(d:string,e:Edition){if(d!==date||e!==edition){setBrief(null);setLoading(true)}setDate(d);setEdition(e);history.replaceState(null,'',newsLink(d,e))}
 return <section className="news" aria-label="한국어 뉴스 브리핑">
  <div className="news-controls">
   <button className="news-date-arrow" aria-label="이전 브리핑 날짜" disabled={!previous} onClick={()=>previous&&choose(previous,edition)}>←</button>
   <div className="news-date-selection"><label><span className="sr-only">브리핑 날짜</span><input type="date" value={date} onChange={e=>e.target.value&&choose(e.target.value,edition)}/></label>
    <div className="news-editions" role="group" aria-label="브리핑 시간">{(['am','pm'] as const).map(e=><button key={e} aria-pressed={edition===e} onClick={()=>choose(date,e)}>{e==='am'?'오전':'오후'}</button>)}</div>
   </div>
   <button className="news-date-arrow" aria-label="다음 브리핑 날짜" disabled={!next} onClick={()=>next&&choose(next,edition)}>→</button>
  </div>
  {loading?<p className="news-message" role="status">브리핑을 불러오고 있습니다.</p>:error?<div className="news-message" role="alert"><p>{error}</p><button onClick={()=>setRetry(v=>v+1)}>다시 시도</button></div>:!brief?<div className="news-message"><h2>아직 발행된 브리핑이 없습니다</h2><p>선택한 날짜의 {editionLabel(edition)}이 발행되면 여기에 표시됩니다.</p></div>:<>
   <div className="news-intro"><h1>전체 뉴스 요약</h1>{(brief.overview||[brief.intro]).map((p,i)=><p key={i}>{p}</p>)}<div className="news-time"><span>기사 기준 {koreaTime(brief.cutoffAt)}</span><span>생성 {koreaTime(brief.generatedAt)}</span><a href={`/daily-k/data/news/${brief.date}/${brief.edition}.json`} target="_blank" rel="noopener noreferrer">JSON ↗</a></div></div>
   <ol className="news-stories">{brief.stories.map((s,i)=><li key={s.id}><article className="news-card" id={`news-${s.id}`}><div className="news-card-top"><span className="news-category">{String(i+1).padStart(2,'0')} · {s.category}</span><span className="news-status">{s.followUp?'후속 업데이트':s.status}</span></div><h2>{s.title}</h2>{s.followUp&&<p className="news-change">{s.followUp.delta}</p>}{s.fallbackNote&&<p className="news-fallback">{s.fallbackNote}</p>}{s.summary.map((p,j)=><p key={j}><Emphasis text={p} phrases={s.emphasis}/></p>)}<p className="news-event-time">사건·발표: {s.eventTimeNote}</p><Sources items={s.sources} related={s.relatedArticles}/></article></li>)}</ol>
   {brief.edition==='pm'&&<section className="news-closing"><h2>오늘의 핵심 키워드</h2><p className="news-keywords">{brief.keywords.join(' · ')}</p></section>}
   <section className="news-closing"><h2>{brief.edition==='am'?'오늘 일정·시장 변수':'내일 주목할 변수'}</h2><ul className="news-events">{brief.events.map((e,i)=><li key={i}><span>{e.at?koreaTime(e.at):`${e.date} · ${e.timeNote||'시각 미확인'}`}</span><h3>{e.title}</h3><p>{e.detail}</p><a href={e.source.url} target="_blank" rel="noopener noreferrer">확인: {e.source.name} ↗</a></li>)}</ul><small>모든 시각은 한국시간입니다. 일정은 주최 측 사정에 따라 바뀔 수 있습니다.</small></section>
  </>}
 </section>;
}
