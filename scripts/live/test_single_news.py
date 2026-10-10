"""Single-run news contract; all writes and remote races use temporary repos."""
import concurrent.futures
import copy
from datetime import datetime,timedelta
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import manage as m
from test_live import create_repo,payload,item,BEFORE

F=m.load_module('single_news_fixtures',m.ROOT/'scripts/news/test_publish.py')
NOW=m.stamp('2026-10-11T09:15:00+09:00')

def brief(edition='am'):
    value=json.loads(json.dumps(F.early_fixture(edition)).replace('2026-10-08','2026-10-12').replace('2026-10-07','2026-10-11'))
    hour='09' if edition=='am' else '21'
    value['cutoffAt']=f'2026-10-11T{hour}:00:00+09:00'
    value['generatedAt']=f'2026-10-11T{hour}:12:00+09:00'
    for story in value['stories']:
        for source in story['sources']+story['relatedArticles']:source['verifiedAt']=f'2026-10-11T{hour}:05:00+09:00'
    for event in value['events']:event['source']['verifiedAt']=f'2026-10-11T{hour}:05:00+09:00'
    return value

class SingleNewsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);create_repo(self.root)
        m.execute(self.root,'upsert',payload('historical-item',items=[item()]),now=BEFORE)
        for folder in ('public','docs'):
            p=self.root/folder/'data/humor/current.json';p.parent.mkdir(parents=True);p.write_text('{"keep":"unchanged"}\n')
        self.windows=self.state()['windows']
    def tearDown(self):self.temp.cleanup()
    def state(self):return json.loads((self.root/'public'/m.CURRENT).read_text())
    def files(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.glob('public/data/**/*.json')}
    def run_op(self,value=None,op='publish-one',now=NOW,check=False):
        return m.execute(self.root,'publish-news',payload(op,brief=value or brief()),now=now,check=check)[0]
    def test_publish_without_preparation_keeps_actual_times_and_issues(self):
        result=self.run_op();state=self.state();self.assertEqual(state['windows'],self.windows)
        snap=json.loads((self.root/'public/data/live/snapshots/2026-10-11-am.json').read_text())
        self.assertEqual(snap['items'],[]);self.assertEqual(snap['checks'],[]);self.assertEqual(snap['channel'],'news')
        self.assertEqual(snap['scheduledFor'],'2026-10-11T09:00:00+09:00');self.assertEqual(snap['finalizedAt'],m.iso(NOW))
        news=json.loads((self.root/'public/data/news/2026-10-11/am.json').read_text())
        self.assertEqual(news['cutoffAt'],brief()['cutoffAt']);self.assertEqual(news['generatedAt'],brief()['generatedAt'])
        self.assertEqual(news['finalizedAt'],m.iso(NOW));self.assertEqual(result['windowId'],'2026-10-11-am')
        index=json.loads((self.root/'public/data/news/issues/index.json').read_text());self.assertEqual(index['storyCount'],5)
        self.assertEqual((self.root/'public/data/humor/current.json').read_text(),'{"keep":"unchanged"}\n')
        for rel,body in self.files().items():self.assertEqual((self.root/rel.replace('public/','docs/',1)).read_bytes(),body)
    def test_exact_boundary_utc_and_pm_after_midnight_keep_explicit_edition(self):
        value=brief();value['cutoffAt']='2026-10-11T00:00:00Z';value['generatedAt']=value['cutoffAt']
        for s in value['stories']:
            for source in s['sources']+s['relatedArticles']:source['verifiedAt']=value['cutoffAt']
        for e in value['events']:e['source']['verifiedAt']=value['cutoffAt']
        self.run_op(value,now=m.stamp(value['cutoffAt']))
        # A separate temporary repository keeps unrelated fixture topics out of this check.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);create_repo(root)
            m.execute(root,'publish-news',payload('late-pm',brief=brief('pm')),now=m.stamp('2026-10-12T00:15:00+09:00'))
            self.assertTrue((root/'public/data/news/2026-10-11/pm.json').exists())
            self.assertFalse((root/'public/data/news/2026-10-12/am.json').exists())
    def test_early_future_old_cutoff_and_backdated_verification_rejected(self):
        with self.assertRaisesRegex(ValueError,'before'):self.run_op(now=m.stamp('2026-10-11T08:59:59.999+09:00'))
        for change in ['old-cutoff','future-generation','early-verification','source-after-cutoff','naive-time','forged-publication']:
            value=brief()
            if change=='old-cutoff':value['cutoffAt']='2026-10-11T08:30:00+09:00'
            if change=='future-generation':value['generatedAt']='2026-10-11T09:15:01+09:00'
            if change=='early-verification':value['stories'][0]['sources'][0]['verifiedAt']='2026-10-11T08:59:59+09:00'
            if change=='source-after-cutoff':value['stories'][0]['sources'][0]['publishedAt']='2026-10-11T09:00:01+09:00'
            if change=='naive-time':value['generatedAt']='2026-10-11T09:12:00'
            if change=='forged-publication':value['finalizedAt']=value['cutoffAt']
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_op(value)
    def test_retries_never_ignore_changed_brief(self):
        self.run_op();before=self.files()
        self.assertTrue(self.run_op()['replayed']);self.assertTrue(self.run_op(op='different-run')['replayed'])
        self.assertEqual(self.files(),before)
        changed=brief();changed['intro']='변경된 입력'
        for op in ['publish-one','changed-input']:
            with self.assertRaises(ValueError):self.run_op(changed,op=op)
        self.assertEqual(self.files(),before)
    def test_retired_commands_and_historical_overwrite_rejected(self):
        for command,data in [('stage-news',payload('stage',expectedRevision=0,brief=brief())),('finalize-news',payload('finalize',edition='2026-10-11-am')),('finalize-news',payload('ignored-brief',edition='2026-10-07-am',brief=brief()))]:
            with self.assertRaises(ValueError):m.execute(self.root,command,data,now=NOW)
        with self.assertRaisesRegex(ValueError,'never backfill'):self.run_op(F.early_fixture())
    def test_historical_cutoff_and_old_edition_bytes_preserved(self):
        old=F.early_fixture();m.NEWS.publish(old,root=self.root,now=NOW)
        before=(self.root/'public/data/news/2026-10-07/am.json').read_bytes()
        new=brief()
        for i,s in enumerate(new['stories']):
            s['followUp']=dict(editionId=old['id'],storyId=f'topic-am-{i}',delta='테스트 후속 발표에서 수치가 실제로 달라졌습니다.')
            s['keyFacts']['metric']=str(100+i);s['summary'][0]+=' 테스트의 새 수치를 반영합니다.'
        self.run_op(new)
        self.assertEqual((self.root/'public/data/news/2026-10-07/am.json').read_bytes(),before)
        issue=json.loads((self.root/'public/data/news/issues/issue-0.json').read_text())
        self.assertEqual([e['editionId'] for e in issue['entries']],['2026-10-07-am','2026-10-11-am'])
    def test_dry_run_and_news_build_failure_leave_all_files_unchanged(self):
        before=self.files();self.run_op(check=True);self.assertEqual(self.files(),before)
        with patch.object(m,'news_files',side_effect=ValueError('derived issue failure')):
            with self.assertRaises(ValueError):self.run_op()
        self.assertEqual(self.files(),before)
    def test_journal_recovery_finishes_all_files_without_duplicate(self):
        original=m.atomic_write
        def crash(path,body):
            if str(path).endswith('public/data/news/index.json'):raise OSError('simulated crash')
            original(path,body)
        with patch.object(m,'atomic_write',side_effect=crash):
            with self.assertRaises(OSError):self.run_op()
        m.execute(self.root,'recover',payload('recover'),now=NOW)
        self.assertTrue(self.run_op()['replayed']);self.assertEqual(len(self.state()['snapshots']),1)
        for rel,body in self.files().items():self.assertEqual((self.root/rel.replace('public/','docs/',1)).read_bytes(),body)
    def test_concurrent_local_publishers_make_one_snapshot(self):
        with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(lambda n:self.run_op(op=f'concurrent-{n}'),range(4)))
        self.assertEqual(sum(bool(r.get('replayed')) for r in results),3);self.assertEqual(len(self.state()['snapshots']),1)
    def test_remote_cas_retries_same_edition_without_lost_history(self):
        m.git(self.root,'add','.');m.git(self.root,'commit','-qm','Initial test fixtures')
        remote=self.root/'remote.git';subprocess.run(['git','clone','--quiet','--bare',str(self.root),str(remote)],check=True)
        m.git(self.root,'remote','add','origin',str(remote));original=m.git;barrier=threading.Barrier(2);seen=set();lock=threading.Lock();rejected=[]
        def gated(root,*args):
            if args and args[0]=='push':
                tid=threading.get_ident()
                with lock:first=tid not in seen;seen.add(tid)
                if first:barrier.wait(timeout=15)
                try:return original(root,*args)
                except subprocess.CalledProcessError:rejected.append(tid);raise
            return original(root,*args)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return NOW
        before=self.files()
        with patch.object(m,'datetime',Clock),patch.object(m,'git',side_effect=gated),concurrent.futures.ThreadPoolExecutor(2) as pool:
            jobs=[pool.submit(m.push_operation,self.root,'publish-news',payload(f'publish-{i}',brief=brief())) for i in range(2)]
            self.assertTrue(all(job.result()['pushed'] for job in jobs))
        self.assertGreaterEqual(len(rejected),1);self.assertEqual(self.files(),before)
        state=json.loads(subprocess.check_output(['git','--git-dir',str(remote),'show','main:public/'+m.CURRENT],text=True))
        self.assertEqual(len(state['snapshots']),1);self.assertEqual(state['windows'],self.windows)
        self.assertEqual(int(subprocess.check_output(['git','--git-dir',str(remote),'rev-list','--count','main'],text=True)),2)

if __name__=='__main__':unittest.main()
