import assert from 'node:assert/strict';
import {containsItem,currentEdition,latestNewsEdition,editionBoundary,editionDates,editionHref,editionId,editionSource,parseEdition,requestedEdition,validDate,type ArchiveEdition} from '../lib/edition-view.ts';
import type {LiveState,LiveWindow,SnapshotRef} from '../lib/live.ts';

// Pure read-model fixtures only: nothing is written to public or docs.
for(const [time,id] of [
 ['2026-10-09T08:59:59.999+09:00','2026-10-09-am'],
 ['2026-10-09T09:00:00+09:00','2026-10-09-pm'],
 ['2026-10-09T20:59:59.999+09:00','2026-10-09-pm'],
 ['2026-10-09T21:00:00+09:00','2026-10-10-am'],
 ['2026-10-10T00:00:00+09:00','2026-10-10-am'],
 ['2026-12-31T12:00:00Z','2027-01-01-am'],
])assert.equal(editionId(currentEdition(Date.parse(time))),id);
for(const date of ['2026-02-30','2026-13-01','2026-00-01','x','2026-1-01'])assert.equal(validDate(date),false);
assert.equal(validDate('2024-02-29'),true);
assert.equal(parseEdition('2026-02-30-pm'),null);
assert.equal(parseEdition('../2026-10-09-pm'),null);
const before=Date.parse('2026-10-09T20:59:59+09:00'),after=Date.parse('2026-10-09T21:00:00+09:00');
const current={date:'2026-10-09',edition:'pm'} as const;
const archives:ArchiveEdition[]=[{id:'2026-10-09-am',date:'2026-10-09',edition:'am',path:'2026-10-09/am.json'}];
const window:LiveWindow={id:'2026-10-09-pm',opensAt:'2026-10-09T09:00:00+09:00',scheduledFor:editionBoundary(current),items:[],checks:[],news:null};
const state:LiveState={schemaVersion:1,timezone:'Asia/Seoul',activatedAt:null,updatedAt:null,windows:[window],snapshots:[],corrections:[]};
assert.deepEqual(editionSource(current,before,state,archives),{kind:'window',window,pending:false});
assert.deepEqual(editionSource(current,after,state,archives),{kind:'window',window,pending:true});
assert.equal(editionSource(currentEdition(after),after,state,archives).kind,'current');
assert.equal(editionSource({date:'2026-10-10',edition:'pm'},after,state,archives).kind,'future');
assert.equal(editionSource({date:'2026-10-01',edition:'am'},after,state,archives).kind,'missing');
assert.equal(editionSource({date:'2026-10-09',edition:'am'},before,state,archives).kind,'archive');
// Following the default screen crosses the boundary; explicit dates stay pinned.
for(const now of [before,after])assert.deepEqual(requestedEdition(new URLSearchParams('date=2026-10-09&edition=pm'),now,state,archives,'humor'),current);
assert.equal(editionId(requestedEdition(new URLSearchParams(),before,state,archives,'humor')),'2026-10-09-pm');
assert.equal(editionId(requestedEdition(new URLSearchParams(),after,state,archives,'humor')),'2026-10-10-am');
assert.equal(editionId(requestedEdition(new URLSearchParams('view=archive'),after,state,archives,'humor')),'2026-10-09-am');
assert.equal(editionId(requestedEdition(new URLSearchParams('view=records&record=2026-10-09-pm'),after,state,archives,'humor')),'2026-10-09-pm');
const ref={id:window.id,path:'snapshots/2026-10-09-pm.json',sha256:'a'.repeat(64),opensAt:window.opensAt,scheduledFor:window.scheduledFor,finalizedAt:'2026-10-09T21:10:00+09:00',empty:true,itemCount:0,hasNews:false} as SnapshotRef;
const finalized={...state,windows:[],snapshots:[ref]};
assert.equal(editionSource(current,after,finalized,archives).kind,'snapshot');
assert.equal(editionSource(currentEdition(after),after,finalized,archives).kind,'current');
assert.equal(editionId(requestedEdition(new URLSearchParams('view=records'),after,finalized,archives,'news')),'2026-10-09-am');
const duplicate=[...archives,{id:window.id,...current,path:'2026-10-09/pm.json'}];
assert.equal(editionSource(current,after,finalized,duplicate).kind,'snapshot');
assert.equal(editionSource(current,after,finalized,duplicate,true).kind,'archive');
assert.equal(editionHref(current,'humor','stable-id'),'/daily-k/?date=2026-10-09&edition=pm&item=stable-id');
assert.equal(editionHref(current,'news','news-id'),'/daily-k/?tab=news&date=2026-10-09&edition=pm&item=news-id');
assert.equal(editionHref(null,'humor'),'/daily-k/');
assert.equal(editionHref(null,'news'),'/daily-k/?tab=news');
assert.deepEqual(editionDates(after,finalized,archives),['2026-10-09','2026-10-10']);
assert.equal(containsItem(window,'humor','missing'),false);
assert.equal(containsItem(window,'news','missing'),false);
const original=JSON.stringify(state);editionSource(current,after,state,archives);requestedEdition(new URLSearchParams(),after,state,archives,'humor');assert.equal(JSON.stringify(state),original);
// News follows actual publications, never the next preparation window.
for(const now of [before,after,Date.parse('2026-10-10T09:00:00+09:00')]){
 assert.equal(editionId(requestedEdition(new URLSearchParams(),now,state,archives,'news')),'2026-10-09-am');
 assert.equal(editionSource(current,now,state,archives,false,'news').kind,now<after?'future':'missing');
}
assert.equal(editionId(latestNewsEdition(after,duplicate)),'2026-10-09-pm');
for(const [time,id] of [['2026-10-11T08:59:59+09:00','2026-10-10-pm'],['2026-10-11T09:00:00+09:00','2026-10-11-am'],['2026-10-11T21:00:00+09:00','2026-10-11-pm'],['2026-10-11T00:00:00Z','2026-10-11-am']])assert.equal(editionId(latestNewsEdition(Date.parse(time),[])),id);
assert.equal(editionId(requestedEdition(new URLSearchParams('record=2026-10-09-pm'),after,finalized,archives,'news')),window.id);
console.log('Edition boundaries, KST rollover, pinned/default selection, legacy URLs, source precedence, empty/pending/finalized states and immutable read mapping passed');
