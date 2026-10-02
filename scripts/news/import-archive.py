#!/usr/bin/env python3
"""Import the reviewed archive once. Repeated imports are idempotent, never overwrites."""
import argparse
from collections import Counter
from datetime import datetime
import fcntl
import json
from pathlib import Path
from archive import make_editions, load_editions, build_index, edition_path
from publish import ROOT, KST, write_json
from timeline import build_timelines


def import_archive(root=ROOT, check=False):
    source=root/'ops/imports/news-briefing-archive.md'
    mapping=json.loads((root/'ops/news-archive-map.json').read_text())
    previous_report=root/'public/data/news/archive/import-report.json'
    imported_at=json.loads(previous_report.read_text())['importedAt'] if previous_report.exists() else datetime.now(KST).isoformat(timespec='seconds')
    incoming=make_editions(source.read_text(),mapping,imported_at)
    history=load_editions(root/'public/data/news')
    known={b['id']:b for b in history}
    for b in incoming:
        if b['id'] in known and known[b['id']]!=b: raise ValueError(f'Existing archive differs: {b["id"]}')
    combined=history+[b for b in incoming if b['id'] not in known]
    timelines=build_timelines(combined)
    counts=Counter(s['timeline']['issueId'] for b in incoming for s in b['stories'])
    textcounts=Counter(s['summary'][0] for b in incoming for s in b['stories'])
    report=dict(importedAt=imported_at,sourceDocument=source.name,sourceSha256=mapping['sourceSha256'],
                firstDate=incoming[0]['date'],lastDate=incoming[-1]['date'],editionCount=len(incoming),
                storyCount=sum(len(b['stories']) for b in incoming),issueCount=len(counts),
                sourceNamedCount=sum(bool(s['archive']['sourceNames']) for b in incoming for s in b['stories']),
                relatedArticleRecordCount=sum(bool(s.get('relatedArticles')) for b in incoming for s in b['stories']),
                verification='Original records preserved; not all historical claims have been independently reverified.',
                repeatedIssueCount=sum(n>1 for n in counts.values()),repeatedTextRecordCount=sum(n-1 for n in textcounts.values() if n>1),
                sameSlotAsPublished=[b['id'] for b in incoming if any(not h.get('archive') and h['date']==b['date'] and h['edition']==b['edition'] for h in history)],
                issues=[dict(id=i,count=n) for i,n in counts.most_common()],
                editions=[dict(id=b['id'],count=len(b['stories']),path=edition_path(b)) for b in incoming])
    index=build_index(combined,max(b.get('updatedAt',b['generatedAt']) for b in combined))
    if not check:
        for folder in ('public/data/news','docs/data/news'):
            for b in incoming:write_json(root/folder/edition_path(b),b)
            for relative,value in timelines.items():write_json(root/folder/relative,value)
            write_json(root/folder/'archive/import-report.json',report)
            write_json(root/folder/'index.json',index)
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    lock=Path.home()/'Library/Application Support/DailyK/news-publish.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('w') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        report=import_archive(check=args.check)
    print(json.dumps({k:v for k,v in report.items() if k not in ('issues','editions')},ensure_ascii=False))

if __name__=='__main__':main()
