import type {NewsBrief,NewsStory} from './news';

export type NewsViewStory = NewsStory & {aliases:string[];additionalRecords:NewsStory[]};
export type NewsView = Omit<NewsBrief,'stories'> & {stories:NewsViewStory[];watchItems:string[]};

/** Unite the display only; preserve every original JSON and each record's provenance. */
export function combineBriefings(input:NewsBrief[]):NewsView|null{
 if(!input.length)return null;
 const editions=[...input].sort((a,b)=>Number(!!a.archive)-Number(!!b.archive));
 const first=editions[0];
 if(editions.some(b=>b.date!==first.date||b.edition!==first.edition))throw Error('Cannot combine different briefing slots');
 const stories:NewsViewStory[]=[];
 for(const edition of editions)for(const story of edition.stories){
  // Only coalesce an imported record with an existing researched item in this slot.
  // Related but distinct items within a single original edition stay separate.
  const match=story.archive&&story.timeline?.issueId?stories.find(s=>!s.archive&&s.timeline?.issueId===story.timeline?.issueId):undefined;
  if(match){match.additionalRecords.push(story);match.aliases.push(story.id)}
  else stories.push({...story,aliases:[story.id],additionalRecords:[]});
 }
 const extra=first.archive?[]:stories.filter(s=>s.archive);
 const overview=[...(first.overview||[first.intro])];
 if(extra.length)overview.push(`함께 보관한 소식: ${extra.map(s=>s.summary[0]).join(' ')}`);
 return {...first,id:`${first.date}-${first.edition}`,stories,overview,
  overviewEmphasis:editions.flatMap(b=>b.overviewEmphasis||[]).filter(p=>overview.some(text=>text.includes(p))),
  watchItems:[...new Set(editions.flatMap(b=>b.archive?.watchItems||[]))]};
}

/** Older editions have no editorial emphasis metadata: highlight exact phrases only. */
export function overviewPhrases(brief:NewsView):string[]{
 const overview=brief.overview||[brief.intro];
 const editorial=brief.overviewEmphasis||[];
 const candidates=brief.stories.flatMap(s=>[...(s.emphasis||[]),s.title]);
 const selected:string[]=[];
 for(const paragraph of overview){
  const exact=editorial.filter(p=>paragraph.includes(p));
  if(exact.length){selected.push(...exact);continue}
  const sentence=paragraph.split(/(?<=[.!?。])\s/)[0];
  if(!paragraph.startsWith('당시 ')&&sentence.length<=65)selected.push(sentence.replace(/^주요 기록: /,''));
  selected.push(...candidates.filter(p=>p.length<=55&&paragraph.includes(p)).slice(0,4));
  selected.push(...(paragraph.match(/[+−-]?\d[\d,.]*(?:%포인트|%p|%|배|조달러|억달러|달러|억원|조원|원)/g)||[]).slice(0,4));
 }
 return [...new Set(selected)].filter(Boolean);
}
