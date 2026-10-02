#!/usr/bin/env python3
"""Rebuild derived issue histories without changing the original editions."""
import argparse
import json
from pathlib import Path

from publish import ROOT, write_json
from timeline import build_timelines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Verify the index and histories without writing')
    args = parser.parse_args()
    editions = [json.loads(p.read_text()) for p in sorted((ROOT/'public/data/news').glob('????-??-??/*.json'))]
    files = build_timelines(editions)
    for folder in ('public/data/news', 'docs/data/news'):
        for relative, data in files.items():
            path = ROOT/folder/relative
            if args.check:
                if not path.exists() or json.loads(path.read_text()) != data:
                    raise ValueError(f'Issue archive out of date: {path}')
            else:
                write_json(path, data)
    index = files['issues/index.json']
    print(json.dumps({'issues': len(index['issues']), 'stories': index['storyCount'], 'unlinked': index['unlinkedStoryCount'], 'checkedOnly': args.check}))


if __name__ == '__main__': main()
