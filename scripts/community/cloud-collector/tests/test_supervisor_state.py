import sys,tempfile,unittest,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from runtime_state import Runtime,source_digest
from supervisor_state import inspect,journal
ROOT=Path(__file__).resolve().parents[1]
class ProjectionTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);self.run=self.root/'private-run'
  subprocess.run([sys.executable,str(ROOT/'src/checkpoint.py'),'init','--end','2026-10-09T02:03:32Z','--run-dir',str(self.run)],check=True,capture_output=True)
  for name in ['posts','listings']:(self.run/name).mkdir(exist_ok=True)
  self.state=self.root/'private-state.json';self.r=Runtime(self.state);self.sha=source_digest();s=self.r.apply('init',{'sourceSha256':self.sha});self.r.apply('start-run',{'sourceSha256':self.sha,'revision':s['revision'],'runDir':str(self.run)})
 def test_allowlist_has_no_paths_or_raw(self):
  value=inspect(self.state);self.assertTrue(value['available']);p=json.dumps(value['projection']);self.assertNotIn('private-run',p);self.assertNotIn(str(self.root),p);self.assertNotIn('evidenceFiles',p);self.assertEqual(value['projection']['progress']['observedRecords'],0)
 def test_stale_summary_recomputed(self):
  (self.run/'summary.json').write_text('{"observedRecords":999,"complete":true}')
  value=inspect(self.state);self.assertEqual(value['projection']['progress']['observedRecords'],0);self.assertFalse(value['projection']['coverage']['complete'])
 def test_missing_raw_fails_closed(self):
  (self.run/'posts').rmdir();self.assertFalse(inspect(self.state)['available'])
 def test_extra_raw_fails_closed(self):
  (self.run/'posts'/'1.json').write_text('{}');self.assertFalse(inspect(self.state)['available'])
 def test_journal_append_keeps_prior_event(self):
  p=self.root/'journal.json';journal(p,{'stage':'one'});journal(p,{'stage':'two'});self.assertEqual(len(json.loads(p.read_text())['events']),2)
 def test_active_runtime_does_not_recompute(self):
  s=self.r.read();self.r.apply('begin',{'revision':s['revision'],'sourceSha256':self.sha,'runDir':str(self.run),'owner':'worker'})
  value=inspect(self.state);self.assertFalse(value['available']);self.assertEqual(value['reasonCode'],'local_execution_unresolved')
 def test_two_inspectors_are_serialized(self):
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=2) as pool:
   values=list(pool.map(lambda _:inspect(self.state),range(4)))
  self.assertTrue(all(v['available'] for v in values))
if __name__=='__main__':unittest.main()
