'use client';
import {useEffect,useRef} from 'react';
import {DialogTitle} from './ui/dialog';

export function ReaderHeading({title,index,total,onClose}:{title:string;index:number;total:number;onClose:()=>void}){
 const start=useRef<{x:number;y:number;id:number}|null>(null);
 const panel=useRef<HTMLElement|null>(null);
 const closing=useRef(false);
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 function reset(){start.current=null;if(panel.current){panel.current.style.removeProperty('--reader-drag-y');delete panel.current.dataset.dragging}}
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);closing.current=false;reset()},[title]);
 return <div className="reader-heading drag-heading"
  onPointerDown={e=>{if(closing.current||e.pointerType!=='touch'||!e.isPrimary||!matchMedia('(max-width: 767px)').matches)return;panel.current=e.currentTarget.closest<HTMLElement>('.reader-dialog');start.current={x:e.clientX,y:e.clientY,id:e.pointerId};if(panel.current)panel.current.dataset.dragging='true';e.currentTarget.setPointerCapture(e.pointerId)}}
  onPointerMove={e=>{const p=start.current;if(p?.id!==e.pointerId||closing.current)return;panel.current?.style.setProperty('--reader-drag-y',`${Math.max(0,e.clientY-p.y)}px`)}}
  onPointerUp={e=>{const p=start.current;if(p?.id!==e.pointerId)return;const close=e.clientY-p.y>=72&&e.clientY-p.y>Math.abs(e.clientX-p.x)*1.2;if(close&&panel.current){closing.current=true;start.current=null;delete panel.current.dataset.dragging;panel.current.style.setProperty('--reader-drag-y',`${window.innerHeight}px`);timer.current=setTimeout(onClose,180)}else reset()}}
  onPointerCancel={()=>{if(!closing.current)reset()}} onLostPointerCapture={()=>{if(!closing.current)reset()}}>
  <DialogTitle className="reader-title">{title} <span className="reader-counter">{index} / {total}</span></DialogTitle>
 </div>;
}
