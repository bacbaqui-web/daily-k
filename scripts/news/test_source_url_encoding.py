import unittest
from oracle_runner import check_sources
class SourceEncodingTests(unittest.TestCase):
 def brief(self,url):
  return {'stories':[{'sources':[{'url':url}],'representativeUrl':url}],'events':[]}
 def test_unicode_matches_percent_encoded_evidence(self):
  check_sources(self.brief('https://example.com/뉴스'),{'https://example.com/%EB%89%B4%EC%8A%A4'})
 def test_reserved_slash_is_not_decoded(self):
  with self.assertRaises(ValueError):
   check_sources(self.brief('https://example.com/a/b'),{'https://example.com/a%2Fb'})
 def test_different_article_still_rejected(self):
  with self.assertRaises(ValueError):
   check_sources(self.brief('https://example.com/news/2'),{'https://example.com/news/1'})
