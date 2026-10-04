"""Validate and publish source-linked community briefings without rebuilding."""
import argparse,datetime as dt,fcntl,json,re,subprocess
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[2]
def url(v):
 p=urlsplit(v);assert p.scheme in ('http','https') and p.netloc and not p.username and not p.password,'invalid URL'
def stamp(v):return dt.datetime.fromisoformat(v.replace('Z','+00:00'))
def validate(v):
 assert v['schemaVersion'] in (1,2) and v['timezone']=='Asia/Seoul'
 assert re.fullmatch(r'\d{4}-\d{2}-\d{2}',v['date']) and v['edition'] in ('am','pm')
 assert v['id']==v['date']+'-'+v['edition']
 cutoff=stamp(v['cutoffAt'])
 assert cutoff.date().isoformat()==v['date'] and cutoff.utcoffset()==dt.timedelta(hours=9)
 if not v.get('test',False):assert cutoff.isoformat()==v['date']+('T09:00:00+09:00' if v['edition']=='am' else 'T21:00:00+09:00')
 assert stamp(v['generatedAt'])>=cutoff
 assert isinstance(v['overview'],list) and (0 if v['schemaVersion']==2 else 1)<=len(v['overview'])<=4 and all(isinstance(p,str) and p.strip() for p in v['overview'])
 assert 3<=len(v['stories'])<=20,'3..20 verified stories required'
 seen=set()
 for s in v['stories']:
  assert s['id'] not in seen;seen.add(s['id'])
  assert s['category'] in ('화제','유머','정보','생활','문화','스포츠','ㅇㅎㅂ') and s['topicKey'].strip()
  for k in ('title','selectionReason','popularityEvidence','verificationNote'):assert isinstance(s[k],str) and s[k].strip(),k
  assert (0 if v['schemaVersion']==2 else 1)<=len(s['summary'])<=5 and all(isinstance(p,str) and p.strip() for p in s['summary'])
  if v['schemaVersion']==2:
   assert not s['summary'] and not v['overview'],'do not write community summaries'
   assert type(s['kCount']) is int and s['kCount']>=0
   assert type(s['commentCount']) is int and s['commentCount']>=0
   assert stamp(s['commentsVerifiedAt']).tzinfo is not None
   assert stamp(s['commentsVerifiedAt'])<=stamp(v['generatedAt'])
   if s['category']=='유머':assert s['kCount']>=10,'humor requires 10 verified k characters'
   quotes=s.get('comments',[]);assert isinstance(quotes,list)
   assert len({c['id'] for c in quotes})==len(quotes),'duplicate comment quote'
   assert all(isinstance(c['text'],str) and c['text'].strip() for c in quotes)
   assert sum(len(text.split()) for text in [s['title'],s.get('originalText',''),*[c['text'] for c in quotes]])<=25,'short quotations only'
   if s['category']=='ㅇㅎㅂ':
    assert s.get('contentReview')=='public-non-explicit','public, non-explicit content review required'
    assert s.get('contentSignals'),'verified comment signal required'
    for signal in s['contentSignals']:
     assert signal['kind'] in ('instagram','x','leaked') and str(signal['commentId']).strip()
     if signal['kind']!='leaked':
      url(signal['url']);host=urlsplit(signal['url']).hostname
      assert host in ('instagram.com','www.instagram.com','x.com','www.x.com','twitter.com','www.twitter.com')
  assert s['sources']
  for field in ('imageUrl','videoUrl','videoPosterUrl'):
   if s.get(field):url(s[field])
  if 'sourceBreakdown' in s:
   assert isinstance(s['sourceBreakdown'],list) and s['sourceBreakdown']
   names=set()
   for item in s['sourceBreakdown']:
    assert isinstance(item['name'],str) and item['name'].strip() and item['name'] not in names
    names.add(item['name'])
    assert type(item['count']) is int and item['count']>0
   assert stamp(s['sourceStatsVerifiedAt']).tzinfo is not None
  for l in s['sources']:
   url(l['url']);assert l['name'].strip() and l['title'].strip()
   assert stamp(l['verifiedAt'])<=stamp(v['generatedAt'])
   assert l['publishedAt'] is None or cutoff-dt.timedelta(hours=24)<=stamp(l['publishedAt'])<=cutoff
   if l.get('imageUrl'):url(l['imageUrl'])
 return v

def git(*args):
 r=subprocess.run(['git','-C',str(ROOT),*args],capture_output=True,text=True,check=True);return r.stdout.strip()
def publish(v,push=False):
 lock=Path.home()/'Library/Application Support/DailyK/news-publish.lock'
 with lock.open('a') as h:
  fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB)
  assert not git('status','--porcelain','--untracked-files=no'),'uncommitted changes: preserve and stop'
  git('pull','--ff-only')
  indexpath=ROOT/'public/data/community/index.json';index=json.loads(indexpath.read_text())
  assert not any(e['id']==v['id'] for e in index['editions']),'edition already published'
  for entry in index['editions'][:14]:
   prior=json.loads((indexpath.parent/entry['path']).read_text())
   prior_keys={s['topicKey'] for s in prior['stories']}
   prior_urls={l['url'] for s in prior['stories'] for l in s['sources']}
   assert not any(l['url'] in prior_urls for s in v['stories'] for l in s['sources']),'recent original URL repeated'
   assert not any(s['topicKey'] in prior_keys for s in v['stories']),'recent topic repeated'
  path=f"{v['date']}/{v['edition']}.json"
  index['editions'].append({k:v[k] for k in ('id','date','edition')});index['editions'][-1]['path']=path
  index['editions'].sort(key=lambda e:(e['date'],e['edition']=='pm'),reverse=True);index['updatedAt']=v['generatedAt']
  paths=[]
  for folder in ('public','docs'):
   for name,value in ((path,v),('index.json',index)):
    p=ROOT/folder/'data/community'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');paths.append(str(p.relative_to(ROOT)))
  git('add','--',*paths);git('commit','-m',f"Publish community briefing {v['id']}",'--',*paths)
  if push:git('push','origin','main')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('draft',type=Path);p.add_argument('--check',action='store_true');p.add_argument('--push',action='store_true');a=p.parse_args();v=validate(json.loads(a.draft.read_text()))
 if not a.check:publish(v,a.push)
 print('Community briefing validated'+(' and published' if not a.check else ''))
