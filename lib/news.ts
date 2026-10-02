export type Edition = 'am' | 'pm';
export type NewsSource = {name:string;title:string;url:string;language:string;publishedAt:string|null;verifiedAt:string;kind:string;imageUrl?:string|null};
export type NewsStory = {
 id:string;topicKey:string;category:string;title:string;summary:string[];status:string;
 publishedAt:string;eventAt:string|null;eventTimeNote:string;whatChanged:string;whyItMatters:string;uncertainty:string;
 keyFacts:Record<string,string>;sources:NewsSource[];score:number;
 followUp?:{editionId:string;storyId:string;delta:string};fallbackNote?:string;emphasis?:string[];relatedArticles?:NewsSource[];
};
export type NewsEvent = {title:string;at:string|null;date:string;timeNote?:string;detail:string;source:NewsSource};
export type NewsBrief = {schemaVersion:1;id:string;date:string;edition:Edition;timezone:'Asia/Seoul';cutoffAt:string;generatedAt:string;updatedAt?:string;intro:string;overview?:string[];stories:NewsStory[];events:NewsEvent[];keywords:string[]};
export type NewsEntry = {id:string;date:string;edition:Edition;generatedAt:string;cutoffAt:string;count:number;path:string;headline:string};
export type NewsIndex = {schemaVersion:1;timezone:'Asia/Seoul';updatedAt:string|null;editions:NewsEntry[]};
export const editionLabel = (edition:Edition)=>edition==='am'?'오전 브리핑':'저녁 브리핑';
export function safeNewsUrl(url:unknown):url is string{
 if(typeof url!=='string')return false;
 try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password}catch{return false}
}
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object';
const time=(v:unknown):v is string=>typeof v==='string'&&Number.isFinite(Date.parse(v));
const strings=(v:unknown):v is string[]=>Array.isArray(v)&&v.every(x=>typeof x==='string');
function source(v:unknown):boolean{return object(v)&&typeof v.name==='string'&&typeof v.title==='string'&&safeNewsUrl(v.url)&&(v.publishedAt===null||time(v.publishedAt))&&(v.imageUrl==null||safeNewsUrl(v.imageUrl))}
export function isNewsIndex(v:unknown):v is NewsIndex{
 return object(v)&&v.schemaVersion===1&&v.timezone==='Asia/Seoul'&&Array.isArray(v.editions)&&v.editions.every(e=>object(e)&&typeof e.id==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(String(e.date))&&['am','pm'].includes(String(e.edition))&&e.id===`${e.date}-${e.edition}`&&e.path===`${e.date}/${e.edition}.json`&&time(e.generatedAt)&&time(e.cutoffAt)&&typeof e.count==='number'&&typeof e.headline==='string');
}
export function isNewsBrief(v:unknown):v is NewsBrief{
 return object(v)&&v.schemaVersion===1&&v.timezone==='Asia/Seoul'&&typeof v.date==='string'&&['am','pm'].includes(String(v.edition))&&v.id===`${v.date}-${v.edition}`&&time(v.cutoffAt)&&time(v.generatedAt)&&(v.updatedAt===undefined||time(v.updatedAt))&&typeof v.intro==='string'&&(v.overview===undefined||(strings(v.overview)&&v.overview.length>0))&&strings(v.keywords)&&Array.isArray(v.events)&&v.events.every(e=>object(e)&&typeof e.title==='string'&&typeof e.detail==='string'&&typeof e.date==='string'&&(e.at===null||time(e.at))&&source(e.source))&&Array.isArray(v.stories)&&v.stories.length>=5&&v.stories.length<=10&&v.stories.every(s=>object(s)&&typeof s.id==='string'&&typeof s.title==='string'&&typeof s.category==='string'&&typeof s.status==='string'&&typeof s.eventTimeNote==='string'&&strings(s.summary)&&(s.emphasis===undefined||strings(s.emphasis))&&(s.relatedArticles===undefined||(Array.isArray(s.relatedArticles)&&s.relatedArticles.length<=3&&s.relatedArticles.every(source)))&&Array.isArray(s.sources)&&s.sources.length>0&&s.sources.every(source)&&(!s.followUp||(object(s.followUp)&&typeof s.followUp.delta==='string')));
}
// Keep summaries as plain text for deduplication; only explicitly selected phrases get emphasis.
export function emphasisParts(text:string,phrases:string[]=[]):{text:string;bold:boolean}[]{
 const words=[...new Set(phrases.filter(Boolean))].sort((a,b)=>b.length-a.length);
 const parts:{text:string;bold:boolean}[]=[];let cursor=0;
 while(cursor<text.length){
  let start=-1,word='';
  for(const candidate of words){const at=text.indexOf(candidate,cursor);if(at>=0&&(start<0||at<start)){start=at;word=candidate}}
  if(start<0){parts.push({text:text.slice(cursor),bold:false});break}
  if(start>cursor)parts.push({text:text.slice(cursor,start),bold:false});
  parts.push({text:word,bold:true});cursor=start+word.length;
 }
 return parts;
}
export function newsLink(date:string,edition:Edition){return `/daily-k/?tab=news&date=${date}&edition=${edition}`}
export function koreaTime(value:string){return new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value))}
