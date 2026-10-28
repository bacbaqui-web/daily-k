'use client';
import {useEffect,useRef,useState} from 'react';
import {Dialog,DialogContent} from './ui/dialog';
import {ReaderHeading} from './reader-heading';
type Comic={id:string;title:string;url:string;publishedAt:string;images:string[];coverImage?:string;content?:{type:string;src?:string;text?:string}[]};
const storageKey='daily-k-comics-hidden';
const readKey='daily-k-comics-read';
const identity=(p:Comic)=>p.id.replace(/^(aagag-\d+)-\d+$/,'$1');
const safe=(url:unknown):url is string=>typeof url==='string'&&/^https?:\/\//.test(url);
function Picture({url,title}:{url:string;title:string}){
 const [failed,setFailed]=useState(false);
 return failed?<p className="comic-image-error">이미지를 불러오지 못했습니다. 원문에서 확인해 주세요.</p>:<img src={url} alt={title} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>;
}
export function ComicBoard(){
 const [read,setRead]=useState<string[]>([]);
 const [posts,setPosts]=useState<Comic[]>([]),[hidden,setHidden]=useState<string[]>([]),[active,setActive]=useState<string|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState(''),[removed,setRemoved]=useState<string|null>(null);
 useEffect(()=>{
  const sync=()=>{try{const saved=JSON.parse(localStorage.getItem(readKey)||'[]');if(Array.isArray(saved))setRead(saved.filter(x=>typeof x==='string'))}catch{}try{const v=JSON.parse(localStorage.getItem(storageKey)||'[]');if(Array.isArray(v))setHidden(v.filter(x=>typeof x==='string'))}catch{}};sync();window.addEventListener('storage',sync);
  const controller=new AbortController();
  async function refresh(){try{const response=await fetch('/daily-k/data/feed.json',{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();const feed=await response.json() as {comicPosts?:Comic[]};if(!Array.isArray(feed.comicPosts??[]))throw Error();setPosts((feed.comicPosts??[]).filter((p:Comic)=>p&&typeof p.id==='string'&&typeof p.title==='string'&&safe(p.url)&&Array.isArray(p.images)&&p.images.every(safe)));setError('')}catch{if(!controller.signal.aborted)setError('만화 목록을 불러오지 못했습니다. 잠시 후 다시 시도합니다.')}finally{if(!controller.signal.aborted)setLoading(false)}}
  refresh();const timer=setInterval(refresh,60000);return()=>{controller.abort();clearInterval(timer);window.removeEventListener('storage',sync)};
 },[]);
 const visible=posts.filter(p=>!hidden.includes(identity(p)));
 const at=visible.findIndex(p=>identity(p)===active),story=visible[at];
 const body=useRef<HTMLDivElement|null>(null);
 useEffect(()=>{if(!active)return;setRead(current=>{const next=[...new Set([...current,active])];try{localStorage.setItem(readKey,JSON.stringify(next))}catch{}return next})},[active]);
 function move(delta:number){const next=at+delta;if(next<0)return;if(next>=visible.length){setActive(null);return}setActive(identity(visible[next]))}
 useEffect(()=>{body.current?.scrollTo({top:0,behavior:'instant'})},[active]);
 useEffect(()=>{
  if(!story)return;
  function navigate(event:KeyboardEvent){
   if(event.defaultPrevented||event.repeat||event.altKey||event.ctrlKey||event.metaKey)return;
   if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
   if(event.target instanceof HTMLElement&&event.target.closest('input,textarea,select,[contenteditable="true"],[role="textbox"],[role="slider"]'))return;
   if(event.shiftKey&&event.key!=='ArrowUp'&&event.key!=='ArrowDown')return;
   event.preventDefault();
   if(event.key==='ArrowLeft'||event.key==='ArrowRight'){move(event.key==='ArrowLeft'?-1:1);return}
   const panel=body.current;if(!panel)return;
   const behavior=matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
   if(event.shiftKey)panel.scrollTo({top:event.key==='ArrowUp'?0:panel.scrollHeight,behavior});
   else panel.scrollBy({top:event.key==='ArrowUp'?-500:500,behavior});
  }
  window.addEventListener('keydown',navigate,true);return()=>window.removeEventListener('keydown',navigate,true);
 },[active,posts,hidden]);
 function save(next:string[]){try{localStorage.setItem(storageKey,JSON.stringify(next));setHidden(next);setNotice('')}catch{setNotice('브라우저 저장 공간에 제외 기록을 저장하지 못했습니다.');}}
 function remove(p:Comic){const id=identity(p);save([...new Set([...hidden,id])]);setRemoved(id);if(active===id)setActive(null)}
 return <section className="comic-board" aria-label="만화 보관함"><div className="comic-intro"><p>만화 보관함 · {visible.length}편</p><small>최신순 · 자동 삭제 없이 보관 · X로 이 브라우저에서 제외</small></div>{removed&&<button className="comic-undo" onClick={()=>{save(hidden.filter(id=>id!==removed));setRemoved(null)}}>제외한 만화 되돌리기</button>}{hidden.length>0&&!removed&&<button className="comic-undo" onClick={()=>save([])}>제외한 글 모두 복원 ({hidden.length})</button>}{notice&&<p role="alert">{notice}</p>}{error&&<p role="alert">{error}</p>}{loading?<p className="news-message">만화를 불러오고 있습니다.</p>:!visible.length?<p className="news-message">아직 보관된 만화가 없습니다. 만화로 분류된 새 글이 올라오면 여기에 쌓입니다.</p>:<ol className="comic-grid">{visible.map((p,i)=><li className={`comic-frame${read.includes(identity(p))?' seen':' unread'}`} key={identity(p)}><button className="comic-open" onClick={()=>setActive(identity(p))}><span className="comic-cover"><Picture url={safe(p.coverImage)?p.coverImage:p.images[0]} title={p.title}/></span><span className="comic-caption"><small>{i+1} · {p.publishedAt?.slice(0,10)}</small><strong>{p.title}</strong><small>{p.images.length}장 · 이어 읽기</small></span></button><button className="comic-remove" aria-label={`${p.title} 만화에서 제외`} title="만화가 아니면 제외" onClick={()=>remove(p)}>×</button></li>)}</ol>}
 <Dialog open={!!story} onOpenChange={open=>!open&&setActive(null)}><DialogContent className="reader-dialog news-reader community-reader comic-reader" showCloseButton={false} aria-describedby={undefined} initialFocus={body}>{story&&<><nav className="reader-nav reader-top" aria-label="만화 이동"><button disabled={at<=0} aria-label="이전 만화" onClick={()=>move(-1)}>←</button><ReaderHeading title={story.title} index={at+1} total={visible.length} onClose={()=>setActive(null)}/><button aria-label="다음 만화" onClick={()=>move(1)}>→</button><div className="laugh-stats news-reader-meta"><a href={story.url} target="_blank" rel="noopener noreferrer">원문 보기</a><button onClick={()=>setActive(null)}>닫기</button></div></nav><div ref={body} tabIndex={-1} className="reader-body news-reader-body comic-pages" key={story.id}>{story.images.map((url,i)=><Picture key={`${i}-${url}`} url={url} title={`${story.title} · ${i+1}장`}/>)}</div></>}</DialogContent></Dialog></section>
}
