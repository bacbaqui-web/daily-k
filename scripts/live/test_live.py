"""Temporary repositories only: no test content is written to the website."""
import concurrent.futures
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import manage as m

BEFORE = m.stamp('2026-10-07T08:59:59+09:00')
BOUNDARY = m.stamp('2026-10-07T09:00:00+09:00')
AFTER = m.stamp('2026-10-07T09:03:00+09:00')


def source():
    return dict(name='테스트 자료', title='테스트 원제', url='https://example.org/topic', publishedAt=None,
                verifiedAt=m.iso(BEFORE), platform='community', region='unknown', regionEvidenceUrl=None,
                periodStart=None, periodEnd=None, limitations='테스트에서만 사용', quotes=[])


def item(id='topic-one'):
    return dict(id=id, kind='topic', topicKey=id, expectedRevision=0, title='테스트 전용 주제', summary='테스트 전용 설명',
                firstObservedAt=m.iso(BEFORE), lastVerifiedAt=m.iso(BEFORE), canonicalUrl=None,
                sources=[source()], observations=[dict(sourceUrl=source()['url'], metric='확인 수', value=None,
                unit='건', observedAt=m.iso(BEFORE), scope='테스트 범위')], limitations='테스트 전용',
                selectionReason='테스트 전용', safetyChecked=True, rightsChecked=True)


def payload(id='run-one', **kwargs):
    return dict(schemaVersion=1, operationId=id, **kwargs)


def create_repo(root):
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'config', 'user.email', 'test@example.invalid'], check=True)
    subprocess.run(['git', '-C', str(root), 'config', 'user.name', 'Tests'], check=True)
    (root / 'public/data/news').mkdir(parents=True)


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        create_repo(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def run_op(self, command='upsert', data=None, now=BEFORE, check=False):
        return m.execute(self.root, command, data or payload(items=[item()]), now=now, check=check)[0]

    def state(self):
        return json.loads((self.root / 'public' / m.CURRENT).read_text())

    def final(self, now=AFTER, op='finalize-2026-10-07-am'):
        return self.run_op('finalize', payload(op, edition='2026-10-07-am'), now)

    def snapshot(self):
        return json.loads((self.root / 'public/data/live/snapshots/2026-10-07-am.json').read_text())

    def test_half_open_boundaries_and_equivalent_timezone(self):
        cases = [('2026-10-07T08:59:59+09:00','2026-10-07-am'), ('2026-10-07T09:00:00+09:00','2026-10-07-pm'),
                 ('2026-10-07T00:00:00Z','2026-10-07-pm'), ('2026-10-07T20:59:59+09:00','2026-10-07-pm'),
                 ('2026-10-07T21:00:00+09:00','2026-10-08-am'), ('2026-10-08T00:00:00+09:00','2026-10-08-am')]
        for at, expected in cases:
            self.assertEqual(m.window_for(m.stamp(at))['id'], expected)
        with self.assertRaises(ValueError):
            m.stamp('2026-10-07T09:00:00')

    def test_news_only_finalization_preserves_old_items_and_rolling_feed(self):
        self.run_op()
        original=copy.deepcopy(self.state()['windows'][0]['items'])
        rolling=self.root/'public/data/humor/current.json';rolling.parent.mkdir(parents=True)
        rolling.write_text('{"preserve":"rolling data is independent"}\n')
        rolling_bytes=rolling.read_bytes()
        result=self.run_op('finalize-news',payload('news-only',edition='2026-10-07-am'),AFTER)
        self.assertEqual(self.snapshot()['items'],[])
        self.assertEqual(self.snapshot()['channel'],'news')
        legacy=next(w for w in self.state()['windows'] if w['id']=='2026-10-07-am')
        self.assertEqual(legacy['items'],original)
        self.assertEqual(rolling.read_bytes(),rolling_bytes)
        self.assertTrue(self.run_op('finalize-news',payload('news-only',edition='2026-10-07-am'),AFTER)['replayed'])
        self.assertEqual(result['id'],'2026-10-07-am')

    def test_rolling_mode_blocks_retired_writes_and_all_channel_finalization(self):
        self.run_op()
        rolling=self.root/'public/data/humor/current.json';rolling.parent.mkdir(parents=True);rolling.write_text('{}')
        with self.assertRaisesRegex(ValueError,'finalize-news'):self.final()
        with self.assertRaisesRegex(ValueError,'no longer'):self.run_op(data=payload('new-topic',items=[item('two')]))

    def test_news_only_existing_snapshot_is_never_rewritten(self):
        self.run_op();self.final()
        before=(self.root/'public/data/live/snapshots/2026-10-07-am.json').read_bytes()
        result=self.run_op('finalize-news',payload('news-again',edition='2026-10-07-am'),AFTER)
        self.assertTrue(result['replayed'])
        self.assertEqual((self.root/'public/data/live/snapshots/2026-10-07-am.json').read_bytes(),before)

    def test_news_only_finalization_keeps_issue_generation_with_legacy_items(self):
        self.run_op()
        fixtures=m.load_module('news_only_fixtures',m.ROOT/'scripts/news/test_publish.py')
        self.run_op('stage-news',payload('prepare-news-only',expectedRevision=0,brief=fixtures.early_fixture()))
        self.run_op('finalize-news',payload('finish-news-only',edition='2026-10-07-am'),AFTER)
        published=json.loads((self.root/'public/data/news/2026-10-07/am.json').read_text())
        self.assertEqual(published['cutoffAt'],'2026-10-07T08:30:00+09:00')
        self.assertEqual(published['generatedAt'],'2026-10-07T08:55:00+09:00')
        self.assertEqual(published['finalizedAt'],m.iso(AFTER))
        self.assertTrue((self.root/'public/data/news/issues/index.json').exists())
        self.assertEqual(self.snapshot()['items'],[])
        self.assertIsNotNone(self.snapshot()['news'])

    def test_new_item_and_dry_run_never_write(self):
        self.run_op(check=True)
        self.assertFalse((self.root / 'public' / m.CURRENT).exists())
        self.run_op()
        self.assertEqual(self.state()['windows'][0]['items'][0]['revision'], 1)
        self.assertEqual((self.root / 'public' / m.CURRENT).read_bytes(), (self.root / 'docs' / m.CURRENT).read_bytes())

    def test_snapshot_keeps_original_and_actual_finalization_time(self):
        self.run_op()
        self.final()
        s = self.snapshot()
        self.assertEqual(s['scheduledFor'], m.iso(BOUNDARY))
        self.assertEqual(s['finalizedAt'], m.iso(AFTER))
        self.assertEqual(s['items'][0]['lastVerifiedAt'], m.iso(BEFORE))
        self.assertEqual(self.state()['windows'][0]['id'], '2026-10-07-pm')
        self.assertEqual(self.state()['windows'][0]['items'], [])

    def test_boundary_arrival_goes_to_next_window_even_with_older_observation(self):
        self.run_op()
        self.run_op(data=payload('run-two', items=[item('topic-two')]), now=BOUNDARY)
        self.final()
        self.assertEqual([i['id'] for i in self.snapshot()['items']], ['topic-one'])
        self.assertEqual([i['id'] for i in self.state()['windows'][0]['items']], ['topic-two'])

    def test_late_update_does_not_mutate_pending_or_finalized_versions(self):
        self.run_op()
        update = item(); update.update(expectedRevision=1, summary='새 확인 내용')
        self.run_op(data=payload('run-two', items=[update]), now=BOUNDARY)
        self.final()
        self.assertEqual(self.snapshot()['items'][0]['summary'], item()['summary'])
        self.assertEqual(self.state()['windows'][0]['items'][0]['summary'], '새 확인 내용')

    def test_idempotency_same_op_and_conflicting_op(self):
        self.run_op()
        before = (self.root / 'public' / m.CURRENT).read_bytes()
        self.assertTrue(self.run_op(now=AFTER)['replayed'])
        self.assertEqual((self.root / 'public' / m.CURRENT).read_bytes(), before)
        other = item();other['summary']='다른 내용'
        with self.assertRaisesRegex(ValueError, 'operationId reused'):
            self.run_op(data=payload(items=[other]))

    def test_finalize_retry_different_operation_does_not_rewrite_bytes(self):
        self.run_op();self.final()
        before = (self.root / 'public/data/live/snapshots/2026-10-07-am.json').read_bytes()
        self.assertTrue(self.final(now=m.stamp('2026-10-08T22:00:00+09:00'), op='another-finalizer')['replayed'])
        self.assertEqual((self.root / 'public/data/live/snapshots/2026-10-07-am.json').read_bytes(), before)

    def test_revision_conflict_and_stable_first_discovery(self):
        self.run_op()
        with self.assertRaisesRegex(ValueError, 'revision conflict'):
            self.run_op(data=payload('run-two', items=[item()]))
        update=item();update.update(expectedRevision=1, firstObservedAt='2026-10-06T10:00:00+09:00')
        with self.assertRaisesRegex(ValueError, 'firstObservedAt'):
            self.run_op(data=payload('run-two', items=[update]))

    def test_duplicate_topic_and_canonical_url(self):
        a=item();a['canonicalUrl']=source()['url'];self.run_op(data=payload(items=[a]))
        for other in [dict(item('other'), topicKey=a['topicKey']), dict(item('other'), canonicalUrl=source()['url']+'?utm_source=test#fragment')]:
            other['sources'][0]['url']=other.get('canonicalUrl') or source()['url']
            with self.assertRaisesRegex(ValueError, 'duplicate topic or original'):
                self.run_op(data=payload('other-run', items=[other]))

    def test_atomic_batch_rejects_all_if_second_fails(self):
        bad=item('bad');bad['safetyChecked']=False
        with self.assertRaises(ValueError):
            self.run_op(data=payload(items=[item(),bad]))
        self.assertFalse((self.root / 'public' / m.CURRENT).exists())

    def test_empty_failed_and_blocked_runs_remain_visible(self):
        self.run_op('init', payload('init'))
        for i,status in enumerate(['empty','blocked','failed','partial']):
            c=dict(id=f'check-{i}', channel='topics', source='테스트', status=status,
                   checkedAt=m.iso(BEFORE), count=0 if status=='empty' else None, note='확인 범위와 실패 이유')
            self.run_op('check', payload(f'run-{i}', check=c))
        self.final()
        self.assertTrue(self.snapshot()['empty'])
        self.assertEqual(len(self.snapshot()['checks']),4)

    def test_early_finalize_and_missing_historical_window_rejected(self):
        self.run_op()
        with self.assertRaisesRegex(ValueError,'before scheduledFor'):
            self.final(now=BEFORE)
        with self.assertRaisesRegex(ValueError,'no recorded window'):
            self.run_op('finalize', payload('old', edition='2026-10-06-pm'), AFTER)

    def test_future_values_timezone_and_numeric_unknown_rejected(self):
        for key,value in [('lastVerifiedAt','2026-10-07T09:00:00+09:00'),('firstObservedAt','2026-10-07T08:59:59'),('rightsChecked',False)]:
            a=item();a[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):m.validate_item(a,BEFORE)
        for value in [True,-1,float('inf'),'100']:
            a=item();a['observations'][0]['value']=value
            with self.assertRaises(ValueError):m.validate_item(a,BEFORE)

    def test_instagram_auxiliary_and_x_korea_evidence(self):
        a=item();s=a['sources'][0];s.update(platform='instagram',region='KR',regionEvidenceUrl=source()['url'])
        with self.assertRaisesRegex(ValueError,'Instagram'):m.validate_item(a,BEFORE)
        s.update(platform='x',region='KR',regionEvidenceUrl=None)
        with self.assertRaises(ValueError):m.validate_item(a,BEFORE)
        s['regionEvidenceUrl']='https://example.org/korea';m.validate_item(a,BEFORE)
        s.update(platform='instagram',region='unknown',regionEvidenceUrl=None);m.validate_item(a,BEFORE)

    def test_source_quotes_titles_and_retired_tags(self):
        a=item();a['sources'][0]['quotes']=['word '*26]
        with self.assertRaisesRegex(ValueError,'25 words'):m.validate_item(a,BEFORE)
        a=item();a['sources'][0]['title']='[ㅎㅂ] 제외 글'
        with self.assertRaisesRegex(ValueError,'excluded'):m.validate_item(a,BEFORE)

    def community_item(self):
        a=item();s=a['sources'][0];s.update(url='https://aagag.com/issue/?idx=123',platform='aagag',title=a['title'])
        a.update(kind='community',summary='',canonicalUrl=s['url'],observations=[])
        a['content']=dict(id=a['id'],topicKey=a['topicKey'],title=a['title'],category='유머',summary=[],
            originalText='짧은 원문',comments=[dict(id='comment-1',text='ㅋㅋㅋ')],kCount=11,commentCount=3,
            commentsVerifiedAt=m.iso(BEFORE),selectionReason='실제 ㅋ 기준',popularityEvidence='표시 댓글 ㅋ 합계',
            verificationNote='확인 범위',imageUrl='https://example.org/a.jpg',sources=[dict(s)])
        return a

    def test_community_single_image_and_body_images_video_roundtrip(self):
        a=self.community_item();self.run_op(data=payload(items=[a]))
        self.assertEqual(self.state()['windows'][0]['items'][0]['content']['imageUrl'],a['content']['imageUrl'])
        a['expectedRevision']=1;a['content'].update(bodyImages=[dict(url='https://example.org/b.jpg',width=100,height=300),
            dict(url='https://example.org/a.jpg',width=100,height=100)],bodyImagesSourceUrl=a['canonicalUrl'],bodyImagesVerifiedAt=m.iso(BEFORE),videoUrl='https://example.org/video.mp4')
        self.run_op(data=payload('images',items=[a]));self.final()
        self.assertEqual(self.snapshot()['items'][0]['content'],a['content'])

    def test_community_laughter_and_invalid_media(self):
        a=self.community_item();a['content']['kCount']=10
        with self.assertRaisesRegex(AssertionError,'at least 11'):m.validate_item(a,BEFORE)
        a=self.community_item();a['content']['imageUrl']='data:image/png;base64,a'
        with self.assertRaises((ValueError,AssertionError)):m.validate_item(a,BEFORE)
        a=self.community_item();a['content']['originalText']='word '*26
        with self.assertRaisesRegex(AssertionError,'quotations'):m.validate_item(a,BEFORE)

    def test_macro_deduplicates_recent_legacy_archive(self):
        a=self.community_item();base=self.root/'public/data/community';base.mkdir(parents=True)
        (base/'index.json').write_text(json.dumps({'editions':[{'path':'old.json'}]}))
        original=json.dumps({'stories':[a['content']]});(base/'old.json').write_text(original)
        with self.assertRaisesRegex(ValueError,'recent legacy'):
            self.run_op(data=payload(items=[a]))
        self.assertEqual((base/'old.json').read_text(),original)

    def test_macro_and_editorial_routes_share_topic_deduplication(self):
        self.run_op()
        a=self.community_item();a['id']='other-id';a['content']['id']='other-id'
        with self.assertRaisesRegex(ValueError,'duplicate topic'):
            self.run_op(data=payload('other-route',items=[a]))

    def test_explicit_correction_preserves_snapshot(self):
        self.run_op();self.final();before=m.encoded(self.snapshot())
        c=dict(id='correction-one',snapshotId='2026-10-07-am',itemId='topic-one',action='correction',
               reason='수치 오기',text='수치는 확인되지 않았습니다.',verifiedAt=m.iso(BEFORE),sources=[source()],safetyChecked=True,rightsChecked=True)
        self.run_op('correct',payload('correct-one',correction=c),AFTER)
        self.assertEqual(m.encoded(self.snapshot()),before)
        self.assertEqual(self.state()['corrections'][0]['text'],c['text'])

    def test_crash_after_snapshot_before_manifest_is_recovered(self):
        self.run_op();original=m.atomic_write
        def fail(path,body):
            if str(path).endswith(m.CURRENT):raise OSError('simulated crash')
            original(path,body)
        with patch.object(m,'atomic_write',side_effect=fail),self.assertRaises(OSError):self.final()
        self.assertTrue((self.root/'.git/daily-k-live.pending.json').exists())
        with self.assertRaisesRegex(ValueError,'pending transaction'):self.run_op(check=True)
        self.run_op('recover',payload('recover'),AFTER)
        self.assertEqual(len(self.state()['snapshots']),1)
        self.assertEqual((self.root/'public'/m.CURRENT).read_bytes(),(self.root/'docs'/m.CURRENT).read_bytes())
        self.assertTrue(self.final()['replayed'])

    def test_journal_replays_dependency_order_despite_sorted_serialization(self):
        self.run_op();original=m.atomic_write;written=[]
        def track(path,body):
            written.append(str(path));original(path,body)
        with patch.object(m,'atomic_write',side_effect=track):self.final()
        snapshot=next(i for i,p in enumerate(written) if '/snapshots/' in p)
        manifests=[i for i,p in enumerate(written) if p.endswith(m.CURRENT)]
        self.assertTrue(all(snapshot<i for i in manifests))

    def test_concurrent_writers_and_finalizers(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            jobs=[pool.submit(self.run_op,'upsert',payload(f'run-{i}',items=[item(f'topic-{i}')])) for i in range(6)]
            [job.result() for job in jobs]
        self.assertEqual(len(self.state()['windows'][0]['items']),6)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            [job.result() for job in [pool.submit(self.final,AFTER,f'final-{i}') for i in range(4)]]
        self.assertEqual(len(self.state()['snapshots']),1)
        self.assertEqual(len(self.snapshot()['items']),6)

    def test_news_preparation_and_finalization_preserve_cutoff_and_issues(self):
        fixtures=m.load_module('news_test_fixtures',m.ROOT/'scripts/news/test_publish.py')
        brief=fixtures.early_fixture()
        (self.root/'public/data/feed.json').write_text('legacy feed unchanged')
        self.run_op('stage-news',payload('prepare-news',expectedRevision=0,brief=brief))
        self.assertFalse((self.root/'public/data/news/2026-10-07/am.json').exists())
        self.final()
        published=json.loads((self.root/'public/data/news/2026-10-07/am.json').read_text())
        self.assertEqual(published['cutoffAt'],'2026-10-07T08:30:00+09:00')
        self.assertEqual(published['generatedAt'],'2026-10-07T08:55:00+09:00')
        self.assertEqual(published['finalizedAt'],m.iso(AFTER))
        self.assertTrue((self.root/'public/data/news/issues/index.json').exists())
        self.assertEqual((self.root/'public/data/feed.json').read_text(),'legacy feed unchanged')

    def test_late_news_cannot_be_inserted_into_past_window(self):
        fixtures=m.load_module('news_test_fixtures',m.ROOT/'scripts/news/test_publish.py')
        self.run_op()
        with self.assertRaisesRegex(ValueError,'no backdated'):
            self.run_op('stage-news',payload('late-news',expectedRevision=0,brief=fixtures.early_fixture()),AFTER)

    def test_remote_cas_reapplies_two_writers_without_lost_updates(self):
        self.run_op('init',payload('init'))
        m.git(self.root,'add','.');m.git(self.root,'commit','-qm','Initial test state')
        remote=self.root/'remote.git'
        subprocess.run(['git','clone','--bare','--quiet',str(self.root),str(remote)],check=True)
        m.git(self.root,'remote','add','origin',str(remote))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(m.push_operation,self.root,'upsert',payload(f'push-{i}',items=[item(f'topic-{i}')])) for i in range(2)]
            results=[job.result() for job in jobs]
        self.assertTrue(all(r['pushed'] for r in results))
        state=json.loads(subprocess.check_output(['git','--git-dir',str(remote),'show','main:public/'+m.CURRENT],text=True))
        self.assertEqual(set(state['registry']),{'topic-0','topic-1'})
        # The caller's files and branch are not used as the publication checkout.
        self.assertEqual(self.state()['registry'],{})


if __name__=='__main__':
    unittest.main()
