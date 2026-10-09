'use client';
import {useEffect,useRef,useState} from 'react';
import {buildNewsQuestion} from '../lib/news-question';
import {newsShareUrl} from '../lib/news';
import type {NewsView,NewsViewStory} from '../lib/news-view';

export function NewsReaderActions({brief,story,sharePath,recordStatus}:{brief:NewsView;story:NewsViewStory;sharePath?:string;recordStatus?:'preparing'|'finalized'}){
 const [state,setState]=useState<'idle'|'copying'|'copied'|'manual'>('idle');
 const [action,setAction]=useState<'share'|'question'>('question');
 const [notice,setNotice]=useState(false);
 const button=useRef<HTMLButtonElement>(null),manual=useRef<HTMLTextAreaElement>(null);
 const alive=useRef(true);
 const shareUrl=sharePath?`https://bacbaqui-web.github.io${sharePath}`:newsShareUrl(brief.date,brief.edition,story.id);
 const prompt=(sharePath?`기록 상태: ${(recordStatus==='preparing'||(!recordStatus&&sharePath.includes('view=live')))?'진행 중 준비본 (확정 전)':'불변 확정 기록'}\n`:'')+buildNewsQuestion(brief,story).replace(newsShareUrl(brief.date,brief.edition,story.id),shareUrl);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 useEffect(()=>{if(state!=='copied'){setNotice(false);return}setNotice(true);const timer=setTimeout(()=>setNotice(false),6500);return()=>clearTimeout(timer)},[state]);
 useEffect(()=>{if(state==='manual'){manual.current?.focus();manual.current?.select()}},[state]);
 async function copy(kind:'share'|'question',trigger:HTMLButtonElement){
  button.current=trigger;setAction(kind);setState('copying');
  try{await navigator.clipboard.writeText(kind==='share'?shareUrl:prompt);if(alive.current)setState('copied')}
  catch{if(alive.current)setState('manual')}
 }
 function closeManual(){setState('idle');button.current?.focus()}
 return <div className="news-question-control">
  <span className="news-copy-buttons">
   <button type="button" className="news-question-button" title="이 뉴스의 링크 복사" onClick={e=>copy('share',e.currentTarget)} disabled={state==='copying'}>{state==='copying'&&action==='share'?'복사 중…':'공유하기'}</button>
   <button type="button" className="news-question-button" title="ChatGPT에 붙여넣을 뉴스 내용과 출처 복사" onClick={e=>copy('question',e.currentTarget)} disabled={state==='copying'}>{state==='copying'&&action==='question'?'복사 중…':'질문하기'}</button>
  </span>
  {state==='copied'&&action==='question'&&<a className="news-chatgpt-link" href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">ChatGPT 열기 ↗</a>}
  {notice&&<p className="news-copy-notice" role="status" aria-live="polite">{action==='share'?'링크주소가 복사됐습니다.':<>뉴스가 복사됐습니다.<br/>ChatGPT에 붙여넣고 질문을 입력하세요.</>}</p>}
  {state==='manual'&&<div className="news-copy-manual" role="group" aria-label={action==='share'?'뉴스 링크 직접 복사':'질문할 뉴스 직접 복사'} onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();closeManual()}}}>
   <p>자동 복사가 되지 않았습니다. 아래 {action==='share'?'주소를':'내용을'} 직접 복사해 주세요.</p>
   <textarea ref={manual} aria-label={action==='share'?'공유할 뉴스 링크':'ChatGPT에 붙여넣을 뉴스'} value={action==='share'?shareUrl:prompt} readOnly onFocus={e=>e.currentTarget.select()}/>
   <div>{action==='question'&&<a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">ChatGPT 열기 ↗</a>}<button type="button" onClick={closeManual}>닫기</button></div>
  </div>}
 </div>;
}
