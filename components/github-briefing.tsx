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
    {failed ? <Text as="p" type="supporting">이미지를 불러오지 못했습니다. 아래 이미지 출처에서 확인해 주세요.</Text> : <a href={item.image.sourceUrl} target="_blank" rel="noopener noreferrer" aria-label={`${item.repo} 이미지 원본 보기`}><img src={item.image.src} alt={item.image.alt} loading="lazy" decoding="async" onError={() => setFailed(true)} className="block w-full max-h-96 object-contain rounded-lg bg-muted" /></a>}
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
    <VStack gap={3}>
      <Text type="supporting">전체 언어 · 일간 Trending</Text>
      <Heading level={1}>오늘의 GitHub 10</Heading>
      <Text as="p">{brief?.intro || '지금 주목받는 프로젝트가 무엇을 하고 어디에 쓰이는지 정리합니다.'}</Text>
      <Text as="p" type="supporting">매일 오전 9시부터 조사하고 확인을 마치면 게시합니다. 새 분석 전에는 최근 발행분을 보여드립니다.</Text>
      {brief && <Text as="p" type="supporting">순위 확인 {time(brief.capturedAt)} · 게시 {time(brief.publishedAt)} · 한국 시간<br/>ChatGPT 분석 · 공식 자료 대조. 직접 설치하거나 실행한 후기는 아닙니다.</Text>}
    </VStack>
    {error ? <VStack gap={3} role="alert"><Text as="p">{error}</Text><Button label="다시 불러오기" onClick={() => setRetry(n => n + 1)} /></VStack> : missing ? <Text as="p" role="status">이 날짜에는 발행된 분석이 없습니다. 다른 날짜를 선택해 주세요.</Text> : !brief || brief.date !== date ? <Text as="p" role="status">분석을 불러오고 있습니다.</Text> : <VStack as="ol" gap={0} className="list-none m-0 p-0">
      {brief.items.map(item => <VStack as="li" key={`${date}:${item.repo}`} gap={5} paddingBlock={8} className="border-t border-border" id={`github-${item.rank}`}>
        <VStack gap={2}>
          <Text type="supporting">{String(item.rank).padStart(2, '0')}위 · 오늘 별 +{item.starsToday.toLocaleString('ko-KR')}</Text>
          <Heading level={2}>{item.title}</Heading>
          <Text type="code"><a href={item.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4 break-all">{item.repo} ↗</a></Text>
          <Text as="p" type="large">{item.summary}</Text>
        </VStack>
        <ProjectImage item={item}/>
        {item.explanation.map((paragraph, i) => <Text as="p" key={i}>{paragraph}</Text>)}
        <VStack gap={2}><Heading level={3}>이렇게 쓸 수 있습니다</Heading><Text as="p">{item.useCase}</Text></VStack>
        <VStack gap={2}><Heading level={3}>사용 조건</Heading>{item.requirements.split('\n').filter(Boolean).map((line, i) => <Text as="p" key={i}>{line}</Text>)}</VStack>
        <HStack wrap="wrap" gap={3}>{item.sources.map(source => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer" className="text-sm underline underline-offset-4">{source.label} ↗</a>)}</HStack>
      </VStack>)}
    </VStack>}
    <Text as="p" type="supporting">순위는 <a href="https://github.com/trending?since=daily" target="_blank" rel="noopener noreferrer" className="underline">GitHub Trending</a>에 표시된 순서를 따릅니다. 오늘 늘어난 별 개수만으로 다시 정렬하지 않습니다.</Text>
  </VStack>;
}
