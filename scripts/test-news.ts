import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isNewsIndex,isNewsBrief,safeNewsUrl,newsLink,emphasisParts} from '../lib/news.ts';
import {combineBriefings,overviewPhrases} from '../lib/news-view.ts';
import {buildNewsQuestion} from '../lib/news-question.ts';
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
const imported=JSON.parse(readFileSync(new URL('../public/data/news/archive/2026-10-02/am.json',import.meta.url),'utf8'));
const original=JSON.stringify([brief,imported]);
const combined=combineBriefings([imported,brief])!;
assert.equal(combined.stories.length,12,'Three matching issues must share one card');
assert.equal(combined.stories.reduce((n,s)=>n+1+s.additionalRecords.length,0),15,'Every original record remains available');
assert.equal(combined.stories.flatMap(s=>s.aliases).length,15,'Old deep links must still find their news');
assert.equal(combined.stories.find(s=>s.aliases.includes('archive-01'))?.id,brief.stories[0].id);
assert.deepEqual(combined,combineBriefings([brief,imported]),'Source loading order must not change the result');
assert.equal(JSON.stringify([brief,imported]),original,'Combining the display must not alter source records');
assert.equal(combineBriefings([]),null);
assert.throws(()=>combineBriefings([brief,{...imported,date:'2026-09-15'}]));
const sameEdition=structuredClone(imported);sameEdition.stories[1].timeline.issueId=sameEdition.stories[0].timeline.issueId;
assert.equal(combineBriefings([sameEdition])!.stories.length,8,'Separate stories within one edition stay separate');
assert.ok(combined.overview!.some(p=>p.includes('항모 1척')),'Additional topics must appear in the overview');
assert.ok(overviewPhrases(combined).length>0);
for(const paragraph of combined.overview!)assert.equal(emphasisParts(paragraph,overviewPhrases(combined)).map(p=>p.text).join(''),paragraph);
const styled=structuredClone(brief);styled.overviewEmphasis=['생활비 부담','7.9배'];assert.ok(isNewsBrief(styled));
styled.overviewEmphasis=['원문에 없는 가짜 내용'];assert.equal(isNewsBrief(styled),false);
const question=buildNewsQuestion(combined,combined.stories[0]);
assert.ok(question.includes(combined.stories[0].title));
for(const paragraph of combined.stories[0].summary)assert.ok(question.includes(paragraph));
for(const source of combined.stories[0].sources)assert.ok(question.includes(source.url));
assert.ok(question.includes('정확한 작성·기사·사건 시각은 미상'));
assert.ok(question.includes(combined.stories[0].additionalRecords[0].summary[0]));
assert.ok(!question.includes(combined.stories[1].title),'Do not copy unrelated news in the same edition');
assert.ok(question.includes('2026-10-02 오전 · 한국시간'));
assert.ok(question.includes('story=korea-cpi-2026-09'));
assert.ok(question.endsWith('내 질문: '));
const previousRecord=combineBriefings([imported])!.stories.find(s=>s.archive?.previousCoverage)!;
const olderQuestion=buildNewsQuestion(combined,previousRecord);
assert.ok(olderQuestion.includes('기사 원문으로 전체 내용을 다시 검증하지 않았습니다'));
assert.ok(olderQuestion.includes(previousRecord.archive!.previousCoverage!.title));
assert.ok(olderQuestion.includes('이전 기록 본문은 이 복사 내용에 포함되지 않았습니다'));
console.log('News data/link checks passed');
