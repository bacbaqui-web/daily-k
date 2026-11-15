import copy
import unittest
from test_publish import fixture, NOW
from publish import validate

class SimpleSelectionTests(unittest.TestCase):
    def test_one_story_without_reserves_or_events(self):
        b=fixture('pm'); b['stories']=b['stories'][:1]; b['events']=[]; b['keywords']=[]
        b['stories'][0]['placement']='lead'
        self.assertEqual(len(validate(b,[],NOW)['stories']),1)

    def test_multiple_leads_same_category(self):
        b=fixture()
        for s in b['stories']:
            s['category']='경제'
            s['placement']='lead'
            s['alternatives']=[]
        self.assertEqual(len(validate(b,[],NOW)['stories']),5)

    def test_empty_edition_not_published(self):
        b=fixture(); b['stories']=[]
        with self.assertRaisesRegex(ValueError,'No verified news'):validate(b,[],NOW)

    def test_duplicate_and_future_checks_remain(self):
        b=fixture(); b['stories'].append(copy.deepcopy(b['stories'][0]))
        with self.assertRaises(ValueError):validate(b,[],NOW)
        b=fixture(); b['stories'][0]['publishedAt']='2026-10-03T08:00:00+09:00'
        with self.assertRaises(ValueError):validate(b,[],NOW)
