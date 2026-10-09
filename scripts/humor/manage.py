#!/usr/bin/env python3
"""Rolling humor publication. No crawling, clock backdating, or scheduling.

Only a verified Aagag publication time determines expiry. Observations and
publication on Daily K never extend that lifetime. Legacy records are untouched.
"""
import argparse
import copy
from datetime import datetime, timedelta
import fcntl
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('live_contract', ROOT / 'scripts/live/manage.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
stamp, iso, require, encoded, digest = live.stamp, live.iso, live.require, live.encoded, live.digest
CURRENT = 'data/humor/current.json'
TTL = timedelta(hours=24)
SAFETY = re.compile(r'(?<![ㄱ-ㅎ])(?:ㅇㅎㅂ|ㅇㅎ|ㅎㅂ)(?![ㄱ-ㅎ])|비키니|ㅂㅋㄴ|섹스|성관계|야동|젖꼭지|알몸|성인물|총살|처형|참수|시신|시체|자살|고문|성폭행|불륜|성추행|몰카|강간')


def identity(url):
    p = urlsplit(live.url(url))
    values = parse_qs(p.query)
    raw = values.get('idx', [''])[0]
    require(p.scheme == 'https' and p.hostname == 'aagag.com' and p.port in (None, 443)
            and p.path.rstrip('/') == '/issue' and len(values.get('idx', [])) == 1
            and re.fullmatch(r'\d+(?:_\d+)?', raw), 'actual Aagag issue URL required')
    return 'aagag-' + raw.split('_')[0]


def initial():
    return dict(schemaVersion=1, mode='rolling-humor', timezone='Asia/Seoul', retentionHours=24,
                minimumLiteralK=10, updatedAt=None, lastCheck=None, items=[], registry={}, operations={})


def fresh(published, now):
    return published <= now < published + TTL


def counts(evidence):
    require(evidence.get('scope') == 'native-aagag-all' and evidence.get('complete') is True,
            'complete native Aagag comments required; no external or lower-bound counts')
    rows = evidence.get('rows')
    require(isinstance(rows, list), 'native comment count rows required')
    unique = {}
    for row in rows:
        cid, count = row.get('id'), row.get('literalKCount')
        require(isinstance(cid, str) and re.fullmatch(r'\d+', cid), 'native comment ID required')
        require(type(count) is int and 0 <= count <= 9007199254740991, 'literal count must be a nonnegative integer')
        require(cid not in unique or unique[cid] == count, 'conflicting duplicate native comment')
        unique[cid] = count
    require(type(evidence.get('reportedCount')) is int and evidence['reportedCount'] == len(unique),
            'native comment total does not reconcile')
    require(sum(unique.values()) <= 9007199254740991, 'native total exceeds safe integer range')
    return sum(unique.values()), len(unique)


def validate_item(item, now):
    require(__debug__, 'run without Python -O')
    require(item.get('id') == identity(item.get('canonicalUrl')), 'stable issue ID mismatch')
    require(type(item.get('expectedRevision')) is int and item['expectedRevision'] >= 0, 'expectedRevision required')
    published, first, last = stamp(item.get('publishedAt')), stamp(item.get('firstObservedAt')), stamp(item.get('lastVerifiedAt'))
    require(published <= first <= last <= now, 'publication/observation times out of order')
    require(fresh(published, now), 'post is expired at 24 hours or has a future publication time')
    proof = item.get('publicationEvidence', {})
    require(set(proof) <= {'method','sourceUrl','value','raw','observedAt','semanticsVerified'}, 'unknown publication evidence fields')
    require(proof.get('semanticsVerified') is True, 'publication meaning unverified; hold, do not substitute firstObservedAt')
    require(proof.get('method') in ('aagag-otime', 'aagag-explicit-publication'), 'exact publication evidence required')
    require(identity(proof.get('sourceUrl')) == item['id'] and stamp(proof.get('value')) == published,
            'publication evidence does not match this post and timestamp')
    require(published <= stamp(proof.get('observedAt')) <= last, 'invalid publication verification time')
    live.text(proof.get('raw'), 'publication evidence', 500)
    if proof['method'] == 'aagag-otime':
        require(re.fullmatch(r'\d+(?:\.\d+)?', proof['raw']) and abs(float(proof['raw']) - published.timestamp()) < .001,
                'otime evidence must be the actual matching epoch timestamp')
    evidence = item.get('nativeComments', {})
    require(identity(evidence.get('sourceUrl')) == item['id'], 'comments must belong to this Aagag issue')
    require(first <= stamp(evidence.get('observedAt')) <= last, 'invalid comment observation time')
    total, comments = counts(evidence)
    require(total >= 10, 'at least 10 literal ㅋ characters required')
    review = item.get('review', {})
    require(set(review) <= {'safetyChecked','rightsChecked','verifiedAt','note'}, 'unknown review fields')
    require(review.get('safetyChecked') is True and review.get('rightsChecked') is True,
            'context/media safety and copyright review required; title rules alone are not clearance')
    require(first <= stamp(review.get('verifiedAt')) <= last, 'review must fall in the actual observation interval')
    live.text(review.get('note'), 'review note')
    live.text(item.get('title'), 'title', 300)
    live.text(item.get('limitations'), 'limitations')
    sources = item.get('sources')
    require(isinstance(sources, list) and sources, 'verified sources required')
    require(any(s['url'] == item['canonicalUrl'] for s in sources), 'Aagag source missing')
    source_urls = set()
    for source in sources:
        require(set(source) <= {'name','title','url','verifiedAt','publishedAt','quotes'}, 'unknown source fields')
        live.url(source['url'])
        require(source['url'] not in source_urls, 'duplicate source URL')
        source_urls.add(source['url'])
        live.text(source.get('name'), 'source.name', 120)
        live.text(source.get('title'), 'source.title', 300)
        require(stamp(source['verifiedAt']) <= last, 'source verification cannot be future')
        require(source.get('publishedAt') is None or stamp(source['publishedAt']) <= stamp(source['verifiedAt']), 'source publication time invalid')
        quotes = source.get('quotes', [])
        require(isinstance(quotes, list) and all(isinstance(q, str) for q in quotes), 'quotes must be text')
        require(sum(len(q) for q in quotes) <= 1000, 'short source quotations only')
        require(sum(len(t.split()) for t in [source['title'], *quotes]) <= 25, 'source title and quotations exceed 25 words')
    content = item.get('content', {})
    require(isinstance(content, dict) and not content.get('contentSignals'), 'excluded content signal')
    live.text(content.get('originalText',''), 'short original text', 1000, empty=True)
    texts = [item['title'], *[s['title'] for s in sources], content.get('originalText', '')]
    require(not any(SAFETY.search(t.replace('\u200b', '')) for t in texts), 'excluded title or text')
    quotes = content.get('comments', [])
    require(isinstance(quotes, list) and all(isinstance(c.get('id'), str) and isinstance(c.get('text'), str) for c in quotes), 'invalid comment quote')
    require(len({c['id'] for c in quotes}) == len(quotes), 'duplicate comment quotation')
    require(all(len(c['text']) <= 500 for c in quotes), 'short comment quotations only')
    require(sum(len(t.split()) for t in [item['title'], content.get('originalText', ''), *[c['text'] for c in quotes]]) <= 25, 'title/body/comments exceed 25 words')
    # Count every quotation attributed to the Aagag page together, not in separate budgets.
    aagag = next(s for s in sources if s['url'] == item['canonicalUrl'])
    quotation_texts = dict.fromkeys([item['title'], aagag['title'], *aagag.get('quotes', []), content.get('originalText', ''), *[c['text'] for c in quotes]])
    require(sum(len(t.split()) for t in quotation_texts) <= 25, 'combined Aagag quotation budget exceeded')
    for key in ('imageUrl', 'videoUrl', 'videoPosterUrl'):
        if content.get(key): live.url(content[key])
    media = dict(content, sources=sources)
    live.COMMUNITY.validate_body_images(media)
    if 'bodyImages' in content:
        require(content['bodyImagesSourceUrl'] in source_urls and stamp(content['bodyImagesVerifiedAt']) <= last, 'unverified body image metadata')
    for link in content.get('portalLinks', []):
        live.url(link)
        require(urlsplit(link).hostname in ('instagram.com', 'www.instagram.com', 'x.com', 'twitter.com'), 'unapproved portal link')
    # Explicit allowlist: raw body, arbitrary HTML and native comment text are never copied.
    public_content = {k: copy.deepcopy(v) for k, v in content.items() if k in ('imageUrl','videoUrl','videoPosterUrl','bodyImages','bodyImagesSourceUrl','bodyImagesVerifiedAt','originalText','comments','portalLinks')}
    return dict(id=item['id'], canonicalUrl=item['canonicalUrl'], title=item['title'], publishedAt=iso(published),
                expiresAt=iso(published + TTL), firstObservedAt=iso(first), lastVerifiedAt=iso(last),
                publicationEvidence=copy.deepcopy(proof), kCount=total, commentCount=comments,
                commentsVerifiedAt=evidence['observedAt'], nativeEvidenceSha256=digest(evidence),
                review=copy.deepcopy(review), sources=copy.deepcopy(sources), content=public_content,
                limitations=item['limitations'])


def plan(root, command, payload, now):
    path = root / 'public' / CURRENT
    state = json.loads(path.read_text()) if path.exists() else initial()
    require(state.get('mode') == 'rolling-humor' and state.get('schemaVersion') == 1, 'unsupported rolling state')
    live.slug(payload['operationId'])
    require(payload.get('schemaVersion') == 1, 'schemaVersion must be 1')
    operation_hash = digest(dict(command=command, payload=payload))
    prior = state['operations'].get(payload['operationId'])
    if prior:
        require(prior['hash'] == operation_hash, 'operationId reused with different input')
        return {}, dict(prior['result'], replayed=True)
    expired = [i['id'] for i in state['items'] if not fresh(stamp(i['publishedAt']), now)]
    state['items'] = [i for i in state['items'] if i['id'] not in expired]
    if command == 'upsert':
        items = payload.get('items')
        require(isinstance(items, list) and items, 'nonempty items required')
        require(len({i.get('id') for i in items}) == len(items), 'duplicate batch IDs')
        for item in items:
            value = validate_item(item, now)
            old = state['registry'].get(value['id'])
            require(item['expectedRevision'] == (old['revision'] if old else 0), 'revision conflict; read latest registry')
            if old:
                for key in ('publishedAt', 'firstObservedAt'):
                    require(stamp(old[key]) == stamp(value[key]), key + ' is immutable; relisting cannot reset expiry')
                require(stamp(value['lastVerifiedAt']) >= stamp(old['lastVerifiedAt']), 'stale verification')
            value.update(revision=item['expectedRevision'] + 1, recordedAt=iso(now))
            state['registry'][value['id']] = {k: value[k] for k in ('publishedAt','firstObservedAt','lastVerifiedAt','revision')}
            state['items'] = [i for i in state['items'] if i['id'] != value['id']] + [value]
    elif command == 'check':
        check = payload['check']
        require(check.get('status') in ('ok','empty','partial','blocked','challenge','failed','stopped'), 'invalid check state')
        require(stamp(check['checkedAt']) <= now, 'check cannot be future')
        live.text(check.get('note'), 'check.note')
        require(check.get('count') is None or type(check['count']) is int and check['count'] >= 0, 'invalid count')
        require(check['status'] not in ('blocked','challenge','failed','stopped') or check.get('count') is None, 'failure is not zero results')
        require(check['status'] != 'empty' or check.get('count') == 0, 'empty requires observed zero')
        state['lastCheck'] = dict(check, recordedAt=iso(now))
    elif command not in ('init', 'expire'):
        raise ValueError('unknown rolling command')
    state['items'].sort(key=lambda i: (i['publishedAt'], i['id']), reverse=True)
    state['updatedAt'] = iso(now)
    result = dict(operationId=payload['operationId'], recordedAt=iso(now), expired=expired, activeCount=len(state['items']))
    state['operations'][payload['operationId']] = dict(hash=operation_hash, result=result)
    # Preserve previous active values on expiry in an immutable event; never rewrite old snapshots.
    event = dict(command=command, inputSha256=digest(payload), result=result, previousItems=json.loads(path.read_text())['items'] if path.exists() else [], items=state['items'])
    writes = {}
    for folder in ('public', 'docs'):
        writes[f'{folder}/data/humor/events/{payload["operationId"]}.json'] = event
        writes[f'{folder}/{CURRENT}'] = state
    return writes, result


def recover(root, journal):
    writes = json.loads(journal.read_text())['writes']
    for relative, body in writes.items():
        require(re.fullmatch(r'(public|docs)/data/humor/(current\.json|events/[a-z0-9-]+\.json)', relative), 'unsafe journal path')
        path = root / relative
        require('/events/' not in relative or not path.exists() or path.read_text() == body, 'immutable event overwrite refused')
    for relative in sorted(writes, key=lambda p: p.endswith(CURRENT)):
        live.atomic_write(root / relative, writes[relative])
    journal.unlink()


def execute(root, command, payload, check=False, now=None):
    control = live.control_dir(root)
    with (control / 'daily-k-humor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal = control / 'daily-k-humor.pending.json'
        if journal.exists():
            require(not check, 'pending transaction: run recover first')
            recover(root, journal)
        if command == 'recover': return {'recovered': True}, []
        writes, result = plan(root, command, payload, now or datetime.now(live.KST))
        if writes and not check:
            live.atomic_write(journal, encoded({'writes': {p: encoded(v) for p,v in writes.items()}}))
            recover(root, journal)
        return dict(result, checkedOnly=check), list(writes)


def push_operation(root, command, payload):
    origin = live.git(root, 'remote', 'get-url', 'origin')
    with tempfile.TemporaryDirectory(prefix='daily-k-humor-') as tmp:
        checkout = Path(tmp) / 'repo'
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(root),str(checkout)], check=True)
        live.git(checkout,'remote','set-url','origin',origin)
        for attempt in range(4):
            live.git(checkout,'fetch','--quiet','origin','main')
            base = live.git(checkout,'rev-parse','origin/main')
            live.git(checkout,'checkout','--detach','--force',base)
            require((checkout / 'scripts/humor/manage.py').exists(), 'deploy rolling code before data writes')
            result, paths = execute(checkout,command,payload)
            if not paths: return dict(result,commit=base,pushed=True)
            live.git(checkout,'add','--',*paths)
            live.git(checkout,'commit','-m',f'Rolling humor {command}: {payload["operationId"]}','--',*paths)
            commit = live.git(checkout,'rev-parse','HEAD')
            try:
                live.git(checkout,'push','origin','HEAD:main')
                return dict(result,commit=commit,pushed=True)
            except subprocess.CalledProcessError:
                live.git(checkout,'fetch','--quiet','origin','main')
                if live.git(checkout,'rev-parse','origin/main') == base or attempt == 3: raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init','upsert','expire','check','recover','status'])
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('--operation-id')
    mode = parser.add_mutually_exclusive_group(); mode.add_argument('--check',action='store_true'); mode.add_argument('--push',action='store_true')
    args = parser.parse_args()
    if args.command == 'status':
        print((ROOT / 'public' / CURRENT).read_text()); return
    payload = json.loads(args.input.read_text()) if args.input else dict(schemaVersion=1,operationId=args.operation_id)
    if args.command != 'recover': require(payload.get('operationId'), 'stable --operation-id or input operationId required')
    result = push_operation(ROOT,args.command,payload) if args.push else execute(ROOT,args.command,payload,args.check)[0]
    print(encoded(result))


if __name__ == '__main__':
    try: main()
    except (ValueError,AssertionError,KeyError,TypeError,subprocess.CalledProcessError) as error:
        print(f'Not published: {error}',file=sys.stderr); sys.exit(1)
