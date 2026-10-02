import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isNewsIndex,isNewsBrief,safeNewsUrl,newsLink,emphasisParts} from '../lib/news.ts';
assert.equal(safeNewsUrl('javascript:alert(1)'),false);
assert.equal(safeNewsUrl('https://user:password@example.com'),false);
assert.equal(safeNewsUrl('https://example.com/article'),true);
const entry={id:'2026-10-02-am',date:'2026-10-02',edition:'am',generatedAt:'2026-10-02T10:00:00+09:00',cutoffAt:'2026-10-02T09:00:00+09:00',count:7,path:'2026-10-02/am.json',headline:'검증'};
const index={schemaVersion:1,timezone:'Asia/Seoul',updatedAt:null,editions:[entry]};
assert.ok(isNewsIndex(index));
assert.equal(isNewsIndex({...index,editions:[{...entry,path:'../../feed.json'}]}),false);
assert.equal(isNewsIndex({...index,editions:[{...entry,edition:'other'}]}),false);
assert.equal(isNewsBrief({schemaVersion:1,stories:[]}),false);
assert.equal(newsLink('2026-10-02','pm'),'/daily-k/?tab=news&date=2026-10-02&edition=pm');
assert.deepEqual(emphasisParts('2.9% 상승, 2.9% 유지',['','2.9','2.9%']),[
 {text:'2.9%',bold:true},{text:' 상승, ',bold:false},{text:'2.9%',bold:true},{text:' 유지',bold:false}
]);
assert.deepEqual(emphasisParts('<b>확정?</b>',['<b>']),[{text:'<b>',bold:true},{text:'확정?</b>',bold:false}]);
const brief=JSON.parse(readFileSync(new URL('../public/data/news/2026-10-02/am.json',import.meta.url),'utf8'));
assert.ok(isNewsBrief(brief));
for(const story of brief.stories){
 for(const paragraph of story.summary)assert.equal(emphasisParts(paragraph,story.emphasis).map(p=>p.text).join(''),paragraph);
}
const unsafe=structuredClone(brief);unsafe.stories[0].relatedArticles![0].imageUrl='javascript:alert(1)';
assert.equal(isNewsBrief(unsafe),false);
const legacy=structuredClone(brief);delete legacy.overview;
for(const story of legacy.stories){delete story.relatedArticles;delete story.emphasis}
assert.ok(isNewsBrief(legacy),'Older editions must remain readable');
const archivedIndex=JSON.parse(readFileSync(new URL('../public/data/news/index.json',import.meta.url),'utf8'));
assert.ok(isNewsIndex(archivedIndex));
for(const item of archivedIndex.editions){
 const stored=JSON.parse(readFileSync(new URL(`../public/data/news/${item.path}`,import.meta.url),'utf8'));
 assert.ok(isNewsBrief(stored),item.id);
 if(!item.archive)continue;
 const unlabelled=structuredClone(stored);delete unlabelled.archive;
 assert.equal(isNewsBrief(unlabelled),false,'An imported record cannot masquerade as a verified edition');
 const missingProvenance=structuredClone(stored);delete missingProvenance.stories[0].archive;
 assert.equal(isNewsBrief(missingProvenance),false);
}
const archivedEntry=archivedIndex.editions.find((e:{archive?:boolean})=>e.archive);
assert.equal(isNewsIndex({...index,editions:[{...archivedEntry,path:'archive/../../feed.json'}]}),false);
assert.equal(newsLink('2026-09-15','am',true,'archive-01'),'/daily-k/?tab=news&date=2026-09-15&edition=am&archive=1&story=archive-01');
console.log('News data/link checks passed');
