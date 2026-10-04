export function isTaggedCommunityTitle(title:string):boolean {
 return /(?<![ㄱ-ㅎ])(?:ㅇㅎㅂ|ㅇㅎ|ㅎㅂ)(?![ㄱ-ㅎ])/.test(title.normalize('NFC').replace(/\u200b/g,''));
}
type CommunityRecord={id:string;title:string;category:string;kCount?:number;commentCount?:number;contentReview?:string;imageUrl?:string|null;videoUrl?:string|null;sources:{title:string;publishedAt?:string|null}[]};
export function prepareCommunityStories<T extends CommunityRecord>(stories:T[]):T[]{
 return stories.flatMap(s=>{
  const title=s.sources[0]?.title||s.title;
  if([s.title,...s.sources.map(source=>source.title)].some(isTaggedCommunityTitle)||s.category==='ㅇㅎㅂ'){
   if(s.contentReview!=='public-non-explicit'||!s.imageUrl&&!s.videoUrl)return [];
   return [{...s,title,category:'ㅇㅎㅂ'} as T];
  }
  return s.category==='유머'&&(s.kCount??0)<10?[]:[{...s,title}];
 });
}
export function communityStoryIndices(stories:CommunityRecord[],category:string):number[]{
 const indices=stories.flatMap((s,i)=>category==='전체'||s.category===category?[i]:[]);
 if(category==='ㅇㅎㅂ')indices.sort((a,b)=>{
  const count=(stories[b].commentCount??-1)-(stories[a].commentCount??-1);
  if(count)return count;
  const time=(Date.parse(stories[b].sources[0]?.publishedAt||'')||0)-(Date.parse(stories[a].sources[0]?.publishedAt||'')||0);
  return time||stories[a].id.localeCompare(stories[b].id);
 });
 return indices;
}
