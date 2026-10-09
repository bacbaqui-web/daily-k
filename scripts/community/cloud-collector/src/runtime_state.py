"""Local fenced execution coordinator. No browser, network, publication or scheduler.
State must be preserved privately with run evidence. Missing state is not resume proof.
"""
import argparse, contextlib, datetime as dt, fcntl, hashlib, json, os, re, tempfile
from pathlib import Path

TERMINAL={'verified_complete','closed_with_gaps'}
def timestamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def parse(value):
    v=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if v.tzinfo is None: raise ValueError('Aware timestamp required')
    return v

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_digest():
    h=hashlib.sha256()
    for path in sorted(Path(__file__).resolve().parent.glob('*')):
        if path.suffix in {'.py','.js'}:
            data=path.read_bytes();h.update(path.name.encode()+b'\0'+str(len(data)).encode()+b'\0'+data)
    return h.hexdigest()

def evidence_files(root):
    return {str(p.relative_to(root)):digest(p) for folder in ('posts','listings') for p in sorted((root/folder).glob('*.json'))}

class Runtime:
    def __init__(self,path): self.path=Path(path)
    @contextlib.contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with open(str(self.path)+'.lock','a') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(f,fcntl.LOCK_UN)
    def read(self): return json.loads(self.path.read_text())
    def write(self,s):
        fd,p=tempfile.mkstemp(dir=self.path.parent,prefix='.runtime-')
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(s,f,ensure_ascii=False,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(p,self.path)
            fd=os.open(self.path.parent,os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        finally:
            if os.path.exists(p):os.unlink(p)
    def apply(self,command,args,now=None):
        now=now or timestamp();parse(now)
        with self.locked():
            if command=='init':
                if self.path.exists():raise ValueError('State already exists; inspect rather than reset')
                source=args['sourceSha256']
                if source!=source_digest():raise ValueError('Actual local source digest required')
                s={'schemaVersion':1,'revision':0,'sourceSha256':source,'status':'idle','run':None,'lease':None,'fence':0,'batches':{},'runDirectories':[],'updatedAt':now}
            else:
                s=self.read()
                if command=='status':return s
                if args.get('revision')!=s['revision']:raise ValueError('Stale revision')
                if args.get('sourceSha256')!=s['sourceSha256'] or source_digest()!=s['sourceSha256']:raise ValueError('Source version changed; explicit review required')
                if command=='start-run':
                    if s['status'] not in {'idle',*TERMINAL}:raise ValueError('Previous run not terminal')
                    run=Path(args['runDir']).resolve(); manifest=run/'run.json'
                    value=json.loads(manifest.read_text())
                    if str(run) in s['runDirectories']:raise ValueError('Fresh run directory required to refresh all counts')
                    s['runDirectories'].append(str(run))
                    s['run']={'directory':str(run),'manifestSha256':digest(manifest),'manifest':value,'evidenceFiles':evidence_files(run)};s['status']='ready';s['lease']=None
                elif command=='begin':
                    if s['status']!='ready':raise ValueError('Paused, active, or terminal; no automatic retry')
                    if str(Path(args['runDir']).resolve())!=s['run']['directory']:raise ValueError('Run directory differs from fenced run')
                    self.evidence(s,verify_files=True)
                    duration=args.get('leaseSeconds',600)
                    if type(duration)!=int or not 30<=duration<=900:raise ValueError('Lease must be 30..900 seconds')
                    owner=args.get('owner','')
                    if not re.fullmatch('[A-Za-z0-9_.-]{1,100}',owner):raise ValueError('Owner required')
                    s['fence']+=1;s['lease']={'owner':owner,'fence':s['fence'],'expiresAt':(parse(now)+dt.timedelta(seconds=duration)).isoformat()};s['status']='running'
                elif command in {'guard','finish'}:
                    lease=s['lease']
                    if s['status']!='running' or not lease or args.get('owner')!=lease['owner'] or args.get('fence')!=lease['fence']:raise ValueError('Invalid execution fence')
                    if parse(now)>=parse(lease['expiresAt']):raise ValueError('Expired lease; outcome review required, never automatic takeover')
                    self.evidence(s)
                    if command=='guard':return s
                    outcome=args['outcome']
                    allowed={'ready','paused_requires_user','paused_runtime','verified_complete','closed_with_gaps'}
                    if outcome not in allowed:raise ValueError('Unknown outcome')
                    if outcome in TERMINAL:
                        summary=json.loads((Path(s['run']['directory'])/'summary.json').read_text())
                        if outcome=='verified_complete' and summary.get('complete') is not True:raise ValueError('Full verification missing')
                        if outcome=='closed_with_gaps' and not(summary.get('listingCoverageComplete') is True and summary.get('passes',{}).get('resweep') is True):raise ValueError('Traversal/resweep incomplete')
                    s['run']['evidenceFiles']=evidence_files(Path(s['run']['directory']));s['status']=outcome;s['lease']=None
                elif command=='pause':
                    s['status']='paused_requires_user';s['fence']+=1
                elif command=='resume':
                    if s['lease'] and parse(now)<parse(s['lease']['expiresAt']):raise ValueError('In-flight lease not expired; wait for outcome, do not overlap')
                    if args.get('inFlightResolved') is not True:raise ValueError('Confirm prior tool operation has ended before resume')
                    if not args.get('reviewReference'):raise ValueError('Explicit outcome/permission review reference required')
                    if s['status'] not in {'paused_requires_user','paused_runtime','running'}:raise ValueError('Not paused or interrupted')
                    self.evidence(s,verify_files=True);s['status']='ready';s['lease']=None;s['fence']+=1;s['reviewReference']=args['reviewReference']
                elif command=='record-batch':
                    key=args['operationId'];sha=args['payloadSha256']
                    if not re.fullmatch('[A-Za-z0-9_.-]{1,150}',key) or not re.fullmatch('[a-f0-9]{64}',sha):raise ValueError('Invalid batch identity')
                    if key in s['batches'] and s['batches'][key]!=sha:raise ValueError('Operation payload changed')
                    s['batches'][key]=sha
                else:raise ValueError('Unknown command')
                s['revision']+=1;s['updatedAt']=now
            self.write(s);return s
    def evidence(self,s,verify_files=False):
        if not s['run']:raise ValueError('Run missing')
        root=Path(s['run']['directory']);manifest=root/'run.json'
        if not manifest.is_file() or digest(manifest)!=s['run']['manifestSha256']:raise ValueError('Evidence manifest missing/changed; cannot trust checkpoint')
        if verify_files and evidence_files(root)!=s['run'].get('evidenceFiles',{}):
            raise ValueError('Private evidence lost/changed/added; explicit reconciliation required')
        if not (root/'posts').is_dir() or not (root/'listings').is_dir():raise ValueError('Private evidence directory missing; restart reviewed fixed window from first page')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('state');p.add_argument('command');p.add_argument('--args',default='{}');a=p.parse_args()
    print(json.dumps(Runtime(a.state).apply(a.command,json.loads(a.args)),ensure_ascii=False))
