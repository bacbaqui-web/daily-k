import copy,unittest
from publish import validate
class ValidationTests(unittest.TestCase):
 def sample(self):
  source={'name':'테스트','title':'원문','url':'https://example.com/post','imageUrl':None,'publishedAt':'2026-10-03T08:00:00+09:00','verifiedAt':'2026-10-03T09:02:00+09:00'}
  return {'schemaVersion':1,'timezone':'Asia/Seoul','id':'2026-10-03-am','date':'2026-10-03','edition':'am','cutoffAt':'2026-10-03T09:00:00+09:00','generatedAt':'2026-10-03T09:03:00+09:00','overview':['요약'],'stories':[{'id':str(i),'topicKey':str(i),'title':'제목','category':'정보','selectionReason':'이유','popularityEvidence':'근거','verificationNote':'확인','summary':['요약'],'sources':[copy.deepcopy(source)]} for i in range(3)]}
 def test_valid(self):validate(self.sample())
 def test_reject_cutoff_after_creation(self):
  v=self.sample();v['generatedAt']='2026-10-03T08:00:00+09:00'
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_unsafe_link(self):
  v=self.sample();v['stories'][0]['sources'][0]['url']='javascript:alert(1)'
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_unsubstantiated_popularity(self):
  v=self.sample();v['stories'][0]['popularityEvidence']=''
  with self.assertRaises(AssertionError):validate(v)
if __name__=='__main__':unittest.main()
