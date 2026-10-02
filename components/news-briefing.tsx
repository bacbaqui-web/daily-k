'use client';
import {useEffect,useState} from 'react';
import {editionLabel,isNewsBrief,isNewsIndex,koreaTime,newsLink,type Edition,type NewsBrief,type NewsIndex,type NewsSource} from '../lib/news';

function Sources({items}:{items:NewsSource[]}){
 return <div className="news-sources"><span>확인:</span>{items.map(s=><div key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.name} · {s.title}<span className="sr-only"> (새 탭)</span> ↗</a>{s.publishedAt&&<time dateTime={s.publishedAt}>{koreaTime(s.publishedAt)} 발행</time>}</div>)}</div>;
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
 const path=entry?.path,version=entry?.generatedAt;
 useEffect(()=>{
  if(!index)return;setBrief(null);setError('');
  if(!path){setLoading(false);return}setLoading(true);const controller=new AbortController();
  void (async()=>{try{const r=await fetch(`/daily-k/data/news/${path}`,{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error();const v:unknown=await r.json();if(!isNewsBrief(v)||v.date!==date||v.edition!==edition)throw Error();if(!controller.signal.aborted)setBrief(v)}catch{if(!controller.signal.aborted)setError('브리핑을 불러오지 못했습니다.')}finally{if(!controller.signal.aborted)setLoading(false)}})();return()=>controller.abort();
 },[path,version,date,edition,retry,!!index]);
 const dates=[...new Set(index?.editions.map(e=>e.date)||[])];
 const selected=dates.indexOf(date);
 function choose(d:string,e:Edition){setDate(d);setEdition(e);history.replaceState(null,'',newsLink(d,e))}
 return <section className="news" aria-label="한국어 뉴스 브리핑">
  <div className="news-masthead"><div><span className="news-eyebrow">하루 두 번, 흐름을 읽는 뉴스</span><h1>ㄴㅇㅅ 브리핑</h1></div><span className="news-schedule">매일 09:00 · 21:00<br/>한국시간</span></div>
  <div className="news-controls"><div className="news-date"><button aria-label="이전 브리핑 날짜" disabled={selected<0||selected>=dates.length-1} onClick={()=>choose(dates[selected+1],edition)}>←</button><label><span className="sr-only">브리핑 날짜</span><input type="date" value={date} onChange={e=>choose(e.target.value,edition)}/></label><button aria-label="다음 브리핑 날짜" disabled={selected<=0} onClick={()=>choose(dates[selected-1],edition)}>→</button></div><div className="news-editions" role="group" aria-label="브리핑 시간">{(['am','pm'] as const).map(e=><button key={e} aria-pressed={edition===e} onClick={()=>choose(date,e)}>{editionLabel(e)}</button>)}</div></div>
  {dates.length>0&&<details className="news-archive"><summary>지난 브리핑 {index?.editions.length}회</summary><div>{index?.editions.map(e=><a href={newsLink(e.date,e.edition)} key={e.id} onClick={event=>{event.preventDefault();choose(e.date,e.edition)}} aria-current={entry?.id===e.id?'page':undefined}>{e.date} · {editionLabel(e.edition)} <small>{e.count}개</small></a>)}</div></details>}
  {loading?<p className="news-message" role="status">브리핑을 불러오고 있습니다.</p>:error?<div className="news-message" role="alert"><p>{error}</p><button onClick={()=>setRetry(v=>v+1)}>다시 시도</button></div>:!brief?<div className="news-message"><h2>아직 발행된 브리핑이 없습니다</h2><p>선택한 날짜의 {editionLabel(edition)}이 발행되면 여기에 표시됩니다.</p><p>오전 9시 · 저녁 9시 기준으로 확인한 뉴스를 정리합니다.</p></div>:<>
   <div className="news-intro"><h2>{brief.date} {editionLabel(brief.edition)}</h2><p>{brief.intro}</p><div className="news-time"><span>기사 기준 {koreaTime(brief.cutoffAt)}</span><span>생성 {koreaTime(brief.generatedAt)}</span><a href={`/daily-k/data/news/${brief.date}/${brief.edition}.json`} target="_blank" rel="noopener noreferrer">JSON ↗</a></div></div>
   <nav className="news-highlights" aria-label="핵심 뉴스">{brief.stories.slice(0,3).map((s,i)=><a href={`#news-${s.id}`} key={s.id}><span>0{i+1} · {s.category}</span><strong>{s.title}</strong></a>)}</nav>
   <ol className="news-stories">{brief.stories.map((s,i)=><li key={s.id}><article className={`news-card${i<3?' news-featured':''}`} id={`news-${s.id}`}><div className="news-card-top"><span>{String(i+1).padStart(2,'0')} · {s.category}</span><span className="news-status">{s.followUp?'후속 업데이트':s.status}</span></div><h2>{s.title}</h2>{s.followUp&&<p className="news-change">{s.followUp.delta}</p>}{s.fallbackNote&&<p className="news-fallback">{s.fallbackNote}</p>}{s.summary.map((p,j)=><p key={j}>{p}</p>)}<p className="news-event-time">사건·발표: {s.eventTimeNote}</p><Sources items={s.sources}/></article></li>)}</ol>
   {brief.edition==='pm'&&<section className="news-closing"><h2>오늘의 핵심 키워드</h2><p className="news-keywords">{brief.keywords.join(' · ')}</p></section>}
   <section className="news-closing"><h2>{brief.edition==='am'?'오늘 일정·시장 변수':'내일 주목할 변수'}</h2><ul className="news-events">{brief.events.map((e,i)=><li key={i}><span>{e.at?koreaTime(e.at):`${e.date} · ${e.timeNote||'시각 미확인'}`}</span><h3>{e.title}</h3><p>{e.detail}</p><a href={e.source.url} target="_blank" rel="noopener noreferrer">확인: {e.source.name} ↗</a></li>)}</ul><small>모든 시각은 한국시간입니다. 일정은 주최 측 사정에 따라 바뀔 수 있습니다.</small></section>
  </>}
 </section>;
}
