
'use client';
import {useEffect,useRef,useState} from 'react';
import {Share2,Check} from 'lucide-react';
import {newsShareUrl} from '../lib/news';
import type {NewsView,NewsViewStory} from '../lib/news-view';

export function NewsReaderActions({brief,story}:{brief:NewsView;story:NewsViewStory}){
 const [state,setState]=useState<'idle'|'copied'|'manual'>('idle');
 const field=useRef<HTMLInputElement>(null),button=useRef<HTMLButtonElement>(null);
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const url=newsShareUrl(brief.date,brief.edition,story.id);
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current)},[]);
 useEffect(()=>{if(state==='manual'){field.current?.focus();field.current?.select()}},[state]);
 async function copy(){
  if(timer.current)clearTimeout(timer.current);
  try{await navigator.clipboard.writeText(url);setState('copied');timer.current=setTimeout(()=>setState('idle'),4000)}
  catch{setState('manual')}
 }
 return <div className="news-share-control">
  <button ref={button} type="button" className="news-share-button" title="이 뉴스 공유 링크 복사" aria-label={`${story.title} 공유 링크 복사`} onClick={copy}>{state==='copied'?<Check size={13} strokeWidth={1.5} aria-hidden="true"/>:<Share2 size={13} strokeWidth={1.5} aria-hidden="true"/>}</button>
  <span className="news-share-feedback" role="status">{state==='copied'?'링크를 복사했습니다.':''}</span>
  {state==='manual'&&<div className="news-share-manual"><label>자동 복사가 되지 않았습니다. 링크를 직접 복사하세요.<input ref={field} aria-label="뉴스 공유 링크" readOnly value={url} onFocus={e=>e.currentTarget.select()}/></label><button type="button" onClick={()=>{setState('idle');button.current?.focus()}}>닫기</button></div>}
 </div>;
}
