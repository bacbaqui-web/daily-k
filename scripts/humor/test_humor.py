import concurrent.futures
import copy
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import manage as m
import collector as c

NOW=m.stamp('2026-10-10T09:00:00+09:00')
URL='https://aagag.com/issue/?idx=123'

def item(k=10, age=1):
    published=m.iso(NOW-timedelta(hours=age)); observed=m.iso(NOW)
    return dict(id='aagag-123',canonicalUrl=URL,title='테스트 전용 유머',publishedAt=published,firstObservedAt=observed,lastVerifiedAt=observed,expectedRevision=0,
        publicationEvidence=dict(method='aagag-otime',sourceUrl=URL,value=published,raw=str(m.stamp(published).timestamp()),observedAt=observed,semanticsVerified=True),
        nativeComments=dict(sourceUrl=URL,observedAt=observed,scope='native-aagag-all',complete=True,reportedCount=1,rows=[dict(id='1',literalKCount=k)]),
        review=dict(safetyChecked=True,rightsChecked=True,verifiedAt=observed,note='테스트 전용 검토'),
        sources=[dict(name='애객',title='테스트 전용 유머',url=URL,publishedAt=published,verifiedAt=observed)],
        content=dict(imageUrl='https://i.aagag.com/test.jpg',originalText='',comments=[]),limitations='테스트 자료이며 실서비스에 쓰지 않음')

def payload(op='test',**extra): return dict(schemaVersion=1,operationId=op,**extra)


class HumorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
    def tearDown(self): self.tmp.cleanup()
    def run_op(self,command='upsert',data=None,now=NOW,check=False):
        return m.execute(self.root,command,data or payload(items=[item()]),check=check,now=now)[0]
    def state(self): return json.loads((self.root/'public'/m.CURRENT).read_text())
    def test_threshold_9_and_10(self):
        with self.assertRaisesRegex(ValueError,'at least 10'):self.run_op(data=payload(items=[item(9)]))
        self.run_op();self.assertEqual(self.state()['items'][0]['kCount'],10)
    def test_literal_unicode_no_normalization(self):
        value=c.parse_comments({'mode':'success','total':1,'comment':[{'w_idx':1,'w_content':'<p>ㅋᄏ크 ㅋㅋ</p><script>ㅋㅋㅋㅋㅋㅋ</script>'}]})
        self.assertEqual(m.counts(value),(3,1))
    def test_24h_boundary_and_equivalent_timezones(self):
        before=item(age=24-1/3600000);self.run_op(data=payload(items=[before]))
        self.run_op('expire',payload('expiry'),NOW+timedelta(milliseconds=1))
        self.assertEqual(self.state()['items'],[])
        self.assertIn('aagag-123',self.state()['registry'])
        self.assertTrue(list((self.root/'public/data/humor/events').glob('*.json')))
        exact=item(age=24)
        with self.assertRaises(ValueError):m.validate_item(exact,NOW)
        value=item();value['publishedAt']='2026-10-09T23:00:00Z'
        self.assertEqual(m.validate_item(value,NOW)['publishedAt'],item()['publishedAt'])
    def test_missing_naive_future_and_unverified_publication_hold(self):
        for field,value in [('publishedAt',None),('publishedAt','2026-10-10T08:00:00'),('publishedAt','2026-10-11T08:00:00+09:00')]:
            bad=item();bad[field]=value
            with self.assertRaises((ValueError,TypeError)):m.validate_item(bad,NOW)
        bad=item();bad['publicationEvidence']['semanticsVerified']=False
        with self.assertRaisesRegex(ValueError,'unverified'):m.validate_item(bad,NOW)
        bad=item();bad['publicationEvidence']['raw']='1'
        with self.assertRaisesRegex(ValueError,'epoch'):m.validate_item(bad,NOW)
    def test_no_relisting_or_first_observation_reset(self):
        self.run_op();bad=item(age=.5);bad['expectedRevision']=1
        with self.assertRaisesRegex(ValueError,'immutable'):self.run_op(data=payload('changed-time',items=[bad]))
        bad=item();bad['expectedRevision']=1;bad['firstObservedAt']=m.iso(NOW-timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError,'immutable'):self.run_op(data=payload('changed-first',items=[bad]))
    def test_duplicate_comment_ids_reconcile_and_conflict(self):
        evidence=item()['nativeComments'];evidence['rows']*=2
        self.assertEqual(m.counts(evidence),(10,1))
        evidence['rows'][1]=dict(id='1',literalKCount=12)
        with self.assertRaisesRegex(ValueError,'conflicting'):m.counts(evidence)
    def test_partial_or_external_native_evidence_fails(self):
        for change in [dict(complete=False),dict(reportedCount=2),dict(scope='external')]:
            bad=item();bad['nativeComments'].update(change)
            with self.assertRaises(ValueError):m.validate_item(bad,NOW)
    def test_revision_url_revision_dedupe_and_retry(self):
        self.run_op();data=payload('revision',items=[item()]);data['items'][0].update(canonicalUrl=URL+'_2',expectedRevision=1)
        data['items'][0]['sources'][0]['url']=URL+'_2'
        self.run_op(data=data)
        self.assertEqual(len(self.state()['items']),1)
        self.assertEqual(self.state()['items'][0]['revision'],2)
        self.assertTrue(self.run_op(data=data)['replayed'])
        data['items'][0]['title']='다른 제목'
        with self.assertRaisesRegex(ValueError,'operationId'):self.run_op(data=data)
    def test_dry_run_is_non_writing_and_mirror_identical(self):
        self.run_op(check=True);self.assertFalse((self.root/'public').exists())
        self.run_op()
        self.assertEqual((self.root/'public'/m.CURRENT).read_bytes(),(self.root/'docs'/m.CURRENT).read_bytes())
    def test_concurrent_same_operation_is_idempotent(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:self.run_op(),range(2)))
        self.assertEqual(sum(bool(r.get('replayed')) for r in results),1)
        self.assertEqual(len(self.state()['items']),1)
    def test_interrupted_journal_recovers(self):
        with patch.object(m,'recover',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):self.run_op()
        self.assertTrue((self.root/'.git/daily-k-humor.pending.json').exists())
        self.run_op('recover',payload('recover'))
        self.assertEqual(len(self.state()['items']),1)
        self.assertTrue(self.run_op()['replayed'])
    def test_safe_media_legacy_body_images_video_and_quotes(self):
        m.validate_item(item(),NOW)
        value=item();value['content'].update(bodyImages=[dict(url='https://i.aagag.com/one.jpg',width=100,height=200)],bodyImagesSourceUrl=URL,bodyImagesVerifiedAt=m.iso(NOW),videoUrl='https://i.aagag.com/a.mp4')
        m.validate_item(value,NOW)
        for key,content in [('imageUrl','file:///secret'),('originalText','word '*30),('bodyImages',[dict(url='https://i.aagag.com/a.jpg',width=0,height=1)])]:
            bad=copy.deepcopy(value);bad['content'][key]=content
            with self.assertRaises((ValueError,AssertionError)):m.validate_item(bad,NOW)
        for title in ['[ㅇㅎ] 제외','ㅎㅂ 게시물','성추행 의혹']:
            bad=item();bad['title']=title
            with self.assertRaises(ValueError):m.validate_item(bad,NOW)
    def test_review_and_combined_quotation_budget(self):
        bad=item();bad['review']['safetyChecked']=False
        with self.assertRaises(ValueError):m.validate_item(bad,NOW)
        bad=item();bad['content']['originalText']='a '*20;bad['sources'][0]['quotes']=['b '*20]
        with self.assertRaises(ValueError):m.validate_item(bad,NOW)
    def test_failure_check_keeps_unexpired_then_expires(self):
        self.run_op();check=dict(status='challenge',checkedAt=m.iso(NOW),count=None,note='CAPTCHA stopped')
        self.run_op('check',payload('blocked',check=check))
        self.assertEqual(len(self.state()['items']),1)
        check['count']=0
        with self.assertRaises(ValueError):self.run_op('check',payload('wrong-zero',check=check))
        self.run_op('expire',payload('later'),NOW+timedelta(hours=23))
        self.assertEqual(self.state()['items'],[])
    def test_remote_two_writers_reapply_without_losing_updates(self):
        git=lambda *args:m.live.git(self.root,*args)
        git('branch','-M','main');git('config','user.email','test@example.invalid');git('config','user.name','Tests')
        code=self.root/'scripts/humor/manage.py';code.parent.mkdir(parents=True);code.write_text('# deployment marker for isolated test only\n')
        self.run_op('init',payload('initialize'))
        git('add','.');git('commit','-qm','Fixture')
        remote=self.root/'remote.git';subprocess.run(['git','clone','--bare','--quiet',str(self.root),str(remote)],check=True)
        git('remote','add','origin',str(remote))
        second=item();second['id']='aagag-124';second['canonicalUrl']=URL.replace('123','124')
        for key in ('publicationEvidence','nativeComments'):second[key]['sourceUrl']=second['canonicalUrl']
        second['sources'][0]['url']=second['canonicalUrl']
        with patch.object(m,'datetime') as clock:
            clock.now.return_value=NOW
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                jobs=[pool.submit(m.push_operation,self.root,'upsert',payload(f'parallel-{i}',items=[value])) for i,value in enumerate([item(),second])]
                results=[job.result() for job in jobs]
        self.assertTrue(all(r['pushed'] for r in results))
        result=json.loads(subprocess.check_output(['git','--git-dir',str(remote),'show','main:public/'+m.CURRENT],text=True))
        self.assertEqual({i['id'] for i in result['items']},{'aagag-123','aagag-124'})
        self.assertEqual(self.state()['items'],[])


def article(idx=123,age=1,title='테스트 유머'):
    data=dict(idx=idx,otime=(NOW-timedelta(hours=age)).timestamp(),title=title,content='<img src="https://i.aagag.com/test.jpg">')
    return '\n'.join('AAGAG_AA.'+key+' = '+json.dumps(value)+';' for key,value in data.items())
def listing(ids=(123,),next_page=False):
    return '<div id="listIssue">'+''.join(f'<a class="article" href="/issue/?idx={i}"><span class="title">테스트 유머</span></a>' for i in ids)+'</div>'+('<a href="?page=2">2</a>' if next_page else '')
class FakeClient:
    def __init__(self,blocked=False):self.calls=[];self.blocked=blocked
    def get(self,url):
        self.calls.append(url)
        if url.endswith('/issue/'):return listing()
        if self.blocked:raise c.Blocked(url,'challenge','challenge',403)
        return article()
    def form(self,path,data):
        self.calls.append(path)
        return dict(mode='success',total=1,comment=[dict(w_idx=1,w_content='ㅋ'*10)])


class CollectorTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'state.json'
    def tearDown(self):self.tmp.cleanup()
    def run_collector(self,client=None,**kw):return c.run_once(self.path,client or FakeClient(),clock=lambda:NOW,**kw)
    def test_regular_program_collects_counts_without_ai_and_holds_time_semantics(self):
        state=self.run_collector();r=state['records']['aagag-123']
        self.assertEqual(r['kCount'],10);self.assertEqual(r['status'],'held')
        self.assertFalse(r['publicationEvidence']['semanticsVerified'])
        self.assertNotIn('w_content',json.dumps(state));self.assertIn('context_media_rights_review_required',r['holds'])
    def test_listing_revision_dedupe_and_actual_next_link(self):
        source=listing(next_page=True).replace('</div>','<a class="article" href="/issue/?idx=123_2"><span class="title">동일 글</span></a></div>')
        values,next_link=c.parse_list(source,'https://aagag.com/issue/')
        self.assertEqual(len(values),1);self.assertEqual(next_link,'https://aagag.com/issue/?page=2')
    def test_block_stops_and_requires_explicit_resume(self):
        client=FakeClient(True);state=self.run_collector(client)
        self.assertEqual(state['status'],'challenge');self.assertEqual(len(state['pending']),1)
        fresh=FakeClient();state=self.run_collector(fresh)
        self.assertEqual(fresh.calls,[])
        state=self.run_collector(fresh,resume_after_review=True)
        self.assertEqual(state['status'],'complete');self.assertEqual(len(state['records']),1)
    def test_partial_and_interruption_resume_without_duplicate(self):
        class Interrupt(FakeClient):
            def form(self,*a):raise KeyboardInterrupt()
        self.assertEqual(self.run_collector(Interrupt())['status'],'stopped')
        state=self.run_collector();self.assertEqual(len(state['records']),1)
        client=FakeClient();state=self.run_collector(client);self.assertEqual(len(state['records']),1)
    def test_unknown_time_partial_comments_and_excluded_title(self):
        with self.assertRaises(ValueError):c.parse_article(article().replace('AAGAG_AA.otime','OTHER.otime'),URL,NOW)
        self.assertTrue(c.parse_article(article(title='ㅇㅎ 사진'),URL,NOW)['excluded'])
        for data in [dict(mode='fail'),dict(mode='success',total=2,comment=[dict(w_idx=1,w_content='ㅋ'*20)])]:
            with self.assertRaises(ValueError):c.parse_comments(data)
    def test_expired_posts_do_not_fetch_comments(self):
        class Old(FakeClient):
            def get(self,url):return listing() if url.endswith('/issue/') else article(age=24)
            def form(self,*a):raise AssertionError('expired comments must not be requested')
        state=self.run_collector(Old());self.assertEqual(state['activeCandidateIds'],[])
    def test_challenge_and_refusal_detection(self):
        self.assertTrue(c.challenge({'cf-mitigated':'challenge'},''))
        self.assertTrue(c.challenge({},'<html><title>Just a moment...</title></html>'))
        self.assertFalse(c.challenge({},'<html><title>정상 글</title><p>captcha라는 댓글</p></html>'))
    def test_changed_publication_is_held(self):
        self.run_collector()
        class Relisted(FakeClient):
            def get(self,url):return listing() if url.endswith('/issue/') else article(age=.5)
        state=self.run_collector(Relisted())
        self.assertIn('publication_time_changed_relisting',state['records']['aagag-123']['holds'])
        state=self.run_collector(Relisted())
        self.assertIn('publication_time_changed_relisting',state['records']['aagag-123']['holds'])
    def test_parse_failure_preserves_discovery_and_publication_on_recovery(self):
        first=self.run_collector()['records']['aagag-123']
        with patch.object(c,'parse_article',side_effect=ValueError('temporary changed markup')):
            failed=c.run_once(self.path,FakeClient(),clock=lambda:NOW+timedelta(minutes=1))['records']['aagag-123']
        self.assertEqual(failed['firstObservedAt'],first['firstObservedAt'])
        self.assertEqual(failed['publishedAt'],first['publishedAt'])
        self.assertNotIn('thresholdQualified',failed)
        recovered=c.run_once(self.path,FakeClient(),clock=lambda:NOW+timedelta(minutes=2))['records']['aagag-123']
        self.assertEqual(recovered['firstObservedAt'],first['firstObservedAt'])
        self.assertEqual(recovered['publishedAt'],first['publishedAt'])
        self.assertNotIn('publication_time_changed_relisting',recovered['holds'])
    def test_blocked_state_prunes_candidates_without_network_retry(self):
        self.run_collector();state=json.loads(self.path.read_text());state['status']='challenge';self.path.write_text(json.dumps(state))
        client=FakeClient()
        state=c.run_once(self.path,client,clock=lambda:NOW+timedelta(hours=24))
        self.assertEqual(client.calls,[]);self.assertEqual(state['activeCandidateIds'],[])
    def test_http_403_stops_later_requests(self):
        import io
        import urllib.error
        client=c.Client();calls=[]
        def refusal(request,timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url,403,'Forbidden',{},io.BytesIO(b'<html><title>Just a moment...</title></html>'))
        client.opener.open=refusal
        with self.assertRaises(c.Blocked):client.get(URL)
        with self.assertRaises(c.Blocked):client.get(URL)
        self.assertEqual(len(calls),1)
    def test_robots_wildcard_and_explicit_allow(self):
        rules='User-agent: *\nDisallow: /api/*\nAllow: /api/cmt$\n'
        self.assertFalse(c.robots_allowed(rules,'https://aagag.com/api/issue.history'))
        self.assertTrue(c.robots_allowed(rules,'https://aagag.com/api/cmt'))
        self.assertFalse(c.robots_allowed(rules,'https://aagag.com/api/cmt?x=1'))


if __name__=='__main__':unittest.main()
