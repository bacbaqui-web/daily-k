import copy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from publish import validate, publish, KST

NOW=datetime(2026,10,2,22,tzinfo=KST)
NAMES=['물가 변화와 가계 비용','국제 외교 회담 결과','반도체 새 생산 공정','국내 도시 교통 정책','웹툰 창작자 지원 사업']
def fixture(edition='am'):
    hour=9 if edition=='am' else 21
    cutoff=f'2026-10-02T{hour:02}:00:00+09:00';publication=f'2026-10-02T{hour-1:02}:00:00+09:00';generated=f'2026-10-02T{hour:02}:10:00+09:00'
    def source(i):return dict(name='검증용 매체',title=NAMES[i%5],url=f'https://example.org/{edition}/{i}',publishedAt=publication,verifiedAt=generated,kind='official',language='ko')
    stories=[dict(id=f'topic-{edition}-{i}',topicKey=f'topic-{edition}-{i}',category='웹툰 산업' if i==4 else '경제',title=t,summary=['첫 번째로 확인한 내용과 구체적 숫자를 설명합니다.','이전 상황과 비교한 차이와 남은 불확실성을 설명합니다.'],status='확정',publishedAt=publication,eventAt=None,eventTimeNote='발표 시각 확인',whatChanged='새 결과',whyItMatters='국내 영향',uncertainty='추가 결과 미확인',keyFacts={'metric':str(i),'result':t},sources=[source(i)],scoreComponents=dict(importance=80,interest=80,domesticImpact=80,reliability=80),scoreReason='핵심 통계') for i,t in enumerate(NAMES)]
    for i,s in enumerate(stories):s.update(emphasis=['구체적 숫자','남은 불확실성'],relatedArticles=[source(i)],timeline=dict(issueId=f'issue-{i}',issueTitle=NAMES[i],eventDate='2026-10-02',eventEndDate=None,eventTimezone='Asia/Seoul',stage='발표',change='이번 발표에서 확인된 내용과 이전 대비 변화를 기록합니다.'))
    day='2026-10-02' if edition=='am' else '2026-10-03'
    events=[dict(title=f'예정 일정 {i}',date=day,at=f'{day}T{12+i:02}:00:00+09:00',detail='실제 발표 예정 시간을 기준으로 확인하는 검증 항목',source=source(i)) for i in range(3)]
    return dict(schemaVersion=1,id=f'2026-10-02-{edition}',date='2026-10-02',edition=edition,timezone='Asia/Seoul',cutoffAt=cutoff,generatedAt=generated,intro='검증용 브리핑',overview=['이번 회차 전체 분야의 주요 변화를 요약합니다.','뉴스들을 함께 보고 앞으로 확인할 변수를 설명합니다.'],stories=stories,events=events,keywords=[] if edition=='am' else [f'주제{i}' for i in range(8)])

class PublishingTests(unittest.TestCase):
    def test_score_and_order(self):
        b=fixture();b['stories'][2]['scoreComponents']['importance']=100
        result=validate(b,[],NOW)
        self.assertEqual(result['stories'][0]['id'],'topic-am-2');self.assertEqual(result['stories'][0]['score'],93)
    def test_missing_webtoon(self):
        b=fixture();b['stories'][-1]['category']='문화'
        with self.assertRaisesRegex(ValueError,'webtoon'):validate(b,[],NOW)
    def test_korean_link_required(self):
        b=fixture();b['stories'][0]['sources'][0]['language']='en'
        with self.assertRaisesRegex(ValueError,'Korean'):validate(b,[],NOW)
    def test_future_source_rejected(self):
        b=fixture();b['stories'][0]['sources'][0]['publishedAt']='2026-10-02T09:01:00+09:00'
        with self.assertRaisesRegex(ValueError,'after edition'):validate(b,[],NOW)
    def test_stale_verification(self):
        b=fixture();b['stories'][0]['sources'][0]['verifiedAt']='2026-10-01T09:00:00+09:00'
        with self.assertRaisesRegex(ValueError,'freshly'):validate(b,[],NOW)
    def test_same_story_in_evening_rejected(self):
        with self.assertRaisesRegex(ValueError,'follow-up'):validate(fixture('pm'),[fixture()],NOW)
    def test_fake_update_rejected(self):
        b=fixture('pm');s=b['stories'][0];s['followUp']=dict(editionId='2026-10-02-am',storyId='topic-am-0',delta='오후에 수치가 바뀌었다고 쓰지만 사실은 그대로입니다.');s['summary'][0]+=' 새 문구입니다.'
        with self.assertRaisesRegex(ValueError,'No new numbers'):validate(b,[fixture()],NOW)
    def test_real_update_allowed(self):
        b=fixture('pm')
        for i,s in enumerate(b['stories']):
            s['followUp']=dict(editionId='2026-10-02-am',storyId=f'topic-am-{i}',delta='아침 잠정 수치에서 오후 확정 수치로 바뀌었습니다.')
            s['keyFacts']['metric']=str(100+i);s['summary'][0]+=' 오후에 확정된 수치를 반영했습니다.'
        result=validate(b,[fixture()],NOW);self.assertEqual(len(result['stories']),5)
    def test_old_evidence_cannot_support_update(self):
        b=fixture('pm');s=b['stories'][0];s['summary'][0]+=' 새로운 발표라고 합니다.';s['keyFacts']['metric']='500';s['followUp']=dict(editionId='2026-10-02-am',storyId='topic-am-0',delta='아침 뒤에 새 수치가 나왔다는 주장입니다.')
        s['publishedAt']=s['sources'][0]['publishedAt']='2026-10-02T08:00:00+09:00'
        with self.assertRaisesRegex(ValueError,'new evidence'):validate(b,[fixture()],NOW)
    def test_wrong_event_date(self):
        b=fixture('pm');b['events'][0]['date']='2026-10-02'
        with self.assertRaisesRegex(ValueError,'target date'):validate(b,[],NOW)
    def test_past_morning_event(self):
        b=fixture();b['events'][0]['at']='2026-10-02T08:00:00+09:00'
        with self.assertRaisesRegex(ValueError,'already ended'):validate(b,[],NOW)
    def test_webtoon_fallback_needs_label(self):
        b=fixture();s=b['stories'][-1];s['publishedAt']=s['sources'][0]['publishedAt']='2026-09-30T10:00:00+09:00'
        with self.assertRaisesRegex(ValueError,'Label older'):validate(b,[],NOW)
        s['fallbackNote']='최근 중요 업데이트입니다.';validate(b,[],NOW)
    def test_unsafe_link(self):
        b=fixture();b['stories'][0]['sources'][0]['url']='javascript:alert(1)'
        with self.assertRaisesRegex(ValueError,'URL'):validate(b,[],NOW)
    def test_related_article_safety_and_cutoff(self):
        for field,value,message in [('url','javascript:alert(1)','URL'),('imageUrl','data:text/html,bad','URL'),('publishedAt','2026-10-02T12:00:00+09:00','after edition')]:
            with self.subTest(field=field):
                b=fixture();b['stories'][0]['relatedArticles'][0][field]=value
                with self.assertRaisesRegex(ValueError,message):validate(b,[],NOW)
    def test_missing_or_invented_emphasis_rejected(self):
        for phrases in [[],['본문에 없는 강조 문구']]:
            b=fixture();b['stories'][0]['emphasis']=phrases
            with self.assertRaisesRegex(ValueError,'Emphasis'):validate(b,[],NOW)
    def test_related_article_revision_keeps_original_generation_time(self):
        b=fixture();b['updatedAt']='2026-10-02T20:00:00+09:00'
        for story in b['stories']:
            for article in story['relatedArticles']:article['verifiedAt']=b['updatedAt']
        result=validate(b,[],NOW);self.assertEqual(result['generatedAt'],b['generatedAt'])
    def test_publish_preserves_archive_and_humor(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'public/data').mkdir(parents=True);humor=root/'public/data/feed.json';humor.write_text('untouched')
            b=fixture();publish(b,root)
            for folder in ('public','docs'):
                self.assertEqual(json.loads((root/folder/'data/news/2026-10-02/am.json').read_text())['id'],b['id'])
            before=(root/'public/data/news/index.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'already published'):publish(b,root)
            self.assertEqual((root/'public/data/news/index.json').read_bytes(),before);self.assertEqual(humor.read_text(),'untouched')

if __name__=='__main__':unittest.main()
