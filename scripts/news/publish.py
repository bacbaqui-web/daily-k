#!/usr/bin/env python3
"""Validate, rank and publish a researched briefing. No news is invented/fetched here."""
import argparse
import copy
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = {'recency': .40, 'importance': .25, 'interest': .15, 'domesticImpact': .10, 'reliability': .10}

def require(ok, message):
    if not ok: raise ValueError(message)

def timestamp(value):
    require(isinstance(value, str), 'Missing timestamp')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, 'Timestamps must include a timezone')
    return dt.astimezone(KST)

def normalized(value):
    return re.sub(r'[^0-9a-z가-힣]', '', value.lower())

def canonical_url(value):
    p = urlparse(value)
    require(p.scheme in ('http', 'https') and p.hostname and not p.username and not p.password, 'Invalid article URL')
    return urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.startswith('utm_') and k not in ('cooper','plink')]), ''))

def fingerprint(facts):
    return hashlib.sha256(json.dumps({normalized(k):normalized(v) for k,v in facts.items()}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def source_check(source, generated, cutoff):
    for field in ('name', 'title', 'url', 'language', 'kind'):
        require(isinstance(source.get(field),str) and source[field].strip(), f'Source missing {field}')
    canonical_url(source['url'])
    if source.get('imageUrl') is not None: canonical_url(source['imageUrl'])
    checked = timestamp(source['verifiedAt'])
    require(generated-timedelta(hours=6) <= checked <= generated, 'Source must be freshly verified for this run')
    if source.get('publishedAt'):
        require(timestamp(source['publishedAt']) <= cutoff, 'Source published after edition cutoff')

def recency_score(published, cutoff, edition):
    midnight = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    if edition == 'am':
        return 100 if published >= midnight else 82 if published >= midnight-timedelta(hours=6) else 50 if published >= midnight-timedelta(days=1) else 25
    return 100 if published >= midnight.replace(hour=12) else 85 if published >= midnight.replace(hour=9) else 50 if published >= midnight else 25

def duplicate(a,b):
    if a['topicKey']==b['topicKey']: return True
    if {canonical_url(s['url']) for s in a['sources']} & {canonical_url(s['url']) for s in b['sources']}: return True
    if fingerprint(a['keyFacts'])==fingerprint(b['keyFacts']): return True
    return SequenceMatcher(None,normalized(a['title']),normalized(b['title'])).ratio() >= .82

def validate(draft, history, now=None):
    b=copy.deepcopy(draft)
    require(b.get('schemaVersion')==1 and b.get('timezone')=='Asia/Seoul','Invalid version/timezone')
    require(b.get('edition') in ('am','pm'),'Invalid edition')
    day=datetime.strptime(b['date'],'%Y-%m-%d').replace(tzinfo=KST)
    cutoff=timestamp(b['cutoffAt']); generated=timestamp(b['generatedAt'])
    require(cutoff == day.replace(hour=9 if b['edition']=='am' else 21),'Cutoff must be 09:00 or 21:00 KST')
    require(cutoff <= generated <= (now or datetime.now(KST))+timedelta(minutes=5),'Invalid generation time')
    require(b.get('id')==f"{b['date']}-{b['edition']}",'Invalid edition ID')
    require(isinstance(b.get('intro'),str) and b['intro'].strip(),'Missing intro')
    require(isinstance(b.get('overview'),list) and 2<=len(b['overview'])<=4 and all(isinstance(p,str) and len(p.strip())>=15 for p in b['overview']),'Provide 2–4 overview paragraphs covering the full edition')
    updated=timestamp(b.get('updatedAt',b['generatedAt']))
    require(generated<=updated<=(now or datetime.now(KST))+timedelta(minutes=5),'Invalid presentation update time')
    stories=b['stories']; require(5<=len(stories)<=10,'Must contain 5–10 stories')
    require(any(s.get('category')=='웹툰 산업' for s in stories),'A domestic webtoon story is required')
    require(len({s['id'] for s in stories})==len(stories),'Duplicate story ID')
    prior=[(old,s) for old in history if old['id']!=b['id'] and timestamp(old['cutoffAt'])<cutoff for s in old['stories']]
    for i,s in enumerate(stories):
        require(re.fullmatch(r'[a-z0-9][a-z0-9-]*',s['id']) is not None,'Unsafe story ID')
        for field in ('topicKey','category','title','status','eventTimeNote','whatChanged','whyItMatters','uncertainty'):
            require(isinstance(s.get(field),str) and s[field].strip(),f'{s["id"]}: missing {field}')
        require(s['status'] in ('확정','예정','검토','보도','주장','분석'),'Invalid fact status')
        require(isinstance(s.get('summary'),list) and 2<=len(s['summary'])<=4 and all(isinstance(p,str) and len(p.strip())>=15 for p in s['summary']),'Use 2–4 short explanatory paragraphs')
        emphasis=s.get('emphasis',[])
        require(isinstance(emphasis,list) and 1<=len(emphasis)<=6 and all(isinstance(p,str) and p.strip() and any(p in paragraph for paragraph in s['summary']) for p in emphasis),'Emphasis must select 1–6 actual phrases from the summary')
        require(isinstance(s.get('keyFacts'),dict) and len(s['keyFacts'])>=2 and all(isinstance(v,str) and v for v in s['keyFacts'].values()),'Missing comparable factual data')
        require(isinstance(s.get('sources'),list) and s['sources'],'Missing sources')
        for source in s['sources']: source_check(source,generated,cutoff)
        related=s.get('relatedArticles',[])
        require(isinstance(related,list) and 1<=len(related)<=3,'Provide up to three verified related articles')
        for article in related: source_check(article,updated,cutoff)
        require(len({canonical_url(article['url']) for article in related})==len(related),'Duplicate related articles')
        require(any(source['language']=='ko' for source in s['sources']),'A Korean source is mandatory')
        published=timestamp(s['publishedAt'])
        require(any(source.get('publishedAt') and timestamp(source['publishedAt'])==published for source in s['sources']),'Story time must be backed by a source')
        age=(cutoff-published).total_seconds()/3600
        require(age>=0,'Future story')
        if s['category']=='웹툰 산업':
            require(age<=72,'Webtoon fallback must be within 3 days')
            if published.date()<day.date(): require(bool(s.get('fallbackNote')),'Label older webtoon updates explicitly')
        else:
            require(published >= (day-timedelta(days=1) if b['edition']=='am' else day),'Story outside time window')
            if b['edition']=='am' and published<day-timedelta(hours=6):
                require(bool(s.get('fallbackNote')),'Label previous-day daytime fallback')
        if s.get('eventAt'): timestamp(s['eventAt'])
        # Same-edition duplicates are never allowed.
        require(not any(duplicate(s,p) for p in stories[:i]),'Duplicate topics inside this edition')
        matches=[(old,p) for old,p in prior if duplicate(s,p)]
        follow=s.get('followUp')
        if matches or follow:
            require(isinstance(follow,dict) and len(follow.get('delta','').strip())>=15,'Repeated topic needs a substantive follow-up delta')
            candidates=[(old,p) for old,p in matches if old['id']==follow.get('editionId') and p['id']==follow.get('storyId')]
            require(bool(candidates),'Follow-up must reference the matching previous story')
            old,p=max(matches,key=lambda item:item[0]['cutoffAt'])
            require(old['id']==follow['editionId'] and p['id']==follow['storyId'],'Reference the most recent coverage')
            require(normalized(' '.join(s['summary']))!=normalized(' '.join(p['summary'])),'Repeated wording')
            require(fingerprint(s['keyFacts'])!=fingerprint(p['keyFacts']),'No new numbers, result or position')
            require(any(source.get('publishedAt') and timestamp(source['publishedAt'])>timestamp(old['cutoffAt']) for source in s['sources']),'Follow-up needs new evidence after prior cutoff')
        c=s.get('scoreComponents',{})
        c['recency']=recency_score(published,cutoff,b['edition'])
        require(all(isinstance(c.get(k),(int,float)) and 0<=c[k]<=100 for k in WEIGHTS),'Scores must be 0–100')
        require(bool(s.get('scoreReason')),'Explain candidate weighting')
        s['scoreComponents']=c;s['score']=round(sum(c[k]*w for k,w in WEIGHTS.items()),2);s['factsHash']=fingerprint(s['keyFacts'])
    b['stories']=sorted(stories,key=lambda s:(s['score'],s['publishedAt']),reverse=True)
    events=b.get('events',[]);require(3<=len(events)<=6,'Provide 3–6 upcoming events')
    target=day if b['edition']=='am' else day+timedelta(days=1)
    for e in events:
        require(e['date']==target.date().isoformat(),'Event must occur on target date')
        require(e.get('title') and e.get('detail'),'Missing event explanation')
        if e.get('at'):
            at=timestamp(e['at']);require(at>cutoff and at.date()==target.date(),'Event already ended or wrong date')
        else: require(bool(e.get('timeNote')),'Disclose unknown event time')
        source_check(e['source'],generated,cutoff)
    keywords=b.get('keywords',[])
    require(isinstance(keywords,list) and all(isinstance(k,str) and k for k in keywords),'Invalid keywords')
    require((b['edition']=='am' and not keywords) or (b['edition']=='pm' and 8<=len(set(keywords))<=12),'Evening requires 8–12 keywords; morning none')
    return b

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(path)

def publish(draft, root=ROOT, check=False):
    base=root/'public/data/news';base.mkdir(parents=True,exist_ok=True)
    history=[json.loads(p.read_text()) for p in sorted(base.glob('????-??-??/*.json'))]
    require(not any(h['id']==draft['id'] for h in history),'Edition already published; never overwrite an archive silently')
    b=validate(draft,history)
    if check:return b,[]
    rel=f"{b['date']}/{b['edition']}.json"
    def entry(v):return {'id':v['id'],'date':v['date'],'edition':v['edition'],'generatedAt':v['generatedAt'],'cutoffAt':v['cutoffAt'],'count':len(v['stories']),'path':f"{v['date']}/{v['edition']}.json",'headline':v['stories'][0]['title']}
    index={'schemaVersion':1,'timezone':'Asia/Seoul','updatedAt':b['generatedAt'],'editions':sorted([entry(v) for v in history]+[entry(b)],key=lambda e:e['cutoffAt'],reverse=True)}
    paths=[]
    # Write edition before its manifest, so readers never see a dangling entry.
    for folder in ('public/data/news','docs/data/news'):
        for relative,data in ((rel,b),('index.json',index)):
            path=root/folder/relative;write_json(path,data);paths.append(str(path.relative_to(root)))
    return b,paths

def main():
    parser=argparse.ArgumentParser();parser.add_argument('draft',type=Path);parser.add_argument('--check',action='store_true');parser.add_argument('--push',action='store_true');args=parser.parse_args()
    require(not(args.check and args.push),'Choose check or push')
    lock=Path.home()/'Library/Application Support/DailyK/news-publish.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('w') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.push:
            require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'Checkout has other work; inspect before publishing')
            subprocess.run(['git','pull','--ff-only'],cwd=ROOT,check=True)
        b,paths=publish(json.loads(args.draft.read_text()),check=args.check)
        if args.push:
            subprocess.run(['git','add','--',*paths],cwd=ROOT,check=True)
            subprocess.run(['git','commit','-m',f"Publish {b['id']} Korean news briefing"],cwd=ROOT,check=True)
            subprocess.run(['git','push','origin','main'],cwd=ROOT,check=True)
        print(json.dumps({'id':b['id'],'stories':len(b['stories']),'checkedOnly':args.check,'paths':paths},ensure_ascii=False))

if __name__=='__main__':main()
