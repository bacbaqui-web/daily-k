import json
import os
import unittest
from unittest.mock import patch
from codex_subscription import environment, normalize_events, check_login

class SubscriptionTests(unittest.TestCase):
    def test_paid_api_environment_is_removed(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret', 'CODEX_API_KEY': 'secret', 'OPENAI_BASE_URL': 'https://example.org', 'CODEX_ACCESS_TOKEN': 'secret'}):
            result = environment()
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'CODEX_ACCESS_TOKEN'):
            self.assertNotIn(key, result)
    def test_search_evidence_comes_from_tools(self):
        lines = '\n'.join(json.dumps(x) for x in [
            {'type': 'item.completed', 'item': {'type': 'web_search', 'action': {'type': 'open_page', 'url': 'https://example.org/news'}, 'results': [{'url': 'https://example.org/second'}]}},
            {'type': 'turn.completed'}])
        response = normalize_events(lines, 'result')
        self.assertEqual(response['output'][0]['action']['url'], 'https://example.org/news')
        self.assertEqual(response['output'][0]['action']['sources'], [{'url': 'https://example.org/second'}])
    def test_incomplete_and_failed_runs_block(self):
        with self.assertRaises(ValueError): normalize_events('', 'partial')
        with self.assertRaises(ValueError): normalize_events('{"type":"turn.failed"}', 'partial')
    def test_api_login_is_rejected(self):
        with patch('codex_subscription.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'Logged in using an API key'
            run.return_value.stderr = ''
            with self.assertRaises(ValueError): check_login()
            run.return_value.stdout = 'Logged in using ChatGPT'
            check_login()

if __name__ == '__main__': unittest.main()
