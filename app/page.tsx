'use client';
import {useEffect,useState} from 'react';
import {Tabs,TabsList,TabsTrigger,TabsContent} from '@/components/ui/tabs';
import {Button} from '@/components/ui/button';
import {NewsBriefing} from '../components/news-briefing';
import {CommunityBriefing} from '../components/community-briefing';
import {LiveBoard} from '../components/live-board';
function ThemeToggle(){
 const [dark,setDark]=useState(false);
 useEffect(()=>{
  const media=matchMedia('(prefers-color-scheme: dark)');
  const sync=()=>{let saved:string|null=null;try{saved=localStorage.getItem('daily-k-theme')}catch{}const value=saved==='dark'||(saved!=='light'&&media.matches);document.documentElement.dataset.theme=value?'dark':'light';setDark(value)};
  sync();media.addEventListener('change',sync);window.addEventListener('storage',sync);
  return()=>{media.removeEventListener('change',sync);window.removeEventListener('storage',sync)};
 },[]);
 function toggle(){const value=!dark;setDark(value);document.documentElement.dataset.theme=value?'dark':'light';try{localStorage.setItem('daily-k-theme',value?'dark':'light')}catch{}}
 return <Button variant="ghost" size="icon" className="theme-toggle" onClick={toggle} aria-label="다크 모드" aria-pressed={dark} title={dark?'밝은 모드로 전환':'다크 모드로 전환'}><svg className="moon-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M20.5 14A9 9 0 0 1 10 3.5 9 9 0 1 0 20.5 14Z"/></svg><svg className="sun-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg></Button>;
}
export default function Home(){
 const [tab,setTab]=useState<'humor'|'news'>('humor');
 const [view,setView]=useState<'live'|'records'|'archive'>('live');
 useEffect(()=>{const sync=()=>{const q=new URLSearchParams(location.search);setTab(q.get('tab')==='news'?'news':'humor');setView(q.get('view')==='records'?'records':q.get('view')==='archive'||q.has('date')||q.has('story')?'archive':'live')};sync();window.addEventListener('popstate',sync);return()=>window.removeEventListener('popstate',sync)},[]);
 function chooseView(next:'live'|'records'|'archive'){if(next===view)return;setView(next);const u=new URL(location.href);for(const k of ['date','edition','post','story','record','item'])u.searchParams.delete(k);u.searchParams.set('view',next);history.pushState(null,'',u)}
 return <main><Tabs value={tab} onValueChange={v=>{const next=v==='news'?'news':'humor';if(next===tab)return;setTab(next);setView('live');const u=new URL(location.href);for(const k of ['date','edition','post','story','record','item','view'])u.searchParams.delete(k);if(next==='news')u.searchParams.set('tab','news');else u.searchParams.delete('tab');history.pushState(null,'',u)}} className="feed-tabs" data-category={tab}><header><TabsList className="category-tabs" aria-label="브리핑 종류"><TabsTrigger value="humor">ㅋㅋㅋ</TabsTrigger><TabsTrigger value="news" className="news-tab">ㄴㅇㅅ</TabsTrigger></TabsList><div className="header-actions"><ThemeToggle/></div></header><nav className="live-navigation" aria-label="기록 상태">{([['live','진행 중'],['records','확정 기록'],['archive','이전 회차']] as const).map(([id,label])=><button key={id} aria-pressed={view===id} onClick={()=>chooseView(id)}>{label}</button>)}</nav><TabsContent value={tab} key={`${tab}:${view}`}>{view==='archive'?<><p className="legacy-note">기존 회차를 원문·미디어·뉴스 이력과 함께 보존한 기록입니다. 새 불변 확정본은 ‘확정 기록’에서 볼 수 있습니다.</p>{tab==='news'?<NewsBriefing/>:<CommunityBriefing/>}</>:<LiveBoard channel={tab} view={view}/>}</TabsContent></Tabs></main>
}
