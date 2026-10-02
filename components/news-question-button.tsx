'use client';
import {useEffect,useRef,useState} from 'react';
import {buildNewsQuestion} from '../lib/news-question';
import type {NewsView,NewsViewStory} from '../lib/news-view';

export function NewsQuestionButton({brief,story}:{brief:NewsView;story:NewsViewStory}){
 const [state,setState]=useState<'idle'|'copying'|'copied'|'manual'>('idle');
 const [notice,setNotice]=useState(false);
 const button=useRef<HTMLButtonElement>(null),manual=useRef<HTMLTextAreaElement>(null);
 const alive=useRef(true);
 const prompt=buildNewsQuestion(brief,story);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 useEffect(()=>{if(state!=='copied'){setNotice(false);return}setNotice(true);const timer=setTimeout(()=>setNotice(false),6500);return()=>clearTimeout(timer)},[state]);
 useEffect(()=>{if(state==='manual'){manual.current?.focus();manual.current?.select()}},[state]);
 async function copy(){
  setState('copying');
  try{await navigator.clipboard.writeText(prompt);if(alive.current)setState('copied')}
  catch{if(alive.current)setState('manual')}
 }
 function closeManual(){setState('idle');button.current?.focus()}
 return <div className="news-question-control">
  <button ref={button} type="button" className="news-question-button" title="ChatGPT에 붙여넣을 뉴스 내용과 출처 복사" onClick={copy} disabled={state==='copying'}>{state==='copying'?'복사 중…':'질문하기'}</button>
  {state==='copied'&&<a className="news-chatgpt-link" href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">ChatGPT 열기 ↗</a>}
  {notice&&<p className="news-copy-notice" role="status" aria-live="polite">뉴스가 복사됐습니다.<br/>ChatGPT에 붙여넣고 질문을 입력하세요.</p>}
  {state==='manual'&&<div className="news-copy-manual" role="group" aria-label="질문할 뉴스 직접 복사" onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();closeManual()}}}>
   <p>자동 복사가 되지 않았습니다. 아래 내용을 직접 복사해 주세요.</p>
   <textarea ref={manual} aria-label="ChatGPT에 붙여넣을 뉴스" value={prompt} readOnly onFocus={e=>e.currentTarget.select()}/>
   <div><a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">ChatGPT 열기 ↗</a><button type="button" onClick={closeManual}>닫기</button></div>
  </div>}
 </div>;
}
