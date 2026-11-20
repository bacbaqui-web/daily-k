'use client';

export function ReaderEdges({onMove,previousDisabled,nextDisabled=false}:{onMove:(delta:number)=>void;previousDisabled:boolean;nextDisabled?:boolean}){
 return <>
  <button type="button" className="reader-edge reader-edge-left" aria-label="이전 글" title="이전 글" disabled={previousDisabled} onClick={()=>onMove(-1)}>‹</button>
  <button type="button" className="reader-edge reader-edge-right" aria-label="다음 글" title="다음 글" disabled={nextDisabled} onClick={()=>onMove(1)}>›</button>
 </>;
}
