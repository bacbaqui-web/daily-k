#!/usr/bin/env python3
"""Bounded standard-library HTTP collector. No AI, browser, daemon or publishing.

Ported from the existing local Aagag HTTP adapter's public markup contract.
Live compatibility/publication-time semantics must be verified before deployment.
Every candidate stays private until the publication contract is satisfied.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urljoin, urlsplit
import manage as m

BASE = 'https://aagag.com'
USER_AGENT = 'DailyK/0.2 (personal source-linked humor reader)'


class Node:
    def __init__(self, tag='', attrs=()): self.tag, self.attrs, self.children = tag, dict(attrs), []
    def nodes(self, tag=None):
        for child in self.children:
            if isinstance(child, Node):
                if tag is None or child.tag == tag: yield child
                yield from child.nodes(tag)
    def text(self):
        if self.tag in ('script','style') or 'hidden' in self.attrs: return ''
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)
    def find_id(self, value): return next((n for n in self.nodes() if n.attrs.get('id') == value), None)


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True); self.root = Node(); self.stack = [self.root]; self.feed(source)
    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs); self.stack[-1].children.append(node)
        if tag not in ('meta','link','br','img','input','hr','source','area','wbr'): self.stack.append(node)
    def handle_startendtag(self, tag, attrs): self.stack[-1].children.append(Node(tag, attrs))
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag: del self.stack[i:]; break
    def handle_data(self, data): self.stack[-1].children.append(data)


def challenge(headers, body):
    if headers.get('cf-mitigated','').lower() == 'challenge': return True
    title = re.search(r'<title[^>]*>(.*?)</title>', body, re.I | re.S)
    return bool(title and re.search(r'just a moment|attention required|access denied|captcha|verify.*human|403 forbidden', title[1], re.I))


def robots_allowed(source,url):
    # Longest rule wins; Allow wins ties. Support wildcard and end anchors.
    groups=[];agents=[];rules=[]
    for line in source.splitlines()+['User-agent: __end__']:
        line=line.split('#',1)[0].strip()
        if ':' not in line:continue
        key,value=[v.strip() for v in line.split(':',1)];key=key.lower()
        if key=='user-agent':
            if rules:groups.append((agents,rules));agents=[];rules=[]
            agents.append(value.lower())
        elif key in ('allow','disallow') and value:rules.append((key,value))
    selected=[r for a,r in groups if any(v!='*' and v in USER_AGENT.lower() for v in a)]
    if not selected:selected=[r for a,r in groups if '*' in a]
    parsed=urlsplit(url);target=parsed.path+('?' + parsed.query if parsed.query else '');matches=[]
    for rules in selected:
        for key,pattern in rules:
            end=pattern.endswith('$');pattern=pattern[:-1] if end else pattern
            regex='^'+'.*'.join(re.escape(v) for v in pattern.split('*'))+('$' if end else '')
            if re.search(regex,target):matches.append((len(pattern.replace('*','')),key=='allow'))
    return max(matches)[1] if matches else True


class Blocked(Exception):
    def __init__(self, url, reason, status='blocked', code=None):
        super().__init__(reason); self.url, self.status, self.code = url, status, code


class SameOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https' or urlsplit(newurl).netloc != 'aagag.com':
            raise Blocked(req.full_url, 'off-origin redirect refused')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, delay=5):
        if not 5 <= delay <= 60: raise ValueError('delay must be 5..60 seconds')
        self.delay, self.last, self.robots, self.blocked = delay, 0, None, False
        self.opener = urllib.request.build_opener(SameOrigin())
    def raw(self, url, data=None):
        if self.blocked: raise Blocked(url, 'stopped after access refusal')
        p = urlsplit(url)
        if p.scheme != 'https' or p.netloc != 'aagag.com': raise ValueError('only the actual Aagag origin is allowed')
        time.sleep(max(0, self.delay - (time.monotonic()-self.last)))
        self.last = time.monotonic()
        request = urllib.request.Request(url, data=urlencode(data).encode() if data is not None else None,
            headers={'User-Agent':USER_AGENT,'Accept':'text/html,application/json,text/plain',
                     **({'Referer':BASE+'/issue/','X-Requested-With':'XMLHttpRequest'} if data is not None else {})})
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000: raise ValueError('response limit exceeded')
                body = raw.decode(response.headers.get_content_charset() or 'utf-8', errors='strict')
                if challenge(response.headers, body):
                    self.blocked = True; raise Blocked(url, 'explicit challenge; operator action required', 'challenge', response.status)
                return body
        except urllib.error.HTTPError as error:
            body = error.read(8192).decode('utf-8', errors='replace'); headers = error.headers or {}; error.close()
            if error.code in (401,403,429) or challenge(headers, body):
                self.blocked = True
                raise Blocked(url, 'access refusal/rate limit; no automatic retry', 'challenge' if challenge(headers,body) else 'blocked', error.code) from error
            raise
    def request(self, url, data=None):
        if self.robots is None:
            try: raw = self.raw(BASE+'/robots.txt')
            except urllib.error.HTTPError as error:
                if error.code != 404: raise
                raw = ''
            self.robots = raw
        if not robots_allowed(self.robots, url):
            self.blocked = True; raise Blocked(url, 'robots.txt disallows this path')
        return self.raw(url, data)
    def get(self, url): return self.request(url)
    def form(self, path, data): return json.loads(self.request(BASE+path, data))


def field(source, name):
    match = re.search(r'^\s*AAGAG_AA\.' + re.escape(name) + r'\s*=\s*', source, re.M)
    if not match: raise ValueError('article field missing: '+name)
    return json.JSONDecoder().raw_decode(source[match.end():])[0]


def parse_list(source, url):
    tree = Document(source).root; root = tree.find_id('listIssue')
    if root is None: raise ValueError('latest list markup changed')
    items = {}; next_links = []
    for node in root.nodes('a'):
        if 'article' not in node.attrs.get('class','').split(): continue
        link = urljoin(url,node.attrs.get('href',''))
        identity = m.identity(link)
        title = next((n.text().strip() for n in node.nodes() if 'title' in n.attrs.get('class','').split()), '')
        items.setdefault(identity, dict(id=identity,url=link,title=title[:300]))
    for node in tree.nodes('a'):
        link = urljoin(url,node.attrs.get('href',''))
        if re.fullmatch(r'https://aagag\.com/issue/\?page=\d+',link): next_links.append(link)
    if not items: raise ValueError('list empty or unrecognized; not an observed zero')
    page = int(re.search(r'page=(\d+)',url)[1]) if 'page=' in url else 1
    next_page = next((link for link in next_links if int(link.rsplit('=',1)[1]) == page+1), None)
    return list(items.values()), next_page


def parse_comments(data):
    if not isinstance(data,dict) or data.get('mode') != 'success': raise ValueError('native comment API did not succeed')
    total = data.get('total')
    if isinstance(total,str) and total.isdigit(): total = int(total)
    if type(total) is not int or total < 0: raise ValueError('native total missing')
    rows = data.get('comment') or []
    if not isinstance(rows,list): raise ValueError('native rows missing')
    counts = {}
    for row in rows:
        if not isinstance(row,dict) or not str(row.get('w_idx','')).isdigit() or not isinstance(row.get('w_content'),str):
            raise ValueError('native row schema changed')
        # System/deleted rows cannot be silently subtracted from the reported total.
        if row.get('w_mb_id') in ('delete','■system■'): raise ValueError('native deleted/system count needs verification')
        cid = str(row['w_idx']); value = Document(row['w_content']).root.text().count('ㅋ')
        if cid in counts and counts[cid] != value: raise ValueError('conflicting native duplicate')
        counts[cid] = value
    if len(counts) != total: raise ValueError('native comments incomplete; total does not reconcile')
    return dict(scope='native-aagag-all',complete=True,reportedCount=total,
                rows=[dict(id=cid,literalKCount=count) for cid,count in counts.items()])


def parse_article(source, url, now):
    identity = m.identity(url)
    if identity != 'aagag-'+str(field(source,'idx')): raise ValueError('article identity mismatch')
    tree = Document(source).root
    title = next((n.attrs.get('content','') for n in tree.nodes('meta') if n.attrs.get('property') == 'og:title'), '') or field(source,'title')
    if not isinstance(title,str) or not title.strip(): raise ValueError('title missing')
    raw = field(source,'otime')
    if type(raw) not in (int,float): raise ValueError('exact timestamp unavailable; relative age is not publication time')
    published = datetime.fromtimestamp(raw, timezone.utc)
    if published > now: raise ValueError('future source timestamp')
    content = field(source,'content')
    if not isinstance(content,str): raise ValueError('body contract changed')
    # Capture URLs only. Unknown dimensions, embeds and script-generated media
    # remain explicit holds; no image/video download and no executable source HTML.
    media = []
    for node in Document(content).root.nodes():
        if node.tag in ('img','video','iframe'):
            src = node.attrs.get('src')
            if src:
                media.append(dict(type={'img':'image','video':'video','iframe':'embed'}[node.tag],url=urljoin(url,src)))
    for match in re.finditer(r'\[sTag\](.*?)\[/sTag\]',content,re.S):
        meta = json.loads(match[1]); q = meta.get('q')
        # Only explicit URLs exposed in the payload, never synthesize a media URL.
        explicit = meta.get('mp4m_url') or meta.get('mp4_url') or meta.get('url')
        media.append(dict(type='video' if meta.get('mp4_seq') else 'image',url=explicit,sourceKey=q))
    return dict(id=identity,canonicalUrl=url,title=' '.join(title.split()[:25]),sourceTitleSha256=hashlib.sha256(title.encode()).hexdigest(),
                publishedAt=m.iso(published),firstObservedAt=m.iso(now),lastVerifiedAt=m.iso(now),media=media,
                publicationEvidence=dict(method='aagag-otime',value=m.iso(published),raw=str(raw),sourceUrl=url,
                    observedAt=m.iso(now),semanticsVerified=False),
                holds=['publication_field_semantics_unverified','context_media_rights_review_required'],
                excluded=bool(m.SAFETY.search(title.replace('\u200b',''))))


def run_once(state_path, client, max_pages=20, max_posts=100, resume_after_review=False, clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    if not 1 <= max_pages <= 100 or not 1 <= max_posts <= 1000: raise ValueError('bounded limits required')
    state_path = Path(state_path); state_path.parent.mkdir(parents=True,exist_ok=True)
    with state_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state = json.loads(state_path.read_text()) if state_path.exists() else dict(schemaVersion=1,records={},pending=[],nextList=BASE+'/issue/',seenLists=[],processed=[],status='new')
        def save(): m.live.atomic_write(state_path,m.encoded(state))
        if state['status'] in ('blocked','challenge') and not resume_after_review:
            state['activeCandidateIds'] = [i for i,r in state['records'].items() if r.get('publishedAt') and m.fresh(m.stamp(r['publishedAt']),clock()) and r.get('thresholdQualified')]
            state['prunedAt'] = m.iso(clock()); save(); return state
        if state['status'] == 'complete':
            state.update(pending=[],nextList=BASE+'/issue/',seenLists=[],processed=[])
        state.update(status='running',startedAt=m.iso(clock()),lastError=None)
        # Expire private candidates on every run, even if the network later fails.
        state['activeCandidateIds'] = [i for i,r in state['records'].items() if r.get('publishedAt') and m.fresh(m.stamp(r['publishedAt']),clock()) and r.get('thresholdQualified')]
        save(); pages = posts = 0; current_url = state.get('nextList') or BASE+'/issue/'
        try:
            while True:
                if state['pending']:
                    if posts >= max_posts: state['status']='partial'; break
                    item = state['pending'][0]; current_url = item['url']; posts += 1
                    if item['id'] in state['processed']:
                        state['pending'].pop(0); save(); continue
                    now = clock(); previous = state['records'].get(item['id'])
                    if m.SAFETY.search(item['title'].replace('\u200b','')):
                        record = dict(item,status='excluded',reason='title_safety',observedAt=m.iso(now))
                    else:
                        try:
                            record = parse_article(client.get(current_url),current_url,clock())
                            if previous and previous.get('publishedAt') and previous['publishedAt'] != record['publishedAt']:
                                record['holds'].append('publication_time_changed_relisting'); record['previousPublishedAt']=previous.get('publishedAt')
                            if previous:
                                record['firstObservedAt']=previous.get('firstObservedAt',previous.get('observedAt',record['firstObservedAt']))
                                if 'publication_time_changed_relisting' in previous.get('holds',[]) and 'publication_time_changed_relisting' not in record['holds']:
                                    record['holds'].append('publication_time_changed_relisting')
                                    record['previousPublishedAt']=previous.get('previousPublishedAt')
                            if record['excluded']: record['status']='excluded'
                            elif not m.fresh(m.stamp(record['publishedAt']),clock()): record['status']='expired'
                            else:
                                evidence = parse_comments(client.form('/api/cmt',{'idx':item['id'].split('-')[1]}))
                                evidence.update(sourceUrl=current_url,observedAt=m.iso(clock()))
                                record.update(nativeComments=evidence,lastVerifiedAt=evidence['observedAt'])
                                total, count = m.counts(evidence)
                                record.update(kCount=total,commentCount=count,thresholdQualified=total>=10,status='held' if total>=10 else 'below_threshold')
                        except (ValueError,KeyError,TypeError) as error:
                            record = dict(item,status='held',reason=str(error),observedAt=m.iso(clock()))
                    # A transient parse failure must not erase the original discovery
                    # or known publication anchor before a later successful retry.
                    record['firstObservedAt'] = (previous or {}).get('firstObservedAt', (previous or {}).get('observedAt', m.iso(now)))
                    if previous and not record.get('publishedAt'):
                        for key in ('publishedAt','holds','previousPublishedAt'):
                            if key in previous: record[key] = previous[key]
                    state['records'][item['id']] = record
                    state['processed'].append(item['id']); state['pending'].pop(0); save()
                elif state['nextList']:
                    if pages >= max_pages: state['status']='partial'; break
                    current_url = state['nextList']
                    if current_url in state['seenLists']: raise ValueError('pagination loop')
                    items,next_link = parse_list(client.get(current_url),current_url); pages += 1
                    state['pending']=items; state['seenLists'].append(current_url); state['nextList']=next_link; save()
                else:
                    state['status']='complete'; break
        except Blocked as error:
            state.update(status=error.status,lastError=dict(url=error.url,reason=str(error),httpStatus=error.code,checkedAt=m.iso(clock()),requiresOperator=True))
        except KeyboardInterrupt:
            state.update(status='stopped',lastError=dict(url=current_url,reason='interrupted; pending work retained',checkedAt=m.iso(clock())))
        except Exception as error:
            state.update(status='failed',lastError=dict(url=current_url,reason=str(error),checkedAt=m.iso(clock())))
        state['checkedAt']=m.iso(clock())
        state['activeCandidateIds']=[i for i,r in state['records'].items() if r.get('publishedAt') and m.fresh(m.stamp(r['publishedAt']),clock()) and r.get('thresholdQualified')]
        state['coverage']='bounded traversal only; no claim of full site coverage or verified publication semantics'
        save(); return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--max-pages',type=int,default=20); parser.add_argument('--max-posts',type=int,default=100)
    parser.add_argument('--delay',type=float,default=5); parser.add_argument('--resume-after-review',action='store_true')
    args=parser.parse_args()
    state=run_once(args.state,Client(args.delay),args.max_pages,args.max_posts,args.resume_after_review)
    print(m.encoded({k:state[k] for k in ('status','checkedAt','activeCandidateIds','coverage') if k in state}))
    raise SystemExit(0 if state['status']=='complete' else 2)


if __name__=='__main__': main()
