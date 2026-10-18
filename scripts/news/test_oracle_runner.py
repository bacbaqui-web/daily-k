import unittest
from datetime import datetime
from oracle_runner import target, extract, evidence_urls, check_sources

class OracleTests(unittest.TestCase):
    def test_korean_schedule_independent_of_host_timezone(self):
        self.assertEqual(target(datetime.fromisoformat('2026-10-19T00:00:00+00:00')), '2026-10-19-am')
        self.assertEqual(target(datetime.fromisoformat('2026-10-19T12:00:00+00:00')), '2026-10-19-pm')
        with self.assertRaises(ValueError):
            target(datetime.fromisoformat('2026-10-19T13:00:00+00:00'))
    def test_incomplete_response_rejected(self):
        with self.assertRaises(ValueError):
            extract({'status': 'incomplete', 'output': []})
    def test_only_actual_tool_evidence_counts(self):
        response = {'output': [{'type': 'web_search_call', 'action': {'sources': [{'url': 'https://example.org/news'}]}},
                               {'type': 'message', 'content': [{'type': 'output_text', 'text': 'https://invented.invalid/news'}]}]}
        self.assertEqual(evidence_urls(response), {'https://example.org/news'})
    def test_hallucinated_source_blocks_publication(self):
        brief = {'stories': [{'sources': [{'url': 'https://example.org/news'}], 'representativeUrl': 'https://invented.invalid/news'}], 'events': []}
        with self.assertRaises(ValueError):
            check_sources(brief, {'https://example.org/news'})
        brief['stories'][0]['representativeUrl'] = 'https://example.org/news'
        check_sources(brief, {'https://example.org/news'})

if __name__ == '__main__':
    unittest.main()
