"""Allowlisted public projection and private supervisor journal. No network."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
from runtime_state import Runtime, source_digest, timestamp

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def inspect(path):
 r=Runtime(path)
 with r.locked():return inspect_locked(r)

def inspect_locked(r):
 s=r.read();run=s.get('run');window=run.get('manifest',{}).get('window',{}) if run else {}
 result={'available':False,'runtimeRevision':s['revision'],'runtimeStatus':s['status'],'sourceSha256':source_digest(),'projection':None,'reasonCode':None}
 if s['status']=='running' or s.get('lease') is not None:result['reasonCode']='local_execution_unresolved';return result
 if s['sourceSha256']!=source_digest():result['reasonCode']='source_changed';return result
 if not run:result['reasonCode']='run_missing';return result
 try:
  r.evidence(s,verify_files=True)
  # Only fixed exact timestamps survive; no titles, paths, raw IDs or comments.
  from runtime_state import parse
  parse(window['start']);parse(window['end'])
 except (ValueError,OSError,KeyError):result['reasonCode']='private_evidence_unavailable';return result
 summaryPath=Path(run['directory'])/'summary.json'
 resultRun=subprocess.run([sys.executable,str(Path(__file__).parent/'checkpoint.py'),'summary','--run-dir',run['directory']],capture_output=True,text=True)
 if resultRun.returncode!=0:result['reasonCode']='derived_checkpoint_invalid';return result
 summary=json.loads(resultRun.stdout)
 def count(k):
  v=summary.get(k);return v if type(v)is int and v>=0 else None
 result['available']=True
 result['projection']={'runKey':run['manifestSha256'],'window':{'start':window['start'],'end':window['end']},'sourceSha256':s['sourceSha256'],'privateEvidenceDigest':sha(run['evidenceFiles']),'localRevision':s['revision'],'progress':{k:count(k) for k in ['observedRecords','qualifiers','candidates']},'coverage':{'listing':summary.get('listingCoverageComplete') is True,'resweep':summary.get('passes',{}).get('resweep') is True,'nativeComments':summary.get('nativeCommentCoverageComplete') is True,'complete':summary.get('complete') is True},'checkpointAt':s['updatedAt']}
 return result

def journal(path,event):
 r=Runtime(path)
 with r.locked():
  value=r.read() if r.path.exists() else {'schemaVersion':1,'events':[]}
  value['events'].append({'recordedAt':timestamp(),'event':event});r.write(value)
 return {'journaled':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['inspect','journal']);p.add_argument('path');p.add_argument('--event');a=p.parse_args()
 try:result=inspect(a.path) if a.command=='inspect' else journal(a.path,json.loads(a.event))
 except FileNotFoundError:result={'available':False,'reasonCode':'private_state_missing'}
 print(json.dumps(result,ensure_ascii=False,allow_nan=False))
