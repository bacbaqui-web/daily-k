"""Offline deterministic normalization, coverage, and atomic checkpoint model."""
from __future__ import annotations
import json,re,hashlib,datetime as dt,os
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
UTC=dt.timezone.utc
TITLE_SAFETY_RULES=[('source_title_nsfw_marker', '(?<![ㄱ-ㅎ])(?:ㅇㅎㅂ|ㅇㅎ|ㅎㅂ)(?![ㄱ-ㅎ])'), ('sexual_title', '비키니|ㅂㅋㄴ|섹스|성관계|야동|젖꼭지|알몸|성인물'), ('graphic_or_death_title', '총살|처형|참수|시신|시체|자살|고문|성폭행'), ('private_allegation_title', '불륜|성추행|몰카|강간')]
MARKER=re.compile(TITLE_SAFETY_RULES[0][1])

def classify_title(title):
    """Apply only the existing explicit title rules; return exact matched text."""
    matches=[]
    for code,pattern in TITLE_SAFETY_RULES:
        match=re.search(pattern,str(title or ''))
        if match:matches.append({'code':code,'matchedText':match[0]})
    return matches

def utc(value): return dt.datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(UTC)
def post_id(value): return re.sub(r'[_-]\d+$','',str(value))
def listed_time(raw):
    if not raw:return None
    m=re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',raw)
    return utc(m[0].replace(' ','T')+'+09:00') if m else None

def age_upper_timestamp(age,observed):
    """Latest possible timestamp from rounded-down age; never call it exact."""
    m=re.search(r'(\d+)\s*(초|분|시간|일|개월|년)\s*전',age or '')
    if not m:return None
    n=int(m[1]);unit={'초':1,'분':60,'시간':3600,'일':86400,'개월':28*86400,'년':365*86400}[m[2]]
    return utc(observed)-dt.timedelta(seconds=n*unit)

def valid_outside_header(record,start,end):
    """Only explicit, actual header evidence may resolve an out-of-window row."""
    if record.get('status')!='outside_window' or not record.get('id') or not str(record.get('title') or '').strip():return False
    try:
        observed=dt.datetime.fromisoformat(record.get('observedAt','').replace('Z','+00:00'))
        if observed.tzinfo is None:return False
        value=listed_time(record.get('listedAtRaw'))
        if value is None or start<=value<=end:return False
        url=urlsplit(record.get('url') or '')
        identity=parse_qs(url.query).get('idx',[None])[0]
        return url.scheme=='https' and url.hostname in ('aagag.com','www.aagag.com') and url.path.rstrip('/')=='/issue' and not url.username and not url.password and identity is not None and post_id(identity)==post_id(record['id'])
    except (AttributeError,TypeError,ValueError):return False

def normalize(record,start,end):
    r=dict(record);r['id']=r.get('id') or r.get('requestedId');r['canonicalId']=post_id(r['id'])
    comments={};conflicts=[]
    raw_comments=r.get('commentCounts')
    if not isinstance(raw_comments,list):
        raw_comments=[];conflicts.append('missing_native_comment_rows')
    for c in raw_comments:
        if not isinstance(c,dict) or type(c.get('id')) not in (str,int) or not str(c['id']).strip():
            conflicts.append('missing_comment_id');continue
        identity=str(c['id']);comment={**c,'id':identity}
        if identity in comments and comments[identity]!=comment:conflicts.append(identity)
        comments[identity]=comment
    invalid_count_ids=[identity for identity,c in comments.items() if type(c.get('kCount')) is not int or c['kCount']<0]
    counts_valid=not invalid_count_ids
    r['commentCount']=len(comments);r['duplicateCommentRows']=len(raw_comments)-len(comments)
    r['kCount']=sum(c['kCount'] for c in comments.values()) if counts_valid else None
    r['commentCounts']=list(comments.values());r['commentConflicts']=conflicts;r['invalidCommentCountIDs']=invalid_count_ids
    r['thresholdQualified']=r['kCount']>=11 if r['kCount'] is not None else None
    t=listed_time(r.get('listedAtRaw'));r['listedAt']=t.isoformat() if t else None
    r['inWindow']=start<=t<=end if t else None
    r['exclusions']=[];seen_safety=set()
    for source in [{'id':r.get('id'),'title':r.get('title','')}]+r.get('sources',[]):
        for match in classify_title(source.get('title')):
            code=match['code']
            if code=='source_title_nsfw_marker':
                r['exclusions'].append({'code':code,'sourceId':source.get('id'),'marker':match['matchedText']})
            elif code not in seen_safety:
                r['exclusions'].append({'code':code});seen_safety.add(code)
    r['commentsComplete']=r.get('commentsAllSelected') is True and r['commentCount']==r.get('commentsExpected') and not conflicts and counts_valid
    r['observedKCount']=r['kCount'];r['observedCommentCount']=r['commentCount']
    r['kCountVerified']=r['commentsComplete'] and r.get('status')=='observed'
    capture_timestamp_valid=False
    try:
        captured=dt.datetime.fromisoformat(r.get('commentEvidenceObservedAt','').replace('Z','+00:00'))
        capture_timestamp_valid=captured.tzinfo is not None
    except (AttributeError,TypeError,ValueError):pass
    captured_context=r.get('status')=='observed' or (r.get('status') in ('failed','blocked','blocked_or_missing') and capture_timestamp_valid)
    trusted_rows=bool(comments) and r.get('commentsAllSelected') is True and not conflicts and counts_valid and captured_context
    r['nativeCountEvidenceTrusted']=bool(r['kCountVerified'] or trusted_rows)
    r['knownLiteralKMinimum']=r['observedKCount'] if r['nativeCountEvidenceTrusted'] else None
    r['thresholdEvidence']='exact_native_total' if r['kCountVerified'] else None
    if not r['kCountVerified']:
        r['kCount']=None;r['commentCount']=None;r['thresholdQualified']=None
        if trusted_rows and r['observedKCount']>=11:
            r['thresholdQualified']=True;r['thresholdEvidence']='observed_lower_bound'
    r['sourcesComplete']=r.get('sourcesExpanded',False) and len(r.get('sources',[]))==r.get('sourcesExpected')
    r['mediaComplete']=isinstance(r.get('media'),list) and all(bool(m.get('url')) and (m.get('type')!='image' or m.get('complete') and m.get('width',0)>0 and m.get('height',0)>0) and (m.get('type')!='video' or m.get('width',0)>0 and m.get('height',0)>0) for m in r.get('media',[]))
    r['sourceMediaVerificationRequired']=bool(r['thresholdQualified'])
    r['inspectionComplete']=r.get('status')=='observed' and t is not None and r['commentsComplete'] and (not r['sourceMediaVerificationRequired'] or r['sourcesComplete'] and r['mediaComplete'])
    r['thresholdExclusion']='literal_k_below_11' if r['thresholdQualified'] is False else None
    r['candidate']=bool(r['thresholdQualified'] and r['inWindow'] is True and not r['exclusions'])
    r['candidateVerificationHeld']=r['candidate'] and r['thresholdEvidence']=='observed_lower_bound'
    r['candidateVerificationHoldReasons']=(['native_comment_total_unverified']+([] if r['sourcesComplete'] else ['source_list_unverified'])+([] if r['mediaComplete'] else ['media_metadata_unverified'])) if r['candidateVerificationHeld'] else []
    dates=[listed_time(c.get('date')) for c in comments.values()];dates=[x for x in dates if x]
    r['oldCommentCount']=sum(x<start for x in dates);r['windowCommentCount']=sum(start<=x<=end for x in dates);r['postWindowCommentCount']=sum(x>end for x in dates)
    r['outsideWindowVerified']=valid_outside_header(record,start,end)
    if r['outsideWindowVerified']:
        for field in ('kCount','commentCount','observedKCount','observedCommentCount','commentsExpected','knownLiteralKMinimum','oldCommentCount','windowCommentCount','postWindowCommentCount'):
            r[field]=None
        r['kCountVerified']=False;r['commentsComplete']=False;r['nativeCountEvidenceTrusted']=False
        r['thresholdQualified']=None;r['thresholdEvidence']=None;r['thresholdExclusion']=None
        r['candidate']=False;r['candidateVerificationHeld']=False;r['candidateVerificationHoldReasons']=[]
        r['inspectionComplete']=True;r['sourceMediaVerificationRequired']=False
        r['verificationScope']='exact_header_outside_window';r['nativeCommentsNotInspected']=True
        r['windowExclusion']='exact_timestamp_outside_fixed_window'
    r['countScope']='native_aagag_cumulative_at_observation; excludes external source comment totals'
    r['safetyReview']='title_rules_only; visual/context review required before publication'
    return r

def atomic_write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)

def listing_policy_exclusions(listings):
    """Resolve explicit listing-title exclusions without opening their details."""
    excluded={}
    for page in listings:
        for item in page['items']:
            matches=classify_title(item.get('title'))
            if not matches:continue
            marker=next((m['matchedText'] for m in matches if m['code']=='source_title_nsfw_marker'),None)
            reason='known_listing_nsfw_marker' if marker else 'known_listing_title_safety_exclusion'
            identity=post_id(item['id'])
            evidence={'id':item['id'],'title':item.get('title'),'url':item.get('url'),'marker':marker,'matchedRules':matches,'sourceListingPage':page.get('page'),'sourceListingObservedAt':page.get('observedAt'),'sourceListingPhase':page.get('phase','initial')}
            if identity not in excluded:
                excluded[identity]={**evidence,'canonicalId':identity,'commentCount':None,'kCount':None,'thresholdQualified':None,'candidate':False,'listedAt':None,'dateVerified':False,'reason':reason,'listingEvidence':[]}
            excluded[identity]['listingEvidence'].append(evidence)
    return [excluded[identity] for identity in sorted(excluded)]

def coverage(listings,posts,start,end,passes_required=('initial','resweep'),verification_holds=()):
    held_ids={post_id(hold['id']) for hold in verification_holds}
    policy_exclusions=[p for p in listing_policy_exclusions(listings) if p['canonicalId'] not in held_ids]
    excluded_ids={p['canonicalId'] for p in policy_exclusions}
    perpass={};unique={}
    for p in listings:
        phase=p.get('phase','initial');perpass.setdefault(phase,[]).append(p)
        for item in p['items']:unique.setdefault(post_id(item['id']),item)
    pass_ok={}
    for phase in passes_required:
        pages=sorted(perpass.get(phase,[]),key=lambda x:x['page'])
        contiguous=[p['page'] for p in pages]==list(range(1,len(pages)+1))
        boundary=bool(pages and pages[-1].get('boundaryConfirmed'))
        pass_ok[phase]=contiguous and boundary
    failures=[p['canonicalId'] for p in posts if p['canonicalId'] not in excluded_ids and not p.get('inspectionComplete')]
    observed={p['canonicalId'] for p in posts};missing=sorted(set(unique)-observed-excluded_ids)
    # Eligible rows require actual detail evidence; explicit title exclusions remain separately evidenced.
    return {'passes':pass_ok,'verificationHeldIDs':sorted(held_ids),'verificationHeldCount':len(held_ids),'listedUnique':len(unique),'eligibleListedUnique':len(set(unique)-excluded_ids),'policyExcludedCount':len(excluded_ids),'policyExcludedIDs':sorted(excluded_ids),'inspected':len(observed),'eligibleInspected':len(observed-excluded_ids),'failedOrIncomplete':failures,'missingIds':missing,'complete':all(pass_ok.values()) and not failures and not missing and not held_ids}
