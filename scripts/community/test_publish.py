import copy,json,unittest
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
class EarlyValidationTests(unittest.TestCase):
 def sample(self,edition='am'):
  v=json.loads(json.dumps(ValidationTests().original_sample()).replace('2026-10-03','2026-10-07'))
  hour=8 if edition=='am' else 20
  v.update(id='2026-10-07-'+edition,edition=edition,cutoffAt=f'2026-10-07T{hour:02}:30:00+09:00',generatedAt=f'2026-10-07T{hour:02}:55:00+09:00')
  for story in v['stories']:
   story['commentsVerifiedAt']=f'2026-10-07T{hour:02}:50:00+09:00'
   for source in story['sources']:source.update(publishedAt=f'2026-10-07T{hour:02}:00:00+09:00',verifiedAt=f'2026-10-07T{hour:02}:50:00+09:00')
  return v
 def test_early_am_and_pm_keep_identity_and_real_timestamps(self):
  for edition in ('am','pm'):
   with self.subTest(edition=edition):
    v=self.sample(edition);result=validate(v)
    self.assertEqual(result['id'],'2026-10-07-'+edition)
    self.assertEqual(result['cutoffAt'],v['cutoffAt'])
    self.assertEqual(result['generatedAt'],v['generatedAt'])
 def test_legacy_cutoff_still_valid(self):validate(ValidationTests().original_sample())
 def test_new_editions_require_exact_early_cutoff(self):
  for value in ('08:29','08:31','09:00','20:30'):
   v=self.sample();v['cutoffAt']=f'2026-10-07T{value}:00+09:00'
   with self.subTest(value=value),self.assertRaises(AssertionError):validate(v)
 def test_new_editions_cannot_bypass_cutoff_with_test_flag(self):
  v=self.sample();v.update(test=True,cutoffAt='2026-10-07T08:00:00+09:00')
  with self.assertRaises(AssertionError):validate(v)
 def test_legacy_editions_cannot_use_early_cutoff(self):
  v=ValidationTests().original_sample();v['cutoffAt']='2026-10-03T08:30:00+09:00'
  with self.assertRaises(AssertionError):validate(v)
 def test_generation_before_cutoff_rejected(self):
  v=self.sample();v['generatedAt']='2026-10-07T08:29:59+09:00'
  with self.assertRaises(AssertionError):validate(v)
 def test_source_after_actual_cutoff_rejected(self):
  v=self.sample();v['stories'][0]['sources'][0]['publishedAt']='2026-10-07T08:30:01+09:00'
  with self.assertRaises(AssertionError):validate(v)
 def test_rolling_twenty_four_hours_uses_actual_cutoff(self):
  v=self.sample();v['stories'][0]['sources'][0]['publishedAt']='2026-10-06T08:30:00+09:00';validate(v)
  v['stories'][0]['sources'][0]['publishedAt']='2026-10-06T08:29:59+09:00'
  with self.assertRaises(AssertionError):validate(v)
 def test_verification_after_generation_rejected(self):
  for field in ('source','comments'):
   v=self.sample()
   if field=='source':v['stories'][0]['sources'][0]['verifiedAt']='2026-10-07T08:56:00+09:00'
   else:v['stories'][0]['commentsVerifiedAt']='2026-10-07T08:56:00+09:00'
   with self.subTest(field=field),self.assertRaises(AssertionError):validate(v)
 def test_original_quote_humor_and_summary_gates_still_apply(self):
  for field,value in [('originalText','word '*26),('kCount',9),('summary',['invented summary'])]:
   v=self.sample();v['stories'][0][field]=value
   with self.subTest(field=field),self.assertRaises(AssertionError):validate(v)

if __name__=='__main__':unittest.main()
