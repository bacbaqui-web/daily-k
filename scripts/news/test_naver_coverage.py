import unittest
from naver_research import coverage_deficits,SECTIONS
class CoverageTests(unittest.TestCase):
 def test_complete(self):
  pool=[{'category':c,'rank':r,'url':f'https://example.com/{i}/{r}'} for i,c in enumerate(SECTIONS) for r in (1,2,3)]
  self.assertEqual(coverage_deficits(pool),{})
 def test_duplicate_rank_and_url_do_not_fill_reserves(self):
  c=SECTIONS[0]
  pool=[{'category':c,'rank':1,'url':'https://example.com/a'}, {'category':c,'rank':1,'url':'https://example.com/b'}, {'category':c,'rank':2,'url':'https://example.com/a'}]
  self.assertEqual(coverage_deficits(pool)[c],2)
 def test_invalid_rank(self):
  self.assertEqual(coverage_deficits([{'category':SECTIONS[0],'rank':4,'url':'https://example.com/a'}])[SECTIONS[0]],3)
if __name__=='__main__':unittest.main()
