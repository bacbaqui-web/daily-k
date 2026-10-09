'use client';
import {useEffect,useRef,useState} from 'react';
import {CommunityBodyImages} from './community-media';
import {RecordCorrections,LiveSourceReference} from './record-corrections';
import {communityThumbnail,isPublicImageUrl} from '../lib/community-media';
import {liveTime,type Correction,type LiveItem} from '../lib/live';
import {editionHref,parseEdition} from '../lib/edition-view';

function Summary({text,id}:{text:string;id:string}) {
 const paragraph=useRef<HTMLParagraphElement>(null);
 const [expanded,setExpanded]=useState(false),[overflows,setOverflows]=useState(false);
 useEffect(()=>{
  const element=paragraph.current;if(!element)return;
  const measure=()=>setOverflows(element.scrollHeight>parseFloat(getComputedStyle(element).lineHeight)*2+2);
  const observer=new ResizeObserver(measure);observer.observe(element);measure();
  return()=>observer.disconnect();
 },[text]);
 if(!text)return null;
 return <div className="live-summary-wrap"><p ref={paragraph} id={id} className={`live-summary${expanded?'':' is-clamped'}`}>{text}</p>{overflows&&<button className="live-text-toggle" aria-expanded={expanded} aria-controls={id} onClick={()=>setExpanded(v=>!v)}>{expanded?'설명 접기':'설명 더보기'}</button>}</div>;
}

export function LiveItemCard({item,corrections,channel,record,windowId}:{item:LiveItem;corrections:Correction[];channel:'humor'|'news';record?:string;windowId:string}) {
 const media=item.content,thumbnail=media?communityThumbnail(media):null;
 const [imageFailed,setImageFailed]=useState(false),[videoFailed,setVideoFailed]=useState(false),[expanded,setExpanded]=useState(false);
 const article=useRef<HTMLElement>(null),title=useRef<HTMLHeadingElement>(null);
 const prefix=`${windowId}-${item.id}`,panelId=`evidence-${prefix}`;
 const original=item.canonicalUrl||item.sources[0]?.url;
 const instagram=item.sources.some(s=>s.platform==='instagram');
 const unknownX=item.sources.some(s=>s.platform==='x'&&(s.region!=='KR'||!s.regionEvidenceUrl));
 useEffect(()=>{
  function reveal(){
   if(new URLSearchParams(location.search).get('item')!==item.id||article.current?.closest('details:not([open])'))return;
   article.current?.scrollIntoView({block:'start'});title.current?.focus({preventScroll:true});
  }
  reveal();window.addEventListener('popstate',reveal);return()=>window.removeEventListener('popstate',reveal);
 },[item.id]);
 return <li className="live-item"><article ref={article} id={`item-${prefix}`} aria-labelledby={`title-${prefix}`}>
  <div className="live-card-topline"><span className="live-eyebrow">{item.kind==='community'?`애객 유머 · 댓글 ㅋ ${media?.kCount??'미확인'}`:instagram?'참고 콘텐츠':'화제 주제'}</span><time dateTime={item.lastVerifiedAt} title={liveTime(item.lastVerifiedAt)}>{new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(item.lastVerifiedAt))} 확인</time></div>
  <div className="live-card-heading"><h2 ref={title} tabIndex={-1} id={`title-${prefix}`}>{item.title}</h2>{thumbnail&&isPublicImageUrl(thumbnail)&&!imageFailed&&<img className="live-thumbnail" src={thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer" onError={()=>setImageFailed(true)}/>}</div>
  {corrections.length>0&&<span className="live-correction-badge">정정·철회 기록 {corrections.length}건</span>}
  <Summary text={item.summary} id={`summary-${prefix}`}/>
  {instagram&&<p className="live-scope-note">Instagram 보조 자료 · 한국 지역 순위 아님 · 집계 기간·실시간 상승 미확인</p>}
  {unknownX&&<p className="live-scope-note">X 공개 자료 · 한국 지역 트렌드 미확인</p>}
  <div className="live-source-chips" aria-label="확인한 출처">{item.sources.map((source,index)=><a key={`${source.url}:${index}`} href={source.url} target="_blank" rel="noopener noreferrer" title={source.title}>{source.name}<span aria-hidden="true"> ↗</span><span className="sr-only"> — {source.title} (새 창)</span></a>)}</div>
  <div className="live-card-actions">{original&&<a className="live-original" href={original} target="_blank" rel="noopener noreferrer">원문 보기 <span aria-hidden="true">↗</span><span className="sr-only"> (새 창)</span></a>}<a className="live-permalink" href={editionHref(parseEdition(record||windowId),channel,item.id)}>이 항목 링크</a></div>
  {media&&<details className="live-media-detail"><summary>본문·이미지·댓글 보기</summary><div className="community-media">{media.videoUrl&&isPublicImageUrl(media.videoUrl)&&(videoFailed?<p>영상을 불러오지 못했습니다. 원문 링크에서 확인해 주세요.</p>:<video controls playsInline preload="metadata" src={media.videoUrl} poster={media.videoPosterUrl||undefined} onError={()=>setVideoFailed(true)}/>)}<CommunityBodyImages story={media}/>{media.originalText&&<blockquote>{media.originalText}</blockquote>}{!!media.comments?.length&&<><h3>짧은 댓글 인용</h3>{media.comments.map(c=><blockquote key={c.id}>{c.text}{c.truncated?'…':''}</blockquote>)}<p>확인한 댓글 {media.commentCount}개 중 일부 인용입니다. 전체 내용은 원문에서 확인하세요.</p></>}</div></details>}
  <RecordCorrections items={corrections}/>
  <div className="live-evidence">
   <span className="live-evidence-label">확인한 관심 근거</span>
   {!expanded&&<p className="live-evidence-preview is-clamped">{item.selectionReason}</p>}
   <button className="live-evidence-toggle" aria-expanded={expanded} aria-controls={panelId} onClick={()=>setExpanded(v=>!v)}><span>{expanded?'관심 근거·관측 기록 접기':'관심 근거·관측 기록 펼치기'}<small>관측 {item.observations.length}건</small></span><span aria-hidden="true">{expanded?'−':'＋'}</span></button>
   <div id={panelId} className="live-detail" hidden={!expanded}>
    <p className="live-evidence-reason">{item.selectionReason}</p><h3>확인 한계</h3><p>{item.limitations}</p>
    <h3>확인 시각</h3><p className="live-item-times">첫 발견 {liveTime(item.firstObservedAt)}<br/>최종 확인 {liveTime(item.lastVerifiedAt)}<br/>데이터 반영 {liveTime(item.recordedAt)} · 수정 {item.revision}차</p>
    <h3>출처별 확인 범위</h3><ul className="live-sources">{item.sources.map((s,index)=><LiveSourceReference key={`${s.url}:${index}`} source={s}/>)}</ul>
    {!!item.observations.length&&<details className="live-observation-history"><summary>관측값 전체 이력 {item.observations.length}건</summary><p className="live-disclaimer">각 지표는 표시된 시각의 관찰입니다. 서로 합산하지 않으며, 9시 당시 수치나 플랫폼 전체 순위를 뜻하지 않습니다.</p><ul className="live-observations">{item.observations.map((o,i)=><li key={i}><strong>{o.metric} {o.value===null?'미확인':`${o.value.toLocaleString('ko-KR')} ${o.unit}`}</strong><span>{liveTime(o.observedAt)} · {o.scope}</span><a href={o.sourceUrl} target="_blank" rel="noopener noreferrer">지표 출처 ↗</a></li>)}</ul></details>}
   </div>
  </div>
 </article></li>;
}
