'use client';
import {useEffect, useState} from 'react';
import {VStack, HStack} from '@astryxdesign/core/Layout';
import {Text, Heading} from '@astryxdesign/core/Text';
import {Button} from '@astryxdesign/core/Button';
import {isGitHubBrief, isGitHubIndex, validGitHubDate, type GitHubBrief, type GitHubIndex, type GitHubItem} from '../lib/github';

const time = (value: string) => new Intl.DateTimeFormat('ko-KR', {timeZone: 'Asia/Seoul', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false}).format(new Date(value));

function ProjectImage({item}: {item: GitHubItem}) {
  const [failed, setFailed] = useState(false);
  return <VStack as="figure" gap={2} className="m-0">
    {failed ? <Text as="p" type="supporting">이미지를 불러오지 못했습니다. 아래 이미지 출처에서 확인해 주세요.</Text> : <a href={item.image.sourceUrl} target="_blank" rel="noopener noreferrer" aria-label={`${item.repo} 이미지 원본 보기`}><img src={item.image.src} alt={item.image.alt} loading="lazy" decoding="async" onError={() => setFailed(true)} className="block w-full max-h-64 object-contain rounded-lg bg-muted" /></a>}
    <figcaption><Text type="supporting">{item.image.caption} · <a href={item.image.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">이미지 출처</a></Text></figcaption>
  </VStack>;
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
      if (!r.ok) throw Error(); const value: unknown = await r.json(); if (!isGitHubBrief(value) || value.date !== date) throw Error(); setBrief(value);
    }).catch(() => {if (!controller.signal.aborted) setError('이 날짜의 분석을 불러오지 못했습니다. 다시 불러오기를 눌러 주세요.');});
    return () => controller.abort();
  }, [date, index, retry]);
  const dates = index?.editions.map(e => e.date).sort() || [];
  const previous = dates.filter(d => date && d < date).at(-1), next = dates.find(d => date && d > date);
  const choose = (value: string) => {const u = new URL(location.href); u.searchParams.set('tab', 'github'); u.searchParams.set('githubDate', value); onNavigate(u.href);};
  const missing = index && (!date || !dates.includes(date));
  return <VStack as="section" gap={6} paddingBlock={6} aria-label="GitHub Trending 브리핑">
    <HStack gap={2} justify="center" wrap="wrap" aria-label="GitHub 브리핑 날짜">
      <Button label="이전 날짜" variant="ghost" size="sm" isDisabled={!previous} onClick={() => previous && choose(previous)}>←</Button>
      <label className="flex items-center gap-2"><Text type="supporting">날짜</Text><select aria-label="GitHub 브리핑 날짜 선택" value={date || ''} onChange={e => choose(e.target.value)} className="rounded-md border border-border bg-background text-foreground p-2">{date && !dates.includes(date) && <option value={date}>{date}</option>}{index?.editions.map(e => <option key={e.date} value={e.date}>{e.date}</option>)}</select></label>
      <Button label="다음 날짜" variant="ghost" size="sm" isDisabled={!next} onClick={() => next && choose(next)}>→</Button>
    </HStack>
    <VStack gap={2}>
      <Heading level={1}>오늘의 GitHub 10</Heading>
      {brief && <Text type="supporting">일간 · 전체 언어 · {time(brief.capturedAt)} 기준</Text>}
    </VStack>
    {error ? <VStack gap={3} role="alert"><Text as="p">{error}</Text><Button label="다시 불러오기" onClick={() => setRetry(n => n + 1)} /></VStack> : missing ? <Text as="p" role="status">이 날짜에는 발행된 분석이 없습니다. 다른 날짜를 선택해 주세요.</Text> : !brief || brief.date !== date ? <Text as="p" role="status">분석을 불러오고 있습니다.</Text> : <VStack as="ol" gap={0} className="list-none m-0 p-0">
      {brief.items.map(item => <VStack as="li" key={`${date}:${item.repo}`} gap={3} paddingBlock={6} className="border-t border-border" id={`github-${item.rank}`}>
        <HStack justify="between" wrap="wrap" gap={2}>
          <Heading level={2}><a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:underline">{item.rank}. {item.repo.split('/')[1]} ↗</a></Heading>
          <Text type="supporting">오늘 별 +{item.starsToday.toLocaleString('ko-KR')}</Text>
        </HStack>
        <ProjectImage item={item}/>
        <Text as="p" type="large">{item.summary}</Text>
        <Text as="p" type="supporting">{item.requirements}</Text>
      </VStack>)}
    </VStack>}
    <Text as="p" type="supporting"><a href="https://github.com/trending?since=daily" target="_blank" rel="noopener noreferrer" className="underline">GitHub Trending</a> · ChatGPT 분석 · 직접 실행 미확인</Text>
  </VStack>;
}
