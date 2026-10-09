import {isBodyImages,isPublicImageUrl,type CommunityMedia} from './community-media.ts';
export type HumorItem={id:string;canonicalUrl:string;title:string;publishedAt:string;expiresAt:string;firstObservedAt:string;lastVerifiedAt:string;recordedAt:string;kCount:number;commentCount:number;commentsVerifiedAt:string;limitations:string;revision:number;publicationEvidence:{method:string;value:string;sourceUrl:string;semanticsVerified:true;observedAt:string;raw:string};sources:{name:string;title:string;url:string;verifiedAt:string;publishedAt:string|null}[];content:CommunityMedia&{originalText?:string;comments?:{id:string;text:string}[]}};
export type HumorState={schemaVersion:1;mode:'rolling-humor';timezone:'Asia/Seoul';retentionHours:24;minimumLiteralK:10;updatedAt:string|null;lastCheck:null|{status:'ok'|'empty'|'partial'|'blocked'|'challenge'|'failed'|'stopped';checkedAt:string;note:string;count:number|null};items:HumorItem[]};
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const text=(v:unknown):v is string=>typeof v==='string';
const time=(v:unknown):v is string=>text(v)&&/(Z|[+-]\d\d:\d\d)$/.test(v)&&Number.isFinite(Date.parse(v));
function identity(v:unknown):string|null {if(!text(v))return null;try{const u=new URL(v);if(u.protocol!=='https:'||u.host!=='aagag.com'||u.username||u.password||u.pathname.replace(/\/$/,'')!=='/issue')return null;const id=u.searchParams.get('idx');return id&&/^\d+(_\d+)?$/.test(id)?`aagag-${id.split('_')[0]}`:null}catch{return null}}
function item(v:unknown):v is HumorItem {
 if(!object(v)||!text(v.id)||identity(v.canonicalUrl)!==v.id||!text(v.title)||!text(v.limitations)||!time(v.publishedAt)||!time(v.expiresAt)||!time(v.firstObservedAt)||!time(v.lastVerifiedAt)||!time(v.recordedAt)||!time(v.commentsVerifiedAt))return false;
 if(Date.parse(v.expiresAt)-Date.parse(v.publishedAt)!==86400000||Date.parse(v.publishedAt)>Date.parse(v.firstObservedAt)||Date.parse(v.firstObservedAt)>Date.parse(v.lastVerifiedAt))return false;
 if(!Number.isSafeInteger(v.kCount)||Number(v.kCount)<10||!Number.isSafeInteger(v.commentCount)||Number(v.commentCount)<1)return false;
 const p=v.publicationEvidence;if(!object(p)||p.semanticsVerified!==true||!['aagag-otime','aagag-explicit-publication'].includes(String(p.method))||identity(p.sourceUrl)!==v.id||!time(p.value)||Date.parse(p.value)!==Date.parse(v.publishedAt)||!time(p.observedAt)||!text(p.raw))return false;
 const c=v.content;if(!object(c)||!Array.isArray(v.sources)||!v.sources.length||!v.sources.every(s=>object(s)&&text(s.name)&&text(s.title)&&isPublicImageUrl(s.url)&&time(s.verifiedAt)))return false;
 if(c.bodyImages!==undefined&&!isBodyImages(c.bodyImages))return false;
 if(['imageUrl','videoUrl','videoPosterUrl'].some(k=>c[k]!==undefined&&c[k]!==null&&!isPublicImageUrl(c[k])))return false;
 if(c.originalText!==undefined&&!text(c.originalText))return false;
 if(c.comments!==undefined&&(!Array.isArray(c.comments)||!c.comments.every(q=>object(q)&&text(q.id)&&text(q.text))))return false;
 return true;
}
export function isHumorState(v:unknown):v is HumorState {
 return object(v)&&v.schemaVersion===1&&v.mode==='rolling-humor'&&v.timezone==='Asia/Seoul'&&v.retentionHours===24&&v.minimumLiteralK===10&&(v.updatedAt===null||time(v.updatedAt))&&Array.isArray(v.items)&&v.items.every(item)&&new Set(v.items.map(i=>i.id)).size===v.items.length&&(v.lastCheck===null||object(v.lastCheck)&&['ok','empty','partial','blocked','challenge','failed','stopped'].includes(String(v.lastCheck.status))&&time(v.lastCheck.checkedAt)&&text(v.lastCheck.note));
}
export function activeHumor(items:HumorItem[],now:number):HumorItem[]{
 return items.filter(i=>Date.parse(i.publishedAt)<=now&&now<Date.parse(i.publishedAt)+86400000&&now<Date.parse(i.expiresAt)).sort((a,b)=>Date.parse(b.publishedAt)-Date.parse(a.publishedAt)||a.id.localeCompare(b.id));
}
export function humorHref(id:string){return `/daily-k/?item=${encodeURIComponent(id)}`}
