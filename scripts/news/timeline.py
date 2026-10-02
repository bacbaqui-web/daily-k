"""Persistent issue histories derived from immutable briefing editions."""
import copy
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from archive import edition_order, edition_path

STAGES = {'예정', '발표', '검토', '확정', '시행', '결과', '후속', '보도', '분석', '정정', '철회'}
SLUG = r'[a-z0-9][a-z0-9-]{0,119}'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def day(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'Invalid timeline event date')
    return date.fromisoformat(value)


def reference(edition, story):
    return {'editionId': edition['id'], 'storyId': story['id']}


def same_issue(a, b):
    issue = a.get('timeline', {}).get('issueId')
    return bool(issue and issue == b.get('timeline', {}).get('issueId'))


def validate_timeline(story, prior, cutoff):
    t = story.get('timeline')
    require(isinstance(t, dict), 'Missing timeline metadata')
    require(isinstance(t.get('issueId'), str) and re.fullmatch(SLUG, t['issueId']), 'Invalid timeline issue ID')
    require(isinstance(t.get('issueTitle'), str) and bool(t['issueTitle'].strip()), 'Missing timeline issue title')
    require(t.get('stage') in STAGES, 'Invalid timeline stage')
    require(isinstance(t.get('change'), str) and len(t['change'].strip()) >= 15, 'Explain the timeline change')
    require(all(k in t for k in ('eventDate', 'eventEndDate', 'eventTimezone')), 'Explicit event date, end date and timezone required (null if unknown)')
    start, end, tz = t['eventDate'], t['eventEndDate'], t['eventTimezone']
    if start is None:
        require(end is None and tz is None and story.get('eventAt') is None, 'Unknown event dates must stay unknown')
    else:
        start_day = day(start)
        require(isinstance(tz, str), 'Known event date needs its source timezone')
        try:
            zone = ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Invalid event timezone') from None
        if end is not None:
            require(day(end) >= start_day, 'Timeline end precedes event start')
        if t['stage'] not in ('예정', '검토'):
            require(day(end or start) <= cutoff.astimezone(zone).date(), 'Future event cannot be presented as completed')
        if story.get('eventAt'):
            at = datetime.fromisoformat(story['eventAt'].replace('Z', '+00:00'))
            require(at.tzinfo is not None, 'Event time needs a timezone')
            require(start_day <= at.astimezone(zone).date() <= day(end or start), 'Event timestamp disagrees with timeline dates')
    matches = [(b, s) for b, s in prior if same_issue(story, s)]
    require(all(s['timeline']['issueTitle'] == t['issueTitle'] for _, s in matches), 'Reuse the existing issue title')
    correction = t.get('correctionOf')
    if t['stage'] in ('정정', '철회'):
        require(isinstance(correction, dict), 'Corrections must identify the original story')
        require(any(reference(b, s) == correction for b, s in matches), 'Correction target must exist in the same issue')
    else:
        require(correction is None, 'Only corrections or retractions may supersede earlier records')
    follow = story.get('followUp')
    if follow:
        target = [(b, s) for b, s in prior if reference(b, s) == {k: follow.get(k) for k in ('editionId', 'storyId')}]
        require(len(target) == 1, 'Follow-up target is missing')
        old = target[0][1]
        if old.get('timeline'):
            require(same_issue(story, old), 'Follow-up must keep its issue ID')


def build_timelines(editions):
    """All history, no retention cutoff. Rebuilding never appends duplicate events."""
    issues, seen, unlinked = {}, set(), 0
    ordered = sorted(editions, key=edition_order)
    prior = []
    for edition in ordered:
        cutoff = datetime.fromisoformat((edition['cutoffAt'] or edition['generatedAt']).replace('Z', '+00:00'))
        for story in edition['stories']:
            entry_id = f"{edition['id']}/{story['id']}"
            require(entry_id not in seen, 'Duplicate archived timeline record')
            seen.add(entry_id)
            if not story.get('timeline'):
                unlinked += 1  # Legacy records are preserved, never guessed into an issue.
                continue
            validate_timeline(story, prior, cutoff)
            t = story['timeline']
            issue = issues.setdefault(t['issueId'], {'schemaVersion': 1, 'id': t['issueId'], 'title': t['issueTitle'], 'entries': []})
            require(issue['title'] == t['issueTitle'], 'Conflicting titles for the same issue')
            previous = issue['entries'][-1] if issue['entries'] else None
            entry = {
                'id': entry_id, **reference(edition, story), 'editionDate': edition['date'], 'edition': edition['edition'],
                'coveredAt': None if edition.get('archive') else edition['generatedAt'], 'coveredOn': edition['date'], 'publishedAt': story['publishedAt'],
                'eventAt': story.get('eventAt'), 'eventDate': t['eventDate'], 'eventEndDate': t['eventEndDate'],
                'eventTimezone': t['eventTimezone'], 'eventTimeNote': story['eventTimeNote'],
                'stage': t['stage'], 'change': t['change'], 'title': story['title'], 'category': story['category'],
                'status': story['status'], 'summary': copy.deepcopy(story['summary']),
                'keyFacts': copy.deepcopy(story['keyFacts']), 'uncertainty': story['uncertainty'],
                'sources': copy.deepcopy(story['sources']),
                'briefingPath': edition_path(edition),
                'previous': {k: previous[k] for k in ('editionId', 'storyId')} if previous else None,
                'followUp': copy.deepcopy(story.get('followUp')),
                'correctionOf': copy.deepcopy(t.get('correctionOf')), 'supersededBy': [],
            }
            if edition.get('archive'):
                entry['archive'] = {**copy.deepcopy(story['archive']), 'sourceDocument': edition['archive']['sourceDocument'], 'importedAt': edition['archive']['importedAt']}
            if t.get('correctionOf'):
                original = next(e for e in issue['entries'] if {k: e[k] for k in ('editionId', 'storyId')} == t['correctionOf'])
                original['supersededBy'].append({**reference(edition, story), 'stage': t['stage']})
            issue['entries'].append(entry)
        prior.extend((edition, story) for story in edition['stories'])
    updated = max((b.get('updatedAt', b['generatedAt']) for b in ordered), default=None)
    index = {'schemaVersion': 1, 'updatedAt': updated, 'editionCount': len(ordered), 'storyCount': len(seen), 'unlinkedStoryCount': unlinked, 'issues': []}
    files = {}
    for issue_id, issue in sorted(issues.items()):
        entries = issue['entries']
        first, latest = entries[0], entries[-1]
        index['issues'].append({
            'id': issue_id, 'title': issue['title'], 'categories': sorted({e['category'] for e in entries}),
            'firstCoveredAt': first['coveredAt'], 'lastCoveredAt': latest['coveredAt'], 'eventCount': len(entries),
            'firstCoveredDate': first['coveredOn'], 'lastCoveredDate': latest['coveredOn'],
            'latest': {**{k: latest[k] for k in ('editionId', 'storyId', 'title', 'stage', 'change')}, 'archive': bool(latest.get('archive'))}, 'path': f'{issue_id}.json',
        })
        # Calendar dates retain their source timezone; unknown dates are placed last.
        issue['entries'] = sorted(entries, key=lambda e: (e['eventDate'] is None, e['eventDate'] or '', e['eventAt'] or '', e['coveredOn'], e['edition'], e['id']))
        issue['updatedAt'] = updated
        files[f'issues/{issue_id}.json'] = issue
    index['issues'].sort(key=lambda i: (i['lastCoveredDate'], i['lastCoveredAt'] or '', i['id']), reverse=True)
    files['issues/index.json'] = index
    return files
