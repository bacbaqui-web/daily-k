'use client';
import {useEffect,useRef,useState} from 'react';
import {Dialog,DialogContent} from './ui/dialog';
import {ReaderHeading} from './reader-heading';
type Link={name:string;title:string;url:string;imageUrl?:string|null};
type SourceCount={name:string;count:number};
type Story={id:string;topicKey:string;title:string;category:'화제'|'유머'|'정보';summary:string[];selectionReason:string;popularityEvidence:string;verificationNote:string;imageUrl?:string|null;videoUrl?:string|null;videoPosterUrl?:string|null;sourceBreakdown?:SourceCount[];sourceStatsVerifiedAt?:string;sources:Link[]};
type Brief={cutoffAt:string;test?:boolean;id:string;date:string;edition:'am'|'pm';generatedAt:string;overview:string[];stories:Story[]};
type Entry={id:string;date:string;edition:'am'|'pm';path:string};
const safe=(v:unknown):v is string=>typeof v==='string'&&/^https?:\/\//.test(v);
function isBrief(v:unknown):v is Brief{if(!v||typeof v!=='object')return false;const b=v as Brief;return typeof b.id==='string'&&Array.isArray(b.overview)&&b.overview.every(p=>typeof p==='string')&&Array.isArray(b.stories)&&b.stories.every(s=>typeof s.title==='string'&&typeof s.selectionReason==='string'&&Array.isArray(s.summary)&&s.summary.every(p=>typeof p==='string')&&Array.isArray(s.sources)&&s.sources.length>0&&s.sources.every(l=>safe(l.url))&&(!s.imageUrl||safe(s.imageUrl))&&(!s.videoUrl||safe(s.videoUrl))&&(!s.videoPosterUrl||safe(s.videoPosterUrl))&&(!s.sourceBreakdown||Array.isArray(s.sourceBreakdown)&&s.sourceBreakdown.every(c=>typeof c.name==='string'&&c.name.trim()&&Number.isSafeInteger(c.count)&&c.count>0)))}
function Image({url,title}:{url?:string|null;title:string}){const [failed,setFailed]=useState(false);return url&&!failed?<img className="community-image" src={url} alt={title} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>:null}
function Video({story}:{story:Story}){const [failed,setFailed]=useState(false);return failed?<p className="community-media-error">영상을 불러오지 못했습니다. 아래 원본 링크에서 확인해 주세요.</p>:<video className="community-video" controls playsInline preload="metadata" src={story.videoUrl!} poster={story.videoPosterUrl||undefined} aria-label={story.title} onError={()=>setFailed(true)}/>}
const sourceColors=['#476ca8','#6b8535','#ac596a','#9565ab','#ae7137','#36867c','#777eb5','#ad6554'];
function SourceGraph({story}:{story:Story}){
 const counts=story.sourceBreakdown?.length?story.sourceBreakdown:null;
 const total=counts?.reduce((sum,s)=>sum+s.count,0)??Number(story.popularityEvidence.match(/총\s*(\d+)개/)?.[1]||0);
 const verified=story.sourceStatsVerifiedAt?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(story.sourceStatsVerifiedAt)):'';
 return <div className="community-popularity" aria-label="인기 근거"><span className="community-source-total">누적 출처 <strong>{total||'미확인'}</strong></span>{counts?<div className="community-source-bar" role="img" aria-label={counts.map(s=>`${s.name} ${s.count}건`).join(', ')} title={`애객에 모인 누적 재게시 출처 수입니다. 당일 반응이나 순위가 아닙니다.${verified?' '+verified+' 확인':''}`}>{counts.map((s,i)=><span key={s.name} style={{flex:s.count,backgroundColor:sourceColors[i%sourceColors.length]}} title={`${s.name} ${s.count}건`}><span>{s.name} {s.count}</span></span>)}</div>:<span className="community-source-unknown">커뮤니티별 집계 미확인</span>}</div>
}
export function CommunityBriefing(){
 const [entries,setEntries]=useState<Entry[]>([]),[date,setDate]=useState(''),[edition,setEdition]=useState<'am'|'pm'>('am'),[brief,setBrief]=useState<Brief|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[active,setActive]=useState<number|null>(null),[read,setRead]=useState<string[]>([]);
 useEffect(()=>{try{setRead(JSON.parse(localStorage.getItem('daily-k-community-read')||'[]'))}catch{}
 const c=new AbortController();fetch('/daily-k/data/community/index.json',{cache:'no-store',signal:c.signal}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(v=>{if(!v||typeof v!=='object'||!('editions' in v)||!Array.isArray(v.editions))throw Error();setEntries(v.editions);const q=new URLSearchParams(location.search),latest=v.editions[0];setDate(q.get('date')||latest?.date||new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(new Date()));setEdition(q.get('edition')==='pm'?'pm':q.get('edition')==='am'?'am':latest?.edition||'am');setLoading(false)}).catch(()=>{if(!c.signal.aborted){setError('브리핑 목록을 불러오지 못했습니다.');setLoading(false)}});return()=>c.abort()},[]);
 const entry=entries.find(e=>e.date===date&&e.edition===edition);
 useEffect(()=>{setBrief(null);setActive(null);if(!entry){setLoading(false);return}const c=new AbortController();setLoading(true);fetch(`/daily-k/data/community/${entry.path}`,{cache:'no-store',signal:c.signal}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(v=>{if(!isBrief(v)||v.id!==entry.id)throw Error();setBrief(v);setError('')}).catch(()=>{if(!c.signal.aborted)setError('브리핑을 불러오지 못했습니다.')}).finally(()=>{if(!c.signal.aborted)setLoading(false)});return()=>c.abort()},[entry?.id]);
 function choose(d:string,e:'am'|'pm'){setDate(d);setEdition(e);setError('');const u=new URL(location.href);u.searchParams.delete('tab');u.searchParams.set('date',d);u.searchParams.set('edition',e);history.replaceState(null,'',u)}
 const body=useRef<HTMLDivElement|null>(null);
 function open(i:number){if(!brief)return;if(i>=brief.stories.length){setActive(null);return}if(i<0)return;setActive(i);setRead(current=>{const ids=[...new Set([...current,`${brief.id}:${brief.stories[i].id}`])].slice(-2000);try{localStorage.setItem('daily-k-community-read',JSON.stringify(ids))}catch{}return ids})}
 useEffect(()=>{body.current?.scrollTo({top:0,behavior:'instant'})},[active]);
 useEffect(()=>{
  if(active===null||!brief)return;
  function navigate(event:KeyboardEvent){
   if(event.defaultPrevented||event.repeat||event.altKey||event.ctrlKey||event.metaKey)return;
   if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
   if(event.target instanceof HTMLElement&&event.target.closest('input,textarea,select,[contenteditable="true"],[role="textbox"],[role="slider"]'))return;
   if(event.shiftKey&&event.key!=='ArrowUp'&&event.key!=='ArrowDown')return;
   event.preventDefault();
   if(event.key==='ArrowLeft'||event.key==='ArrowRight'){open(active!+(event.key==='ArrowLeft'?-1:1));return}
   const panel=body.current;if(!panel)return;
   const behavior=matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
   if(event.shiftKey){const sources=panel.querySelector<HTMLElement>('.news-sources');panel.scrollTo({top:event.key==='ArrowUp'?0:sources?panel.scrollTop+sources.getBoundingClientRect().top-panel.getBoundingClientRect().top:panel.scrollHeight,behavior})}
   else panel.scrollBy({top:event.key==='ArrowUp'?-500:500,behavior});
  }
  window.addEventListener('keydown',navigate,true);return()=>window.removeEventListener('keydown',navigate,true);
 },[active,brief]);
 const dates=[...new Set(entries.map(e=>e.date))].sort(),previous=dates.filter(d=>d<date).at(-1),next=dates.find(d=>d>date),story=active===null?null:brief?.stories[active];
 return <section className="news community" aria-label="커뮤니티 인기 글 브리핑">
 <div className="news-controls news-controls-inline"><button disabled={!previous} onClick={()=>previous&&choose(previous,edition)} aria-label="이전 날짜">←</button><button aria-pressed={edition==='am'} onClick={()=>choose(date,'am')}>오전</button><input type="date" aria-label="브리핑 날짜" value={date} onChange={e=>choose(e.target.value,edition)}/><button aria-pressed={edition==='pm'} onClick={()=>choose(date,'pm')}>오후</button><button disabled={!next} onClick={()=>next&&choose(next,edition)} aria-label="다음 날짜">→</button></div>
 {loading?<p className="news-message">브리핑을 불러오고 있습니다.</p>:error?<p className="news-message" role="alert">{error}</p>:!brief?<div className="news-message"><h2>아직 발행된 브리핑이 없습니다</h2><p>매일 오전 9시·오후 9시에 커뮤니티 화제·유머·정보 글을 선별합니다.</p></div>:<><div className="news-intro"><p>{brief.test?'테스트 브리핑 · ':''}{new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(brief.cutoffAt))} 기준</p><h1>인터넷에서는 무슨 이야기가 화제였을까요?</h1>{brief.overview.map((p,i)=><p key={i}>{p}</p>)}</div><ol className="posts community-stories">{brief.stories.map((s,i)=><li className={read.includes(`${brief.id}:${s.id}`)?'seen':''} key={s.id}><button className="news-story-trigger post-top" onClick={()=>open(i)}><span className="rank">{i+1}</span><span className="post-main"><span className="news-category">{s.category}</span><span className="news-story-title">{s.title}</span><span className="news-story-summary">{s.summary[0]}</span></span><Image url={s.imageUrl||s.videoPosterUrl} title={s.title}/></button></li>)}</ol></>}
 <Dialog open={!!story} onOpenChange={v=>!v&&setActive(null)}><DialogContent className="reader-dialog news-reader community-reader" showCloseButton={false} aria-describedby={undefined} initialFocus={body}>{story&&brief&&<><nav className="reader-nav reader-top"><button disabled={active===0} onClick={()=>open(active!-1)}>←</button><ReaderHeading title={story.title} index={active!+1} total={brief.stories.length} onClose={()=>setActive(null)}/><button onClick={()=>open(active!+1)}>→</button></nav><div ref={body} tabIndex={-1} className="reader-body news-reader-body"><div key={story.id} className="community-media">{story.videoUrl?<Video story={story}/>:<Image url={story.imageUrl} title={story.title}/>}</div>{story.summary.map((p,i)=><p key={i}>{p}</p>)}<SourceGraph story={story}/><div className="news-sources"><h3>원본 글 · 관련 링크</h3><div className="news-related">{story.sources.map(l=><a className="news-link-card" key={l.url} href={l.url} target="_blank" rel="noopener noreferrer"><Image url={l.imageUrl} title={l.title}/><span className="news-link-copy"><span className="news-publisher">{l.name}</span><strong>{l.title}</strong></span></a>)}</div></div><details key={story.id} className="community-notes"><summary>선정 이유 · 확인 범위</summary><p><strong>선정 이유</strong> · {story.selectionReason}</p><p><strong>확인 범위</strong> · {story.verificationNote}</p><p className="news-event-time">{story.popularityEvidence}</p></details></div></>}</DialogContent></Dialog>
 </section>
}
