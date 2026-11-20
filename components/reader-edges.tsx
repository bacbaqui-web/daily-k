'use client';
import {useEffect,useRef} from 'react';

export function ReaderEdges({onMove,previousDisabled,nextDisabled=false}:{onMove:(delta:number)=>void;previousDisabled:boolean;nextDisabled?:boolean}){
 const left=useRef<HTMLButtonElement>(null),right=useRef<HTMLButtonElement>(null);
 useEffect(()=>{
  const buttons=[left.current,right.current].filter((button):button is HTMLButtonElement=>!!button);
  const scroll=(event:WheelEvent)=>{
   if(event.ctrlKey)return;
   const button=event.currentTarget as HTMLButtonElement;
   const body=button.closest('.reader-dialog')?.querySelector<HTMLElement>('.reader-body');
   if(!body)return;
   event.preventDefault();
   const unit=event.deltaMode===1?(parseFloat(getComputedStyle(body).lineHeight)||24):event.deltaMode===2?body.clientHeight:1;
   body.scrollTop+=event.deltaY*unit;
  };
  buttons.forEach(button=>button.addEventListener('wheel',scroll,{passive:false}));
  return()=>buttons.forEach(button=>button.removeEventListener('wheel',scroll));
 },[]);
 return <>
  <button ref={left} type="button" className="reader-edge reader-edge-left" aria-label="이전 글" title="이전 글" disabled={previousDisabled} onClick={()=>onMove(-1)}>‹</button>
  <button ref={right} type="button" className="reader-edge reader-edge-right" aria-label="다음 글" title="다음 글" disabled={nextDisabled} onClick={()=>onMove(1)}>›</button>
 </>;
}
