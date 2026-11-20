
'use client';
import {useEffect,useRef,useState} from 'react';
import {Share2,Check} from 'lucide-react';
import {newsShareUrl} from '../lib/news';
import type {NewsView,NewsViewStory} from '../lib/news-view';

export function NewsReaderActions({brief,story}:{brief:NewsView;story:NewsViewStory}){
 return <BriefCopyButton text={newsShareUrl(brief.date,brief.edition,story.id)} title={story.title}/>;
}

export function BriefCopyButton({text,title,question=false}:{text:string;title:string;question?:boolean}){
 const [state,setState]=useState<'idle'|'copied'|'manual'>('idle');
 const field=useRef<HTMLTextAreaElement>(null),button=useRef<HTMLButtonElement>(null);
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const url=text;
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current)},[]);
 useEffect(()=>{if(state==='manual'){field.current?.focus();field.current?.select()}},[state]);
 async function copy(){
  if(timer.current)clearTimeout(timer.current);
  try{await navigator.clipboard.writeText(url);setState('copied');timer.current=setTimeout(()=>setState('idle'),4000)}
  catch{setState('manual')}
 }
 return <div className="news-share-control">
  <button ref={button} type="button" className="news-share-button" title={question?"ChatGPT에 질문할 내용 복사":"이 뉴스 공유 링크 복사"} aria-label={`${title} ${question?"질문 내용 복사":"공유 링크 복사"}`} onClick={copy}>{state==='copied'?<Check size={13} strokeWidth={1.5} aria-hidden="true"/>:<Share2 size={13} strokeWidth={1.5} aria-hidden="true"/>}</button>
  <span className="news-share-feedback" role="status">{state==='copied'?(question?'복사했습니다. ChatGPT에 붙여넣으세요.':'링크를 복사했습니다.'):''}</span>
  {state==='manual'&&<div className="news-share-manual"><label>자동 복사가 되지 않았습니다. 아래 내용을 직접 복사하세요.<textarea ref={field} rows={question?8:2} aria-label={question?"ChatGPT 질문 자료":"뉴스 공유 링크"} readOnly value={url} onFocus={e=>e.currentTarget.select()}/></label><button type="button" onClick={()=>{setState('idle');button.current?.focus()}}>닫기</button></div>}
 </div>;
}
