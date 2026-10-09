import sys, tempfile, unittest, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from runtime_state import Runtime,source_digest
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.run=self.root/'run';self.run.mkdir();(self.run/'run.json').write_text('{"end":"2026-10-09T02:03:32Z"}');(self.run/'posts').mkdir();(self.run/'listings').mkdir()
  self.r=Runtime(self.root/'state.json');self.sha=source_digest();self.now='2026-10-09T12:00:00Z'
  self.s=self.r.apply('init',{'sourceSha256':self.sha},self.now);self.call('start-run',runDir=str(self.run))
 def call(self,c,**kw):
  self.s=self.r.apply(c,{'revision':self.s['revision'],'sourceSha256':self.sha,'runDir':str(self.run),**kw},self.now);return self.s
 def begin(self):self.call('begin',owner='worker');return {'owner':'worker','fence':self.s['lease']['fence']}
 def test_stale_revision(self):
  with self.assertRaisesRegex(ValueError,'revision'):self.r.apply('begin',{'revision':0,'sourceSha256':self.sha},self.now)
 def test_second_writer(self):
  self.begin()
  with self.assertRaisesRegex(ValueError,'active'):self.call('begin',owner='other')
 def test_expired_not_taken_over(self):
  args=self.begin();self.now='2026-10-09T12:11:00Z'
  with self.assertRaisesRegex(ValueError,'Expired'):self.call('guard',**args)
  with self.assertRaisesRegex(ValueError,'active'):self.call('begin',owner='other')
 def test_pause_revokes_fence(self):
  args=self.begin();self.call('pause')
  with self.assertRaisesRegex(ValueError,'fence'):self.call('guard',**args)
 def test_denial_requires_review(self):
  args=self.begin();self.call('finish',**args,outcome='paused_requires_user')
  with self.assertRaises(ValueError):self.call('begin',owner='worker')
  with self.assertRaises(ValueError):self.call('resume')
  self.call('resume',reviewReference='verified-owner-approval-message',inFlightResolved=True);self.begin()
 def test_source_change(self):
  with self.assertRaisesRegex(ValueError,'Source'):self.r.apply('begin',{'revision':self.s['revision'],'sourceSha256':'b'*64},self.now)
 def test_missing_evidence(self):
  (self.run/'posts').rmdir()
  with self.assertRaisesRegex(ValueError,'evidence'):self.begin()
 def test_changed_manifest(self):
  (self.run/'run.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'manifest'):self.begin()
 def test_guard_does_not_change_revision(self):
  args=self.begin();rev=self.s['revision'];self.call('guard',**args);self.assertEqual(self.s['revision'],rev)
 def test_finish_preserves_run(self):
  args=self.begin();run=self.s['run'];self.call('finish',**args,outcome='ready');self.assertEqual(run,self.s['run'])
 def test_no_fake_complete(self):
  (self.run/'summary.json').write_text('{"complete":false}')
  args=self.begin()
  with self.assertRaisesRegex(ValueError,'verification'):self.call('finish',**args,outcome='verified_complete')
 def test_closed_gaps_requires_traversal(self):
  (self.run/'summary.json').write_text('{"complete":false}')
  args=self.begin()
  with self.assertRaisesRegex(ValueError,'Traversal'):self.call('finish',**args,outcome='closed_with_gaps')
 def test_batch_identity(self):
  self.call('record-batch',operationId='batch-1',payloadSha256='b'*64);self.call('record-batch',operationId='batch-1',payloadSha256='b'*64)
  with self.assertRaisesRegex(ValueError,'payload'):self.call('record-batch',operationId='batch-1',payloadSha256='c'*64)
 def test_new_cycle_must_use_fresh_run(self):
  (self.run/'summary.json').write_text('{"complete":true}')
  args=self.begin();self.call('finish',**args,outcome='verified_complete')
  with self.assertRaisesRegex(ValueError,'Fresh'):self.call('start-run',runDir=str(self.run))
 def test_initialize_never_resets(self):
  with self.assertRaises(ValueError):self.r.apply('init',{'sourceSha256':self.sha},self.now)
 def test_unexpected_evidence_fails_closed(self):
  (self.run/'posts'/'1.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'reconciliation'):self.begin()
 def test_wrong_run_directory(self):
  with self.assertRaisesRegex(ValueError,'directory'):self.call('begin',owner='worker',runDir=str(self.root/'other'))
 def test_pause_cannot_resume_while_inflight(self):
  self.begin();self.call('pause')
  with self.assertRaisesRegex(ValueError,'In-flight'):self.call('resume',reviewReference='review',inFlightResolved=True)
 def test_no_A_B_A_reuse(self):
  (self.run/'summary.json').write_text('{"complete":true}')
  args=self.begin();self.call('finish',**args,outcome='verified_complete')
  other=self.root/'other';other.mkdir();(other/'run.json').write_text('{}');(other/'posts').mkdir();(other/'listings').mkdir();(other/'summary.json').write_text('{"complete":true}')
  self.call('start-run',runDir=str(other));self.call('begin',owner='worker',runDir=str(other));self.call('finish',owner='worker',fence=self.s['lease']['fence'],outcome='verified_complete')
  with self.assertRaisesRegex(ValueError,'Fresh'):self.call('start-run',runDir=str(self.run))
if __name__=='__main__':unittest.main()
