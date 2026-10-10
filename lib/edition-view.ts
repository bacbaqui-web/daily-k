import {nextWindow,type LiveState,type LiveWindow,type SnapshotRef} from './live.ts';
import type {Edition} from './news.ts';

export type Channel='humor'|'news';
export type EditionSelection={date:string;edition:Edition};
export type ArchiveEdition=EditionSelection&{id:string;path:string};
export const editionId=(value:EditionSelection)=>`${value.date}-${value.edition}`;
export function validDate(value:string|null):value is string {
 if(!value||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
 const date=new Date(`${value}T00:00:00Z`);return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;
}
export function parseEdition(value:string|null|undefined):EditionSelection|null {
 const match=value?.match(/^(\d{4}-\d{2}-\d{2})-(am|pm)$/);
 return match&&validDate(match[1])?{date:match[1],edition:match[2] as Edition}:null;
}
export function currentEdition(now:number):EditionSelection {
 const end=new Date(Date.parse(nextWindow(now).scheduledFor)+9*3600000);
 return {date:end.toISOString().slice(0,10),edition:end.getUTCHours()===9?'am':'pm'};
}
export function latestNewsEdition(now:number,archives:ArchiveEdition[]):EditionSelection {
 const published=[...archives].sort((a,b)=>editionId(b).localeCompare(editionId(a)))[0];
 if(published)return {date:published.date,edition:published.edition};
 const local=new Date(now+9*3600000),hour=local.getUTCHours();
 if(hour<9)local.setUTCDate(local.getUTCDate()-1);
 return {date:local.toISOString().slice(0,10),edition:hour>=9&&hour<21?'am':'pm'};
}
export function editionBoundary(value:EditionSelection):string{return `${value.date}T${value.edition==='am'?'09':'21'}:00:00+09:00`}
export function containsItem(window:LiveWindow,channel:Channel,id:string):boolean {
 return channel==='news'?!!window.news?.brief.stories.some(s=>s.id===id):window.items.some(i=>i.id===id);
}
export function requestedEdition(query:URLSearchParams,now:number,state:LiveState|null,archives:ArchiveEdition[],channel:Channel):EditionSelection {
 const record=parseEdition(query.get('record'));if(record)return record;
 const date=query.get('date');
 if(validDate(date))return {date,edition:query.get('edition')==='pm'?'pm':'am'};
 const item=query.get('item');
 if(item&&channel!=='news'){const w=state?.windows.find(w=>containsItem(w,channel,item));if(w)return parseEdition(w.id)!;}
 const records=state?.snapshots.filter(s=>channel!=='news'||s.hasNews);
 if(query.get('view')==='records'&&records?.length)return parseEdition(records[0].id)!;
 if(query.get('view')==='archive'&&archives.length)return {date:archives[0].date,edition:archives[0].edition};
 return channel==='news'?latestNewsEdition(now,archives):currentEdition(now);
}
export type EditionSource={kind:'snapshot';ref:SnapshotRef}|{kind:'window';window:LiveWindow;pending:boolean}|{kind:'archive'}|{kind:'current'|'future'|'missing'};
export function editionSource(selection:EditionSelection,now:number,state:LiveState|null,archives:ArchiveEdition[],preferArchive=false,channel:Channel='humor'):EditionSource {
 const id=editionId(selection),archive=archives.some(e=>e.date===selection.date&&e.edition===selection.edition);
 if(preferArchive&&archive)return {kind:'archive'};
 const ref=state?.snapshots.find(s=>s.id===id);if(ref&&(channel!=='news'||ref.hasNews))return {kind:'snapshot',ref};
 if(channel==='news')return archive?{kind:'archive'}:{kind:Date.parse(editionBoundary(selection))>now?'future':'missing'};
 const window=state?.windows.find(w=>w.id===id);if(window)return {kind:'window',window,pending:Date.parse(window.scheduledFor)<=now};
 if(archive)return {kind:'archive'};
 if(id===editionId(currentEdition(now)))return {kind:'current'};
 return {kind:Date.parse(editionBoundary(selection))>now?'future':'missing'};
}
export function editionHref(selection:EditionSelection|null,channel:Channel,item?:string):string {
 const q=new URLSearchParams();if(channel==='news')q.set('tab','news');
 if(selection){q.set('date',selection.date);q.set('edition',selection.edition)}if(item)q.set('item',item);
 return `/daily-k/${q.size?`?${q}`:''}`;
}
export function editionDates(now:number,state:LiveState|null,archives:ArchiveEdition[]):string[] {
 return [...new Set([currentEdition(now).date,...archives.map(e=>e.date),...(state?.windows||[]).map(w=>w.id.slice(0,10)),...(state?.snapshots||[]).map(w=>w.id.slice(0,10))])].sort();
}
