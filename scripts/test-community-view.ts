import assert from 'node:assert/strict';
import {isTaggedCommunityTitle,prepareCommunityStories,communityStoryIndices,communityCategories,communityCategoryLabel} from '../lib/community-view.ts';
import {contentMarkers} from '../lib/content-markers.ts';
for(const title of ['ㅇㅎ) 공개 행사','[ㅎㅂ] 공개 행사','ㅇㅎㅂ 공연'])assert(isTaggedCommunityTitle(title));
for(const title of ['정보 글','ㅋㅋㅇㅎㅋㅋ','ㅇㅎㅎ'])assert(!isTaggedCommunityTitle(title));
const source={title:'ㅇㅎ) 공개 공연',publishedAt:'2026-10-04T08:00:00+09:00'};
const items=prepareCommunityStories([{id:'a',title:source.title,category:'ㅇㅎㅂ',kCount:0,commentCount:2,contentReview:'public-non-explicit',imageUrl:'https://example.com/image.jpg',sources:[source]},{id:'b',title:source.title,category:'ㅇㅎㅂ',kCount:0,commentCount:20,contentReview:'public-non-explicit',videoUrl:'https://example.com/video.mp4',sources:[source]}]);
assert.equal(items.length,2);assert.deepEqual(communityStoryIndices(items,'전체'),[0,1]);
assert.deepEqual(communityCategories,['유머','정보','화제','생활','문화','스포츠']);
assert.equal(communityCategoryLabel('ㅇㅎㅂ'),null);
for(const category of communityCategories)assert.equal(communityCategoryLabel(category),category);
assert.deepEqual(communityStoryIndices(items,'ㅇㅎㅂ'),[]);
assert.equal(prepareCommunityStories([{id:'x',title:source.title,category:'ㅇㅎㅂ',imageUrl:'https://example.com/image.jpg',sources:[source]}]).length,0);
assert.deepEqual(contentMarkers({portalLinks:['https://instagram.com/example/','https://x.com/example/status/1','https://x.com.evil.test/example']}),[{label:'인스타',url:'https://instagram.com/example/'},{label:'X',url:'https://x.com/example/status/1'}]);


const originOnly={...items[0],title:'공개 공연',category:'유머',kCount:0,sources:[{title:'공개 공연'},source]};
assert.equal(prepareCommunityStories([originOnly])[0]?.category,'ㅇㅎㅂ');
assert.equal(prepareCommunityStories([originOnly])[0]?.title,'공개 공연');

const ordinary={id:'normal',title:'정보',category:'정보',kCount:0,sources:[{title:'원문 정보'}]};
const humor={...ordinary,id:'humor',category:'유머',kCount:10};
const mixed=prepareCommunityStories([items[0],ordinary,humor,{...humor,id:'low',kCount:9}]);
assert.deepEqual(mixed.map(s=>s.id),['a','normal','humor']);
assert.deepEqual(communityStoryIndices(mixed,'전체'),[0,1,2]);
assert.deepEqual(communityStoryIndices(mixed,'정보'),[1]);
assert.deepEqual(communityStoryIndices(mixed,'유머'),[2]);
assert.equal(mixed[0].title,source.title);
assert.equal(mixed[1].title,'원문 정보');
console.log('Community filters, hidden retired badges, preserved archive records and social links passed');
