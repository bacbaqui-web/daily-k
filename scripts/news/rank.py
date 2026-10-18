#!/usr/bin/env python3
"""Score a private candidate ledger before editorial selection."""
import argparse
import json
from pathlib import Path
from publish import WEIGHTS, recency_score, timestamp, require, editorial_priority

p=argparse.ArgumentParser();p.add_argument('ledger',type=Path);a=p.parse_args()
v=json.loads(a.ledger.read_text());cutoff=timestamp(v['cutoffAt'])
for c in v['candidates']:
    require(c.get('publishedAt') or (c.get('publishedDate') and c.get('publishedTimezone')=='Asia/Seoul'),'Candidate needs a timestamp or confirmed Korean date')
    published=timestamp(c['publishedAt']) if c.get('publishedAt') else timestamp(c['publishedDate']+'T00:00:00+09:00')
    scores=c['scoreComponents'];scores['recency']=recency_score(published,cutoff,v['edition'])
    require(all(isinstance(scores.get(k),(int,float)) and 0<=scores[k]<=100 for k in WEIGHTS),'Invalid candidate score')
    c['score']=round(sum(scores[k]*w for k,w in WEIGHTS.items()),2)
v['candidates'].sort(key=editorial_priority,reverse=True)
a.ledger.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{'id':c['id'],'score':c['score'],'decision':c['decision']} for c in v['candidates']],ensure_ascii=False))
