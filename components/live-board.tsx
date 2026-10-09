'use client';
import {LiveItemCard} from './live-item';
import {NewsPrepared} from './news-briefing';
import {liveTime,type Correction,type LiveWindow} from '../lib/live';

const checkLabels={ok:'확인 완료',empty:'조건에 맞는 자료 없음',blocked:'접근 차단',failed:'확인 실패',partial:'일부 확인'};
function Checks({window:w,channel}:{window:LiveWindow;channel:'humor'|'news'}) {
 const checks=w.checks.filter(c=>channel==='news'?c.channel==='news':c.channel!=='news');
 return <details className="live-checks"><summary>수집 상태 · 누락 범위 {checks.length}건</summary>{checks.length?<ul>{checks.map(c=><li key={c.id}><strong>{c.source} · {checkLabels[c.status]}</strong><p>{liveTime(c.checkedAt)} · {c.count===null?'개수 미확인':`${c.count}건`}</p><p>{c.note}</p></li>)}</ul>:<p>이 회차에 등록된 수집 확인 기록이 없습니다. 자료가 없다는 뜻으로 해석하지 않습니다.</p>}</details>;
}
export function WindowContent({window:w,channel,corrections,record}:{window:LiveWindow;channel:'humor'|'news';corrections:Correction[];record?:string}) {
 return <>{channel==='news'?(w.news?<><p className="live-disclaimer">{record?'이 회차에 보관한 뉴스입니다.':'진행 중 뉴스 준비본입니다. 확정 전까지 수정될 수 있습니다.'} · 준비본 반영 {liveTime(w.news.recordedAt)}</p><NewsPrepared brief={w.news.brief} record={record} corrections={corrections.filter(c=>w.news!.brief.stories.some(s=>s.id===c.itemId))}/></>:<div className="live-empty"><h2>등록된 뉴스 준비본이 없습니다</h2><p>미등록 상태를 ‘뉴스가 없음’으로 해석하지 않습니다.<br/>08:30 / 20:30에 준비하고 09:00 / 21:00에 확정합니다.</p></div>):w.items.length?<ol className="live-items">{w.items.map(item=><LiveItemCard windowId={w.id} key={`${w.id}:${item.id}`} item={item} channel={channel} record={record} corrections={corrections.filter(c=>c.itemId===item.id)}/>)}</ol>:<div className="live-empty"><h2>등록된 새 내용이 없습니다</h2><p>조건을 충족한 자료만 추가합니다. 수집 상태와 확인 한계는 아래에 남깁니다.</p></div>}<Checks window={w} channel={channel}/></>;
}
