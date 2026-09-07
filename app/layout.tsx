import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title:'ㅋㅋㅋ',description:'ㅋㅋㅋ'};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="ko" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:`try{var t=localStorage.getItem("daily-k-theme");document.documentElement.dataset.theme=t==="dark"||t!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}catch(e){document.documentElement.dataset.theme=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}`}}/></head><body>{children}</body></html>}
