import copy
import unittest
from oracle_runner import check_reserve_coverage, SECTIONS

class ReserveDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.ledger={'candidates':[{'category':c,'rank':r,'url':f'https://example.org/{i}/{r}'} for i,c in enumerate(SECTIONS) for r in (1,2,3)]}
        self.brief={'stories':[{'category':c,'placement':'lead','representativeUrl':f'https://example.org/{i}/1','alternatives':[{'rank':r,'url':f'https://example.org/{i}/{r}'} for r in (2,3)]} for i,c in enumerate(SECTIONS)]}
    def test_all_seven_categories_pass(self):
        check_reserve_coverage(self.brief,self.ledger)
    def test_missing_reserve_rejected_without_test_environment(self):
        for i in range(7):
            b=copy.deepcopy(self.brief); b['stories'][i]['alternatives'].pop()
            with self.assertRaises(ValueError):check_reserve_coverage(b,self.ledger)
    def test_duplicate_url_does_not_count(self):
        self.brief['stories'][0]['alternatives'][1]['url']=self.brief['stories'][0]['alternatives'][0]['url']
        with self.assertRaises(ValueError):check_reserve_coverage(self.brief,self.ledger)
    def test_rejected_candidate_not_forced_back(self):
        self.brief['stories'][0]['alternatives'].pop()
        check_reserve_coverage(self.brief,self.ledger,[{'urls':['https://example.org/0/3']}])
    def test_strict_test_requires_all_reserves(self):
        self.brief['stories'][0]['alternatives'].pop()
        with self.assertRaises(ValueError):check_reserve_coverage(self.brief,{'candidates':[]},strict=True)
if __name__=='__main__': unittest.main()
