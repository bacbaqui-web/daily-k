import {liveTime,sourceScope,type Correction,type LiveSource} from '../lib/live';

export function LiveSourceReference({source:s}:{source:LiveSource}) {
 return <li><a href={s.url} target="_blank" rel="noopener noreferrer">{s.name} · {s.title} ↗</a><p>{sourceScope(s)}</p><p>원문 게시 {s.publishedAt?liveTime(s.publishedAt):'시각 미확인'} · 확인 {liveTime(s.verifiedAt)}</p><p>집계 기간 {s.periodStart&&s.periodEnd?`${liveTime(s.periodStart)} ~ ${liveTime(s.periodEnd)}`:'미확인'}</p>{s.regionEvidenceUrl&&<a href={s.regionEvidenceUrl} target="_blank" rel="noopener noreferrer">지역 기준 확인 자료 ↗</a>}<p>{s.limitations}</p>{s.quotes?.map((q,i)=><blockquote key={i}>{q}</blockquote>)}</li>;
}
export function RecordCorrections({items}:{items:Correction[]}) {
 return items.length>0?<section className="live-corrections" aria-label="명시적 정정 기록"><h3>정정 · 철회 기록</h3>{items.map(c=><article key={c.id}><strong>{c.action==='withdrawal'?'철회':'정정'} · {liveTime(c.recordedAt)}</strong><p>{c.text}</p><p>사유: {c.reason}</p><p>근거 확인: {liveTime(c.verifiedAt)}</p><ul>{c.sources.map(s=><LiveSourceReference key={s.url} source={s}/>)}</ul><small>확정본 원본은 그대로 보존됩니다.</small></article>)}</section>:null;
}
