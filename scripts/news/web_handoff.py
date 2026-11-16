"""ChatGPT app handoff. No browser credentials, model calls, or billing fallback."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse
import oracle_runner as runner


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def cutoff(edition):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}-(am|pm)', edition):
        raise ValueError('Invalid edition ID')
    value = edition[:10] + ('T09:00:00+09:00' if edition.endswith('-am') else 'T21:00:00+09:00')
    datetime.fromisoformat(value)
    return value


@contextmanager
def locked():
    state = Path(os.environ.get('NEWS_STATE_DIR', '/home/ubuntu/daily-k-news/state'))
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield state


def sync():
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=runner.ROOT, text=True).strip():
        raise ValueError('Dirty checkout; refusing handoff')
    subprocess.run(['git', 'pull', '--ff-only'], cwd=runner.ROOT, check=True)


def published(edition):
    return (runner.ROOT / 'public/data/news' / edition[:10] / (edition[11:] + '.json')).exists()


def queue():
    edition = runner.target(datetime.now(runner.KST))
    with locked() as state:
        sync()
        if published(edition):
            print('Already published; no new request: ' + edition)
            return
        run = state / edition
        marker = run / 'awaiting-chatgpt.json'
        if not marker.exists():
            runner.save(marker, {'edition': edition, 'cutoffAt': cutoff(edition),
                                'queuedAt': datetime.now(runner.KST).isoformat(),
                                'generationMode': 'chatgpt-app', 'status': 'awaiting_result'})
        print('Awaiting verified ChatGPT result: ' + edition)


def validate_handoff(payload, review, history):
    brief = payload['brief']
    edition = brief['id']
    if brief.get('cutoffAt') != cutoff(edition):
        raise ValueError('Original scheduled cutoff required')
    if payload.get('operationId') != 'publish-news-' + edition:
        raise ValueError('Stable operationId required')
    if review.get('edition') != edition or review.get('approved') is not True:
        raise ValueError('Approved edition review required')
    if review.get('payloadSha256') != digest(payload):
        raise ValueError('Review does not cover this exact payload')
    if review.get('historySha256') != digest(history):
        raise ValueError('History changed; repeat duplicate review')
    if urlparse(review.get('conversationUrl', '')).hostname != 'chatgpt.com':
        raise ValueError('ChatGPT conversation provenance required')
    for key in ('responseCompletedAt', 'verifiedAt'):
        when = datetime.fromisoformat(review[key])
        if when.tzinfo is None or when > datetime.now(runner.KST):
            raise ValueError('Actual completed timestamps required')
    for key in ('factsChecked', 'publicationDatesChecked', 'eventDatesChecked', 'priorLeadAndReserveChecked'):
        if review.get(key) is not True:
            raise ValueError('Missing verification: ' + key)
    records = review.get('sources', [])
    if not records or any(s.get('accessible') is not True or s.get('factsSupported') is not True for s in records):
        raise ValueError('Every retained source must be accessible and support the facts')
    runner.check_sources(brief, {s['url'] for s in records})
    from publish import validate
    validate(brief, history)


def consume(payload_path, review_path, push=False):
    payload = json.loads(Path(payload_path).read_text())
    review = json.loads(Path(review_path).read_text())
    edition = payload['brief']['id']
    cutoff(edition)
    with locked() as state:
        sync()
        if published(edition):
            print('Already published; do not overwrite. Check delivery only: ' + edition)
            return
        run = state / edition
        history, _, _ = runner.histories(edition)
        validate_handoff(payload, review, history)
        if (run / 'publish-result.json').exists() or (run / 'publication.json').exists():
            raise ValueError('Existing publication transaction; reconcile it before recovery')
        if (run / 'attempted.json').exists():
            raise ValueError('Existing generation attempt; reconcile before handoff')
        command = [sys.executable, 'scripts/live/manage.py', 'publish-news', str(Path(payload_path).resolve())]
        subprocess.run(command + ['--check'], cwd=runner.ROOT, check=True)
        if not push:
            print('Verified handoff; no publication: ' + edition)
            return
        runner.save(run / 'attempted.json', {'edition': edition, 'cutoffAt': cutoff(edition),
                    'startedAt': datetime.now(runner.KST).isoformat(), 'generationMode': 'chatgpt-app'})
        runner.save(run / 'chatgpt-review.json', review)
        runner.save(run / 'publication.json', payload)
        command[3] = str(run / 'publication.json')
        result = subprocess.run(command + ['--push'], cwd=runner.ROOT, text=True, capture_output=True)
        runner.save(run / 'publish-result.json', {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode:
            raise ValueError('Publication failed; reconcile existing transaction before retry')
        runner.verify_delivery(edition, run)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', action='store_true')
    parser.add_argument('--payload')
    parser.add_argument('--review')
    parser.add_argument('--push', action='store_true')
    args = parser.parse_args()
    if args.queue and not (args.payload or args.review or args.push):
        queue()
    elif args.payload and args.review and not args.queue:
        consume(args.payload, args.review, args.push)
    else:
        parser.error('Use --queue OR --payload FILE --review FILE [--push]')
