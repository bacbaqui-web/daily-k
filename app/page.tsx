'use client';
import { useEffect, useState, useMemo, type CSSProperties } from 'react';
import { Dialog, DialogTrigger, DialogContent, DialogTitle, DialogDescription, DialogClose } from '@/components/ui/dialog';
import { PreviewCard as PreviewCardPrimitive } from '@base-ui/react/preview-card';
import { HoverCard, HoverCardTrigger } from '@/components/ui/hover-card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { unreadFirst, adjacentPost, within24Hours } from '../lib/reading';
type ContentBlock = {type:"text";text:string}|{type:"image";src:string;alt?:string}|{type:"video";src:string;poster?:string};
type Post = {commentsPartial?:boolean;reportedCommentCount?:number|null;publishedAt?:string;comments?:{id:string;text:string}[];commentsError?:boolean;commentsFetchedAt?:string;content?:ContentBlock[];matchedPosts?:{url:string;source:string}[];kCount:number;commentCount:number;kPerComment?:number;id:string;title:string;url:string;source:string;excerpt:string;images:string[];videos?:{src:string;poster:string;type:string}[]};
type Feed = {date:string;posts:Post[];taggedPosts?:Post[];collectionStatus?:string;collectionMessage?:string};
function isFeed(value:unknown):value is Feed {
 if(!value||typeof value!=='object')return false;
 const v=value as Partial<Feed>;
 if(!Array.isArray(v.posts)||(v.taggedPosts!==undefined&&!Array.isArray(v.taggedPosts)))return false;
 return typeof v.date==='string'&&(v.collectionMessage===undefined||typeof v.collectionMessage==='string')&&v.posts.every(p=>p&&p.kCount>=10&&p.commentCount>0)&&[...v.posts,...(v.taggedPosts||[])].every(p=>p&&typeof p.id==='string'&&typeof p.title==='string'&&typeof p.source==='string'&&typeof p.url==='string'&&p.url.startsWith('https://')&&typeof p.excerpt==='string'&&(p.comments===undefined||(Array.isArray(p.comments)&&p.comments.every(c=>c&&typeof c.id==='string'&&typeof c.text==='string')))&&(p.content===undefined||(Array.isArray(p.content)&&p.content.every(b=>b&&(b.type==='text'?typeof b.text==='string':(b.type==='image'||b.type==='video')&&typeof b.src==='string'&&b.src.startsWith('https://')&&(b.type!=='video'||!b.poster||b.poster.startsWith('https://'))))))&&Number.isFinite(p.kCount)&&p.kCount>=0&&Number.isFinite(p.commentCount)&&p.commentCount>=0&&(p.matchedPosts===undefined||(Array.isArray(p.matchedPosts)&&p.matchedPosts.every(m=>m&&typeof m.url==='string'&&m.url.startsWith('https://')&&typeof m.source==='string')))&&Array.isArray(p.images)&&p.images.every((u:unknown)=>typeof u==='string'&&u.startsWith('https://'))&&(p.videos===undefined||(Array.isArray(p.videos)&&p.videos.every(v=>v&&typeof v.src==='string'&&v.src.startsWith('https://')&&typeof v.poster==='string'&&(v.poster===''||v.poster.startsWith('https://'))))));
}
const sourceColors:Record<string,string>={'애객':'#ce3d46','루리웹':'#2367b3','에펨코리아':'#315b99','개드립':'#946500','이토랜드':'#b52326','웃긴대학':'#d62e35','디시인사이드':'#3b4890','오늘의유머':'#357087'};
function LaughStats({post}:{post:Post}){return <div className="laugh-stats"><strong>ㅋ {post.kCount.toLocaleString('ko-KR')}</strong><span title={`수집한 댓글 ${post.commentCount}개 기준 · 통계적인 신뢰 확률은 아닙니다`}>댓글당 ㅋ {(post.commentCount? (post.kCount/post.commentCount).toFixed(2):'—')}</span><small>댓글 {post.commentCount.toLocaleString('ko-KR')}개{post.commentsPartial?' · 일부':''}</small></div>}
function ArticleImage({src,alt}:{src:string;alt:string}){
 const [failed,setFailed]=useState(false);
 useEffect(()=>setFailed(false),[src]);
 return failed?<div className="image-unavailable" role="img" aria-label="이미지를 불러오지 못했습니다"><svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m4 17 5-5 4 4 3-3 4 5M3 3l18 18"/></svg><strong>이미지를 불러오지 못했어요</strong><span>원문에 이미지가 있는 자리입니다</span></div>:<img src={src} alt={alt} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>;
}
function Video({src,poster}:{src:string;poster:string}){
 const [failed,setFailed]=useState(false);
 return failed?<p className="media-error">이 영상은 원문에서 확인해 주세요.</p>:<video src={src} poster={poster||undefined} controls autoPlay muted playsInline preload="metadata" onError={()=>setFailed(true)} />;
}
function Body({post}:{post:Post}){
 if(post.content?.length)return <>{post.content.map((b,i)=>b.type==='text'?<p key={i}>{b.text}</p>:b.type==='image'?<ArticleImage key={`${i}-${b.src}`} src={b.src} alt={b.alt||`${post.title} 본문 이미지`}/>:<Video key={i} src={b.src} poster={b.poster||''}/>)}</>;
 return <>{post.excerpt&&<p>{post.excerpt}</p>}{post.images.map((src,i)=><ArticleImage key={`${i}-${src}`} src={src} alt={`${post.title} 본문 이미지`}/>)}{post.videos?.map(v=><Video key={v.src} src={v.src} poster={v.poster}/>)}</>;
}
function Comments({post,preview=false}:{post:Post;preview?:boolean}){
 const comments=preview?post.comments?.slice(0,8):post.comments;
 return <section className={preview?'preview-comments':'article-comments'} aria-label="원문 댓글"><h3>{preview?'댓글 미리보기':'원문 댓글'}</h3>{post.commentsError?<p className="comment-note">댓글을 불러오지 못했습니다. 원문에서 확인해 주세요.</p>:comments===undefined?<p className="comment-note">아직 수집한 댓글이 없습니다.</p>:comments.length===0?<p className="comment-note">수집된 댓글이 없습니다.</p>:<><p className="comment-note">{post.commentsPartial?`애객 표시 ${post.reportedCommentCount}개 중 ${post.commentCount}개 확인${preview?` · 미리보기 ${comments.length}개`:''}`:preview?`수집한 댓글 중 ${comments.length}개`:`수집한 댓글 ${comments.length}개`}</p><ol className="comment-list">{comments.map((c,i)=><li key={c.id}><span className="comment-number">{i+1}</span><p>{c.text||'이미지·이모티콘 등 텍스트가 없는 댓글입니다.'}</p></li>)}</ol>{preview&&(post.comments?.length||0)>8&&<span className="preview-hint">전체 글을 열면 더 볼 수 있어요</span>}</>}</section>;
}
function PostTitle({post,expanded}:{post:Post;expanded:boolean}){
 const [peek,setPeek]=useState(false),[canHover,setCanHover]=useState(false);
 const [pointer,setPointer]=useState<{x:number;y:number;element:HTMLElement|null}>({x:0,y:0,element:null});
 const anchor=useMemo(()=>({getBoundingClientRect:()=>new DOMRect(pointer.x,pointer.y,0,0),contextElement:pointer.element||undefined}),[pointer]);
 useEffect(()=>{const query=matchMedia('(hover: hover) and (pointer: fine)');const update=()=>setCanHover(query.matches);update();query.addEventListener('change',update);return()=>query.removeEventListener('change',update)},[]);
 useEffect(()=>{if(!peek)return;const close=()=>setPeek(false);window.addEventListener('scroll',close,{passive:true});return()=>window.removeEventListener('scroll',close)},[peek]);
 const firstImage=post.content?.find(b=>b.type==='image');
 const src=firstImage?.type==='image'?firstImage.src:(post.images[0]||post.videos?.[0]?.poster);
 const firstVideo=post.content?.find(b=>b.type==='video');
 const previewVideo=firstVideo?.type==='video'?firstVideo:post.videos?.[0];
 const excerpt=post.content?.filter(b=>b.type==='text').map(b=>b.type==='text'?b.text:'').join(' ').slice(0,240)||post.excerpt.slice(0,240);
 return <HoverCard open={peek&&canHover&&!expanded} onOpenChange={open=>setPeek(open&&canHover&&!expanded)}><HoverCardTrigger render={<DialogTrigger/>} delay={400} closeDelay={150} onPointerEnter={e=>{if(e.pointerType==='mouse')setPointer({x:e.currentTarget.getBoundingClientRect().right,y:e.clientY,element:e.currentTarget})}} onPointerMove={e=>{if(e.pointerType==='mouse')setPointer({x:e.currentTarget.getBoundingClientRect().right,y:e.clientY,element:e.currentTarget})}} onFocus={e=>{const r=e.currentTarget.getBoundingClientRect();setPointer({x:r.right,y:r.top+r.height/2,element:e.currentTarget})}} onClick={()=>setPeek(false)}>{post.title}</HoverCardTrigger><PreviewCardPrimitive.Portal><PreviewCardPrimitive.Positioner anchor={anchor} positionMethod="fixed" side="right" align="center" sideOffset={14} collisionPadding={12} collisionAvoidance={{side:'shift',align:'shift'}} className="preview-positioner"><PreviewCardPrimitive.Popup data-slot="hover-card-content" className="post-preview split-preview"><div className="preview-article">{post.source!=='애객'&&<span className="preview-source" style={{background:sourceColors[post.source]||'#596661'}}>{post.source}</span>}<h3>{post.title}</h3>{previewVideo?(peek&&canHover&&!expanded&&<Video key={previewVideo.src} src={previewVideo.src} poster={previewVideo.poster||''}/>):src&&<ArticleImage src={src} alt="본문 미리보기"/>}{excerpt&&<p>{excerpt}</p>}{!src&&!previewVideo&&!excerpt&&<p>전체 글을 열어 내용을 확인해 주세요.</p>}<span className="preview-hint">제목을 누르면 전체 글을 볼 수 있어요</span></div><Comments post={post} preview/></PreviewCardPrimitive.Popup></PreviewCardPrimitive.Positioner></PreviewCardPrimitive.Portal></HoverCard>;
}
function SourceList(){return <Dialog><DialogTrigger className="sources-button">수집 사이트</DialogTrigger><DialogContent className="reader-dialog sources-dialog" showCloseButton={false}><DialogTitle className="reader-title">수집 사이트</DialogTitle><DialogClose className="reader-close" aria-label="닫기">×</DialogClose><DialogDescription className="reader-description">애객 최신 이슈 모음</DialogDescription><ul className="source-list"><li><a href="https://aagag.com/issue/" target="_blank" rel="noopener noreferrer">애객 ↗</a><span>최근 24시간</span></li></ul><p className="reader-description">현재 시각 기준으로 최근 24시간에 애객에 올라온 글 중 본문 이미지나 영상이 있는 글을 모읍니다. ㅋㅋㅋ는 애객 댓글의 ㅋ가 10개 이상인 글을 ㅋ 총개수순, ㅇㅎㅂ은 제목에 ㅇㅎ·ㅎㅂ·ㅇㅎㅂ 표시가 있는 글을 애객 댓글 수순으로 보여줍니다. ㅇㅎㅂ은 최소 댓글 수 제한이 없습니다. 댓글 수집에 실패한 글은 순위에서 제외합니다. Oracle 서버에서 한 시간마다 새 글을 확인합니다.</p></DialogContent></Dialog>}
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
 function openPost(id:string){setReaderOrder(posts.map(p=>p.id));setOpened(id);mark(id)}
 function nextPost(delta:number){const id=adjacentPost(activeOrder,opened,delta);if(id){setOpened(id);mark(id)}}
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
   const id=adjacentPost(activeOrder,opened,event.key==='ArrowLeft'?-1:1);
   if(id){setOpened(id);mark(id)}
  }
  window.addEventListener('keydown',navigate,true);
  return()=>window.removeEventListener('keydown',navigate,true);
 },[opened,activeOrder]);
 return <main>
  <Tabs value={tab} onValueChange={value=>{setTab(value==='tagged'?'tagged':'humor');setOpened(null)}} className="feed-tabs"><header><TabsList className="category-tabs" aria-label="게시글 종류"><TabsTrigger value="humor">ㅋㅋㅋ</TabsTrigger><TabsTrigger value="tagged">ㅇㅎㅂ</TabsTrigger></TabsList><div className="header-actions"><ThemeToggle/><SourceList /></div></header>
  {feed?.collectionMessage&&feed.collectionStatus!=='complete'&&<p className="collection-notice" role="status">{feed.collectionMessage}</p>}<TabsContent value={tab} key={tab}>{error&&!feed?<div className="empty" role="alert"><span className="big-k">ㅋ</span><p>불러오지 못했습니다</p><button onClick={()=>setRetry(v=>v+1)}>다시 시도</button></div>:posts.length===0?<div className="empty" role="status"><span className="big-k" aria-hidden="true">ㅋ</span><p>{feed?.collectionMessage?'수집된 글이 없습니다':tab==='humor'?'ㅋ수집중':'아직 수집한 글이 없어요'}</p></div>:<ol className="posts">{posts.map((p,i)=><li key={p.id} style={{'--source-color':sourceColors[p.source]||'#596661'} as CSSProperties} className={read.includes(p.id)?'seen':''}><Dialog open={opened===p.id} onOpenChange={open=>{if(open)openPost(p.id);else setOpened(current=>current===p.id?null:current)}}><article><div className="post-top"><span className="rank">{String(i+1).padStart(2,'0')}</span><div className="post-main">{(p.source!=='애객'||read.includes(p.id))&&<span className="source">{p.source==='애객'?'읽음':p.source+(read.includes(p.id)?' · 읽음':'')}</span>}<h2><PostTitle post={p} expanded={opened===p.id}/></h2><LaughStats post={p}/></div></div></article><DialogContent className="reader-dialog" showCloseButton={false}><DialogTitle className="reader-title">{p.title}</DialogTitle><DialogClose className="reader-close" aria-label="닫기">×</DialogClose><DialogDescription className="reader-description">{p.source!=='애객'?p.source:'본문과 댓글'}</DialogDescription><nav className="reader-nav" aria-label="게시글 이동"><button onClick={()=>nextPost(-1)} disabled={activeOrder.indexOf(p.id)<=0} aria-label="이전 글">← 이전 글</button><span>{activeOrder.indexOf(p.id)+1} / {activeOrder.length}</span><button onClick={()=>nextPost(1)} disabled={activeOrder.indexOf(p.id)>=activeOrder.length-1} aria-label="다음 글">다음 글 →</button></nav><LaughStats post={p}/>{opened===p.id&&<div className="reader-body" data-reader-active="true"><Body post={p}/><Comments post={p}/>{(p.matchedPosts?.length?p.matchedPosts:[{url:p.url,source:p.source}]).map(m=><a key={m.url} className="original" href={m.url} target="_blank" rel="noopener noreferrer">{m.source==='애객'?'':m.source+' '}원문 보기 ↗</a>)}</div>}</DialogContent></Dialog></li>)}</ol>}</TabsContent></Tabs>
 </main>
}
