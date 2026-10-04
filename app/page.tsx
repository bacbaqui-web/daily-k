'use client';
import {useEffect,useState} from 'react';
import {Tabs,TabsList,TabsTrigger,TabsContent} from '@/components/ui/tabs';
import {Button} from '@/components/ui/button';
import {NewsBriefing} from '../components/news-briefing';
import {CommunityBriefing} from '../components/community-briefing';
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
 useEffect(()=>{setTab(new URLSearchParams(location.search).get('tab')==='news'?'news':'humor')},[]);
 return <main><Tabs value={tab} onValueChange={v=>{const next=v==='news'?'news':'humor';setTab(next);const u=new URL(location.href);u.searchParams.delete('date');u.searchParams.delete('edition');u.searchParams.delete('post');u.searchParams.delete('story');if(next==='news')u.searchParams.set('tab','news');else u.searchParams.delete('tab');history.replaceState(null,'',u)}} className="feed-tabs" data-category={tab}><header><TabsList className="category-tabs" aria-label="브리핑 종류"><TabsTrigger value="humor">ㅋㅋㅋ</TabsTrigger><TabsTrigger value="news" className="news-tab">ㄴㅇㅅ</TabsTrigger></TabsList><div className="header-actions"><ThemeToggle/></div></header><TabsContent value={tab} key={tab}>{tab==='news'?<NewsBriefing/>:<CommunityBriefing/>}</TabsContent></Tabs></main>
}
