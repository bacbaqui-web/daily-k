import copy,json,unittest
from publish import validate,publish
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
  for s in v['stories']:s.update(summary=[],originalText='짧은 원문',comments=[{'id':'c1','text':'ㅋㅋ'}],kCount=11,commentCount=3,commentsVerifiedAt='2026-10-03T09:02:00+09:00',category='유머')
  return v
 def test_original_sample(self):validate(self.original_sample())
 def test_reject_humor_below_threshold(self):
  v=self.original_sample();v['stories'][0]['kCount']=10
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_unknown_k_count(self):
  v=self.original_sample();v['stories'][0]['kCount']=None
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_long_original_copy(self):
  v=self.original_sample();v['stories'][0]['originalText']='word '*26
  with self.assertRaises(AssertionError):validate(v)
 def test_reject_retired_category_even_with_previous_review(self):
  v=self.original_sample();v['stories'][0].update(category='ㅇㅎㅂ',kCount=100,contentReview='public-non-explicit',imageUrl='https://example.com/photo.jpg')
  with self.assertRaisesRegex(AssertionError,'retired or unsupported'):validate(v)
 def test_reject_retired_titles_in_any_category_and_source(self):
  for category in ('유머','정보','화제','생활','문화','스포츠'):
   for title in ('ㅇㅎ) 공개 행사','[ㅎㅂ] 공개 행사','ㅇㅎㅂ 공연','ㅇ\u200bㅎ) 공개 행사'):
    for location in ('title','first-source','other-source'):
     v=self.original_sample();story=v['stories'][0];story.update(category=category,kCount=100)
     if location=='title':story['title']=title
     elif location=='first-source':story['sources'][0]['title']=title
     else:story['sources'].append(dict(story['sources'][0],title=title,url='https://example.com/original'))
     with self.subTest(category=category,title=title,location=location),self.assertRaisesRegex(AssertionError,'retired title tag'):validate(v)
 def test_old_date_and_schema_do_not_bypass_collection_stop(self):
  for field in ('category','title','source','signal'):
   v=self.sample();story=v['stories'][0]
   if field=='category':story['category']='ㅇㅎㅂ'
   elif field=='title':story['title']='ㅇㅎ) 공개 행사'
   elif field=='source':story['sources'][0]['title']='[ㅎㅂ] 공개 행사'
   else:story['contentSignals']=[{'kind':'leaked','commentId':'c1'}]
   with self.subTest(field=field),self.assertRaisesRegex(AssertionError,'retired'):validate(v)
 def test_reject_retired_signal_route_relabelled_as_normal_content(self):
  for kind in ('instagram','x','leaked'):
   v=self.original_sample();v['stories'][0]['contentSignals']=[{'kind':kind,'commentId':'c1','url':'https://x.com/example'}]
   with self.subTest(kind=kind),self.assertRaisesRegex(AssertionError,'retired ㅇㅎㅂ collection signals'):validate(v)
 def test_ordinary_social_links_and_non_tag_consonants_remain_valid(self):
  v=self.original_sample();v['stories'][0].update(title='ㅋㅋㅇㅎㅋㅋ ㅇㅎㅎ 정보',portalLinks=['https://www.instagram.com/example/','https://x.com/example'],contentSignals=[]);validate(v)
 def test_reject_spoofed_social_domain(self):
  v=self.original_sample();v['stories'][0]['portalLinks']=['https://x.com.evil.test/example']
  with self.assertRaises(AssertionError):validate(v)
 def test_laughter_threshold_requires_eleven_and_does_not_apply_to_other_categories(self):
  for count in (11,12):
   v=self.original_sample();v['stories'][0]['kCount']=count;validate(v)
  for category in ('정보','화제','생활','문화','스포츠'):
   v=self.original_sample();v['stories'][0].update(category=category,kCount=0);validate(v)
 def test_humor_threshold_cannot_be_bypassed_with_legacy_schema(self):
  for count in (None,9,10,True):
   v=self.sample();v['stories'][0].update(category='유머',kCount=count)
   with self.subTest(count=count),self.assertRaisesRegex(AssertionError,'at least 11'):validate(v)
  v=self.sample();v['stories'][0].update(category='유머',kCount=11);validate(v)
 def test_direct_publish_rejects_retired_posts_before_writing(self):
  v=self.original_sample();v['stories'][0]['title']='ㅇㅎ) 공개 행사'
  with self.assertRaisesRegex(AssertionError,'retired title tag'):publish(v)
class BodyImageTests(unittest.TestCase):
 def sample(self):
  v=ValidationTests().original_sample();s=v['stories'][0]
  s.update(imageUrl='https://example.com/first.webp',bodyImages=[{'url':'https://example.com/first.webp','width':800,'height':600},{'url':'https://example.com/second.webp','width':800,'height':12000}],bodyImagesSourceUrl=s['sources'][0]['url'],bodyImagesVerifiedAt='2026-10-08T21:00:00+09:00')
  return v
 def test_order_dimensions_and_later_media_repair_preserved(self):
  v=self.sample();before=copy.deepcopy(v);validate(v);self.assertEqual(v,before)
 def test_images_can_coexist_with_video(self):
  v=self.sample();v['stories'][0]['videoUrl']='https://example.com/clip.mp4';validate(v)
 def test_explicit_no_body_images_and_legacy(self):
  v=self.sample();v['stories'][0]['bodyImages']=[];validate(v)
  validate(ValidationTests().sample())
 def test_reject_malformed_or_nonpublic_images(self):
  for images in (None,{},'https://example.com/a.jpg',[None],[{'url':'data:image/png;base64,a','width':1,'height':1}]):
   v=self.sample();v['stories'][0]['bodyImages']=images
   with self.subTest(images=images),self.assertRaises(AssertionError):validate(v)
  for url in ('javascript:alert(1)','https://user:secret@example.com/a','http://127.0.0.1/a','http://192.168.1.1/a','http://localhost/a','http://test.local/a','https://example.com/a '):
   v=self.sample();v['stories'][0]['bodyImages'][0]['url']=url
   with self.subTest(url=url),self.assertRaises(AssertionError):validate(v)
 def test_reject_unloaded_or_invalid_dimensions(self):
  for dimension in ('width','height'):
   for value in (0,-1,True,1.5,None):
    v=self.sample();v['stories'][0]['bodyImages'][0][dimension]=value
    with self.subTest(dimension=dimension,value=value),self.assertRaises(AssertionError):validate(v)
 def test_reject_duplicate_urls_including_fragments(self):
  for suffix in ('','#again'):
   v=self.sample();v['stories'][0]['bodyImages'][1]['url']=v['stories'][0]['bodyImages'][0]['url']+suffix
   with self.assertRaisesRegex(AssertionError,'duplicate body image'):validate(v)
 def test_reject_missing_or_unrelated_evidence(self):
  for field,value in (('bodyImagesSourceUrl','https://example.com/unrelated'),('bodyImagesVerifiedAt',None),('bodyImagesVerifiedAt','2026-10-08T21:00:00')):
   v=self.sample();v['stories'][0][field]=value
   with self.subTest(field=field,value=value),self.assertRaises(AssertionError):validate(v)

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
  for field,value in [('originalText','word '*26),('kCount',10),('summary',['invented summary'])]:
   v=self.sample();v['stories'][0][field]=value
   with self.subTest(field=field),self.assertRaises(AssertionError):validate(v)

if __name__=='__main__':unittest.main()
