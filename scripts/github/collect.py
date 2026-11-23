"""Capture GitHub's displayed daily ranking. No LLM or paid API calls."""
import argparse
import concurrent.futures
import html
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TRENDING = 'https://github.com/trending?since=daily'
KST = ZoneInfo('Asia/Seoul')

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'DailyK-GitHub/1.0'})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()

def parse_ranking(source):
    items = []
    articles = re.findall(r'<article\b.*?</article>', source, re.S)
    if len(articles) != len(re.findall(r'<article\b', source)):
        raise ValueError('Incomplete ranking HTML')
    for article in articles:
        heading = re.search(r'<h2\b.*?</h2>', article, re.S)
        if not heading:
            raise ValueError("Ranking entry is missing its heading")
        link = re.search(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', heading[0])
        if not link:
            raise ValueError("Ranking entry is missing its repository")
        repo = link[1]
        text = html.unescape(re.sub(r'<[^>]+>', ' ', article))
        stars = re.search(r'([\d,]+)\s+stars?\s+today', text)
        if not stars:
            raise ValueError(f'Missing daily stars: {repo}')
        def total(suffix):
            anchor = re.search(r'<a\b[^>]*href="/' + re.escape(repo) + '/' + suffix + r'"[^>]*>(.*?)</a>', article, re.S)
            value = html.unescape(re.sub(r'<[^>]+>', '', anchor[1])).strip() if anchor else ''
            if not re.fullmatch(r'[\d,]+', value):
                raise ValueError(f'Missing or invalid {suffix}: {repo}')
            return int(value.replace(',', ''))
        language = re.search(r'<span\b[^>]*itemprop="programmingLanguage"[^>]*>(.*?)</span>', article, re.S)
        items.append({'rank': len(items) + 1, 'repo': repo,
                      'url': f'https://github.com/{repo}',
                      'starsToday': int(stars[1].replace(',', '')),
                      'starsTotal': total('stargazers'), 'forks': total('forks'),
                      'language': html.unescape(language[1]).strip() if language else None})
    if not items or len({x['repo'] for x in items}) != len(items):
        raise ValueError('Expected a non-empty ranking with unique repositories')
    return items

def collect(output, saved_html=None):
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'snapshot.json'
    if target.exists():
        raise ValueError('Snapshot already exists; reuse it rather than changing this edition')
    raw = saved_html.read_bytes() if saved_html else fetch(TRENDING)
    captured = datetime.fromtimestamp(saved_html.stat().st_mtime, KST) if saved_html else datetime.now(KST)
    items = parse_ranking(raw.decode())
    (output / 'trending.html').write_bytes(raw)
    def enrich(item):
        repo = item['repo']
        page = fetch(item['url']).decode()
        tags = re.findall(r'<meta\b[^>]+>', page)
        for tag in tags:
            if 'property="og:image"' in tag:
                match = re.search(r'content="([^"]+)"', tag)
                if match:
                    item['socialImage'] = html.unescape(match[1])
        for branch in ['main', 'master']:
            url = f'https://raw.githubusercontent.com/{repo}/{branch}/README.md'
            try:
                readme = fetch(url).decode()
                (output / f"{item['rank']:02d}-README.md").write_text(readme)
                item['readmeUrl'] = url
                break
            except Exception:
                continue
        return item
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        items = list(pool.map(enrich, items))
    value = {'schemaVersion': 1, 'date': captured.date().isoformat(),
             'capturedAt': captured.isoformat(), 'rankingUrl': TRENDING,
             'period': 'daily', 'language': 'all', 'itemCount': len(items), 'items': items}
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'snapshot': str(target), 'date': value['date'], 'count': len(items)}))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--html', type=Path, help='Reuse an already captured HTML file with its original modification time')
    a = p.parse_args()
    collect(a.output, a.html)
