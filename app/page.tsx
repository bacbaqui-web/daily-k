'use client';
import { useEffect, useState, useMemo, useRef, type CSSProperties } from 'react';
import { Dialog, DialogTrigger, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { PreviewCard as PreviewCardPrimitive } from '@base-ui/react/preview-card';
import { HoverCard, HoverCardTrigger } from '@/components/ui/hover-card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { contentMarkers } from '../lib/content-markers';
import { unreadFirst, adjacentPost, nextUnreadPost, within24Hours } from '../lib/reading';
type ContentBlock = {type:"text";text:string}|{type:"image";src:string;alt?:string}|{type:"video";src:string;poster?:string};
type Post = {portalLinks?:string[];commentsPartial?:boolean;reportedCommentCount?:number|null;publishedAt?:string;comments?:{id:string;text:string}[];commentsError?:boolean;commentsFetchedAt?:string;content?:ContentBlock[];matchedPosts?:{url:string;source:string}[];kCount:number;commentCount:number;kPerComment?:number;id:string;title:string;url:string;source:string;excerpt:string;images:string[];videos?:{src:string;poster:string;type:string}[]};
type Feed = {date:string;posts:Post[];taggedPosts?:Post[];collectionStatus?:string;collectionMessage?:string};
function isFeed(value:unknown):value is Feed {
 if(!value||typeof value!=='object')return false;
 const v=value as Partial<Feed>;
 if(!Array.isArray(v.posts)||(v.taggedPosts!==undefined&&!Array.isArray(v.taggedPosts)))return false;
 return typeof v.date==='string'&&(v.collectionMessage===undefined||typeof v.collectionMessage==='string')&&v.posts.every(p=>p&&p.kCount>=10&&p.commentCount>0)&&[...v.posts,...(v.taggedPosts||[])].every(p=>p&&typeof p.id==='string'&&typeof p.title==='string'&&typeof p.source==='string'&&typeof p.url==='string'&&p.url.startsWith('https://')&&typeof p.excerpt==='string'&&(p.comments===undefined||(Array.isArray(p.comments)&&p.comments.every(c=>c&&typeof c.id==='string'&&typeof c.text==='string')))&&(p.content===undefined||(Array.isArray(p.content)&&p.content.every(b=>b&&(b.type==='text'?typeof b.text==='string':(b.type==='image'||b.type==='video')&&typeof b.src==='string'&&b.src.startsWith('https://')&&(b.type!=='video'||!b.poster||b.poster.startsWith('https://'))))))&&Number.isFinite(p.kCount)&&p.kCount>=0&&Number.isFinite(p.commentCount)&&p.commentCount>=0&&(p.matchedPosts===undefined||(Array.isArray(p.matchedPosts)&&p.matchedPosts.every(m=>m&&typeof m.url==='string'&&m.url.startsWith('https://')&&typeof m.source==='string')))&&Array.isArray(p.images)&&p.images.every((u:unknown)=>typeof u==='string'&&u.startsWith('https://'))&&(p.videos===undefined||(Array.isArray(p.videos)&&p.videos.every(v=>v&&typeof v.src==='string'&&v.src.startsWith('https://')&&typeof v.poster==='string'&&(v.poster===''||v.poster.startsWith('https://'))))));
}
const sourceColors:Record<string,string>={'애객':'#ce3d46','루리웹':'#2367b3','에펨코리아':'#315b99','개드립':'#946500','이토랜드':'#b52326','웃긴대학':'#d62e35','디시인사이드':'#3b4890','오늘의유머':'#357087'};
function ShareButton({postId}:{postId:string}){
 const [message,setMessage]=useState('');
 const [copying,setCopying]=useState(false);
 useEffect(()=>{if(!message)return;const timer=window.setTimeout(()=>setMessage(''),3000);return ()=>window.clearTimeout(timer)},[message]);
 async function copy(){setCopying(true);setMessage('');try{const url=new URL('/daily-k/',window.location.origin);url.searchParams.set('post',postId);await navigator.clipboard.writeText(url.href);setMessage('링크주소가 복사됐습니다.')}catch{setMessage('링크를 복사하지 못했습니다. 다시 시도해 주세요.')}finally{setCopying(false)}}
 return <span className="share-control"><button type="button" className="share-button" onClick={copy} disabled={copying}>공유</button><span className={message?'share-notice':''} role="status" aria-live="polite">{message}</span></span>
}
function LaughStats({post,tab,now,compact=false}:{post:Post;tab:string;now:number;compact?:boolean}){
 const fetched=Date.parse(post.commentsFetchedAt||'');
 const minutes=Math.floor(Math.max(0,now-fetched)/60000);
 const age=!Number.isFinite(fetched)||!now?'수집 시간 미상':minutes<1?'방금 수집':minutes<60?`${minutes}분 전 수집`:minutes<1440?`${Math.floor(minutes/60)}시간 ${minutes%60}분 전 수집`:`${Math.floor(minutes/1440)}일 전 수집`;
 return <div className="laugh-stats">{tab==='humor'?<><strong>ㅋ {post.kCount.toLocaleString('ko-KR')}</strong><span>댓글당 ㅋ {post.commentCount?(post.kCount/post.commentCount).toFixed(2):'—'}</span></>:contentMarkers(post).map(label=><span className="content-marker" key={label} title="수집된 본문·댓글에서 발견">{label}</span>)}{!compact&&<small>댓글 {post.commentCount.toLocaleString('ko-KR')}개{post.commentsPartial?' · 일부':''}</small>}<small title={Number.isFinite(fetched)?`댓글 수집 완료: ${new Date(fetched).toLocaleString('ko-KR')}`:undefined}>{age}</small>{compact&&<ShareButton postId={post.id}/>}</div>
}
function ArticleImage({src,alt}:{src:string;alt:string}){
 const [failed,setFailed]=useState(false);
 useEffect(()=>setFailed(false),[src]);
 return failed?<div className="image-unavailable" role="img" aria-label="이미지를 불러오지 못했습니다"><svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m4 17 5-5 4 4 3-3 4 5M3 3l18 18"/></svg><strong>이미지를 불러오지 못했어요</strong><span>원문에 이미지가 있는 자리입니다</span></div>:<img src={src} alt={alt} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>;
}
function Video({src,poster}:{src:string;poster:string}){
 const [failed,setFailed]=useState(false);
 return failed?<p className="media-error">이 영상은 원문에서 확인해 주세요.</p>:<video src={src} poster={poster||undefined} controls autoPlay muted playsInline preload="metadata" onError={()=>setFailed(true)} />;
}
function PortalLinks({post}:{post:Post}){const links=[...new Set((post.portalLinks||[]).filter(url=>{try{const u=new URL(url);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password}catch{return false}}))];return links.length?<div className="portal-links">{links.map((url,i)=><a key={url} href={url} target="_blank" rel="noopener noreferrer">강호의 도리로 가는 포탈{links.length>1?` ${i+1}`:''} ↗</a>)}</div>:null}
function Body({post}:{post:Post}){
 if(post.content?.length)return <>{post.content.map((b,i)=>b.type==='text'?<p key={i}>{b.text}</p>:b.type==='image'?<ArticleImage key={`${i}-${b.src}`} src={b.src} alt={b.alt||`${post.title} 본문 이미지`}/>:<Video key={i} src={b.src} poster={b.poster||''}/>)}</>;
 return <>{post.excerpt&&<p>{post.excerpt}</p>}{post.images.map((src,i)=><ArticleImage key={`${i}-${src}`} src={src} alt={`${post.title} 본문 이미지`}/>)}{post.videos?.map(v=><Video key={v.src} src={v.src} poster={v.poster}/>)}</>;
}
function Comments({post,preview=false}:{post:Post;preview?:boolean}){
 const comments=post.comments;
 return <section className={preview?'preview-comments':'article-comments'} aria-label="원문 댓글"><h3>{preview?'댓글 미리보기':'원문 댓글'}</h3>{post.commentsError?<p className="comment-note">댓글을 불러오지 못했습니다. 원문에서 확인해 주세요.</p>:comments===undefined?<p className="comment-note">아직 수집한 댓글이 없습니다.</p>:comments.length===0?<p className="comment-note">수집된 댓글이 없습니다.</p>:<><p className="comment-note">{post.commentsPartial?`애객 표시 ${post.reportedCommentCount}개 중 ${post.commentCount}개 확인${preview?` · 미리보기 ${comments.length}개`:''}`:preview?`수집한 댓글 ${comments.length}개`:`수집한 댓글 ${comments.length}개`}</p><ol className="comment-list">{comments.map((c,i)=><li key={c.id}><span className="comment-number">{i+1}</span><p>{c.text||'이미지·이모티콘 등 텍스트가 없는 댓글입니다.'}</p></li>)}</ol></>}</section>;
}
function PostTitle({post,expanded}:{post:Post;expanded:boolean}){
 const [peek,setPeek]=useState(false),[canHover,setCanHover]=useState(false);
 const [pointer,setPointer]=useState<{x:number;y:number;element:HTMLElement|null}>({x:0,y:0,element:null});
 const anchor=useMemo(()=>({getBoundingClientRect:()=>new DOMRect(pointer.x,pointer.y,0,0),contextElement:pointer.element||undefined}),[pointer]);
 useEffect(()=>{const query=matchMedia('(hover: hover) and (pointer: fine)');const update=()=>setCanHover(query.matches);update();query.addEventListener('change',update);return()=>query.removeEventListener('change',update)},[]);
 useEffect(()=>{if(!peek)return;const close=()=>setPeek(false);window.addEventListener('scroll',close,{passive:true});return()=>window.removeEventListener('scroll',close)},[peek]);
 return <HoverCard open={peek&&canHover&&!expanded} onOpenChange={open=>setPeek(open&&canHover&&!expanded)}><HoverCardTrigger render={<DialogTrigger/>} delay={400} closeDelay={150} onPointerEnter={e=>{if(e.pointerType==='mouse')setPointer({x:e.currentTarget.getBoundingClientRect().right,y:e.clientY,element:e.currentTarget})}} onPointerMove={e=>{if(e.pointerType==='mouse')setPointer({x:e.currentTarget.getBoundingClientRect().right,y:e.clientY,element:e.currentTarget})}} onFocus={e=>{const r=e.currentTarget.getBoundingClientRect();setPointer({x:r.right,y:r.top+r.height/2,element:e.currentTarget})}} onClick={()=>setPeek(false)}>{post.title}</HoverCardTrigger><PreviewCardPrimitive.Portal><PreviewCardPrimitive.Positioner anchor={anchor} positionMethod="fixed" side="right" align="center" sideOffset={14} collisionPadding={12} collisionAvoidance={{side:'shift',align:'shift'}} className="preview-positioner"><PreviewCardPrimitive.Popup data-slot="hover-card-content" className="post-preview split-preview"><div className="preview-article">{post.source!=='애객'&&<span className="preview-source" style={{background:sourceColors[post.source]||'#596661'}}>{post.source}</span>}<PortalLinks post={post}/><h3>{post.title}</h3>{peek&&canHover&&!expanded&&<Body post={post}/>}<span className="preview-hint">제목을 누르면 전체 글을 볼 수 있어요</span></div><Comments post={post} preview/></PreviewCardPrimitive.Popup></PreviewCardPrimitive.Positioner></PreviewCardPrimitive.Portal></HoverCard>;
}
function ReaderHeading({title,index,total,onClose}:{title:string;index:number;total:number;onClose:()=>void}){
 const start=useRef<{x:number;y:number;id:number}|null>(null);
 const [offset,setOffset]=useState(0);
 function reset(){start.current=null;setOffset(0)}
 return <div className="reader-heading drag-heading" style={{transform:`translateY(${Math.min(offset,110)}px)`}}
  onPointerDown={e=>{if(e.pointerType!=='touch'||!e.isPrimary||!matchMedia('(max-width: 767px)').matches)return;start.current={x:e.clientX,y:e.clientY,id:e.pointerId};e.currentTarget.setPointerCapture(e.pointerId)}}
  onPointerMove={e=>{const p=start.current;if(p?.id!==e.pointerId)return;setOffset(Math.max(0,e.clientY-p.y))}}
  onPointerUp={e=>{const p=start.current;if(p?.id!==e.pointerId)return;const close=e.clientY-p.y>=72&&e.clientY-p.y>Math.abs(e.clientX-p.x)*1.2;reset();if(close)onClose()}}
  onPointerCancel={reset} onLostPointerCapture={reset}>
  <DialogTitle className="reader-title">{title}</DialogTitle><span className="reader-counter">{index} / {total}</span>
 </div>;
}
function ThemeToggle(){
 const [dark,setDark]=useState(false);
 useEffect(()=>{
  const media=matchMedia('(prefers-color-scheme: dark)');
  const sync=()=>{let saved:string|null=null;try{saved=localStorage.getItem('daily-k-theme')}catch{}const value=saved==='dark'||(saved!=='light'&&media.matches);document.documentElement.dataset.theme=value?'dark':'light';setDark(value)};
  sync();media.addEventListener('change',sync);window.addEventListener('storage',sync);
  return()=>{media.removeEventListener('change',sync);window.removeEventListener('storage',sync)};
 },[]);
 function toggle(){const value=!dark;setDark(value);document.documentElement.dataset.theme=value?'dark':'light';try{localStorage.setItem('daily-k-theme',value?'dark':'light')}catch{}}
 return <Button variant="ghost" size="icon" className="theme-toggle" onClick={toggle} aria-label="다크 모드" aria-pressed={dark} title={dark?'밝은 모드로 전환':'다크 모드로 전환'}><svg className="moon-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M20.5 14A9 9 0 0 1 10 3.5 9 9 0 1 0 20.5 14Z"/></svg><svg className="sun-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg></Button>;
}
export default function Home(){
 const sharedHandled=useRef(false);
 const [shareNotice,setShareNotice]=useState('');
 const [readerOrder,setReaderOrder]=useState<string[]>([]);
 const [tab,setTab]=useState<'humor'|'tagged'>('humor');
 const [now,setNow]=useState(0),[feed,setFeed]=useState<Feed|null>(null),[error,setError]=useState(false),[read,setRead]=useState<string[]>([]),[opened,setOpened]=useState<string|null>(null),[retry,setRetry]=useState(0);
 useEffect(()=>{
  const tick=()=>setNow(Date.now());tick();const timer=window.setInterval(tick,1000);
  window.addEventListener('focus',tick);
  try{const saved=JSON.parse(localStorage.getItem('daily-k-read')||'[]');if(Array.isArray(saved))setRead(saved.filter((v:unknown)=>typeof v==='string'))}catch{}
  return()=>{clearInterval(timer);window.removeEventListener('focus',tick)};
 },[]);
 useEffect(()=>{
  const controller=new AbortController();let loading=false;
  async function load(){
   if(loading)return;loading=true;
   try{
    const response=await fetch('/daily-k/data/feed.json',{cache:'no-store',signal:controller.signal});
    if(!response.ok)throw Error('Feed unavailable');
    const value:unknown=await response.json();if(!isFeed(value))throw Error('Invalid feed');
    if(!controller.signal.aborted){setFeed(value);setError(false)}
   }catch{if(!controller.signal.aborted)setError(true)}finally{loading=false}
  }
  void load();const timer=window.setInterval(load,60000);window.addEventListener('focus',load);
  return()=>{controller.abort();clearInterval(timer);window.removeEventListener('focus',load)};
 },[retry]);
 function mark(id:string){setRead(prev=>{const next=[...new Set([...prev,id])].slice(-2000);try{localStorage.setItem('daily-k-read',JSON.stringify(next))}catch{}return next})}
 const rankedPosts=feed?(tab==='humor'?[...feed.posts].sort((a,b)=>b.kCount-a.kCount):[...(feed.taggedPosts||[])].sort((a,b)=>b.commentCount-a.commentCount||(b.publishedAt||'').localeCompare(a.publishedAt||'')||b.id.localeCompare(a.id))):[];
 const posts=unreadFirst(rankedPosts.filter(p=>within24Hours(p,now)),read);
 const activeOrder=readerOrder.filter(id=>posts.some(p=>p.id===id));
 useEffect(()=>{if(opened&&!rankedPosts.some(p=>p.id===opened&&within24Hours(p,now)))setOpened(null)},[opened,feed,now]);
 useEffect(()=>{
  if(!feed||!now||sharedHandled.current)return;
  sharedHandled.current=true;
  const id=new URL(window.location.href).searchParams.get('post');
  if(!id)return;
  const category=feed.posts.some(p=>p.id===id)?'humor':'tagged';
  const group=category==='humor'?feed.posts:(feed.taggedPosts||[]);
  const target=group.find(p=>p.id===id);
  if(!target||!within24Hours(target,now)){setShareNotice('공유된 글은 24시간이 지났거나 현재 목록에서 삭제되었습니다.');return}
  const ordered=[...group].filter(p=>within24Hours(p,now)).sort((a,b)=>category==='humor'?b.kCount-a.kCount:b.commentCount-a.commentCount||(b.publishedAt||'').localeCompare(a.publishedAt||''));
  setTab(category);setReaderOrder(unreadFirst(ordered,read).map(p=>p.id));setOpened(id);mark(id);
 },[feed,now]);
 function openPost(id:string){setReaderOrder(posts.map(p=>p.id));setOpened(id);mark(id)}
 function nextPost(delta:number){const id=delta>0?nextUnreadPost(activeOrder,opened,read):adjacentPost(activeOrder,opened,delta);if(id){setOpened(id);mark(id)}else if(delta>0)setOpened(null)}
 useEffect(()=>{
  if(!opened)return;
  function navigate(event:KeyboardEvent){
   if(event.defaultPrevented||event.repeat||event.altKey||event.ctrlKey||event.metaKey)return;
   if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
   const target=event.target;
   if(target instanceof HTMLElement&&target.closest('input,textarea,select,[contenteditable="true"],[role="textbox"],[role="slider"]'))return;
   if(event.shiftKey){
    if(event.key!=='ArrowUp'&&event.key!=='ArrowDown')return;
    event.preventDefault();
    const body=document.querySelector<HTMLElement>('[data-reader-active="true"]');
    if(!body)return;
    const comments=body.querySelector<HTMLElement>('.article-comments');
    const top=event.key==='ArrowUp'?0:comments?body.scrollTop+comments.getBoundingClientRect().top-body.getBoundingClientRect().top:body.scrollHeight;
    body.scrollTo({top,behavior:'smooth'});
    return;
   }
   event.preventDefault();
   if(event.key==='ArrowUp'||event.key==='ArrowDown'){
    document.querySelector<HTMLElement>('[data-reader-active="true"]')?.scrollBy({top:event.key==='ArrowUp'?-500:500,behavior:'smooth'});
    return;
   }
   nextPost(event.key==='ArrowLeft'?-1:1);
  }
  window.addEventListener('keydown',navigate,true);
  return()=>window.removeEventListener('keydown',navigate,true);
 },[opened,activeOrder,read]);
 return <main>
  {shareNotice&&<p className="collection-notice" role="status">{shareNotice}</p>}
  <Tabs value={tab} onValueChange={value=>{setTab(value==='tagged'?'tagged':'humor');setOpened(null)}} className="feed-tabs"><header><TabsList className="category-tabs" aria-label="게시글 종류"><TabsTrigger value="humor">ㅋㅋㅋ</TabsTrigger><TabsTrigger value="tagged">ㅇㅎㅂ</TabsTrigger></TabsList><div className="header-actions"><ThemeToggle/></div></header>
  {feed?.collectionMessage&&feed.collectionStatus!=='complete'&&<p className="collection-notice" role="status">{feed.collectionMessage}</p>}<TabsContent value={tab} key={tab}>{error&&!feed?<div className="empty" role="alert"><span className="big-k">ㅋ</span><p>불러오지 못했습니다</p><button onClick={()=>setRetry(v=>v+1)}>다시 시도</button></div>:posts.length===0?<div className="empty" role="status"><span className="big-k" aria-hidden="true">ㅋ</span><p>{feed?.collectionMessage?'수집된 글이 없습니다':tab==='humor'?'ㅋ수집중':'아직 수집한 글이 없어요'}</p></div>:<ol className="posts">{posts.map((p,i)=><li key={p.id} style={{'--source-color':sourceColors[p.source]||'#596661'} as CSSProperties} className={read.includes(p.id)?'seen':''}><Dialog disablePointerDismissal={false} open={opened===p.id} onOpenChange={open=>{if(open)openPost(p.id);else setOpened(current=>current===p.id?null:current)}}><article><div className="post-top"><span className="rank">{String(i+1).padStart(2,'0')}</span><div className="post-main">{(p.source!=='애객'||read.includes(p.id))&&<span className="source">{p.source==='애객'?'읽음':p.source+(read.includes(p.id)?' · 읽음':'')}</span>}<h2><PostTitle post={p} expanded={opened===p.id}/></h2><LaughStats post={p} tab={tab} now={now}/></div></div></article><DialogContent className="reader-dialog" showCloseButton={false} aria-describedby={undefined}><PortalLinks post={p}/><nav className="reader-nav reader-top" aria-label="게시글 이동"><button onClick={()=>nextPost(-1)} disabled={activeOrder.indexOf(p.id)<=0} aria-label="이전 글">← 이전 글</button><ReaderHeading title={p.title} index={activeOrder.indexOf(p.id)+1} total={activeOrder.length} onClose={()=>setOpened(null)}/><button onClick={()=>nextPost(1)} aria-label="다음 글">다음 글 →</button></nav><LaughStats post={p} tab={tab} now={now} compact/>{opened===p.id&&<div className="reader-body" data-reader-active="true"><Body post={p}/><Comments post={p}/>{(p.matchedPosts?.length?p.matchedPosts:[{url:p.url,source:p.source}]).map(m=><a key={m.url} className="original" href={m.url} target="_blank" rel="noopener noreferrer">{m.source==='애객'?'':m.source+' '}원문 보기 ↗</a>)}</div>}</DialogContent></Dialog></li>)}</ol>}</TabsContent></Tabs>
 </main>
}
