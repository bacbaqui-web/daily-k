import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import web_handoff as web

class WebHandoffTests(unittest.TestCase):
    def test_cutoff_is_fixed_and_rejects_paths(self):
        self.assertEqual(web.cutoff('2026-11-16-pm'), '2026-11-16T21:00:00+09:00')
        with self.assertRaises(ValueError):
            web.cutoff('../../invalid')

    def test_queue_is_idempotent_and_does_not_generate(self):
        with TemporaryDirectory() as temp, patch.dict('os.environ', {'NEWS_STATE_DIR': temp}), \
             patch.object(web, 'sync'), patch.object(web, 'published', return_value=False), \
             patch.object(web.runner, 'target', return_value='2026-11-16-pm'):
            web.queue()
            file = Path(temp) / '2026-11-16-pm/awaiting-chatgpt.json'
            before = file.read_bytes()
            web.queue()
            self.assertEqual(file.read_bytes(), before)
            self.assertFalse(file.with_name('attempted.json').exists())

    def test_already_published_cannot_be_overwritten(self):
        with TemporaryDirectory() as temp, patch.dict('os.environ', {'NEWS_STATE_DIR': temp}), \
             patch.object(web, 'sync'), patch.object(web, 'published', return_value=True), \
             patch.object(web, 'validate_handoff') as validate:
            payload = Path(temp) / 'p.json'
            payload.write_text(json.dumps({'brief': {'id': '2026-11-16-am'}}))
            review = Path(temp) / 'r.json'
            review.write_text('{}')
            web.consume(payload, review, push=True)
            validate.assert_not_called()

    def test_changed_payload_or_history_and_missing_checks_rejected(self):
        payload = {'operationId':'publish-news-2026-11-16-am', 'brief':{
            'id':'2026-11-16-am','cutoffAt':web.cutoff('2026-11-16-am')}}
        review = {'edition':'2026-11-16-am','approved':True,'payloadSha256':web.digest(payload),
                  'historySha256':web.digest([]),'conversationUrl':'https://chatgpt.com/c/test',
                  'responseCompletedAt':'2026-01-01T00:00:00+09:00','verifiedAt':'2026-01-01T00:01:00+09:00'}
        for changes in ({'payloadSha256':'wrong'}, {'historySha256':'wrong'}, {}):
            with self.assertRaises(ValueError):
                web.validate_handoff(payload, review | changes, [])

if __name__ == '__main__':
    unittest.main()
