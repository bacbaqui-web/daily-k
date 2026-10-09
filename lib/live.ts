import {isPublicImageUrl,isBodyImages,type CommunityMedia} from './community-media.ts';
import {isNewsBrief,type NewsBrief} from './news.ts';

export type LiveSource={name:string;url:string;title:string;publishedAt:string|null;verifiedAt:string;platform:'aagag'|'community'|'dcinside'|'instagram'|'x'|'other';region:'KR'|'unknown';regionEvidenceUrl?:string|null;periodStart?:string|null;periodEnd?:string|null;limitations:string;quotes?:string[]};
export type Observation={sourceUrl:string;metric:string;value:number|null;unit:string;observedAt:string;scope:string};
export type LiveItem={id:string;kind:'topic'|'community';topicKey:string;title:string;summary:string;firstObservedAt:string;lastVerifiedAt:string;firstRecordedAt:string;recordedAt:string;revision:number;canonicalUrl:string|null;sources:LiveSource[];observations:Observation[];limitations:string;selectionReason:string;content?:CommunityMedia&{title:string;originalText?:string;comments?:{id:string;text:string;truncated?:boolean;likes?:number}[];kCount:number;commentCount:number;sources:{name:string;title:string;url:string}[]}};
export type CollectionCheck={id:string;channel:'community'|'topics'|'news';source:string;status:'ok'|'empty'|'blocked'|'failed'|'partial';checkedAt:string;recordedAt:string;count:number|null;note:string};
export type LiveWindow={id:string;opensAt:string;scheduledFor:string;items:LiveItem[];checks:CollectionCheck[];news:{brief:NewsBrief;recordedAt:string;revision:number}|null};
export type Snapshot=LiveWindow&{schemaVersion:1;timezone:'Asia/Seoul';status:'finalized';finalizedAt:string;activatedAt:string;empty:boolean};
export type SnapshotRef={id:string;opensAt:string;scheduledFor:string;finalizedAt:string;empty:boolean;path:string;sha256:string;itemCount:number;hasNews:boolean};
export type Correction={id:string;snapshotId:string;itemId:string;action:'correction'|'withdrawal';reason:string;text:string;verifiedAt:string;recordedAt:string;sources:LiveSource[]};
export type LiveState={schemaVersion:1;timezone:'Asia/Seoul';activatedAt:string|null;updatedAt:string|null;windows:LiveWindow[];snapshots:SnapshotRef[];corrections:Correction[]};
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const time=(v:unknown):v is string=>typeof v==='string'&&/(Z|[+-]\d\d:\d\d)$/.test(v)&&Number.isFinite(Date.parse(v));
const str=(v:unknown):v is string=>typeof v==='string';
const source=(v:unknown):v is LiveSource=>object(v)&&str(v.name)&&str(v.title)&&isPublicImageUrl(v.url)&&time(v.verifiedAt)&&str(v.platform)&&str(v.limitations)&&(v.region==='KR'||v.region==='unknown')&&(!v.regionEvidenceUrl||isPublicImageUrl(v.regionEvidenceUrl))&&(!v.quotes||Array.isArray(v.quotes)&&v.quotes.every(str));
function item(v:unknown):v is LiveItem {
 if(!object(v)||!str(v.id)||!['topic','community'].includes(String(v.kind))||!str(v.title)||!str(v.summary)||!str(v.limitations)||!str(v.selectionReason)||!time(v.firstObservedAt)||!time(v.lastVerifiedAt)||!time(v.recordedAt)||!Array.isArray(v.sources)||!v.sources.length||!v.sources.every(source)||!Array.isArray(v.observations))return false;
 if(!v.observations.every(o=>object(o)&&isPublicImageUrl(o.sourceUrl)&&str(o.metric)&&str(o.unit)&&str(o.scope)&&time(o.observedAt)&&(o.value===null||typeof o.value==='number'&&Number.isFinite(o.value))))return false;
 if(v.kind==='community') {
  const c=v.content;if(!object(c)||!str(c.title)||!Array.isArray(c.sources)||!c.sources.every(s=>object(s)&&isPublicImageUrl(s.url)))return false;
  if(c.bodyImages!==undefined&&!isBodyImages(c.bodyImages))return false;
  if(c.comments!==undefined&&(!Array.isArray(c.comments)||!c.comments.every(q=>object(q)&&str(q.id)&&str(q.text))))return false;
 }
 return true;
}
function windowValue(v:unknown):v is LiveWindow {
 return object(v)&&str(v.id)&&time(v.opensAt)&&time(v.scheduledFor)&&Array.isArray(v.items)&&v.items.every(item)&&Array.isArray(v.checks)&&v.checks.every(c=>object(c)&&str(c.id)&&str(c.source)&&str(c.note)&&time(c.checkedAt)&&['ok','empty','blocked','failed','partial'].includes(String(c.status)))&&(v.news===null||object(v.news)&&time(v.news.recordedAt)&&isNewsBrief(v.news.brief));
}
export function isLiveState(v:unknown):v is LiveState {
 return object(v)&&v.schemaVersion===1&&v.timezone==='Asia/Seoul'&&(v.updatedAt===null||time(v.updatedAt))&&Array.isArray(v.windows)&&v.windows.every(windowValue)&&Array.isArray(v.snapshots)&&v.snapshots.every(s=>object(s)&&str(s.id)&&str(s.path)&&/^snapshots\/\d{4}-\d{2}-\d{2}-(am|pm)\.json$/.test(s.path)&&time(s.scheduledFor)&&time(s.finalizedAt)&&str(s.sha256))&&Array.isArray(v.corrections)&&v.corrections.every(c=>object(c)&&str(c.id)&&str(c.snapshotId)&&str(c.itemId)&&str(c.text)&&str(c.reason)&&time(c.recordedAt)&&Array.isArray(c.sources)&&c.sources.every(source));
}
export function isSnapshot(v:unknown):v is Snapshot {
 return object(v)&&v.schemaVersion===1&&v.timezone==='Asia/Seoul'&&v.status==='finalized'&&time(v.finalizedAt)&&windowValue(v);
}
export function liveTime(value:string|null|undefined):string {
 return value?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(value)):'아직 없음';
}
export function nextWindow(now:number):{opensAt:string;scheduledFor:string} {
 const local=new Date(now+9*3600000),start=Date.UTC(local.getUTCFullYear(),local.getUTCMonth(),local.getUTCDate());
 const end=now<start?start:now<start+12*3600000?start+12*3600000:start+24*3600000;
 return {opensAt:new Date(end-12*3600000).toISOString(),scheduledFor:new Date(end).toISOString()};
}
export function sourceScope(s:LiveSource):string {
 if(s.platform==='instagram')return '인스타 공개 인기 · 보조 자료 (한국 지역 순위 아님)';
 if(s.platform==='x')return s.region==='KR'&&s.regionEvidenceUrl?'X 한국 지역 트렌드 확인':'X 공개 자료 · 한국 지역 트렌드 미확인';
 return s.name;
}
export function liveLink(view:'live'|'records',channel:'humor'|'news',record?:string,itemId?:string):string {
 const q=new URLSearchParams();if(channel==='news')q.set('tab','news');q.set('view',view);if(record)q.set('record',record);if(itemId)q.set('item',itemId);return `/daily-k/?${q}`;
}

export async function snapshotHash(raw:string):Promise<string>{const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw));return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('')}
