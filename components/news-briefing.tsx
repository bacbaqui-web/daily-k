'use client';
import {editionHref,type EditionSelection} from '../lib/edition-view';
import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {PreviewCard as PreviewCardPrimitive} from '@base-ui/react/preview-card';
import {HoverCard,HoverCardTrigger} from './ui/hover-card';
import {Dialog,DialogContent} from './ui/dialog';
import {ReaderHeading} from './reader-heading';
import {NewsReaderActions} from './news-question-button';
import {editionLabel,emphasisParts,isNewsBrief,isNewsIndex,koreaTime,newsLink,type Edition,type NewsIndex,type NewsSource,type NewsStory,type NewsBrief} from '../lib/news';
import {combineBriefings,overviewPhrases,type NewsView,type NewsViewStory} from '../lib/news-view';
import {type Correction} from '../lib/live';
import {RecordCorrections} from './record-corrections';

function ArticleImage({item}:{item:NewsSource}){
 const [failed,setFailed]=useState(false);
 return <div className="news-link-image">{item.imageUrl&&!failed?<img src={item.imageUrl} alt="" loading="lazy" decoding="async" onError={()=>setFailed(true)}/>:<span>{item.name}</span>}</div>;
}
function Sources({items,related=[],archived=false}:{items:NewsSource[];related?:NewsSource[];archived?:boolean}){
 const unique=[...new Map([...related,...items].map(s=>[s.url,s])).values()];
 // Related metadata includes thumbnails; retain it when the same URL is also a source.
 const cards=unique.slice(0,3).map(s=>related.find(r=>r.url===s.url)||s);
 const remaining=items.filter(s=>!cards.some(c=>c.url===s.url));
 return <div className="news-sources">
  <h3>{archived?'재검색한 관련 보도':'확인 · 관련 뉴스'}</h3>
  <div className="news-related">{cards.map(s=><a className="news-link-card" href={s.url} target="_blank" rel="noopener noreferrer" key={s.url}>
   <ArticleImage item={s}/><div className="news-link-copy"><span className="news-publisher">{items.some(item=>item.url===s.url)?'확인: ':''}{s.name}</span><strong>{s.title}</strong>{s.publishedAt&&<time dateTime={s.publishedAt}>{koreaTime(s.publishedAt)}</time>}<span className="sr-only"> (새 탭)</span></div>
  </a>)}</div>
  {remaining.length>0&&<p className="news-extra-sources">추가 확인: {remaining.map((s,i)=><span key={s.url}>{i>0?' · ':''}<a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}<span className="sr-only"> · {s.title} (새 탭)</span></a></span>)}</p>}
 </div>;
}
function Emphasis({text,phrases}:{text:string;phrases?:string[]}){
 return <>{emphasisParts(text,phrases).map((part,i)=>part.bold?<strong key={i}>{part.text}</strong>:part.text)}</>;
}
function NewsRecord({story,brief}:{story:NewsStory;brief:NewsView}){
 return <>
  {story.followUp&&<p className="news-change">{story.followUp.delta}</p>}{story.fallbackNote&&<p className="news-fallback">{story.fallbackNote}</p>}
  {story.summary.map((p,j)=><p key={`${story.id}-${j}`}><Emphasis text={p} phrases={story.emphasis}/></p>)}
  {story.archive?<>
   <details className="news-archive-detail"><summary>출처·기록 정보</summary><p>이전 ChatGPT 브리핑에서 옮긴 기록이며, 기사 원문으로 전체 내용을 재검증한 상태는 아닙니다.</p><p>{story.archive.sourceNames.length?`당시 적힌 출처: ${story.archive.sourceNames.join(' · ')} · 기사 URL 없음`:'원본 기록에 기사 출처·URL이 남아 있지 않습니다.'}</p><p>{brief.date} {brief.edition==='am'?'오전':'오후'} · 정확한 작성·사건 시각 미상</p>{story.archive.reviewNote&&<p>{story.archive.reviewNote}</p>}</details>
   {story.archive.previousCoverage&&<a className="news-previous-record" href={newsLink(story.archive.previousCoverage.date,story.archive.previousCoverage.edition,false,story.archive.previousCoverage.storyId)}>앞선 같은 이슈 · {story.archive.previousCoverage.date} {story.archive.previousCoverage.edition==='am'?'오전':'오후'}<br/>{story.archive.previousCoverage.title} →</a>}
   {!!story.relatedArticles?.length&&<Sources items={[]} related={story.relatedArticles} archived/>}
  </>:<><p className="news-event-time">사건·발표: {story.eventTimeNote}</p><Sources items={story.sources} related={story.relatedArticles}/></>}
 </>;
}
function NewsDetails({story,brief}:{story:NewsViewStory;brief:NewsView}){
 return <><NewsRecord key={story.id} story={story} brief={brief}/>{story.additionalRecords.length>0&&<details className="news-additional-records"><summary>함께 보관한 내용 {story.additionalRecords.length}건</summary>{story.additionalRecords.map(s=><div className="news-additional-record" key={s.id}><h3>{s.title}</h3><NewsRecord story={s} brief={brief}/></div>)}</details>}</>;
}
function NewsPreview({story,brief,disabled,onOpen,children}:{story:NewsViewStory;brief:NewsView;disabled:boolean;onOpen:(button:HTMLElement)=>void;children:ReactNode}){
 const [open,setOpen]=useState(false),[canHover,setCanHover]=useState(false);
 const [pointer,setPointer]=useState<{x:number;y:number;element:HTMLElement|null}>({x:0,y:0,element:null});
 const anchor=useMemo(()=>({getBoundingClientRect:()=>new DOMRect(pointer.x,pointer.y,0,0),contextElement:pointer.element||undefined}),[pointer]);
 useEffect(()=>{const media=matchMedia('(hover: hover) and (pointer: fine)');const sync=()=>setCanHover(media.matches);sync();media.addEventListener('change',sync);return()=>media.removeEventListener('change',sync)},[]);
 useEffect(()=>{if(disabled)setOpen(false)},[disabled]);
 useEffect(()=>{if(!open)return;const close=()=>setOpen(false);window.addEventListener('scroll',close,{passive:true});window.addEventListener('resize',close);return()=>{window.removeEventListener('scroll',close);window.removeEventListener('resize',close)}},[open]);
 const visible=open&&canHover&&!disabled;
 return <HoverCard open={visible} onOpenChange={value=>setOpen(value&&canHover&&!disabled)}>
  <HoverCardTrigger render={<button type="button"/>} delay={400} closeDelay={180} className="post-top news-story-trigger" aria-haspopup="dialog" aria-labelledby={`news-${story.id}`}
   onPointerEnter={e=>{if(e.pointerType==='mouse')setPointer({x:e.currentTarget.getBoundingClientRect().right,y:e.clientY,element:e.currentTarget})}}
   onPointerMove={e=>{if(e.pointerType==='mouse')setPointer({x:e.currentTarget.getBoundingClientRect().right,y:e.clientY,element:e.currentTarget})}}
   onFocus={e=>{const rect=e.currentTarget.getBoundingClientRect();setPointer({x:rect.right,y:rect.top+rect.height/2,element:e.currentTarget})}}
   onClick={e=>{setOpen(false);onOpen(e.currentTarget)}}>{children}</HoverCardTrigger>
  <PreviewCardPrimitive.Portal><PreviewCardPrimitive.Positioner anchor={anchor} positionMethod="fixed" side="right" align="center" sideOffset={14} collisionPadding={12} collisionAvoidance={{side:'shift',align:'shift'}} className="preview-positioner">
   <PreviewCardPrimitive.Popup className="news-preview" aria-label="뉴스 미리보기">{visible&&<><div className="news-preview-heading"><span>{story.category} · {story.status}</span><h3>{story.title}</h3></div><NewsDetails story={story} brief={brief}/><p className="preview-hint">뉴스를 누르면 읽기 창이 열립니다.</p></>}</PreviewCardPrimitive.Popup>
  </PreviewCardPrimitive.Positioner></PreviewCardPrimitive.Portal>
 </HoverCard>;
}
function NewsStories({brief,liveRecord,corrections=[]}:{brief:NewsView;liveRecord?:string;corrections?:Correction[]}){
 const [active,setActive]=useState<number|null>(null);
 useEffect(()=>{const q=new URLSearchParams(location.search),id=liveRecord!==undefined?(q.get('item')||q.get('story')):q.get('story');const at=brief.stories.findIndex(s=>s.aliases.includes(id||''));if(at>=0)setActive(at)},[brief.id,liveRecord]);
 const body=useRef<HTMLDivElement|null>(null),trigger=useRef<HTMLElement|null>(null);
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
   <NewsPreview story={s} brief={brief} disabled={active!==null} onOpen={button=>{trigger.current=button;setActive(i)}}>
    <span className="rank" aria-hidden="true">{String(i+1).padStart(2,'0')}</span>
    <span className="post-main"><span className="news-story-meta"><span>{s.category}</span><span>{s.followUp?'후속 업데이트':s.status}</span>{corrections.some(c=>c.itemId===s.id)&&<span className="live-correction-badge">정정·철회 기록 있음</span>}</span><span className="news-story-title" role="heading" aria-level={2} id={`news-${s.id}`}>{s.title}</span><span className="news-story-summary">{s.summary[0]}</span></span>
   </NewsPreview>
  </li>)}</ol>
  <DialogContent className="reader-dialog news-reader" showCloseButton={false} aria-describedby={undefined} initialFocus={body} finalFocus={()=>trigger.current||true}>
   {story&&<>
    <nav className="reader-nav reader-top" aria-label="뉴스 이동"><button onClick={()=>move(-1)} disabled={active===0} aria-label="이전 글">←</button><ReaderHeading title={story.title} index={active!+1} total={brief.stories.length} onClose={()=>setActive(null)}/><button onClick={()=>move(1)} aria-label="다음 글">→</button><div className="laugh-stats news-reader-meta"><span>{story.category}</span><span>{story.followUp?'후속 업데이트':story.status}</span><NewsReaderActions key={story.id} brief={brief} story={story} sharePath={liveRecord!==undefined?editionHref(brief,'news',story.id):undefined} recordStatus={liveRecord===undefined?undefined:liveRecord?'finalized':'preparing'}/></div></nav>
    <div className="reader-body news-reader-body" ref={body} tabIndex={-1}>
     <RecordCorrections items={corrections.filter(c=>c.itemId===story.id)}/><NewsDetails key={story.id} story={story} brief={brief}/>
    </div>
   </>}
  </DialogContent>
 </Dialog>;
}
function NewsClosing({brief}:{brief:NewsView}){return <>
   {brief.edition==='pm'&&brief.keywords.length>0&&<section className="news-closing"><h2>오늘의 핵심 키워드</h2><p className="news-keywords">{brief.keywords.join(' · ')}</p></section>}
   {brief.watchItems.length>0&&brief.events.length===0&&<section className="news-closing"><h2>주목할 변수</h2><ul>{brief.watchItems.map(item=><li key={item}>{item}</li>)}</ul></section>}
   {brief.events.length>0&&<section className="news-closing"><h2>{brief.edition==='am'?'오늘 일정·시장 변수':'내일 주목할 변수'}</h2><ul className="news-events">{brief.events.map((e,i)=><li key={i}><span>{e.at?koreaTime(e.at):`${e.date} · ${e.timeNote||'시각 미확인'}`}</span><h3>{e.title}</h3><p>{e.detail}</p><a href={e.source.url} target="_blank" rel="noopener noreferrer">확인: {e.source.name} ↗</a></li>)}</ul><small>모든 시각은 한국시간입니다. 일정은 주최 측 사정에 따라 바뀔 수 있습니다.</small></section>}
</>}
export function NewsPrepared({brief,record,corrections=[]}:{brief:NewsBrief;record?:string;corrections?:Correction[]}){
 const view=combineBriefings([brief]);
 if(!view)return null;
 return <section className="news"><div className="news-intro"><h2>전체 뉴스 요약</h2>{(view.overview||[view.intro]).map((p,i)=><p key={i}><Emphasis text={p} phrases={overviewPhrases(view)}/></p>)}<div className="news-time">{view.cutoffAt&&<span>기사 기준 {koreaTime(view.cutoffAt)}</span>}<span>실제 작성 {koreaTime(view.generatedAt)}</span></div></div><NewsStories brief={view} liveRecord={record||''} corrections={corrections}/><NewsClosing brief={view}/></section>;
}
export function NewsBriefing({selection}:{selection?:EditionSelection}){
 const [index,setIndex]=useState<NewsIndex|null>(null),[localDate,setDate]=useState(''),[localEdition,setEdition]=useState<Edition>('am');
 const [brief,setBrief]=useState<NewsView|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
 const date=selection?.date??localDate,edition=selection?.edition??localEdition;
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
 const editions=index?.editions.filter(e=>e.date===date&&e.edition===edition)||[];
 const entriesKey=editions.map(e=>`${e.id}:${e.path}`).join('|'),version=index?.updatedAt;
 useEffect(()=>{
  if(!index)return;setBrief(null);setError('');
  if(!editions.length){setLoading(false);return}setLoading(true);const controller=new AbortController();
  void (async()=>{try{
   const parts=await Promise.all(editions.map(async entry=>{const r=await fetch(`/daily-k/data/news/${entry.path}`,{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error();const v:unknown=await r.json();if(!isNewsBrief(v)||v.id!==entry.id||v.date!==date||v.edition!==edition)throw Error();return v}));
   if(!controller.signal.aborted)setBrief(combineBriefings(parts));
  }catch{if(!controller.signal.aborted)setError('브리핑을 불러오지 못했습니다.')}finally{if(!controller.signal.aborted)setLoading(false)}})();return()=>controller.abort();
 },[entriesKey,version,date,edition,retry,!!index]);
 const dates=[...new Set(index?.editions.map(e=>e.date)||[])].sort().reverse();
 const previous=dates.find(d=>d<date),next=[...dates].reverse().find(d=>d>date);
 function choose(d:string,e:Edition){if(d!==date||e!==edition){setBrief(null);setLoading(true)}setDate(d);setEdition(e);history.replaceState(null,'',newsLink(d,e))}
 return <section className="news" aria-label="한국어 뉴스 브리핑">
  {!selection&&<div className="news-controls news-controls-inline" role="group" aria-label="브리핑 날짜와 시간">
   <button className="news-date-arrow" aria-label="이전 브리핑 날짜" disabled={!previous} onClick={()=>previous&&choose(previous,edition)}>←</button>
   <button className="news-edition-button" aria-pressed={edition==='am'} onClick={()=>choose(date,'am')}>오전</button>
   <label className="news-date-selection"><span className="sr-only">브리핑 날짜</span><input type="date" value={date} onChange={e=>e.target.value&&choose(e.target.value,edition)}/></label>
   <button className="news-edition-button" aria-pressed={edition==='pm'} onClick={()=>choose(date,'pm')}>오후</button>
   <button className="news-date-arrow" aria-label="다음 브리핑 날짜" disabled={!next} onClick={()=>next&&choose(next,edition)}>→</button>
  </div>}
  {loading?<p className="news-message" role="status">브리핑을 불러오고 있습니다.</p>:error?<div className="news-message" role="alert"><p>{error}</p><button onClick={()=>setRetry(v=>v+1)}>다시 시도</button></div>:!brief?<div className="news-message"><h2>아직 발행된 브리핑이 없습니다</h2><p>선택한 날짜의 {editionLabel(edition)}이 발행되면 여기에 표시됩니다.</p></div>:<>
   <div className="news-intro"><h1>전체 뉴스 요약</h1>{(brief.overview||[brief.intro]).map((p,i)=><p key={i}><Emphasis text={p} phrases={overviewPhrases(brief)}/></p>)}{brief.cutoffAt&&<div className="news-time"><span>기사 기준 {koreaTime(brief.cutoffAt)}</span><span>생성 {koreaTime(brief.generatedAt)}</span></div>}</div>
   <NewsStories key={brief.id} brief={brief}/>
   <NewsClosing brief={brief}/>
  </>}
 </section>;
}
