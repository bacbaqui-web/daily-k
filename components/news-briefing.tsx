'use client';
import {useEffect,useRef,useState} from 'react';
import {Dialog,DialogContent} from './ui/dialog';
import {ReaderHeading} from './reader-heading';
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
function NewsStories({brief}:{brief:NewsBrief}){
 const [active,setActive]=useState<number|null>(null);
 const body=useRef<HTMLDivElement|null>(null),trigger=useRef<HTMLButtonElement|null>(null);
 const story=active===null?null:brief.stories[active];
 function move(delta:number){setActive(current=>current===null?null:current+delta>=brief.stories.length?null:Math.max(0,current+delta))}
 useEffect(()=>{body.current?.scrollTo({top:0,behavior:'instant'})},[active]);
 useEffect(()=>{
  if(active===null)return;
  function navigate(event:KeyboardEvent){
   if(event.defaultPrevented||event.repeat||event.altKey||event.ctrlKey||event.metaKey)return;
   if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
   if(event.target instanceof HTMLElement&&event.target.closest('input,textarea,select,[contenteditable="true"],[role="textbox"],[role="slider"]'))return;
   if(event.shiftKey&&event.key!=='ArrowUp'&&event.key!=='ArrowDown')return;
   event.preventDefault();
   if(event.key==='ArrowLeft'||event.key==='ArrowRight'){move(event.key==='ArrowLeft'?-1:1);return}
   const panel=body.current;if(!panel)return;
   const behavior=matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
   if(event.shiftKey){const sources=panel.querySelector<HTMLElement>('.news-sources');panel.scrollTo({top:event.key==='ArrowUp'?0:sources?panel.scrollTop+sources.getBoundingClientRect().top-panel.getBoundingClientRect().top:panel.scrollHeight,behavior})}
   else panel.scrollBy({top:event.key==='ArrowUp'?-500:500,behavior});
  }
  window.addEventListener('keydown',navigate,true);return()=>window.removeEventListener('keydown',navigate,true);
 },[active,brief.stories.length]);
 return <Dialog open={story!==null} disablePointerDismissal={false} onOpenChange={open=>{if(!open)setActive(null)}}>
  <ol className="posts news-stories">{brief.stories.map((s,i)=><li key={s.id}>
   <button type="button" className="post-top news-story-trigger" aria-haspopup="dialog" aria-labelledby={`news-${s.id}`} onClick={event=>{trigger.current=event.currentTarget;setActive(i)}}>
    <span className="rank" aria-hidden="true">{String(i+1).padStart(2,'0')}</span>
    <span className="post-main"><span className="news-story-meta"><span>{s.category}</span><span>{s.followUp?'후속 업데이트':s.status}</span></span><span className="news-story-title" role="heading" aria-level={2} id={`news-${s.id}`}>{s.title}</span><span className="news-story-summary">{s.summary[0]}</span></span>
   </button>
  </li>)}</ol>
  <DialogContent className="reader-dialog news-reader" showCloseButton={false} aria-describedby={undefined} initialFocus={body} finalFocus={()=>trigger.current||true}>
   {story&&<>
    <nav className="reader-nav reader-top" aria-label="뉴스 이동"><button onClick={()=>move(-1)} disabled={active===0} aria-label="이전 글">←</button><ReaderHeading title={story.title} index={active!+1} total={brief.stories.length} onClose={()=>setActive(null)}/><button onClick={()=>move(1)} aria-label="다음 글">→</button><div className="laugh-stats news-reader-meta"><span>{story.category}</span><span>{story.followUp?'후속 업데이트':story.status}</span></div></nav>
    <div className="reader-body news-reader-body" ref={body} tabIndex={-1}>
     {story.followUp&&<p className="news-change">{story.followUp.delta}</p>}{story.fallbackNote&&<p className="news-fallback">{story.fallbackNote}</p>}
     {story.summary.map((p,j)=><p key={`${story.id}-${j}`}><Emphasis text={p} phrases={story.emphasis}/></p>)}
     <p className="news-event-time">사건·발표: {story.eventTimeNote}</p><Sources key={story.id} items={story.sources} related={story.relatedArticles}/>
    </div>
   </>}
  </DialogContent>
 </Dialog>;
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
   <NewsStories key={brief.id} brief={brief}/>
   {brief.edition==='pm'&&<section className="news-closing"><h2>오늘의 핵심 키워드</h2><p className="news-keywords">{brief.keywords.join(' · ')}</p></section>}
   <section className="news-closing"><h2>{brief.edition==='am'?'오늘 일정·시장 변수':'내일 주목할 변수'}</h2><ul className="news-events">{brief.events.map((e,i)=><li key={i}><span>{e.at?koreaTime(e.at):`${e.date} · ${e.timeNote||'시각 미확인'}`}</span><h3>{e.title}</h3><p>{e.detail}</p><a href={e.source.url} target="_blank" rel="noopener noreferrer">확인: {e.source.name} ↗</a></li>)}</ul><small>모든 시각은 한국시간입니다. 일정은 주최 측 사정에 따라 바뀔 수 있습니다.</small></section>
  </>}
 </section>;
}
