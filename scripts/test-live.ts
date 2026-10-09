import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isLiveState,isSnapshot,nextWindow,sourceScope,liveLink,type LiveSource} from '../lib/live.ts';
for(const [now,end] of [
 ['2026-10-07T08:59:59+09:00','2026-10-07T09:00:00+09:00'],
 ['2026-10-07T09:00:00+09:00','2026-10-07T21:00:00+09:00'],
 ['2026-10-07T20:59:59+09:00','2026-10-07T21:00:00+09:00'],
 ['2026-10-07T21:00:00+09:00','2026-10-08T09:00:00+09:00'],
 ['2026-10-07T15:00:00Z','2026-10-08T09:00:00+09:00'],
])assert.equal(Date.parse(nextWindow(Date.parse(now)).scheduledFor),Date.parse(end));
const empty={schemaVersion:1,timezone:'Asia/Seoul',activatedAt:null,updatedAt:null,windows:[],snapshots:[],corrections:[]};
assert(isLiveState(empty));
assert(!isLiveState({...empty,schemaVersion:2}));
assert(!isLiveState({...empty,updatedAt:'2026-10-07T10:00:00'}));
assert(!isLiveState({...empty,snapshots:[{id:'a',path:'../../unsafe.json'}]}));
const window={id:'2026-10-07-am',opensAt:'2026-10-06T21:00:00+09:00',scheduledFor:'2026-10-07T09:00:00+09:00',items:[],checks:[],news:null};
assert(isLiveState({...empty,windows:[window]}));
assert(!isLiveState({...empty,windows:[{...window,items:[{}]}]}));
assert(!isLiveState({...empty,windows:[{...window,news:{}}]}));
assert(isSnapshot({...window,schemaVersion:1,timezone:'Asia/Seoul',status:'finalized',finalizedAt:'2026-10-07T09:10:00+09:00'}));
assert(!isSnapshot({...window,schemaVersion:1,status:'in_progress'}));
const source={name:'source',platform:'instagram',region:'unknown'} as LiveSource;
assert.match(sourceScope(source),/보조 자료.*한국 지역 순위 아님/);
assert.match(sourceScope({...source,platform:'x'}),/미확인/);
assert.match(sourceScope({...source,platform:'x',region:'KR'}),/미확인/);
assert.match(sourceScope({...source,platform:'x',region:'KR',regionEvidenceUrl:'https://example.org/kr'}),/한국 지역 트렌드 확인/);
assert.equal(liveLink('records','news','2026-10-07-am','stable-id'),'/daily-k/?tab=news&view=records&record=2026-10-07-am&item=stable-id');
const legacyNews=JSON.parse(readFileSync(new URL('../public/data/news/2026-10-07/am.json',import.meta.url),'utf8'));
assert(isLiveState({...empty,windows:[{...window,news:{brief:legacyNews,recordedAt:'2026-10-07T08:55:00+09:00',revision:1}}]}));
console.log('Live boundary, empty/failure guards, scope disclosure, stable links and news compatibility passed');
