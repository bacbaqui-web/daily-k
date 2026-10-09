from pathlib import Path
import argparse
import os
import sys,json,datetime as dt
from core import *

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_RUN=ROOT/'runs/20261009T020332Z'
DEFAULT_END=utc('2026-10-09T02:03:32.390Z')
DEFAULT_START=DEFAULT_END-dt.timedelta(hours=24)
RUN=Path(os.environ.get('DAILYK_RUN_DIR') or DEFAULT_RUN).expanduser()
# Compatibility constants for the original active run. Custom runs use run.json.
START=DEFAULT_START
END=DEFAULT_END
WINDOW_BASIS='aagag latest listing/relisting timestamp, NOT original publication'


def parse_utc_anchor(value):
    """Require an explicit aware UTC instant; never infer a cutoff from now."""
    if not isinstance(value,str):
        raise ValueError('Window timestamps must be ISO UTC strings ending in Z or +00:00')
    try:
        stamp=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as error:
        raise ValueError('Invalid ISO UTC window timestamp: '+value) from error
    if stamp.tzinfo is None or stamp.utcoffset()!=dt.timedelta(0):
        raise ValueError('Window timestamps must include the UTC timezone (Z or +00:00)')
    return stamp.astimezone(UTC)


def manifest_window(manifest):
    if manifest.get('version',1)!=1:
        raise ValueError('Unsupported run.json manifest version')
    try:
        start=parse_utc_anchor(manifest['window']['start'])
        end=parse_utc_anchor(manifest['window']['end'])
    except (KeyError,TypeError) as error:
        raise ValueError('run.json must contain window.start and window.end') from error
    if end-start!=dt.timedelta(hours=24):
        raise ValueError('run.json window must be exactly 24 hours')
    return start,end


def resolve_run(run_dir=None):
    run=Path(run_dir if run_dir is not None else RUN).expanduser().resolve()
    manifest_path=run/'run.json'
    if manifest_path.exists():
        start,end=manifest_window(json.loads(manifest_path.read_text()))
    elif run==DEFAULT_RUN.resolve():
        # Existing collection keeps its original anchor without touching its files.
        start,end=DEFAULT_START,DEFAULT_END
    else:
        raise ValueError('Custom run has no run.json; initialize it with init --end <actual initial UTC observation> --run-dir '+str(run))
    return run,start,end


def initialize_run(end,run_dir=None):
    """Create a fixed-window manifest, or resume it only with the identical anchor."""
    end=parse_utc_anchor(end)
    start=end-dt.timedelta(hours=24)
    chosen=run_dir if run_dir is not None else os.environ.get('DAILYK_RUN_DIR')
    if chosen is None:
        suffix=end.strftime('%Y%m%dT%H%M%S')+(('.%06d'%end.microsecond) if end.microsecond else '')+'Z'
        chosen=ROOT/'runs'/suffix
    run=Path(chosen).expanduser().resolve()
    run.mkdir(parents=True,exist_ok=True)
    lock=run/'.initializing'
    try:
        lock_handle=lock.open('x')
    except FileExistsError as error:
        raise ValueError('Run initialization is already in progress: '+str(run)) from error
    lock_handle.close()
    try:
        manifest_path=run/'run.json'
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text())
            existing_start,existing_end=manifest_window(manifest)
            if (existing_start,existing_end)!=(start,end):
                raise ValueError('Existing run cutoff is immutable; use a new run directory for a different --end')
        else:
            has_evidence=any((run/'listings').glob('*.json')) or any((run/'posts').glob('*.json')) or (run/'summary.json').exists()
            legacy_match=run==DEFAULT_RUN.resolve() and end==DEFAULT_END
            if has_evidence and not legacy_match:
                raise ValueError('Refusing to assign a new cutoff to an existing uninitialized run with evidence')
            manifest={'version':1,'createdAt':dt.datetime.now(UTC).isoformat(),'anchorBasis':'explicit_initial_observation','window':{'start':start.isoformat(),'end':end.isoformat(),'timezone':'Asia/Seoul','basis':WINDOW_BASIS}}
            atomic_write(manifest_path,manifest)
        (run/'listings').mkdir(exist_ok=True)
        (run/'posts').mkdir(exist_ok=True)
        return run,manifest
    finally:
        lock.unlink(missing_ok=True)


def load_verification_holds(run):
    """Read explicit unresolved holds; never infer a hold or a content classification."""
    path=Path(run)/'verification-holds.json'
    if not path.exists():return []
    records=json.loads(path.read_text())
    if not isinstance(records,list):
        raise ValueError('verification-holds.json must be a list of explicit hold records')
    holds=[]
    required=('id','title','url','reason','heldAt')
    for index,record in enumerate(records):
        if not isinstance(record,dict) or any(not isinstance(record.get(key),str) or not record[key].strip() for key in required):
            raise ValueError('verification-holds.json record '+str(index)+' must provide nonempty id, title, url, reason, and heldAt strings')
        holds.append({**record,'canonicalId':post_id(record['id'])})
    return holds


TEMPORAL_HOLD_REASON='relisted_after_cutoff_original_exact_time_unknown'

def load_temporal_holds(run,listings):
    path=Path(run)/'temporal-holds.json'
    if not path.exists():return []
    records=json.loads(path.read_text())
    if not isinstance(records,list):raise ValueError('temporal-holds.json must be a list')
    holds=[];seen=set()
    for record in records:
        if not isinstance(record,dict) or not isinstance(record.get('id'),str) or not record['id'].strip() or record.get('reason')!=TEMPORAL_HOLD_REASON or not isinstance(record.get('heldAt'),str):
            raise ValueError('Invalid explicit temporal verification hold')
        identity=post_id(record['id']);provided=record.get('initialListingEvidence')
        if identity in seen:raise ValueError('Duplicate canonical temporal hold')
        if not isinstance(provided,dict) or any(key not in provided for key in ('page','observedAt','age')):
            raise ValueError('Temporal hold requires original page, observedAt, and displayed age evidence')
        matches=[]
        for page in listings:
            if page.get('phase','initial')!='initial':continue
            for item in page['items']:
                if post_id(item['id'])!=identity:continue
                evidence={'id':item['id'],'phase':'initial','page':page['page'],'observedAt':page.get('observedAt'),'age':item.get('age'),'url':item.get('url')}
                if all(provided[key]==evidence.get(key) for key in provided if key in evidence):matches.append(evidence)
        if not matches:raise ValueError('Temporal hold does not match stored initial-listing evidence for '+identity)
        holds.append({**record,'canonicalId':identity,'initialListingEvidence':matches[0],'originalExactListedAt':None});seen.add(identity)
    return holds

def apply_temporal_holds(posts,holds):
    by_id={hold['canonicalId']:hold for hold in holds}
    for post in posts:
        for key in ('temporalMembershipUncertain','temporalHoldReason','temporalVerificationHeld','initialListingEvidence','originalExactListedAt','latestListedAt'):
            post.pop(key,None)
        hold=by_id.get(post['canonicalId'])
        if hold is None:continue
        post['latestListedAt']=post.get('listedAt')
        post['originalExactListedAt']=None;post['inWindow']=None
        post['temporalMembershipUncertain']=True;post['temporalVerificationHeld']=True
        post['temporalHoldReason']=TEMPORAL_HOLD_REASON
        post['initialListingEvidence']=hold['initialListingEvidence']
        post['outsideWindowVerified']=False;post['inspectionComplete']=False
        post['candidate']=bool(post.get('thresholdQualified') and not post.get('exclusions'))
        post['candidateVerificationHeld']=post['candidate']
        post['candidateVerificationHoldReasons']=list(dict.fromkeys(post.get('candidateVerificationHoldReasons',[])+[TEMPORAL_HOLD_REASON]))
    return posts


def _load_records(run,start,end):
 listings=[json.loads(p.read_text()) for p in sorted((run/'listings').glob('*.json'))]
 # Raw aliases remain evidence. Fresh verified comment counts take precedence
 # over full source/media completeness so a newer threshold crossing is kept.
 grouped={}
 for path in sorted((run/'posts').glob('*.json')):
  post=normalize(json.loads(path.read_text()),start,end)
  stamps=[]
  for value in [post.get('observedAt')]+[a.get('at') for a in post.get('attempts',[])]:
   try:stamps.append(utc(value or ''))
   except (TypeError,ValueError,AttributeError):pass
  observed=max(stamps) if stamps else None
  rank_time=observed or dt.datetime.min.replace(tzinfo=UTC)
  grouped.setdefault(post['canonicalId'],[]).append((rank_time,path.name,observed,post))
 posts=[]
 for identity in sorted(grouped):
  aliases=grouped[identity]
  selected=max(aliases,key=lambda a:(bool(a[3].get('commentsComplete')),a[0],a[1]))
  latest=max(aliases,key=lambda a:(a[0],a[1]))
  def alias_info(alias):
   return {'rawFile':alias[1],'id':alias[3].get('id'),'evidenceAt':alias[2].isoformat() if alias[2] else None,'status':alias[3].get('status'),'commentsComplete':bool(alias[3].get('commentsComplete')),'inspectionComplete':bool(alias[3].get('inspectionComplete'))}
  post=selected[3]
  post['observationSelection']={'strategy':'newest_comments_complete_else_newest','selectedRawFile':selected[1],'selectedEvidenceAt':selected[2].isoformat() if selected[2] else None,'latestKnownAttempt':alias_info(latest) if latest[2] is not None else None,'selectedIsLatestKnownAttempt':selected[1]==latest[1] if all(a[2] is not None for a in aliases) else None,'allAliasTimestampsKnown':all(a[2] is not None for a in aliases),'rawAliasCount':len(aliases),'newerIncompleteAliases':[alias_info(a) for a in sorted(aliases,key=lambda a:(a[0],a[1])) if (a[0],a[1])>(selected[0],selected[1])]}
  posts.append(post)
 return listings,posts

def load(run_dir=None):
 run,start,end=resolve_run(run_dir)
 listings,posts=_load_records(run,start,end)
 return listings,apply_temporal_holds(posts,load_temporal_holds(run,listings))

def update(run_dir=None):
 run,start,end=resolve_run(run_dir)
 listings,posts=_load_records(run,start,end)
 temporal_holds=load_temporal_holds(run,listings);temporal_ids={hold['canonicalId'] for hold in temporal_holds}
 posts=apply_temporal_holds(posts,temporal_holds);pmap={p['canonicalId']:p for p in posts}
 verification_holds=load_verification_holds(run)
 held_ids={hold['canonicalId'] for hold in verification_holds}
 policy_exclusions=[p for p in listing_policy_exclusions(listings) if p['canonicalId'] not in held_ids]
 excluded_ids={p['canonicalId'] for p in policy_exclusions}
 for listing in listings:
  exact=[listed_time(pmap.get(post_id(i['id']),{}).get('listedAtRaw')) for i in listing['items'] if post_id(i['id']) not in excluded_ids|held_ids|temporal_ids]
  # Boundary proof uses every nonexcluded, non-held row and at least one
  # eligible older witness. Held dates remain explicitly outside this proof.
  listing['boundaryConfirmed']=bool(exact) and all(t is not None and t<start for t in exact)
  listing['boundaryHeldIDs']=sorted({post_id(i['id']) for i in listing['items'] if post_id(i['id']) in held_ids|temporal_ids})
  listing['boundaryHeldDatesUnverified']=bool(listing['boundaryHeldIDs'])
 last_pages={}
 for listing in listings:
  phase=listing.get('phase','initial')
  if phase not in last_pages or listing['page']>=last_pages[phase]['page']:last_pages[phase]=listing
 boundary_held_by_pass={phase:{'page':page['page'],'heldIDs':page['boundaryHeldIDs']} for phase,page in last_pages.items() if page['boundaryHeldIDs']}
 boundary_held_ids=sorted({identity for evidence in boundary_held_by_pass.values() for identity in evidence['heldIDs']})
 audit=coverage(listings,posts,start,end,verification_holds=verification_holds)
 if temporal_ids:audit['complete']=False
 listing_complete=all(audit['passes'].values())
 native_incomplete=[p['canonicalId'] for p in posts if p['canonicalId'] not in excluded_ids and not p.get('outsideWindowVerified') and (not p.get('kCountVerified') or p.get('listedAt') is None)]
 native_complete=listing_complete and not audit['missingIds'] and not native_incomplete and not held_ids and not temporal_ids
 candidates=[p for p in posts if p['canonicalId'] not in excluded_ids|held_ids and p['candidate']]
 qualifiers=[p for p in posts if p['canonicalId'] not in excluded_ids|held_ids and p['thresholdQualified'] and (p['inWindow'] is True or p.get('temporalMembershipUncertain') is True)]
 summary={'window':{'start':start.isoformat(),'end':end.isoformat(),'timezone':'Asia/Seoul','basis':'aagag latest listing/relisting timestamp, NOT original publication'},'lastUpdatedAt':dt.datetime.now(UTC).isoformat(),**audit,'verificationHolds':verification_holds,'temporalVerificationHeldIDs':sorted(temporal_ids),'temporalVerificationHeldCount':len(temporal_ids),'temporalVerificationHolds':temporal_holds,'listingCoverageComplete':listing_complete,'nativeCommentCoverageComplete':native_complete,'nativeCommentIncompleteIDs':native_incomplete,'boundaryHeldDatesUnverified':bool(boundary_held_ids),'boundaryHeldIDs':boundary_held_ids,'boundaryHeldIDsByPass':boundary_held_by_pass,'boundaryProofScope':'exact older timestamps for all non-policy-excluded, non-held rows; at least one eligible witness; held dates not used','listingRows':sum(len(x['items']) for x in listings),'pagesByPass':{s:len([x for x in listings if x['phase']==s]) for s in ['initial','resweep']},'observedRecords':len(posts),'outsideWindowHeaderVerified':sum(p.get('outsideWindowVerified') is True for p in posts),'inWindow':sum(p['inWindow'] is True for p in posts),'outOfWindow':sum(p['inWindow'] is False for p in posts),'unknownWindowMembership':sum(p['inWindow'] is None for p in posts),'qualifiers':len(qualifiers),'candidates':len(candidates),'excludedQualifiers':len(qualifiers)-len(candidates),'fullyVerifiedCandidates':sum(p['inspectionComplete'] for p in candidates),'candidateIDs':[p['id'] for p in candidates],'incompleteIDs':[p['id'] for p in posts if p['canonicalId'] not in excluded_ids|held_ids|temporal_ids and not p['inspectionComplete']],'scope':'native aagag comments, literal ㅋ, ID deduplicated; cumulative actual observations; no copyrighted full bodies/comments or image files retained','delivery':'Not published. All threshold candidates retained without editorial sample cap.'}
 atomic_write(run/'listing-exclusions.json',policy_exclusions)
 atomic_write(run/'summary.json',summary);atomic_write(run/'normalized-posts.json',posts);atomic_write(run/'all-threshold-qualifiers.json',qualifiers);atomic_write(run/'candidates.json',candidates)
 items=[];seen=set(pmap)|excluded_ids|held_ids|temporal_ids
 for page in listings:
  for i in page['items']:
   ident=post_id(i['id'])
   if ident not in seen:items.append(i);seen.add(ident)
 atomic_write(run/'pending.json',items)
 return summary,items

def main(argv=None):
    parser=argparse.ArgumentParser(description='Checkpoint fixed-window browser collection runs')
    parser.add_argument('--run-dir',default=None,help='Run directory; overrides DAILYK_RUN_DIR')
    commands=parser.add_subparsers(dest='command')
    initialize=commands.add_parser('init',help='Anchor a new run to its actual initial observation')
    initialize.add_argument('--end',required=True,help='Actual initial observation as an ISO UTC timestamp')
    initialize.add_argument('--run-dir',default=argparse.SUPPRESS)
    pending=commands.add_parser('pending',help='Print never-observed rows')
    pending.add_argument('limit',nargs='?',type=int)
    pending.add_argument('--run-dir',default=argparse.SUPPRESS)
    summary=commands.add_parser('summary',help='Rebuild and print the current checkpoint summary')
    summary.add_argument('--run-dir',default=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    try:
        if args.command=='init':
            run,manifest=initialize_run(args.end,args.run_dir)
            print(json.dumps({'runDir':str(run),'manifest':manifest},ensure_ascii=False,indent=2))
            return 0
        if args.command=='pending' and args.limit is not None and args.limit<0:
            raise ValueError('Pending limit must be nonnegative')
        result,items=update(args.run_dir)
        if args.command=='pending':
            print(json.dumps(items[:args.limit] if args.limit is not None else items,ensure_ascii=False))
        else:
            print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError) as error:
        parser.error(str(error))


if __name__=='__main__':
    raise SystemExit(main())
