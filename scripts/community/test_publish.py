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
 def test_valid_media_and_source_graph(self):
  v=self.sample();s=v['stories'][0];s.update(videoUrl='https://example.com/clip.mp4',videoPosterUrl='https://example.com/poster.jpg',sourceBreakdown=[{'name':'루리웹','count':2}],sourceStatsVerifiedAt='2026-10-03T10:00:00+09:00');validate(v)
 def test_reject_unsafe_video(self):
  v=self.sample();v['stories'][0]['videoUrl']='javascript:alert(1)'
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_invalid_source_counts(self):
  for count in (0,-1,True,1.5):
   v=self.sample();v['stories'][0].update(sourceBreakdown=[{'name':'루리웹','count':count}],sourceStatsVerifiedAt='2026-10-03T10:00:00+09:00')
   with self.assertRaises(AssertionError):validate(v)
 def original_sample(self):
  v=self.sample();v['schemaVersion']=2;v['overview']=[]
  for s in v['stories']:s.update(summary=[],originalText='짧은 원문',comments=[{'id':'c1','text':'ㅋㅋ'}],kCount=10,commentCount=3,commentsVerifiedAt='2026-10-03T09:02:00+09:00',category='유머')
  return v
 def test_original_sample(self):validate(self.original_sample())
 def test_reject_humor_below_threshold(self):
  v=self.original_sample();v['stories'][0]['kCount']=9
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_unknown_k_count(self):
  v=self.original_sample();v['stories'][0]['kCount']=None
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_long_original_copy(self):
  v=self.original_sample();v['stories'][0]['originalText']='word '*26
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_tagged_without_review(self):
  v=self.original_sample();v['stories'][0]['category']='ㅇㅎㅂ'
  with self.assertRaises(AssertionError):validate(v)
 def tagged_sample(self):
  v=self.original_sample();v['stories'][0].update(title='ㅇㅎ) 공개 행사',category='ㅇㅎㅂ',kCount=0,contentReview='public-non-explicit',imageUrl='https://example.com/photo.jpg',portalLinks=['https://www.instagram.com/example/'])
  return v
 def test_title_tag_without_laughter_or_signal(self):validate(self.tagged_sample())
 def test_reject_tagged_without_media(self):
  v=self.tagged_sample();v['stories'][0]['imageUrl']=None
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_spoofed_social_domain(self):
  v=self.tagged_sample();v['stories'][0]['portalLinks']=['https://x.com.evil.test/example']
  with self.assertRaises(AssertionError):validate(v)
 def test_origin_title_tag_without_laughter(self):
  v=self.tagged_sample();v['stories'][0]['title']='공개 행사';v['stories'][0]['sources'][0]['title']='ㅎㅂ) 공개 행사'
  validate(v)
if __name__=='__main__':unittest.main()
