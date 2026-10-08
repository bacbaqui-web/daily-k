export const communityCategories=['유머','정보','화제','생활','문화','스포츠'] as const;
export type CommunityCategory=typeof communityCategories[number];
export function communityCategoryLabel(category:string):CommunityCategory|null {
 return communityCategories.find(label=>label===category)??null;
}
export function isTaggedCommunityTitle(title:string):boolean {
 return /(?<![ㄱ-ㅎ])(?:ㅇㅎㅂ|ㅇㅎ|ㅎㅂ)(?![ㄱ-ㅎ])/.test(title.normalize('NFC').replace(/\u200b/g,''));
}
type CommunityRecord={id:string;title:string;category:string;kCount?:number;commentCount?:number;contentReview?:string;imageUrl?:string|null;videoUrl?:string|null;sources:{title:string;publishedAt?:string|null}[]};
export function prepareCommunityStories<T extends CommunityRecord>(stories:T[]):T[]{
 // Preserve previously published records and their existing media/review gates.
 // New tagged posts are rejected by the publisher; the retired badge is hidden.
 return stories.flatMap(s=>{
  const title=s.sources[0]?.title||s.title;
  if([s.title,...s.sources.map(source=>source.title)].some(isTaggedCommunityTitle)||s.category==='ㅇㅎㅂ'){
   if(s.contentReview!=='public-non-explicit'||!s.imageUrl&&!s.videoUrl)return [];
   return [{...s,title,category:'ㅇㅎㅂ'} as T];
  }
  // Keep historical 10-count humor visible; new drafts require at least 11.
  return s.category==='유머'&&(s.kCount??0)<10?[]:[{...s,title}];
 });
}
export function communityStoryIndices(stories:CommunityRecord[],category:string):number[]{
 if(category!=='전체'&&!communityCategoryLabel(category))return [];
 return stories.flatMap((s,i)=>category==='전체'||s.category===category?[i]:[]);
}
