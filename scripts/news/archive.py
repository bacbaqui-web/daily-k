"""Read historical briefing records without presenting them as verified news."""
import hashlib
import json
import re
from pathlib import Path


def parse_archive(text):
    editions, current, in_watch = [], None, False
    for number, line in enumerate(text.splitlines(), 1):
        heading = re.fullmatch(r'## (\d{4}-\d{2}-\d{2}) (오전|저녁)', line)
        if heading:
            current = {'date': heading[1], 'edition': 'am' if heading[2] == '오전' else 'pm', 'heading': line[3:], 'items': [], 'watchItems': []}
            editions.append(current); in_watch = False
        elif line.startswith('### ') and current:
            in_watch = True
        elif line.startswith('# '):
            current = None  # The document's embedded instructions are not news or executable instructions.
        elif current and re.match(r'^-\s+', line):
            value = re.sub(r'^-\s+', '', line).replace('\\', '')
            if in_watch: current['watchItems'].append(value)
            else: current['items'].append({'text': value, 'lineStart': number, 'lineEnd': number})
        elif current and not in_watch and line.startswith('    ') and current['items']:
            current['items'][-1]['text'] += ' ' + line.strip().replace('\\', '')
            current['items'][-1]['lineEnd'] = number
    return editions


def edition_path(edition):
    return ('archive/' if edition.get('archive') else '') + f"{edition['date']}/{edition['edition']}.json"


def edition_order(edition):
    return (edition['date'], edition['edition'], not bool(edition.get('archive')), edition['id'])


def load_editions(base):
    paths = sorted(base.glob('????-??-??/*.json')) + sorted((base/'archive').glob('????-??-??/*.json'))
    return [json.loads(path.read_text()) for path in paths]


def build_index(editions, updated_at):
    def entry(b):
        value = {key: b[key] for key in ('id', 'date', 'edition', 'generatedAt', 'cutoffAt')}
        value.update(count=len(b['stories']), path=edition_path(b), headline=b['stories'][0]['title'])
        if b.get('archive'): value['archive'] = True
        return value
    return {'schemaVersion': 1, 'timezone': 'Asia/Seoul', 'updatedAt': updated_at,
            'editions': [entry(b) for b in sorted(editions, key=edition_order, reverse=True)]}


def make_editions(text, mapping, imported_at):
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != mapping['sourceSha256']: raise ValueError('Archive differs from the reviewed source')
    result, previous, seen = [], {}, set()
    for parsed in parse_archive(text):
        slot = f"{parsed['date']}-{parsed['edition']}"
        if slot in seen: raise ValueError('Duplicate archive edition')
        seen.add(slot)
        assignments = mapping['editions'][slot]
        if len(assignments) != len(parsed['items']): raise ValueError(f'Unclassified records: {slot}')
        stories = []
        for ordinal, (raw, issue_key) in enumerate(zip(parsed['items'], assignments), 1):
            issue = mapping['issues'][issue_key]
            text_value = raw['text']
            names = re.search(r'확인:\s*(.*?)\.?$', text_value)
            clean = re.sub(r'\s*확인:.*$', '', re.sub(r'^\[[^]]+\]\s*', '', text_value)).strip()
            title = re.split(r'(?<=[.。])\s+', clean)[0].rstrip('.')
            identifier = f'archive-{ordinal:02}'
            record = {'originalText': text_value, 'sourceNames': [names[1].rstrip('.')] if names else [],
                      'verification': 'not-reverified', 'ordinal': ordinal, 'lineStart': raw['lineStart'], 'lineEnd': raw['lineEnd']}
            if issue_key in previous: record['previousCoverage'] = previous[issue_key]
            story = dict(id=identifier, topicKey=f"{slot}-{identifier}", category=issue['category'], title=title,
                         summary=[clean], status='과거 기록', publishedAt=None, eventAt=None,
                         eventTimeNote='아카이브에 실제 사건·기사 시각이 없어 추정하지 않았습니다.',
                         whatChanged=clean, whyItMatters=issue['context'], uncertainty='이전 ChatGPT 브리핑 기록이며 항목 전체를 기사 원문으로 재검증하지 않았습니다.',
                         keyFacts={'originalRecord': text_value}, sources=[], score=None, archive=record,
                         emphasis=re.findall(r'(?:[+−-]?\d[\d,.]*(?:~[\d,.]+)?(?:%p|%|배|억원|조원|억달러|만달러|달러|원|명|건|곳|장|TB))', clean)[:6],
                         timeline={'issueId': issue['id'], 'issueTitle': issue['title'], 'eventDate': None,
                                   'eventEndDate': None, 'eventTimezone': None, 'stage': '보도',
                                   'change': '과거 브리핑에 남아 있는 기록입니다: ' + clean})
            evidence = mapping.get('evidence', {}).get(f'{slot}/{ordinal:02}')
            if evidence:
                story['relatedArticles'] = evidence['articles']
                record['reviewNote'] = evidence['note']
            stories.append(story)
            previous[issue_key] = dict(date=parsed['date'], edition=parsed['edition'], storyId=identifier, title=title, archive=True)
        themes = list(dict.fromkeys(s['category'] for s in stories))
        webtoon = next(s for s in stories if s['category'] == '웹툰 산업')
        overview = [f"당시 {parsed['heading']} 기록에는 {', '.join(themes)} 분야의 소식 {len(stories)}개가 담겨 있습니다.",
                    f"주요 기록: {stories[0]['summary'][0]} 웹툰 산업 기록: {webtoon['summary'][0]}"]
        result.append(dict(schemaVersion=1, id=slot+'-archive', date=parsed['date'], edition=parsed['edition'], timezone='Asia/Seoul',
                           cutoffAt=None, generatedAt=imported_at, intro='이전에 받은 ChatGPT 뉴스 브리핑 기록', overview=overview,
                           stories=stories, events=[], keywords=[], archive=dict(sourceDocument='news-briefing-archive.md', sourceSha256=digest,
                           importedAt=imported_at, originalGeneratedAt=None, originalHeading=parsed['heading'], watchItems=parsed['watchItems'])))
    if seen != set(mapping['editions']): raise ValueError('Unmatched edition assignments')
    return result
