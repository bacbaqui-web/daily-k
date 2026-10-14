'use client';
import type {EditionSelection} from '../lib/edition-view';
import {useEffect,useRef,useState} from 'react';
import {Dialog,DialogContent} from './ui/dialog';
import {ReaderHeading} from './reader-heading';
import {CommunityBodyImages} from './community-media';
import {communityThumbnail,isBodyImages,type CommunityMedia} from '../lib/community-media';
import {contentMarkers} from '../lib/content-markers';
import {prepareCommunityStories,communityStoryIndices,communityCategories,communityCategoryLabel,type CommunityCategory} from '../lib/community-view';
type Link={name:string;title:string;url:string;publishedAt?:string;imageUrl?:string|null};
type SourceCount={name:string;count:number};
type Category=CommunityCategory;
const categories=communityCategories;
type CommentQuote={id:string;text:string;truncated?:boolean;likes?:number};
type Story=CommunityMedia&{id:string;topicKey:string;title:string;category:Category|'ㅇㅎㅂ';originalText?:string;comments?:CommentQuote[];kCount?:number;commentCount?:number;commentsVerifiedAt?:string;contentReview?:string;portalLinks?:string[];contentSignals?:{kind:'instagram'|'x'|'leaked';commentId:string;url?:string}[];summary:string[];selectionReason:string;popularityEvidence:string;verificationNote:string;imageUrl?:string|null;videoUrl?:string|null;videoPosterUrl?:string|null;sourceBreakdown?:SourceCount[];sourceStatsVerifiedAt?:string;sources:Link[]};
type Brief={cutoffAt:string;test?:boolean;id:string;date:string;edition:'am'|'pm';generatedAt:string;overview:string[];stories:Story[]};
type Entry={id:string;date:string;edition:'am'|'pm';path:string};
const safe=(v:unknown):v is string=>typeof v==='string'&&/^https?:\/\//.test(v);
function isBrief(v:unknown):v is Brief{if(!v||typeof v!=='object')return false;const b=v as Brief;return typeof b.id==='string'&&Array.isArray(b.overview)&&b.overview.every(p=>typeof p==='string')&&Array.isArray(b.stories)&&b.stories.every(s=>typeof s.title==='string'&&typeof s.selectionReason==='string'&&Array.isArray(s.summary)&&s.summary.every(p=>typeof p==='string')&&Array.isArray(s.sources)&&s.sources.length>0&&s.sources.every(l=>safe(l.url))&&(!s.comments||Array.isArray(s.comments)&&s.comments.every(c=>typeof c.id==='string'&&typeof c.text==='string'))&&(s.kCount===undefined||Number.isSafeInteger(s.kCount)&&s.kCount>=0)&&(s.bodyImages===undefined||isBodyImages(s.bodyImages)&&safe(s.bodyImagesSourceUrl)&&s.sources.some(l=>l.url===s.bodyImagesSourceUrl)&&typeof s.bodyImagesVerifiedAt==='string'&&Number.isFinite(Date.parse(s.bodyImagesVerifiedAt)))&&(!s.imageUrl||safe(s.imageUrl))&&(!s.videoUrl||safe(s.videoUrl))&&(!s.videoPosterUrl||safe(s.videoPosterUrl))&&(!s.sourceBreakdown||Array.isArray(s.sourceBreakdown)&&s.sourceBreakdown.every(c=>typeof c.name==='string'&&c.name.trim()&&Number.isSafeInteger(c.count)&&c.count>0)))}
function Image({url,title}:{url?:string|null;title:string}){const [failed,setFailed]=useState(false);return url&&!failed?<img className="community-image" src={url} alt={title} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>:null}
function Video({story}:{story:Story}){const [failed,setFailed]=useState(false);return failed?<p className="community-media-error">영상을 불러오지 못했습니다. 아래 원본 링크에서 확인해 주세요.</p>:<video className="community-video" controls playsInline preload="metadata" src={story.videoUrl!} poster={story.videoPosterUrl||undefined} aria-label={story.title} onError={()=>setFailed(true)}/>}
const sourceColors=['#476ca8','#6b8535','#ac596a','#9565ab','#ae7137','#36867c','#777eb5','#ad6554'];
function SourceGraph({story}:{story:Story}){
 const counts=story.sourceBreakdown?.length?story.sourceBreakdown:null;
 const total=counts?.reduce((sum,s)=>sum+s.count,0)??Number(story.popularityEvidence.match(/총\s*(\d+)개/)?.[1]||0);
 const verified=story.sourceStatsVerifiedAt?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(story.sourceStatsVerifiedAt)):'';
 return <div className="community-popularity" aria-label="인기 근거"><span className="community-source-total">누적 출처 <strong>{total||'미확인'}</strong></span>{counts?<div className="community-source-bar" role="img" aria-label={counts.map(s=>`${s.name} ${s.count}건`).join(', ')} title={`애객에 모인 누적 재게시 출처 수입니다. 당일 반응이나 순위가 아닙니다.${verified?' '+verified+' 확인':''}`}>{counts.map((s,i)=><span key={s.name} style={{flex:s.count,backgroundColor:sourceColors[i%sourceColors.length]}} title={`${s.name} ${s.count}건`}><span>{s.name} {s.count}</span></span>)}</div>:<span className="community-source-unknown">커뮤니티별 집계 미확인</span>}</div>
}
function CommunityShare({brief,story}:{brief:Brief;story:Story}){
 const [state,setState]=useState<'idle'|'copying'|'copied'|'manual'>('idle');
 const [link,setLink]=useState('');const manual=useRef<HTMLTextAreaElement|null>(null),button=useRef<HTMLButtonElement|null>(null);
 useEffect(()=>{const u=new URL(location.href);if(story.category==='ㅇㅎㅂ')u.searchParams.set('tab','tagged');else u.searchParams.delete('tab');u.searchParams.set('date',brief.date);u.searchParams.set('edition',brief.edition);u.searchParams.set('story',story.id);setLink(u.href)},[brief.id,story.id]);
 useEffect(()=>{if(state!=='copied')return;const t=setTimeout(()=>setState('idle'),6500);return()=>clearTimeout(t)},[state]);
 useEffect(()=>{if(state==='manual'){manual.current?.focus();manual.current?.select()}},[state]);
 async function copy(){setState('copying');try{await navigator.clipboard.writeText(link);setState('copied')}catch{setState('manual')}}
 return <div className="news-question-control"><span className="news-copy-buttons"><button ref={button} type="button" className="news-question-button" title="이 글의 링크 복사" onClick={copy} disabled={!link||state==='copying'}>{state==='copying'?'복사 중…':'공유하기'}</button></span>{state==='copied'&&<p className="news-copy-notice" role="status">링크주소가 복사됐습니다.</p>}{state==='manual'&&<div className="news-copy-manual" role="group" aria-label="글 링크 직접 복사" onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();setState('idle');button.current?.focus()}}}><p>자동 복사가 되지 않았습니다. 아래 주소를 직접 복사해 주세요.</p><textarea ref={manual} aria-label="공유할 글 링크" value={link} readOnly/><div><button onClick={()=>{setState('idle');button.current?.focus()}}>닫기</button></div></div>}</div>
}
function SocialLinks({story}:{story:Story}){const links=contentMarkers({comments:story.comments,excerpt:story.originalText,portalLinks:[...(story.portalLinks||[]),...(story.contentSignals||[]).flatMap(s=>s.url?[s.url]:[])]});return <>{links.map(l=><a className="content-marker" data-social={l.label==='인스타'?'instagram':'x'} href={l.url} key={l.url} target="_blank" rel="noopener noreferrer">{l.label}<span className="sr-only"> (새 탭)</span></a>)}</>}
function Comments({story}:{story:Story}){return <section className="community-comments"><h3>댓글 <span>{story.commentCount===undefined?'미확인':`${story.commentCount}개 확인`}</span></h3>{story.comments?.length?<><ol>{story.comments.map(c=><li key={c.id}><blockquote>{c.text}{c.truncated?'…':''}</blockquote>{c.likes!==undefined&&<small>추천 {c.likes}</small>}</li>)}</ol><p className="community-comment-note">확인한 댓글 중 짧은 인용입니다. 전체 댓글은 원본에서 볼 수 있습니다.</p></>:<p className="community-comment-note">이 회차의 댓글 인용은 아직 없습니다. 원본 링크에서 확인해 주세요.</p>}</section>}
export function CommunityBriefing({selection,tagged=false}:{selection?:EditionSelection;tagged?:boolean}){
 const [entries,setEntries]=useState<Entry[]>([]),[localDate,setDate]=useState(''),[localEdition,setEdition]=useState<'am'|'pm'>('am'),[brief,setBrief]=useState<Brief|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[active,setActive]=useState<string|null>(null),[read,setRead]=useState<string[]>([]),[category,setCategory]=useState<Category|'전체'>('전체');
 const date=localDate,edition=localEdition;
 const [now,setNow]=useState(Date.now());
 useEffect(()=>{
  try{setRead(JSON.parse(localStorage.getItem('daily-k-community-read')||'[]'))}catch{}
  const c=new AbortController();
  async function refresh(){try{
   const r=await fetch('/daily-k/data/community/index.json',{cache:'no-store',signal:c.signal});if(!r.ok)throw Error();
   const index=await r.json(),latest=index.editions?.[0];if(!latest){setBrief(null);setLoading(false);return}
   const response=await fetch(`/daily-k/data/community/${latest.path}`,{cache:'no-store',signal:c.signal});if(!response.ok)throw Error();
   const v=await response.json();if(!isBrief(v))throw Error();
   setBrief({...v,stories:prepareCommunityStories(v.stories)});setError('');setLoading(false);
  }catch{if(!c.signal.aborted){setError('게시글을 불러오지 못했습니다.');setLoading(false)}}}
  refresh();const timer=setInterval(()=>{setNow(Date.now());refresh()},60000);
  return()=>{c.abort();clearInterval(timer)};
 },[]);
 function uploadAge(s:Story){const stamp=Date.parse(s.sources[0]?.publishedAt||'');return Number.isFinite(stamp)?now-stamp:Infinity}
 function ageLabel(s:Story){const minutes=Math.max(0,Math.floor(uploadAge(s)/60000));return minutes<1?'방금 전':minutes<60?`${minutes}분 전`:`${Math.floor(minutes/60)}시간 전`}
 function choose(d:string,e:'am'|'pm'){setDate(d);setEdition(e);setError('');const u=new URL(location.href);u.searchParams.delete('tab');u.searchParams.delete('story');u.searchParams.set('date',d);u.searchParams.set('edition',e);history.replaceState(null,'',u)}
 const body=useRef<HTMLDivElement|null>(null);
 const [readerOrder,setReaderOrder]=useState<string[]>([]);
 const isRead=(id:string)=>read.some(key=>key===id||key.endsWith(`:${id}`));
 const visibleIndices=brief?communityStoryIndices(brief.stories,'전체').filter(i=>(brief.stories[i].category==='ㅇㅎㅂ')===tagged&&uploadAge(brief.stories[i])>=0&&uploadAge(brief.stories[i])<86400000).sort((a,b)=>Number(isRead(brief.stories[a].id))-Number(isRead(brief.stories[b].id))||(tagged?(brief.stories[b].commentCount??0)-(brief.stories[a].commentCount??0):(brief.stories[b].kCount??0)-(brief.stories[a].kCount??0))):[];
 const readerIndices=brief?readerOrder.map(id=>brief.stories.findIndex(s=>s.id===id)).filter(i=>visibleIndices.includes(i)):[];
 const visibleActive=readerIndices.findIndex(i=>brief?.stories[i].id===active);
 function move(delta:number){const next=visibleActive+delta;if(next<0)return;if(next>=readerIndices.length){setActive(null);return}open(readerIndices[next],true)}
 function open(i:number,continuing=false){if(!brief||i<0||i>=brief.stories.length)return;const id=brief.stories[i].id;if(!continuing)setReaderOrder(visibleIndices.map(j=>brief.stories[j].id));setActive(id);setRead(current=>{const ids=[...new Set([...current,id])].slice(-2000);try{localStorage.setItem('daily-k-community-read',JSON.stringify(ids))}catch{}return ids})}
 useEffect(()=>{if(!brief)return;const id=new URLSearchParams(location.search).get('story');const at=brief.stories.findIndex(s=>s.id===id);if(at>=0)open(at)},[brief?.id]);
 useEffect(()=>{body.current?.scrollTo({top:0,behavior:'instant'})},[active]);
 useEffect(()=>{
  if(active===null||!brief)return;
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
 },[active,brief,category]);
 const dates=[...new Set(entries.map(e=>e.date))].sort(),previous=dates.filter(d=>d<date).at(-1),next=dates.find(d=>d>date),story=brief?.stories.find(s=>s.id===active&&uploadAge(s)>=0&&uploadAge(s)<86400000);
 return <section className="news community" aria-label="커뮤니티 인기 글 브리핑">

 {loading?<p className="news-message">브리핑을 불러오고 있습니다.</p>:error?<p className="news-message" role="alert">{error}</p>:!brief?<div className="news-message"><h2>아직 발행된 브리핑이 없습니다</h2><p>최근 24시간 내 게시글을 수집하면 여기에 표시됩니다.</p></div>:<><ol className="posts community-stories">{visibleIndices.map((i,rank)=>{const s=brief.stories[i];return <li className={isRead(s.id)?'seen':''} key={s.id}><button className="news-story-trigger post-top" onClick={()=>open(i)}><span className="rank">{rank+1}</span><span className="post-main"><span className="news-story-meta"><span>{s.kCount===undefined?'ㅋ 미확인':`ㅋ ${s.kCount}`}</span><time dateTime={s.sources[0]?.publishedAt}>{ageLabel(s)}</time></span><span className="news-story-title">{s.title}</span></span><Image url={communityThumbnail(s)} title={s.title}/></button></li>})}</ol>{!visibleIndices.length&&<p className="news-message">최근 24시간 내 게시글이 없습니다.</p>}</>}
 <Dialog open={!!story} onOpenChange={v=>!v&&setActive(null)}><DialogContent className="reader-dialog news-reader community-reader" showCloseButton={false} aria-describedby={undefined} initialFocus={body}>{story&&brief&&<><nav className="reader-nav reader-top"><button disabled={visibleActive===0} onClick={()=>move(-1)}>←</button><ReaderHeading title={story.title} index={visibleActive+1} total={readerIndices.length} onClose={()=>setActive(null)}/><button onClick={()=>move(1)}>→</button><div className="laugh-stats news-reader-meta"><span>{story.kCount===undefined?'ㅋ 미확인':`ㅋ ${story.kCount}`} · {ageLabel(story)} · 댓글 {story.commentCount??'미확인'}</span><SocialLinks story={story}/><CommunityShare key={story.id} brief={brief} story={story}/></div></nav><div ref={body} tabIndex={-1} className="reader-body news-reader-body"><div key={`media-${story.id}`} className="community-media">{story.videoUrl&&<Video story={story}/>}<CommunityBodyImages story={story}/></div>{story.originalText&&<blockquote className="community-original">{story.originalText}</blockquote>}<Comments story={story}/><SourceGraph story={story}/><div className="news-sources"><h3>원본 글 · 관련 링크</h3><div className="news-related">{story.sources.map(l=><a className="news-link-card" key={l.url} href={l.url} target="_blank" rel="noopener noreferrer"><Image url={l.imageUrl} title={l.title}/><span className="news-link-copy"><span className="news-publisher">{l.name}</span><strong>{l.title}</strong></span></a>)}</div></div><details key={`notes-${story.id}`} className="community-notes"><summary>선정 이유 · 확인 범위</summary><p><strong>선정 이유</strong> · {story.selectionReason}</p><p><strong>확인 범위</strong> · {story.verificationNote}</p><p className="news-event-time">{story.popularityEvidence}</p></details></div></>}</DialogContent></Dialog>
 </section>
}
