'use client';
import {useEffect,useState} from 'react';
import {Dialog,DialogContent,DialogTitle} from './ui/dialog';
type Comic={id:string;title:string;url:string;publishedAt:string;images:string[];coverImage?:string;content?:{type:string;src?:string;text?:string}[]};
const storageKey='daily-k-comics-hidden';
const identity=(p:Comic)=>p.id.replace(/^(aagag-\d+)-\d+$/,'$1');
const safe=(url:unknown):url is string=>typeof url==='string'&&/^https?:\/\//.test(url);
function Picture({url,title}:{url:string;title:string}){
 const [failed,setFailed]=useState(false);
 return failed?<p className="comic-image-error">이미지를 불러오지 못했습니다. 원문에서 확인해 주세요.</p>:<img src={url} alt={title} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>;
}
export function ComicBoard(){
 const [posts,setPosts]=useState<Comic[]>([]),[hidden,setHidden]=useState<string[]>([]),[active,setActive]=useState<string|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState(''),[removed,setRemoved]=useState<string|null>(null);
 useEffect(()=>{
  const sync=()=>{try{const v=JSON.parse(localStorage.getItem(storageKey)||'[]');if(Array.isArray(v))setHidden(v.filter(x=>typeof x==='string'))}catch{}};sync();window.addEventListener('storage',sync);
  const controller=new AbortController();
  async function refresh(){try{const response=await fetch('/daily-k/data/feed.json',{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();const feed=await response.json() as {comicPosts?:Comic[]};if(!Array.isArray(feed.comicPosts??[]))throw Error();setPosts((feed.comicPosts??[]).filter((p:Comic)=>p&&typeof p.id==='string'&&typeof p.title==='string'&&safe(p.url)&&Array.isArray(p.images)&&p.images.every(safe)));setError('')}catch{if(!controller.signal.aborted)setError('만화 목록을 불러오지 못했습니다. 잠시 후 다시 시도합니다.')}finally{if(!controller.signal.aborted)setLoading(false)}}
  refresh();const timer=setInterval(refresh,60000);return()=>{controller.abort();clearInterval(timer);window.removeEventListener('storage',sync)};
 },[]);
 const visible=posts.filter(p=>!hidden.includes(identity(p)));
 const at=visible.findIndex(p=>identity(p)===active),story=visible[at];
 function save(next:string[]){try{localStorage.setItem(storageKey,JSON.stringify(next));setHidden(next);setNotice('')}catch{setNotice('브라우저 저장 공간에 제외 기록을 저장하지 못했습니다.');}}
 function remove(p:Comic){const id=identity(p);save([...new Set([...hidden,id])]);setRemoved(id);if(active===id)setActive(null)}
 return <section className="comic-board" aria-label="만화 보관함"><div className="comic-intro"><p>만화 보관함 · {visible.length}편</p><small>최신순 · 자동 삭제 없이 보관 · X로 이 브라우저에서 제외</small></div>{removed&&<button className="comic-undo" onClick={()=>{save(hidden.filter(id=>id!==removed));setRemoved(null)}}>제외한 만화 되돌리기</button>}{hidden.length>0&&!removed&&<button className="comic-undo" onClick={()=>save([])}>제외한 글 모두 복원 ({hidden.length})</button>}{notice&&<p role="alert">{notice}</p>}{error&&<p role="alert">{error}</p>}{loading?<p className="news-message">만화를 불러오고 있습니다.</p>:!visible.length?<p className="news-message">아직 보관된 만화가 없습니다. 만화로 분류된 새 글이 올라오면 여기에 쌓입니다.</p>:<ol className="comic-grid">{visible.map((p,i)=><li className="comic-frame" key={identity(p)}><button className="comic-open" onClick={()=>setActive(identity(p))}><span className="comic-cover"><Picture url={safe(p.coverImage)?p.coverImage:p.images[0]} title={p.title}/></span><span className="comic-caption"><small>{i+1} · {p.publishedAt?.slice(0,10)}</small><strong>{p.title}</strong><small>{p.images.length}장 · 이어 읽기</small></span></button><button className="comic-remove" aria-label={`${p.title} 만화에서 제외`} title="만화가 아니면 제외" onClick={()=>remove(p)}>×</button></li>)}</ol>}
 <Dialog open={!!story} onOpenChange={open=>!open&&setActive(null)}><DialogContent className="reader-dialog comic-reader" aria-describedby={undefined}>{story&&<><div className="comic-reader-heading"><DialogTitle>{story.title}</DialogTitle><nav aria-label="만화 이동"><button disabled={at<=0} onClick={()=>setActive(identity(visible[at-1]))}>← 이전</button><span>{at+1} / {visible.length}</span><button disabled={at>=visible.length-1} onClick={()=>setActive(identity(visible[at+1]))}>다음 →</button><a href={story.url} target="_blank" rel="noopener noreferrer">원문</a></nav></div><div className="comic-pages" key={story.id}>{story.images.map((url,i)=><Picture key={`${i}-${url}`} url={url} title={`${story.title} · ${i+1}장`}/>)}</div></>}</DialogContent></Dialog></section>
}
