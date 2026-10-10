#!/usr/bin/env python3
"""Researched input only. No fetching, scheduling, credentials, or invented times.

One local lock + a recoverable write-ahead transaction; remote publication uses
fast-forward CAS in an isolated clone and replays the operation on the latest main.
"""
import argparse
import copy
from datetime import datetime, timedelta
import fcntl
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
KST = ZoneInfo('Asia/Seoul')
CURRENT = 'data/live/current.json'
SLUG = r'[a-z0-9][a-z0-9-]{0,119}'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def stamp(value):
    require(isinstance(value, str), 'timestamp required')
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(value.tzinfo is not None, 'timestamp needs timezone')
    return value.astimezone(KST)


def iso(value):
    return value.astimezone(KST).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def slug(value):
    require(isinstance(value, str) and re.fullmatch(SLUG, value), 'invalid stable ID')
    return value


def url(value):
    require(isinstance(value, str) and value == value.strip(), 'URL required')
    p = urlsplit(value)
    host = p.hostname or ''
    require(p.scheme in ('http', 'https') and '.' in host and not p.username and not p.password,
            'public HTTP(S) URL required')
    require(not host.endswith(('.', '.local', '.localhost')), 'public hostname required')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return value
    raise ValueError('IP address not allowed in public source/media URL')


def canonical(value):
    p = urlsplit(url(value))
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.startswith('utm_') and k not in ('fbclid', 'gclid')]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), urlencode(sorted(query)), ''))


def text(value, name, limit=1200, empty=False):
    require(isinstance(value, str) and (empty or value.strip()) and len(value) <= limit,
            f'{name}: nonempty text up to {limit} characters required')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMUNITY = load_module('community_publisher', ROOT / 'scripts/community/publish.py')
sys.path.insert(0, str(ROOT / 'scripts/news'))
NEWS = load_module('news_publisher', ROOT / 'scripts/news/publish.py')


def validate_sources(sources, now, last):
    require(isinstance(sources, list) and sources, 'verified sources required')
    seen = set()
    for source in sources:
        key = canonical(source['url'])
        require(key not in seen, 'duplicate source URL')
        seen.add(key)
        text(source.get('name'), 'source.name', 120)
        text(source.get('title'), 'source.title', 300)
        text(source.get('limitations'), 'source.limitations')
        verified = stamp(source['verifiedAt'])
        require(verified <= last <= now, 'source verification cannot be future or after item verification')
        require('publishedAt' in source, 'publishedAt must be a verified time or null')
        if source['publishedAt'] is not None:
            require(stamp(source['publishedAt']) <= verified, 'publication after verification')
        require(source.get('platform') in ('aagag', 'community', 'dcinside', 'instagram', 'x', 'other'), 'source.platform invalid')
        require(source.get('region') in ('KR', 'unknown'), 'region must be KR or unknown')
        if source['region'] == 'KR':
            url(source.get('regionEvidenceUrl'))
        else:
            require(source.get('regionEvidenceUrl') is None, 'unknown region has no verified region evidence')
        if source['platform'] == 'instagram':
            require(source['region'] == 'unknown', 'Instagram is auxiliary popularity data, not a Korean ranking')
        start, end = source.get('periodStart'), source.get('periodEnd')
        require((start is None) == (end is None), 'period needs both endpoints or both null')
        if start is not None:
            require(stamp(start) < stamp(end) <= verified, 'invalid aggregation period')
        quotes = source.get('quotes', [])
        require(isinstance(quotes, list) and all(isinstance(q, str) for q in quotes), 'quotes must be text array')
        require(sum(len(t.split()) for t in [source['title'], *quotes]) <= 25, 'source title + quotes exceed 25 words')
    return seen


def validate_item(item, now):
    require(__debug__, 'run Python without -O: inherited community checks must remain enabled')
    slug(item.get('id'))
    require(item.get('kind') in ('topic', 'community'), 'kind must be topic or community')
    text(item.get('topicKey'), 'topicKey', 200)
    text(item.get('title'), 'title', 300)
    text(item.get('summary'), 'summary', 1200, empty=item['kind'] == 'community')
    for key in ('limitations', 'selectionReason'):
        text(item.get(key), key)
    require(item.get('safetyChecked') is True and item.get('rightsChecked') is True,
            'human safety and copyright review required')
    first, last = stamp(item['firstObservedAt']), stamp(item['lastVerifiedAt'])
    require(first <= last <= now, 'invalid actual observation times')
    require(type(item.get('expectedRevision')) is int and item['expectedRevision'] >= 0, 'expectedRevision required')
    if item.get('canonicalUrl') is not None:
        canonical(item['canonicalUrl'])
    sources = validate_sources(item.get('sources'), now, last)
    if item.get('canonicalUrl'):
        require(canonical(item['canonicalUrl']) in sources, 'canonicalUrl must be a verified source')
    titles = [item['title'], *[s['title'] for s in item['sources']]]
    require(not any(COMMUNITY.has_retired_tag(t) for t in titles), 'excluded ㅇㅎ/ㅎㅂ/ㅇㅎㅂ title')
    observations = item.get('observations')
    require(isinstance(observations, list), 'observations array required (empty if unverified)')
    for observation in observations:
        require(canonical(observation['sourceUrl']) in sources, 'observation source not verified')
        require(first <= stamp(observation['observedAt']) <= last, 'observation time outside verified interval')
        for key in ('metric', 'unit', 'scope'):
            text(observation.get(key), 'observation.' + key, 600)
        value = observation.get('value')
        require(value is None or (type(value) in (int, float) and math.isfinite(value) and value >= 0),
                'unverified metric is null; numeric values must be finite and nonnegative')
    if item['kind'] == 'community':
        story = item.get('content')
        require(isinstance(story, dict), 'community.content needs existing schema v2 story')
        require(item.get('canonicalUrl') and urlsplit(item['canonicalUrl']).hostname in ('aagag.com', 'www.aagag.com'),
                'macro community item requires actual aagag canonical URL')
        require(story.get('id') == item['id'] and story.get('title') == item['title'] and story.get('topicKey') == item['topicKey'], 'content identity mismatch')
        require(story.get('category') == '유머', 'macro path is verified humor only; use topic for editorial discoveries')
        require(item['summary'] == '', 'do not reproduce or summarize community body')
        # Reuse the existing complete media, quote, title and comment validations.
        # Source age cutoff is a legacy edition rule, not an ingestion rule.
        scratch = copy.deepcopy(story)
        for source in scratch.get('sources', []):
            require(canonical(source['url']) in sources, 'content source missing observation metadata')
            source['publishedAt'] = None
        cutoff = now.replace(hour=8, minute=30, second=0, microsecond=0)
        if cutoff > now:
            cutoff -= timedelta(days=1)
        copies = [dict(scratch, id=f'validation-{i}') for i in range(3)]
        COMMUNITY.validate({'schemaVersion': 2, 'timezone': 'Asia/Seoul', 'id': cutoff.date().isoformat() + '-am',
                            'date': cutoff.date().isoformat(), 'edition': 'am', 'cutoffAt': iso(cutoff),
                            'generatedAt': iso(now), 'overview': [], 'stories': copies})
        for field in ('commentsVerifiedAt', 'bodyImagesVerifiedAt', 'sourceStatsVerifiedAt'):
            if story.get(field):
                require(stamp(story[field]) <= last, field + ' is after lastVerifiedAt')
        for field in ('imageUrl', 'videoUrl', 'videoPosterUrl'):
            if story.get(field):
                url(story[field])
    else:
        require('content' not in item, 'topic cannot carry a copied community body')
    return item


def deadline(edition_id):
    require(isinstance(edition_id, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}-(am|pm)', edition_id), 'invalid edition ID')
    return stamp(edition_id[:10] + ('T09:00:00+09:00' if edition_id.endswith('-am') else 'T21:00:00+09:00'))


def window_for(now):
    end = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now >= end:
        end += timedelta(hours=12)
    if now >= end:
        end += timedelta(hours=12)
    return {'id': end.date().isoformat() + ('-am' if end.hour == 9 else '-pm'),
            'opensAt': iso(end - timedelta(hours=12)), 'scheduledFor': iso(end),
            'items': [], 'checks': [], 'news': None}


def initial():
    return {'schemaVersion': 1, 'timezone': 'Asia/Seoul', 'activatedAt': None, 'updatedAt': None,
            'windows': [], 'snapshots': [], 'corrections': [], 'registry': {}, 'operations': {}}


def advance(state, now):
    if not state['windows']:
        state['windows'].append(window_for(now))
    while stamp(state['windows'][-1]['scheduledFor']) <= now:
        state['windows'].append(window_for(stamp(state['windows'][-1]['scheduledFor'])))
    return state['windows'][-1]


def validate_check(check, now):
    slug(check.get('id'))
    require(check.get('channel') in ('community', 'topics', 'news'), 'invalid check channel')
    require(check.get('status') in ('ok', 'empty', 'blocked', 'failed', 'partial'), 'invalid check status')
    require(stamp(check['checkedAt']) <= now, 'check cannot be in the future')
    text(check.get('source'), 'check.source', 200)
    text(check.get('note'), 'check.note')
    require(check.get('count') is None or type(check.get('count')) is int and check['count'] >= 0, 'check count invalid')
    require(check['status'] != 'empty' or check.get('count') == 0, 'empty check requires count 0')


def check_legacy_community_duplicate(root, item):
    """Do not relaunch a recently published legacy post as a new macro discovery."""
    index_path = root / 'public/data/community/index.json'
    if item['kind'] != 'community' or not index_path.exists():
        return
    entries = json.loads(index_path.read_text())['editions'][:14]
    for entry in entries:
        relative = Path(entry['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe legacy edition path')
        prior = json.loads((index_path.parent / relative).read_text())
        for story in prior['stories']:
            require(item['topicKey'] != story.get('topicKey') and
                    canonical(item['canonicalUrl']) not in {canonical(s['url']) for s in story['sources']},
                    'recent legacy community post repeated; preserve its existing archive')


def news_files(root, brief, finalized_at, record_id):
    # Existing edition and long-term issue builders are reused on an isolated copy.
    with tempfile.TemporaryDirectory(prefix='daily-k-news-') as tmp:
        staging = Path(tmp)
        if (root / 'public/data/news').exists():
            shutil.copytree(root / 'public/data/news', staging / 'public/data/news')
        else:
            (staging / 'public/data/news').mkdir(parents=True)
        draft = dict(brief, finalizedAt=finalized_at, recordId=record_id, scheduledFor=iso(deadline(record_id)))
        _, paths = NEWS.publish(draft, root=staging, now=stamp(finalized_at))
        return {p: json.loads((staging / p).read_text()) for p in paths}


def plan(root, command, payload, now):
    current = root / 'public' / CURRENT
    state = json.loads(current.read_text()) if current.exists() else initial()
    require(state.get('schemaVersion') == 1 and state.get('timezone') == 'Asia/Seoul', 'unsupported live state')
    if command in ('finalize', 'finalize-news'):
        require('brief' not in payload, 'finalize cannot accept or ignore brief; use publish-news with the researched brief')
        require(str(payload.get('edition',''))[:10] < NEWS.SINGLE_RUN_START,
                'Single-run news uses publish-news; separate finalization is retired')
    if command == 'stage-news':
        require(payload.get('brief',{}).get('date','') < NEWS.SINGLE_RUN_START,
                'Advance preparation is retired; use publish-news at or after 09:00/21:00')
    rolling = (root / 'public/data/humor/current.json').exists()
    if rolling:
        require(command != 'finalize', 'rolling humor enabled: use finalize-news; legacy all-channel finalization is disabled')
        require(command != 'upsert', 'community/topics no longer enter edition windows; use scripts/humor/manage.py for verified humor')
        require(command != 'check' or payload.get('check', {}).get('channel') == 'news', 'edition checks are news-only; use rolling humor check')
    operation_id = slug(payload['operationId'])
    operation_hash = digest({'command': command, 'payload': payload})
    old = state['operations'].get(operation_id)
    if old:
        require(old['hash'] == operation_hash, 'operationId reused with different content')
        return {}, dict(old['result'], replayed=True)
    require(payload.get('schemaVersion') == 1, 'input schemaVersion must be 1')
    if command == 'publish-news':
        require(set(payload) <= {'schemaVersion','operationId','brief'}, 'publish-news accepts schemaVersion, operationId and brief only')
        brief = payload['brief']
        require(brief.get('date','') >= NEWS.SINGLE_RUN_START, 'Single-run contract starts 2026-10-11; never backfill old editions with a new cutoff')
        edition = brief['id']
        cutoff = deadline(edition)
        require(cutoff <= now, 'Cannot publish before the 09:00/21:00 cutoff')
        require(stamp(brief['cutoffAt']) == cutoff, 'Input cutoff must match the explicit target edition')
        require(not any(k in brief for k in ('finalizedAt','scheduledFor','recordId','publicationMode','newsInputSha256','publishedAt','deployedAt')),
                'Publication metadata is recorded by the publisher, not supplied or backdated')
        prior = next((s for s in state['snapshots'] if s['id'] == edition), None)
        if prior:
            value = json.loads((root / 'public/data/live' / prior['path']).read_text())
            require(digest(value) == prior['sha256'], 'immutable snapshot was modified')
            require(value.get('newsInputSha256') == digest(brief), 'Edition already finalized with different input; preserve it and publish an explicit correction')
            return {}, {'id': edition, 'replayed': True, 'sha256': prior['sha256']}
        history = NEWS.load_editions(root / 'public/data/news')
        require(not any(b['id'] == edition for b in history), 'News edition already published; never overwrite')
        validated = NEWS.validate(brief, history, now=now)
        recorded = iso(now)
        snapshot = dict(window_for(cutoff-timedelta(microseconds=1)), schemaVersion=1, timezone='Asia/Seoul',
                        channel='news', publicationMode='single-run', status='finalized', finalizedAt=recorded,
                        activatedAt=state['activatedAt'] or recorded, empty=False, newsInputSha256=digest(brief),
                        news={'brief': validated, 'recordedAt': recorded, 'revision': 1})
        path = f'snapshots/{edition}.json'
        writes = news_files(root, validated, recorded, edition)
        for folder in ('public','docs'):
            writes[f'{folder}/data/live/{path}'] = snapshot
        ref = {k: snapshot[k] for k in ('id','opensAt','scheduledFor','finalizedAt','empty')}
        ref.update(path=path, sha256=digest(snapshot), itemCount=0, hasNews=True)
        state['snapshots'].append(ref)
        state['snapshots'].sort(key=lambda s:s['scheduledFor'], reverse=True)
        # No preparation window is created or advanced. Legacy windows are preserved.
        state['activatedAt'] = state['activatedAt'] or recorded
        result = {'operationId':operation_id, 'id':edition, 'windowId':edition, 'recordedAt':recorded, 'sha256':ref['sha256']}
        return finish_plan(state, command, payload, writes, result, now)
    if command in ('finalize', 'finalize-news'):
        prior = next((s for s in state['snapshots'] if s['id'] == payload['edition']), None)
        if prior:
            value = json.loads((root / 'public/data/live' / prior['path']).read_text())
            require(digest(value) == prior['sha256'], 'immutable snapshot was modified')
            return {}, {'id': prior['id'], 'replayed': True, 'sha256': prior['sha256']}
        require(deadline(payload['edition']) <= now, 'cannot finalize before scheduledFor')
        require(any(w['id'] == payload['edition'] for w in state['windows']), 'no recorded window; do not invent historical collection')
    state['activatedAt'] = state['activatedAt'] or iso(now)
    active = advance(state, now)
    writes = {}
    result = {'operationId': operation_id, 'windowId': active['id'], 'recordedAt': iso(now)}
    if command == 'upsert':
        items = payload.get('items')
        require(isinstance(items, list) and items, 'nonempty items required; use check to record empty/failed collection')
        require(len({i.get('id') for i in items}) == len(items), 'duplicate IDs in batch')
        for item in items:
            validate_item(item, now)
            old = state['registry'].get(item['id'])
            require(item['expectedRevision'] == (old['revision'] if old else 0), 'revision conflict; read latest current.json')
            if not old:
                check_legacy_community_duplicate(root, item)
            identity = (item['kind'], item['topicKey'])
            link = canonical(item['canonicalUrl']) if item.get('canonicalUrl') else None
            for other_id, registered in state['registry'].items():
                require(other_id == item['id'] or (item['topicKey'] != registered['topicKey'] and
                        (not link or link != registered['canonicalUrl'])), 'duplicate topic or original URL; reuse stable ID')
            if old:
                require(identity == (old['kind'], old['topicKey']) and link == old['canonicalUrl'], 'stable identity cannot be changed')
                require(stamp(item['firstObservedAt']) == stamp(old['firstObservedAt']), 'firstObservedAt is immutable')
                require(stamp(item['lastVerifiedAt']) >= stamp(old['lastVerifiedAt']), 'stale verification update')
            value = {k: v for k, v in item.items() if k != 'expectedRevision'}
            value.update(revision=item['expectedRevision'] + 1, recordedAt=iso(now),
                         firstRecordedAt=old['firstRecordedAt'] if old else iso(now))
            active['items'] = [i for i in active['items'] if i['id'] != item['id']] + [value]
            state['registry'][item['id']] = {k: value[k] for k in ('kind', 'topicKey', 'revision', 'firstObservedAt', 'lastVerifiedAt', 'firstRecordedAt')}
            state['registry'][item['id']]['canonicalUrl'] = link
        result['items'] = [{'id': i['id'], 'revision': state['registry'][i['id']]['revision']} for i in items]
    elif command == 'check':
        check = payload['check']
        validate_check(check, now)
        require(not any(c['id'] == check['id'] for w in state['windows'] for c in w['checks']), 'duplicate check ID')
        active['checks'].append(dict(check, recordedAt=iso(now)))
    elif command == 'stage-news':
        brief = payload['brief']
        require(stamp(brief['generatedAt']) <= now and stamp(brief.get('updatedAt', brief['generatedAt'])) <= now,
                'news generation must be an actual time, not a future estimate')
        require(brief['id'] == active['id'], 'news must be prepared in its active target window; no backdated late insertion')
        require(payload.get('expectedRevision') == (active['news']['revision'] if active['news'] else 0), 'news revision conflict')
        history = NEWS.load_editions(root / 'public/data/news')
        require(not any(b['id'] == brief['id'] for b in history), 'news edition already published')
        brief = NEWS.validate(brief, history, now=now)
        active['news'] = {'brief': brief, 'recordedAt': iso(now), 'revision': payload['expectedRevision'] + 1}
    elif command in ('finalize', 'finalize-news'):
        target = next(w for w in state['windows'] if w['id'] == payload['edition'])
        selected = dict(target, items=[], checks=[c for c in target['checks'] if c['channel'] == 'news']) if command == 'finalize-news' else target
        snapshot = dict(selected, schemaVersion=1, timezone='Asia/Seoul', status='finalized', finalizedAt=iso(now),
                        activatedAt=state['activatedAt'], empty=not selected['items'] and selected['news'] is None)
        if command == 'finalize-news': snapshot['channel'] = 'news'
        path = f"snapshots/{target['id']}.json"
        for folder in ('public', 'docs'):
            writes[f'{folder}/data/live/{path}'] = snapshot
        ref = {k: snapshot[k] for k in ('id', 'opensAt', 'scheduledFor', 'finalizedAt', 'empty')}
        ref.update(path=path, sha256=digest(snapshot), itemCount=len(selected['items']), hasNews=selected['news'] is not None)
        state['snapshots'].append(ref)
        state['snapshots'].sort(key=lambda s: s['scheduledFor'], reverse=True)
        # Preserve pre-transition humor/topics byte-for-byte as an unfrozen legacy
        # window; the new snapshot contains only news. Rolling data is independent.
        if command == 'finalize-news' and (target['items'] or any(c['channel'] != 'news' for c in target['checks'])):
            target['news'] = None
            target['checks'] = [c for c in target['checks'] if c['channel'] != 'news']
        else:
            state['windows'].remove(target)
        if selected['news']:
            writes.update(news_files(root, selected['news']['brief'], iso(now), target['id']))
        result.update(id=target['id'], sha256=ref['sha256'])
    elif command == 'correct':
        correction = payload['correction']
        slug(correction.get('id'))
        target = next((s for s in state['snapshots'] if s['id'] == correction.get('snapshotId')), None)
        require(target, 'correction must reference an existing immutable snapshot')
        original = json.loads((root / 'public/data/live' / target['path']).read_text())
        require(digest(original) == target['sha256'], 'snapshot hash mismatch')
        ids = {i['id'] for i in original['items']}
        if original['news']:
            ids.update(s['id'] for s in original['news']['brief']['stories'])
        require(correction.get('itemId') in ids, 'correction item missing in snapshot')
        require(not any(c['id'] == correction['id'] for c in state['corrections']), 'correction ID exists')
        require(correction.get('action') in ('correction', 'withdrawal'), 'invalid correction action')
        for k in ('reason', 'text'):
            text(correction.get(k), k)
        verified = stamp(correction['verifiedAt'])
        validate_sources(correction['sources'], now, verified)
        require(correction.get('safetyChecked') is True and correction.get('rightsChecked') is True, 'correction needs editorial review')
        value = dict(correction, recordedAt=iso(now))
        state['corrections'].append(value)
        for folder in ('public', 'docs'):
            writes[f"{folder}/data/live/corrections/{correction['id']}.json"] = value
    elif command != 'init':
        raise ValueError('unknown command')
    return finish_plan(state, command, payload, writes, result, now)


def finish_plan(state, command, payload, writes, result, now):
    operation_id = payload['operationId']
    operation_hash = digest({'command':command, 'payload':payload})
    state['updatedAt'] = iso(now)
    state['operations'][operation_id] = {'hash': operation_hash, 'result': result}
    # Immutable operation records preserve superseded live revisions, too.
    event = {'command': command, 'payload': payload, 'recordedAt': iso(now), 'result': result}
    for folder in ('public', 'docs'):
        writes[f'{folder}/data/live/events/{operation_id}.json'] = event
        writes[f'{folder}/{CURRENT}'] = state
    return writes, result


def control_dir(root):
    # Works in ordinary clones and managed worktrees; stays out of published data.
    return Path(subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--absolute-git-dir'], text=True).strip())


def atomic_write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.live-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def complete_transaction(root, journal):
    transaction = json.loads(journal.read_text())
    # Preflight every immutable path before any mutable write, including recovery.
    for relative, body in transaction['writes'].items():
        path = root / relative
        require(relative.startswith(('public/data/', 'docs/data/')) and '..' not in Path(relative).parts, 'unsafe transaction path')
        immutable = any(part in relative for part in ('/snapshots/', '/corrections/', '/events/'))
        require(not immutable or not path.exists() or path.read_text() == body, 'refusing immutable record overwrite')
    # encoded() sorts object keys; explicitly restore dependency order on replay.
    def priority(relative):
        return 2 if relative.endswith(CURRENT) else 1 if relative.endswith('/index.json') else 0
    for relative in sorted(transaction['writes'], key=priority):
        atomic_write(root / relative, transaction['writes'][relative])
    journal.unlink()


def execute(root, command, payload, check=False, now=None):
    control = control_dir(root)
    with (control / 'daily-k-live.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        journal = control / 'daily-k-live.pending.json'
        if journal.exists():
            require(not check, 'pending transaction: run recover before checking')
            complete_transaction(root, journal)
        if command == 'recover':
            return {'recovered': True}, []
        writes, result = plan(root, command, payload, now or datetime.now(KST))
        if not check and writes:
            # Manifests last, so no reader sees a dangling snapshot reference.
            ordered = sorted(writes, key=lambda p: p.endswith(CURRENT))
            atomic_write(journal, encoded({'writes': {p: encoded(writes[p]) for p in ordered}}))
            complete_transaction(root, journal)
        return dict(result, checkedOnly=check), list(writes)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.PIPE).strip()


def push_operation(root, command, payload):
    origin = git(root, 'remote', 'get-url', 'origin')
    with tempfile.TemporaryDirectory(prefix='daily-k-publish-') as tmp:
        checkout = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', str(root), str(checkout)], check=True)
        git(checkout, 'remote', 'set-url', 'origin', origin)
        for attempt in range(4):
            git(checkout, 'fetch', '--quiet', 'origin', 'main')
            base = git(checkout, 'rev-parse', 'origin/main')
            git(checkout, 'checkout', '--detach', '--force', base)
            result, paths = execute(checkout, command, payload)
            if not paths:
                return dict(result, commit=base, pushed=True)
            git(checkout, 'add', '--', *paths)
            git(checkout, 'commit', '-m', f"Live {command}: {payload['operationId']}", '--', *paths)
            commit = git(checkout, 'rev-parse', 'HEAD')
            try:
                git(checkout, 'push', 'origin', 'HEAD:main')
                return dict(result, commit=commit, pushed=True)
            except subprocess.CalledProcessError:
                # Never rebase generated manifests or force push. Reapply intent.
                git(checkout, 'fetch', '--quiet', 'origin', 'main')
                if git(checkout, 'rev-parse', 'origin/main') == base or attempt == 3:
                    raise
        raise ValueError('remote changed repeatedly; retry with the same operationId')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'upsert', 'check', 'stage-news', 'publish-news', 'finalize', 'finalize-news', 'correct', 'recover', 'status'])
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('--edition')
    parser.add_argument('--operation-id')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--push', action='store_true')
    args = parser.parse_args()
    require(args.command != 'publish-news' or args.input is not None and args.edition is None,
            'publish-news requires an input envelope; target edition is brief.id, not --edition')
    if args.command == 'status':
        state = json.loads((ROOT / 'public' / CURRENT).read_text())
        print(encoded({k: state[k] for k in ('activatedAt', 'updatedAt', 'windows', 'snapshots')}))
        return
    payload = json.loads(args.input.read_text()) if args.input else {
        'schemaVersion': 1, 'operationId': args.operation_id or (f'{args.command}-{args.edition}' if args.command in ('finalize', 'finalize-news') else 'initialize-live-v1')}
    if args.command in ('finalize', 'finalize-news'):
        payload['edition'] = args.edition
    result = push_operation(ROOT, args.command, payload) if args.push else execute(ROOT, args.command, payload, args.check)[0]
    print(encoded(result))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, AssertionError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'Not published: {error}', file=sys.stderr)
        sys.exit(1)
