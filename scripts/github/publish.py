"""Validate a reviewed ChatGPT analysis and publish an immutable daily edition.

--check never changes publication state. Git commit/push remains explicit.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def require(value, message):
    if not value:
        raise ValueError(message)

def nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def validate(state):
    snapshot = json.loads((state / 'snapshot.json').read_text())
    analysis = json.loads((state / 'analysis.json').read_text())
    review = json.loads((state / 'review.json').read_text())
    images = json.loads((state / 'images.json').read_text())
    date = snapshot['date']
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', date), 'Invalid date')
    datetime.strptime(date, '%Y-%m-%d')
    require(analysis['date'] == date and review['date'] == date, 'Edition dates differ')
    require(snapshot['rankingUrl'] == 'https://github.com/trending?since=daily' and snapshot['period'] == 'daily' and snapshot['language'] == 'all', 'Invalid ranking scope')
    require(datetime.fromisoformat(snapshot['capturedAt']).astimezone(ZoneInfo('Asia/Seoul')).date().isoformat() == date, 'Capture date mismatch')
    require(review.get('approved') is True and review.get('responseComplete') is True, 'Completed ChatGPT response and approval required')
    require(nonempty(review.get('conversationUrl')) and review['conversationUrl'].startswith('https://chatgpt.com/'), 'Missing ChatGPT provenance')
    require('[DailyK-GitHub:' + date + ']' in (state / 'request.txt').read_text(), 'Request edition marker missing')
    for name in ['snapshot', 'analysis', 'images']:
        require(review.get(name + 'Sha256') == digest(state / (name + '.json')), name + ' changed after review')
    require(review.get('responseSha256') == digest(state / 'chatgpt-response.txt'), 'Response changed after review')
    require(nonempty(analysis.get('intro')), 'Missing intro')
    require(len(snapshot['items']) == len(analysis['items']) == len(images) == 10, 'Exactly ten entries required')
    require(len({i['repo'] for i in snapshot['items']}) == 10, 'Duplicate repository')
    checks = review.get('items', [])
    require(len(checks) == 10, 'Ten source reviews required')
    output = []
    for rank, (original, item, image, check) in enumerate(zip(snapshot['items'], analysis['items'], images, checks), 1):
        repo = original['repo']
        require(re.fullmatch(r'[\w.-]+/[\w.-]+', repo), 'Invalid repository')
        require(item['repo'] == image['repo'] == check['repo'] == repo and item['rank'] == original['rank'] == rank, 'Ranking/order mismatch')
        require(type(original['starsToday']) is int and original['starsToday'] >= 0, 'Invalid stars')
        require(check.get('factsChecked') is True and check.get('imageChecked') is True and nonempty(check.get('notes')), 'Source/image review incomplete')
        for field in ['title', 'summary', 'useCase', 'requirements']:
            require(nonempty(item.get(field)), 'Missing ' + field)
        require(isinstance(item.get('explanation'), list) and len(item['explanation']) > 0 and all(map(nonempty, item['explanation'])), 'Missing explanation')
        require(isinstance(item.get('sources'), list) and item['sources'], 'Missing sources')
        for source in item['sources']:
            require(nonempty(source.get('label')) and source.get('url', '').startswith('https://'), 'Invalid source URL')
        require(re.fullmatch(r'[\w-]+\.(png|jpg|webp)', image['file']), 'Unsafe image filename')
        file = state / 'images' / image['file']
        require(file.is_file() and file.stat().st_size > 100 and file.stat().st_size < 15_000_000, 'Missing/invalid image')
        require(image.get('sha256') == digest(file), 'Image changed after review')
        data = file.read_bytes()
        require(data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff') or (data.startswith(b'RIFF') and data[8:12] == b'WEBP'), 'Unsupported image bytes')
        require(nonempty(image.get('alt')) and nonempty(image.get('caption')) and image.get('sourceUrl', '').startswith('https://'), 'Missing image attribution')
        output.append({**{k: item[k] for k in ['rank', 'repo', 'title', 'summary', 'explanation', 'useCase', 'requirements', 'sources']},
                       'url': f'https://github.com/{repo}', 'starsToday': original['starsToday'],
                       'image': {'src': f"/daily-k/data/github/images/{date}/{image['file']}", **{k: image[k] for k in ['alt', 'caption', 'sourceUrl']}}})
    return {'schemaVersion': 1, 'date': date, 'capturedAt': snapshot['capturedAt'],
            'publishedAt': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
            'rankingUrl': snapshot['rankingUrl'], 'intro': analysis['intro'], 'items': output}, images

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(f.name, path)

def publish(state, root=ROOT, check=False):
    brief, images = validate(state)
    date = brief['date']
    # Validate both destinations before writing. Existing editions are immutable.
    for folder in ['public', 'docs']:
        path = root / folder / 'data/github' / f'{date}.json'
        if path.exists():
            existing = json.loads(path.read_text())
            brief['publishedAt'] = existing['publishedAt']
            require(existing == brief, 'Edition already published with different content; preserve it and review a correction separately')
        for image in images:
            published = root / folder / 'data/github/images' / date / image['file']
            require(not published.exists() or digest(published) == image['sha256'], 'Published image differs; preserve the original')
    if check:
        return {'checked': True, 'date': date, 'count': 10}
    lock = root / '.github-publish.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        for folder in ['public', 'docs']:
            base = root / folder / 'data/github'
            target = base / 'images' / date
            target.mkdir(parents=True, exist_ok=True)
            for image in images:
                shutil.copyfile(state / 'images' / image['file'], target / image['file'])
            atomic_json(base / f'{date}.json', brief)
            index_path = base / 'index.json'
            index = json.loads(index_path.read_text()) if index_path.exists() else {'schemaVersion': 1, 'editions': []}
            entries = [e for e in index['editions'] if e['date'] != date]
            entries.append({'date': date, 'path': f'{date}.json', 'count': 10})
            atomic_json(index_path, {'schemaVersion': 1, 'editions': sorted(entries, key=lambda e: e['date'], reverse=True)})
    finally:
        os.close(fd)
        lock.unlink()
    return {'written': True, 'date': date, 'count': 10, 'gitPushRequired': True}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(publish(args.state, check=args.check)))
