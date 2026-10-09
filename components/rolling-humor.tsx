'use client';
import {useEffect,useRef,useState} from 'react';
import {CommunityBodyImages} from './community-media';
import {communityThumbnail} from '../lib/community-media';
import {activeHumor,humorHref,isHumorState,type HumorItem,type HumorState} from '../lib/rolling-humor';
import {liveTime} from '../lib/live';

function HumorCard({item}:{item:HumorItem}){
 const [failed,setFailed]=useState(false),[videoFailed,setVideoFailed]=useState(false);
 const heading=useRef<HTMLHeadingElement>(null),thumbnail=communityThumbnail(item.content);
 useEffect(()=>{if(new URLSearchParams(location.search).get('item')===item.id){heading.current?.scrollIntoView({block:'start'});heading.current?.focus({preventScroll:true})}},[item.id]);
 return <li className="live-item rolling-card"><article aria-labelledby={`humor-${item.id}`}>
  <div className="live-card-topline"><span className="live-eyebrow">애객 유머 · 댓글 ㅋ {item.kCount}</span><span>댓글 {item.commentCount}개 확인</span></div>
  <div className="live-card-heading"><h2 ref={heading} id={`humor-${item.id}`} tabIndex={-1}>{item.title}</h2>{thumbnail&&!failed&&<img className="live-thumbnail" src={thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>}</div>
  <p className="rolling-time">애객 게시 <time dateTime={item.publishedAt}>{liveTime(item.publishedAt)}</time><br/>목록에서 내려가는 시각 <time dateTime={item.expiresAt}>{liveTime(item.expiresAt)}</time></p>
  <div className="live-card-actions"><a className="live-original" href={item.canonicalUrl} target="_blank" rel="noopener noreferrer">원문 보기 ↗</a><a className="live-permalink" href={humorHref(item.id)}>이 항목 링크</a></div>
  <details className="live-media-detail"><summary>본문·이미지·영상 보기</summary><div className="community-media">{item.content.videoUrl&&(videoFailed?<p>영상을 불러오지 못했습니다. 원문에서 확인해 주세요.</p>:<video controls playsInline preload="metadata" src={item.content.videoUrl} poster={item.content.videoPosterUrl||undefined} onError={()=>setVideoFailed(true)}/>)}<CommunityBodyImages story={{...item.content,title:item.title,sources:item.sources}}/>{item.content.originalText&&<blockquote>{item.content.originalText}</blockquote>}{item.content.comments?.map(c=><blockquote key={c.id}>{c.text}</blockquote>)}</div></details>
  <details className="rolling-evidence"><summary>확인 시각·출처·한계</summary><p>첫 발견 {liveTime(item.firstObservedAt)}<br/>최종 확인 {liveTime(item.lastVerifiedAt)}<br/>댓글 확인 {liveTime(item.commentsVerifiedAt)}<br/>목록 반영 {liveTime(item.recordedAt)}</p><p>문자 그대로의 ㅋ만 셉니다. 애객 고유 댓글의 확인 시점 누적값이며 외부 커뮤니티 댓글·최근 24시간 댓글 수를 뜻하지 않습니다.</p><p>{item.limitations}</p><ul>{item.sources.map(s=><li key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.name} · {s.title} ↗</a></li>)}</ul></details>
 </article></li>;
}
const labels={ok:'확인 완료',empty:'조건에 맞는 자료 없음',partial:'일부 확인',blocked:'접근 차단',challenge:'CAPTCHA 확인 필요',failed:'확인 실패',stopped:'수집 중단'};
export function RollingHumor({search}:{search:string}){
 const [now,setNow]=useState(0),[data,setData]=useState<HumorState|null>(null),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();let running=false;
  const sync=()=>setNow(Date.now());
  async function load(){if(running)return;running=true;try{const response=await fetch('/daily-k/data/humor/current.json',{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();const value:unknown=await response.json();if(!isHumorState(value))throw Error();if(!controller.signal.aborted){setData(value);setError('')}}catch{if(!controller.signal.aborted)setError('최신 유머 목록을 확인하지 못했습니다. 이전에 읽은 자료도 게시 후 24시간이 지나면 숨깁니다.')}finally{running=false;sync()}}
  const resume=()=>{sync();if(!document.hidden)void load()};sync();void load();
  const clock=setInterval(sync,1000),poll=setInterval(load,60000);
  window.addEventListener('focus',resume);window.addEventListener('pageshow',resume);document.addEventListener('visibilitychange',resume);
  return()=>{controller.abort();clearInterval(clock);clearInterval(poll);window.removeEventListener('focus',resume);window.removeEventListener('pageshow',resume);document.removeEventListener('visibilitychange',resume)};
 },[retry]);
 const items=activeHumor(data?.items||[],now),requested=new URLSearchParams(search).get('item');
 if(!now)return <p role="status" className="news-message">최근 24시간 유머를 불러오고 있습니다.</p>;
 return <section className="rolling-humor" aria-label="최근 24시간 유머">
  <div className="rolling-heading"><h1>최근 24시간 ㅋㅋㅋ</h1><p>애객 댓글 ㅋ 10개 이상 · 게시 후 24시간까지만</p></div>
  <p className="rolling-meta">목록 반영 {liveTime(data?.updatedAt)} · 한국시간{data?` · ${items.length}건`:''}</p>
  {error&&<div role="alert" className="live-alert"><p>{error}</p><button onClick={()=>setRetry(v=>v+1)}>다시 시도</button></div>}
  {!data?(!error?<p role="status" className="news-message">검증된 목록을 불러오고 있습니다.</p>:<div className="live-empty"><h2>목록을 확인하지 못했습니다</h2><p>등록된 자료가 없는지 판단할 수 없습니다. 다시 시도해 주세요.</p></div>):<>
   {requested&&!items.some(i=>i.id===requested)&&<p className="live-disclaimer">공유한 항목은 24시간이 지났거나 현재 검증된 목록에 없습니다.</p>}
   {items.length?<ol className="live-items">{items.map(item=><HumorCard key={`${item.id}:${search}`} item={item}/>)}</ol>:<div className="live-empty"><h2>현재 표시할 유머가 없습니다</h2><p>게시 시각과 댓글 기준이 확인된 자료만 표시합니다. 게시 시각이 불명확한 자료는 보류합니다.</p></div>}
  </>}
  <details className="rolling-evidence"><summary>최근 수집 확인 · {data?.lastCheck?labels[data.lastCheck.status]:'미확인'}</summary>{data?.lastCheck?<p>{liveTime(data.lastCheck.checkedAt)}<br/>{data.lastCheck.note}</p>:<p>새 경로의 수집 확인 기록이 아직 없습니다. 수집기가 가동 중이거나 조건에 맞는 글이 0건이라는 뜻은 아닙니다.</p>}<p>애객에서 확인한 게시 시각부터 만 24시간이 되면 활성 목록에서 내려갑니다. 첫 발견·재확인·사이트 반영 시각으로 기간을 늘리지 않습니다. 과거 원본 기록은 보존합니다.</p></details>
 </section>;
}
