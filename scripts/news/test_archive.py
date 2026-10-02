import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from archive import make_editions, parse_archive, load_editions, build_index
from publish import ROOT, publish, validate
from test_publish import fixture, NOW
from timeline import build_timelines

spec = importlib.util.spec_from_file_location('archive_import', Path(__file__).with_name('import-archive.py'))
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class HistoricalImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT/'ops/imports/news-briefing-archive.md').read_text()
        cls.mapping = json.loads((ROOT/'ops/news-archive-map.json').read_text())
        cls.editions = make_editions(cls.text, cls.mapping, '2026-10-02T12:34:33+09:00')

    def test_all_records_preserved_without_document_instructions(self):
        parsed = parse_archive(self.text)
        self.assertEqual(len(parsed), 35)
        self.assertEqual(sum(len(p['items']) for p in parsed), 291)
        self.assertEqual(sum(len(p['watchItems']) for p in parsed), 5)
        for raw, edition in zip(parsed, self.editions):
            self.assertEqual(len(raw['items']), len(edition['stories']))
            for n, (item, story) in enumerate(zip(raw['items'], edition['stories']), 1):
                self.assertEqual(story['archive']['originalText'], item['text'])
                self.assertEqual(story['archive']['ordinal'], n)
                self.assertEqual(story['archive']['lineStart'], item['lineStart'])
                self.assertEqual(story['archive']['lineEnd'], item['lineEnd'])
        self.assertEqual(sum(bool(s['archive']['sourceNames']) for b in self.editions for s in b['stories']), 20)

    def test_unknown_dates_and_links_are_not_invented(self):
        for edition in self.editions:
            self.assertIsNone(edition['cutoffAt'])
            self.assertIsNone(edition['archive']['originalGeneratedAt'])
            for story in edition['stories']:
                self.assertIsNone(story['publishedAt'])
                self.assertIsNone(story['eventAt'])
                self.assertIsNone(story['timeline']['eventDate'])
                self.assertEqual(story['sources'], [])
                self.assertEqual(story['status'], '과거 기록')
        issues = build_timelines(self.editions)
        self.assertEqual(len(issues['issues/index.json']['issues']), 132)
        self.assertEqual(issues['issues/index.json']['storyCount'], 291)
        self.assertTrue(all(i['latest']['archive'] for i in issues['issues/index.json']['issues']))
        for name, issue in issues.items():
            if name == 'issues/index.json': continue
            for entry in issue['entries']:
                self.assertIsNone(entry['coveredAt'])
                self.assertEqual(entry['coveredOn'], entry['editionDate'])
                self.assertTrue(entry['briefingPath'].startswith('archive/'))

    def test_previous_links_resolve_to_same_issue_earlier_records(self):
        known = {}
        for edition in self.editions:
            for story in edition['stories']:
                previous = story['archive'].get('previousCoverage')
                if previous:
                    target = known[(previous['date'], previous['edition'], previous['storyId'])]
                    self.assertEqual(target['timeline']['issueId'], story['timeline']['issueId'])
                known[(edition['date'], edition['edition'], story['id'])] = story

    def test_unreviewed_source_or_missing_assignment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'reviewed source'):
            make_editions(self.text+'\n', self.mapping, NOW.isoformat())
        mapping = copy.deepcopy(self.mapping)
        mapping['editions']['2026-09-15-am'].pop()
        with self.assertRaisesRegex(ValueError, 'Unclassified'):
            make_editions(self.text, mapping, NOW.isoformat())

    def test_archive_cannot_bypass_normal_publishing_requirements(self):
        with self.assertRaises(ValueError): validate(self.editions[0], [], NOW)
        draft = fixture()
        # An unverified record with a matching issue must not become factual evidence.
        old = copy.deepcopy(self.editions[0])
        old['stories'][0]['timeline'] = copy.deepcopy(draft['stories'][0]['timeline'])
        validate(draft, [old], NOW)

    def test_import_is_idempotent_and_future_publishing_preserves_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shutil.copytree(ROOT/'ops/imports', root/'ops/imports')
            shutil.copy2(ROOT/'ops/news-archive-map.json', root/'ops/news-archive-map.json')
            for folder in ('public', 'docs'):
                target = root/folder/'data/news/2026-10-02'
                target.mkdir(parents=True)
                shutil.copy2(ROOT/'public/data/news/2026-10-02/am.json', target/'am.json')
            original = (root/'public/data/news/2026-10-02/am.json').read_bytes()
            report = importer.import_archive(root)
            self.assertEqual(report['sameSlotAsPublished'], ['2026-10-02-am-archive'])
            self.assertEqual(report['repeatedIssueCount'], 44)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.glob('*/data/news/**/*.json')}
            self.assertEqual(report, importer.import_archive(root))
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.glob('*/data/news/**/*.json')})
            self.assertEqual(original, (root/'public/data/news/2026-10-02/am.json').read_bytes())
            with patch('publish.datetime', wraps=datetime) as clock:
                clock.now.return_value = NOW
                publish(fixture('pm'), root)
            for folder in ('public', 'docs'):
                base = root/folder/'data/news'
                index = json.loads((base/'index.json').read_text())
                self.assertEqual(len(index['editions']), 37)
                self.assertEqual(sum(bool(e.get('archive')) for e in index['editions']), 35)
                self.assertEqual(index['editions'][0]['id'], '2026-10-02-pm')
                for entry in index['editions']: self.assertTrue((base/entry['path']).exists())
                self.assertEqual(json.loads((base/'issues/index.json').read_text())['storyCount'], 303)
            self.assertEqual(original, (root/'public/data/news/2026-10-02/am.json').read_bytes())
            self.assertEqual(before['public/data/news/archive/2026-10-02/am.json'], (root/'public/data/news/archive/2026-10-02/am.json').read_bytes())


if __name__ == '__main__': unittest.main()
