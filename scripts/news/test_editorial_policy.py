import unittest
from publish import validate_previous_alternatives
from editorial_policy import POLICY

class PreviousReserveTests(unittest.TestCase):
    def setUp(self):
        self.old = {'id':'2026-11-06-am','cutoffAt':'2026-11-06T09:00:00+09:00',
                    'stories':[{'alternatives':[{'title':'통학버스 아동 방치 경찰 수사','url':'https://example.org/a'}]}]}
        self.item = {'title':'통학버스 아동 방치 경찰 수사','representativeUrl':'https://example.org/a'}
        self.brief = {'id':'2026-11-06-pm','cutoffAt':'2026-11-06T21:00:00+09:00','stories':[self.item]}
    def test_reserve_promotion_without_update_rejected(self):
        with self.assertRaises(ValueError):
            validate_previous_alternatives(self.brief,[self.old])
    def test_other_outlet_same_title_rejected(self):
        self.item['representativeUrl']='https://other.org/new'
        with self.assertRaises(ValueError):
            validate_previous_alternatives(self.brief,[self.old])
    def test_repeat_as_alternative_rejected(self):
        self.brief['stories']=[{'title':'다른 소식','alternatives':[dict(self.item,url='https://example.org/a')]}]
        with self.assertRaises(ValueError):
            validate_previous_alternatives(self.brief,[self.old])
    def test_new_evidence_allowed(self):
        self.item['reserveUpdate']={'editionId':self.old['id'],'delta':'오전 조사 착수 이후 오후에 수사 결과와 공식 개선조치가 발표됐습니다.',
                                   'sourceUrl':'https://example.org/result','publishedAt':'2026-11-06T17:00:00+09:00'}
        validate_previous_alternatives(self.brief,[self.old])
        self.item['reserveUpdate']['publishedAt']='2026-11-06T08:00:00+09:00'
        with self.assertRaises(ValueError):
            validate_previous_alternatives(self.brief,[self.old])
    def test_archive_without_cutoff_is_ignored(self):
        validate_previous_alternatives(self.brief,[{'id':'archive','archive':True,'cutoffAt':None,'stories':[]}])
    def test_unrelated_story_allowed(self):
        self.item.update(title='새로운 과학 연구 성과 발표',representativeUrl='https://example.org/science')
        validate_previous_alternatives(self.brief,[self.old])
if __name__=='__main__':unittest.main()
