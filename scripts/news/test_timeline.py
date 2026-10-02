import copy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from publish import KST, publish, validate
from test_publish import fixture, NOW
from timeline import build_timelines


def followup(edition='pm'):
    b = fixture(edition)
    for i, s in enumerate(b['stories']):
        s['summary'][0] += ' 발표된 확정 수치가 바뀌었습니다.'
        s['keyFacts']['metric'] = str(100 + i)
        s['followUp'] = dict(editionId='2026-10-02-am', storyId=f'topic-am-{i}', delta='아침 잠정 발표 이후 확정 수치가 새로 나왔습니다.')
        s['timeline']['stage'] = '결과'
    return b


class TimelineTests(unittest.TestCase):
    def test_metadata_required_for_new_editions(self):
        b = fixture(); del b['stories'][0]['timeline']
        with self.assertRaisesRegex(ValueError, 'Missing timeline'): validate(b, [], NOW)

    def test_issue_id_reuse_without_topic_or_title_match(self):
        old = fixture(); new = followup()
        new['stories'][0]['title'] = '관련 기업이 후속 조치를 결정했습니다'
        result = validate(new, [old], NOW)
        self.assertEqual(result['stories'][0]['timeline']['issueId'], 'issue-0')
        del new['stories'][0]['followUp']
        with self.assertRaisesRegex(ValueError, 'follow-up'): validate(new, [old], NOW)

    def test_prevent_relabeling_followup_as_new_issue(self):
        b = followup(); b['stories'][0]['timeline']['issueId'] = 'unrelated'
        with self.assertRaisesRegex(ValueError, 'keep its issue ID'): validate(b, [fixture()], NOW)

    def test_invalid_dates_paths_and_stage(self):
        for field, value in [('issueId', '../secret'), ('eventDate', '2026-02-30'), ('eventEndDate', '2026-10-01'), ('eventDate', '2026-10-03'), ('eventTimezone', 'Invalid/Zone'), ('stage', '완전확실')]:
            with self.subTest(field=field, value=value):
                b = fixture(); b['stories'][0]['timeline'][field] = value
                with self.assertRaises(ValueError): validate(b, [], NOW)

    def test_unknown_dates_are_not_article_dates(self):
        b = fixture(); s = b['stories'][0]
        s['timeline'].update(eventDate=None, eventEndDate=None, eventTimezone=None)
        validate(b, [], NOW)
        entry = build_timelines([b])['issues/issue-0.json']['entries'][0]
        self.assertIsNone(entry['eventDate']); self.assertIsNotNone(entry['publishedAt'])

    def test_exact_time_matches_event_timezone(self):
        b = fixture(); s = b['stories'][0]
        s['eventAt'] = '2026-10-02T05:00:00+09:00'
        s['timeline'].update(eventDate='2026-10-01', eventTimezone='America/New_York')
        validate(b, [], NOW)
        s['timeline']['eventDate'] = '2026-09-30'
        with self.assertRaisesRegex(ValueError, 'disagrees'): validate(b, [], NOW)

    def test_archive_is_idempotent_and_keeps_more_than_seven_days(self):
        old, new = fixture(), followup()
        # Shift the old edition back a month; the registry has no seven-day expiry.
        old = json.loads(json.dumps(old).replace('2026-10-02', '2026-09-02'))
        for s in new['stories']: s['followUp']['editionId'] = old['id']
        validate(new, [old], NOW)
        before = copy.deepcopy(old)
        files = build_timelines([new, old])
        self.assertEqual(files, build_timelines([old, new]))
        self.assertEqual(files['issues/index.json']['storyCount'], 10)
        entries = files['issues/issue-0.json']['entries']
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]['previous']['editionId'], old['id'])
        self.assertEqual(old, before)

    def test_correction_links_back_without_replacing_old_record(self):
        old, new = fixture(), followup()
        s = new['stories'][0]
        s['timeline'].update(stage='정정', correctionOf=dict(editionId=old['id'], storyId=old['stories'][0]['id']))
        validate(new, [old], NOW)
        entries = build_timelines([old, new])['issues/issue-0.json']['entries']
        self.assertEqual(entries[0]['keyFacts'], old['stories'][0]['keyFacts'])
        self.assertEqual(entries[0]['supersededBy'][0]['storyId'], s['id'])
        s['timeline']['correctionOf']['storyId'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'Correction target'): validate(new, [old], NOW)

    def test_legacy_archives_preserved_as_unlinked(self):
        b = fixture()
        for s in b['stories']: del s['timeline']
        files = build_timelines([b])
        self.assertEqual(files['issues/index.json']['unlinkedStoryCount'], 5)
        self.assertEqual(files['issues/index.json']['issues'], [])

    def test_publish_updates_both_issue_archives_and_preserves_first_edition(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); first = fixture()
            with patch('publish.datetime', wraps=datetime) as clock:
                clock.now.return_value = NOW
                publish(first, root)
                original = (root/'public/data/news/2026-10-02/am.json').read_bytes()
                publish(followup(), root)
            for folder in ('public', 'docs'):
                index = root/folder/'data/news/issues/index.json'
                self.assertTrue(index.exists())
                self.assertEqual(json.loads(index.read_text())['storyCount'], 10)
                issue = root/folder/'data/news/issues/issue-0.json'
                self.assertEqual(len(json.loads(issue.read_text())['entries']), 2)
            self.assertEqual((root/'public/data/news/issues/issue-0.json').read_bytes(), (root/'docs/data/news/issues/issue-0.json').read_bytes())
            self.assertEqual(original, (root/'public/data/news/2026-10-02/am.json').read_bytes())


if __name__ == '__main__': unittest.main()
