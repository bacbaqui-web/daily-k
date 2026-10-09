import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compare_history import canonical_id, normalize_url, normalize_title, build_index, compare, run_comparison


class ComparisonTests(unittest.TestCase):
    def test_suffix_aliases(self):
        for value in ['123', '123_1', '123-1', 'aagag-123_1', 'aagag-123-1', 'aagag-123-2', 'https://aagag.com/issue/?idx=123_1&foo=x']:
            self.assertEqual(canonical_id(value), '123')

    def test_external_numeric_ids_not_aagag(self):
        self.assertIsNone(canonical_id('https://www.dogdrip.net/123'))
        self.assertIsNone(canonical_id('https://example.org/?idx=123'))
        self.assertIsNone(canonical_id('not-123'))
        self.assertIsNone(canonical_id('2026-10-09'))

    def test_normalize_aagag(self):
        self.assertEqual(normalize_url('http://WWW.AAGAG.COM/issue/?utm_source=x&idx=123-1#comments'), 'https://aagag.com/issue/?idx=123')

    def test_normalize_other_url(self):
        self.assertEqual(normalize_url('https://Example.org/post/?b=2&amp;a=1&utm_source=x#comments'), 'https://example.org/post?a=1&b=2')
        self.assertNotEqual(normalize_url('https://example.org/post?id=1'), normalize_url('https://example.org/post?id=2'))
        self.assertNotEqual(normalize_url('http://example.org/1'), normalize_url('https://example.org/1'))
        self.assertIsNone(normalize_url('javascript:alert(1)'))

    def test_title_normalization_no_fuzzy_match(self):
        self.assertEqual(normalize_title(' Hello  WORLD\n'), 'hello world')
        self.assertNotEqual(normalize_title('Hello!'), normalize_title('Hello'))

    def match(self, new, old):
        idx, keys = build_index([old])
        return compare(new, [old], idx, keys)

    def test_id_match_is_published(self):
        result = self.match({'id': '123_1'}, {'id': 'aagag-123-1', 'publicationClass': 'deployed_community_edition'})
        self.assertTrue(result['alreadyPublishedIdentityMatch'])
        self.assertTrue(result['publishedCommunityEditionMatch'])

    def test_original_url_match_is_published(self):
        result = self.match({'id': '789', 'sources': [{'url': 'https://example.org/post?id=7&utm_source=a'}]},
                            {'id': 'aagag-123', 'originalUrls': ['https://example.org/post?id=7'], 'publicationClass': 'deployed_community_edition'})
        self.assertTrue(result['alreadyPublishedIdentityMatch'])
        self.assertEqual(result['publicationMatches'][0]['matches']['originalUrl'], ['https://example.org/post?id=7'])

    def test_media_title_only_is_flag_not_published(self):
        result = self.match({'id': '789', 'title': ' same ', 'media': [{'url': 'https://i.aagag.com/o/a.webp'}]},
                            {'id': 'aagag-123', 'title': 'SAME', 'mediaUrls': ['https://i.aagag.com/o/a.webp']})
        self.assertFalse(result['alreadyPublishedIdentityMatch'])
        self.assertTrue(result['mediaMatch'])
        self.assertTrue(result['titleMatch'])
        self.assertTrue(result['additionalMediaOrTitleOnlyMatch'])

    def test_legacy_distinguished(self):
        result = self.match({'id': '123'}, {'id': 'aagag-123', 'publicationClass': 'legacy_public_feed'})
        self.assertTrue(result['alreadyPublishedIdentityMatch'])
        self.assertTrue(result['legacyPublicFeedMatch'])
        self.assertFalse(result['publishedCommunityEditionMatch'])

    def test_supplemental_source_url(self):
        old = {'id': 'aagag-1', 'originalUrls': ['https://example.org/post/2']}
        idx, keys = build_index([old])
        result = compare({'id': '456'}, [old], idx, keys, {'url': 'https://example.org/post/2'})
        self.assertTrue(result['alreadyPublishedIdentityMatch'])

    def fixture(self, root):
        run = root / 'run'
        run.mkdir()
        records = [{'id': str(n), 'canonicalId': str(n), 'title': 'Post ' + str(n), 'kCount': 11, 'commentCount': 1,
                    'kCountVerified': True, 'thresholdQualified': True, 'inWindow': True, 'observedAt': '2026-10-09T02:03:33Z'} for n in (1, 2, 3)]
        # Include a held threshold qualifier and a below-threshold observed row.
        records[1]['exclusions'] = ['review_hold']
        records[2].update({'kCount': 1, 'thresholdQualified': False})
        summary = {'candidates': 1, 'qualifiers': 2, 'observedRecords': 3, 'candidateIDs': ['1'],
                   'lastUpdatedAt': '2026-10-09T02:04:00Z', 'window': {'start': '2026-10-08T02:03:32.390Z', 'end': '2026-10-09T02:03:32.390Z'}, 'complete': False}
        for name, value in [('summary.json', summary), ('normalized-posts.json', records), ('candidates.json', records[:1]), ('all-threshold-qualifiers.json', records[:2])]:
            (run / name).write_text(json.dumps(value))
        snapshot = root / 'snapshot.json'
        snapshot.write_text(json.dumps({'records': [{'id': 'aagag-1_1', 'publicationClass': 'deployed_community_edition'}],
                                       'capturedAt': '2026-10-09T02:01:00Z', 'commitSha': 'fixture', 'publicationBasis': 'fixture'}))
        return run, snapshot

    def test_no_candidate_or_qualifier_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, snapshot = self.fixture(root)
            before = {p.name: p.read_bytes() for p in run.iterdir()}
            result = run_comparison(run, snapshot, root / 'output')
            self.assertEqual(result['allObserved']['count'], 3)
            self.assertEqual(result['allThresholdQualifiers']['count'], 2)
            self.assertEqual(result['allThresholdQualifiers']['alreadyPublishedIdentityOverlaps'], 1)
            self.assertEqual(result['candidates']['count'], 1)
            self.assertEqual(result['candidates']['alreadyPublishedIdentityOverlaps'], 1)
            rows = json.loads((root / 'output/all-observed-comparison.json').read_text())
            self.assertEqual([r['id'] for r in rows], ['1', '2', '3'])
            self.assertTrue(all(r['omittedByComparison'] is False for r in rows))
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir()})

    def test_torn_checkpoint_fails_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, snapshot = self.fixture(root)
            data = json.loads((run / 'candidates.json').read_text())
            data[0]['kCount'] = 99
            (run / 'candidates.json').write_text(json.dumps(data))
            with patch('compare_history.time.sleep'), self.assertRaises(RuntimeError):
                run_comparison(run, snapshot, root / 'output')
            self.assertFalse((root / 'output').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
