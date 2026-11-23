'use client';
import {useEffect, useState} from 'react';
import {BriefCopyButton} from './news-question-button';
import {buildGitHubQuestion} from '../lib/github-question';
import {emphasisParts} from '../lib/news';
import {isGitHubBrief, isGitHubIndex, validGitHubDate, type GitHubBrief, type GitHubIndex, type GitHubItem} from '../lib/github';

const time = (value: string) => new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false}).format(new Date(value));

function ProjectImage({item}: {item: GitHubItem}) {
  const [failed, setFailed] = useState(false);
  return <figure className="github-hero">
    <a href={item.image.sourceUrl} target="_blank" rel="noopener noreferrer" aria-label={`${item.repo} 이미지 원본 보기`}>
      {failed ? <small>이미지를 불러오지 못했습니다.</small> : <img src={item.image.src} alt={item.image.alt} loading={item.rank === 1 ? 'eager' : 'lazy'} decoding="async" onError={() => setFailed(true)} />}
    </a>
  </figure>;
}

export function GitHubBriefing({search, onNavigate}: {search: string; onNavigate: (href: string) => void}) {
  const [index, setIndex] = useState<GitHubIndex | null>(null);
  const [brief, setBrief] = useState<GitHubBrief | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const requested = new URLSearchParams(search).get('githubDate');
  const date = validGitHubDate(requested) ? requested : index?.editions[0]?.date;
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    fetch('/daily-k/data/github/index.json', {cache: 'no-store', signal: controller.signal}).then(async r => {
      if (!r.ok) throw Error(); const value: unknown = await r.json(); if (!isGitHubIndex(value)) throw Error();
      setIndex({...value, editions: [...value.editions].sort((a, b) => b.date.localeCompare(a.date))});
    }).catch(() => {if (!controller.signal.aborted) setError('GitHub 기록을 불러오지 못했습니다. 다시 불러오기를 눌러 주세요.');});
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    setBrief(null); if (!date || !index) return;
    setError('');
    if (!index.editions.some(e => e.date === date)) return;
    const controller = new AbortController();
    fetch(`/daily-k/data/github/${date}.json`, {cache: 'no-store', signal: controller.signal}).then(async r => {
      if (!r.ok) throw Error(); const value: unknown = await r.json(); if (!isGitHubBrief(value, index.editions.find(e => e.date === date)?.count) || value.date !== date) throw Error(); setBrief(value);
    }).catch(() => {if (!controller.signal.aborted) setError('이 날짜의 분석을 불러오지 못했습니다. 다시 불러오기를 눌러 주세요.');});
    return () => controller.abort();
  }, [date, index, retry]);
  const dates = index?.editions.map(e => e.date).sort() || [];
  const previous = dates.filter(d => date && d < date).at(-1), next = dates.find(d => date && d > date);
  const choose = (value: string) => {const u = new URL(location.href); u.searchParams.set('tab', 'github'); u.searchParams.set('githubDate', value); onNavigate(u.href);};
  const missing = index && (!date || !dates.includes(date));
  return <section className="news edition-board github-briefing" aria-label="GitHub Trending 브리핑">
    <section className="news-controls news-controls-inline edition-controls github-controls" role="group" aria-label="GitHub 브리핑 날짜">
      <button className="news-date-arrow" aria-label="이전 날짜" disabled={!previous} onClick={() => previous && choose(previous)}>←</button>
      <label className="news-date-selection"><span className="sr-only">GitHub 브리핑 날짜 선택</span><input type="date" value={date || ''} onChange={e => validGitHubDate(e.target.value) && choose(e.target.value)} /></label>
      <button className="news-date-arrow" aria-label="다음 날짜" disabled={!next} onClick={() => next && choose(next)}>→</button>
    </section>
    <h1 className="sr-only">{date} GitHub Trending{brief ? ` ${brief.items.length}개` : ''}</h1>
    {error ? <section className="news-message" role="alert"><p>{error}</p><button onClick={() => setRetry(n => n + 1)}>다시 불러오기</button></section> : missing ? <p className="news-message" role="status">이 날짜에는 발행된 분석이 없습니다. 다른 날짜를 선택해 주세요.</p> : !brief || brief.date !== date ? <p className="news-message" role="status">분석을 불러오고 있습니다.</p> : <ol className="posts news-stories">
      {brief.items.map(item => <li key={`${date}:${item.repo}`}><article>
        <ProjectImage item={item}/>
        <section className="post-top news-static-heading">
          <small className="rank" aria-hidden="true">{String(item.rank).padStart(2, '0')}</small>
          <hgroup className="post-main">
            <p className="news-story-meta"><span>GitHub Trending</span><span>{[item.language ?? (item.starsTotal !== undefined ? '언어 미표기' : null), item.starsTotal !== undefined ? `누적 별 ${item.starsTotal.toLocaleString('ko-KR')}` : null, `오늘 +${item.starsToday.toLocaleString('ko-KR')}`, item.forks !== undefined ? `포크 ${item.forks.toLocaleString('ko-KR')}` : null].filter(Boolean).join(' · ')}</span></p>
            <section className="news-title-share"><h2 className="news-story-title" id={`github-${item.rank}`}><a href={item.url} target="_blank" rel="noopener noreferrer">{item.repo.split('/')[1]} · {item.title}</a></h2><BriefCopyButton text={buildGitHubQuestion(brief,item)} title={item.repo} question/></section>
          </hgroup>
        </section>
        <section className="news-full-content" aria-labelledby={`github-${item.rank}`}>
          <p>{emphasisParts(item.summary, item.emphasis).map((part, i) => part.bold ? <strong key={i}>{part.text}</strong> : part.text)}</p>
          <p>{emphasisParts(item.requirements, item.emphasis).map((part, i) => part.bold ? <strong key={i}>{part.text}</strong> : part.text)}</p>
        </section>
      </article></li>)}
    </ol>}
    <details className="edition-record-info"><summary>순위·확인 정보</summary><p>전체 언어 · 일간{brief && ` · ${time(brief.capturedAt)} 기준`}</p><p><a href="https://github.com/trending?since=daily" target="_blank" rel="noopener noreferrer">GitHub Trending ↗</a> · ChatGPT 분석 · 직접 실행 미확인</p></details>
  </section>;
}
