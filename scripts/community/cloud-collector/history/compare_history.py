#!/usr/bin/env python3
"""Offline publication comparison. Reads inputs only; never drops candidate rows.

A fresh source scan does not refresh publication history. Recapture the public
GitHub snapshot separately when the repository changes.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
DEFAULT_RUN = HERE.parent / 'runs/20261009T020332Z'
TRACKING = {'fbclid', 'gclid', 'dclid', 'msclkid', 'mc_cid', 'mc_eid'}


def canonical_id(value):
    if value is None:
        return None
    value = str(value).strip()
    if '://' in value:
        p = urlsplit(html.unescape(value))
        if (p.hostname or '').lower().removeprefix('www.') != 'aagag.com':
            return None
        value = dict(parse_qsl(p.query)).get('idx', '')
    m = re.fullmatch(r'(?:aagag[-_])?(\d+)(?:[_-]\d+)?', value)
    return m.group(1) if m else None


def normalize_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    value = html.unescape(value.strip())
    try:
        p = urlsplit(value)
        if p.scheme.lower() not in ('http', 'https') or not p.hostname:
            return None
        ident = canonical_id(value)
        if ident:
            return 'https://aagag.com/issue/?idx=' + ident
        host = p.hostname.lower()
        if p.port and not (p.scheme.lower() == 'https' and p.port == 443 or p.scheme.lower() == 'http' and p.port == 80):
            host += ':' + str(p.port)
        params = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                        if not k.lower().startswith('utm_') and k.lower() not in TRACKING)
        # Preserve non-aagag scheme/host and all nontracking query fields.
        return urlunsplit((p.scheme.lower(), host, p.path.rstrip('/') or '/', urlencode(params), ''))
    except (ValueError, TypeError):
        return None


def normalize_title(value):
    return ' '.join(unicodedata.normalize('NFC', str(value or '')).casefold().split())


def strings(value):
    if isinstance(value, str):
        return [value]
    return [x for x in value or [] if isinstance(x, str)]


def keys(record, supplemental=None):
    urls = strings(record.get('originalUrls'))
    urls += [record.get(k) for k in ('url', 'requestedUrl', 'originalURL', 'originalUrl', 'bodyImagesSourceUrl')]
    urls += [s.get('url') for s in record.get('sources', []) if isinstance(s, dict)]
    if supplemental:
        urls += [supplemental.get('url')]
    urls = {u for raw in urls if (u := normalize_url(raw))}
    topic_key = record.get('topicKey')
    if not isinstance(topic_key, str) or not topic_key.startswith(('aagag-', 'aagag_')):
        topic_key = None
    ids = {i for raw in [record.get('id'), record.get('requestedId'), record.get('canonicalId'), topic_key, *urls]
           if (i := canonical_id(raw))}
    titles = strings(record.get('titles')) + strings(record.get('sourceTitles')) + [record.get('title')]
    titles += [s.get('title') for s in record.get('sources', []) if isinstance(s, dict)]
    titles = {t for raw in titles if (t := normalize_title(raw))}
    media = strings(record.get('mediaUrls'))
    media += [record.get(k) for k in ('imageUrl', 'videoUrl', 'videoPosterUrl')]
    for field in ('media', 'bodyImages', 'images', 'videos'):
        for item in record.get(field, []) or []:
            media += [item] if isinstance(item, str) else [item.get('url'), item.get('src'), item.get('poster')]
    media = {u for raw in media if (u := normalize_url(raw))}
    return {'canonicalId': ids, 'originalUrl': urls, 'mediaUrl': media, 'title': titles}


def build_index(records):
    indexes = {key: defaultdict(set) for key in ('canonicalId', 'originalUrl', 'mediaUrl', 'title')}
    record_keys = []
    for pos, record in enumerate(records):
        k = keys(record)
        record_keys.append(k)
        for field, values in k.items():
            for value in values:
                indexes[field][value].add(pos)
    return indexes, record_keys


def compare(record, history, indexes, history_keys, supplemental=None):
    candidate_keys = keys(record, supplemental)
    matched = defaultdict(lambda: defaultdict(set))
    for field, values in candidate_keys.items():
        for value in values:
            for pos in indexes[field].get(value, []):
                matched[pos][field].add(value)
    matches = []
    for pos, flags in sorted(matched.items()):
        previous = history[pos]
        matches.append({'snapshotRecordIndex': pos, 'id': previous.get('id'),
                        'editionId': previous.get('editionId'), 'publicationClass': previous.get('publicationClass'),
                        'repositoryPath': previous.get('repositoryPath'), 'publicDataUrl': previous.get('publicDataUrl'),
                        'githubUrl': previous.get('githubUrl'),
                        'identityMatch': bool(flags.get('canonicalId') or flags.get('originalUrl')),
                        'matches': {field: sorted(values) for field, values in flags.items()}})
    identity = [m for m in matches if m['identityMatch']]
    extra = [m for m in matches if not m['identityMatch']]
    return {'canonicalIds': sorted(candidate_keys['canonicalId']), 'normalizedOriginalUrls': sorted(candidate_keys['originalUrl']),
            'alreadyPublishedIdentityMatch': bool(identity),
            'publishedCommunityEditionMatch': any(m['publicationClass'] == 'deployed_community_edition' for m in identity),
            'legacyPublicFeedMatch': any(m['publicationClass'] == 'legacy_public_feed' for m in identity),
            'mediaMatch': any('mediaUrl' in m['matches'] for m in matches),
            'titleMatch': any('title' in m['matches'] for m in matches),
            'additionalMediaOrTitleOnlyMatch': bool(extra), 'publicationMatches': matches}


def read_json_bytes(path):
    data = path.read_bytes()
    return json.loads(data), {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'byteSize': len(data)}


def load_run(run):
    names = ['summary.json', 'normalized-posts.json', 'candidates.json', 'all-threshold-qualifiers.json']
    optional = ['original-source-links.json', 'run.json']
    # Check both bytes and collection identities because checkpoint files are
    # replaced separately. Fail instead of silently comparing torn inputs.
    for attempt in range(5):
        loaded, metadata = {}, {}
        for name in names + [n for n in optional if (run / n).exists()]:
            loaded[name], metadata[name] = read_json_bytes(run / name)
        stable = all(hashlib.sha256((run / name).read_bytes()).hexdigest() == meta['sha256'] for name, meta in metadata.items())
        summary = loaded['summary.json']
        candidates = loaded['candidates.json']
        qualifiers = loaded['all-threshold-qualifiers.json']
        norm = loaded['normalized-posts.json']
        consistent = (summary.get('candidates') == len(candidates)
                      and summary.get('qualifiers') == len(qualifiers)
                      and summary.get('observedRecords') == len(norm)
                      and set(summary.get('candidateIDs', [])) == {r.get('id') for r in candidates})
        nmap = {canonical_id(r.get('canonicalId') or r.get('id')): r for r in norm}
        consistent &= all(nmap.get(canonical_id(r.get('canonicalId') or r.get('id'))) == r for r in candidates + qualifiers)
        if stable and consistent:
            return loaded, metadata
        time.sleep(0.2)
    raise RuntimeError('Run checkpoint changed or is inconsistent; rerun after checkpoint writing completes. No comparison written.')


def stats(rows):
    return {'count': len(rows),
            'alreadyPublishedIdentityOverlaps': sum(r['alreadyPublishedIdentityMatch'] for r in rows),
            'notMatchedByIdentityInSnapshot': sum(not r['alreadyPublishedIdentityMatch'] for r in rows),
            'communityEditionOverlaps': sum(r['publishedCommunityEditionMatch'] for r in rows),
            'legacyPublicFeedOverlaps': sum(r['legacyPublicFeedMatch'] for r in rows),
            'mediaMatchFlags': sum(r['mediaMatch'] for r in rows), 'titleMatchFlags': sum(r['titleMatch'] for r in rows),
            'additionalMediaOrTitleOnlyFlags': sum(r['additionalMediaOrTitleOnlyMatch'] for r in rows)}


def atomic_json(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def run_comparison(run, snapshot_path, output):
    loaded, inputs = load_run(run)
    snapshot, snapshot_meta = read_json_bytes(snapshot_path)
    history = snapshot['records']
    indexes, hkeys = build_index(history)
    candidates = loaded['candidates.json']
    qualifiers = loaded['all-threshold-qualifiers.json']
    candidate_ids = {canonical_id(r.get('canonicalId') or r.get('id')) for r in candidates}
    qualifier_ids = {canonical_id(r.get('canonicalId') or r.get('id')) for r in qualifiers}
    source_links = loaded.get('original-source-links.json', {})
    rows = []
    for row_index, record in enumerate(loaded['normalized-posts.json']):
        identity = canonical_id(record.get('canonicalId') or record.get('id'))
        result = compare(record, history, indexes, hkeys, source_links.get(identity))
        result.update({'inputRowIndex': row_index, 'id': record.get('id'), 'title': record.get('title'),
                       'isCandidate': identity in candidate_ids, 'isAllThresholdQualifier': identity in qualifier_ids,
                       'thresholdQualified': record.get('thresholdQualified'), 'inWindow': record.get('inWindow'),
                       'kCount': record.get('kCount'), 'commentCount': record.get('commentCount'),
                       'kCountVerified': record.get('kCountVerified'), 'inspectionComplete': record.get('inspectionComplete'),
                       'listedAt': record.get('listedAt'), 'observedAt': record.get('observedAt'),
                       'countScope': record.get('countScope'), 'oldCommentCount': record.get('oldCommentCount'),
                       'windowCommentCount': record.get('windowCommentCount'), 'postWindowCommentCount': record.get('postWindowCommentCount'),
                       'exclusions': record.get('exclusions', []), 'omittedByComparison': False})
        rows.append(result)
    selected_candidates = [r for r in rows if r['isCandidate']]
    selected_qualifiers = [r for r in rows if r['isAllThresholdQualifier']]
    assert len(selected_candidates) == len(candidates), 'Candidate identity duplication/loss'
    assert len(selected_qualifiers) == len(qualifiers), 'Qualifier identity duplication/loss'
    summary = loaded['summary.json']
    observed = sorted(r['observedAt'] for r in rows if r.get('observedAt'))
    current_edition = [r for r in history if r.get('editionId') == '2026-10-09-am']
    published_ids = set().union(*(k['canonicalId'] for k in hkeys)) if hkeys else set()
    output.mkdir(parents=True, exist_ok=True)
    report = {'schemaVersion': 1, 'generatedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
              'inputs': inputs, 'publishedSnapshot': snapshot_meta,
              'publishedSnapshotCapturedAt': snapshot['capturedAt'], 'publishedCommitSha': snapshot['commitSha'],
              'publicationScope': snapshot['publicationBasis'],
              'publishedRecordCount': len(history), 'publishedCanonicalIdCount': len(published_ids),
              'fixedListingWindow': summary['window'],
              'observationTimeRange': {'first': observed[0] if observed else None, 'last': observed[-1] if observed else None},
              'sourceCheckpointAt': summary.get('lastUpdatedAt'),
              'scanComplete': summary.get('complete', False),
              'listingCoverageComplete': summary.get('listingCoverageComplete', False),
              'nativeCommentCoverageComplete': summary.get('nativeCommentCoverageComplete', False),
              'missingIdsCount': len(summary.get('missingIds', [])),
              'incompleteIdsCount': len(summary.get('incompleteIDs', [])),
              'allObserved': stats(rows), 'allThresholdQualifiers': stats(selected_qualifiers), 'candidates': stats(selected_candidates),
              'old0830KSTEdition': {'editionId': '2026-10-09-am', 'cutoffAt': '2026-10-09T08:30:00+09:00',
                                    'publishedStoryCount': len(current_edition),
                                    'publishedIds': [r['id'] for r in current_edition],
                                    'commentsObservedAt': sorted({r['commentsObservedAt'] for r in current_edition if r.get('commentsObservedAt')})},
              'interpretation': ['Every input normalized row is retained. Identity matches are flags, never exclusions.',
                                 'Already published = canonical aagag identity OR normalized original/source URL matches in the captured deployed history.',
                                 'Media/title matches are review flags only and cannot establish identity alone.',
                                 'Nonmatches mean absent from this captured public history, not proof of never having appeared anywhere.',
                                 'Fixed 24-hour window is based on listing/relisting timestamps, not content creation or comment age.',
                                 'Literal ㅋ counts are cumulative at each actual observation, including older and post-cutoff comments.',
                                 'This later window and observation pass differs from the old 08:30 KST edition; new qualifiers cannot all be called misses in the original smaller run.',
                                 'Partial scan statistics remain provisional until the source scan completes.']}
    atomic_json(output / 'comparison-summary.json', report)
    atomic_json(output / 'all-observed-comparison.json', rows)
    atomic_json(output / 'all-threshold-comparison.json', selected_qualifiers)
    atomic_json(output / 'candidate-comparison.json', selected_candidates)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--snapshot', type=Path, default=HERE / 'published-history.snapshot.json')
    parser.add_argument('--output-dir', type=Path, default=None)
    args = parser.parse_args()
    result = run_comparison(args.run_dir.resolve(), args.snapshot.resolve(), args.output_dir or HERE / 'comparisons' / args.run_dir.name)
    print(json.dumps({k: result[k] for k in ('sourceCheckpointAt', 'scanComplete', 'allThresholdQualifiers', 'candidates', 'publishedCommitSha')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
