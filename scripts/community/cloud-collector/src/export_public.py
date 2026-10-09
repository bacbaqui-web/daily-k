"""Offline, allowlisted public report and reusable collector package exporter.

No browser, network, upload, publication, or source-run mutation occurs here.
Run history/compare_history.py first to refresh publication annotations.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "runs" / "20261009T020332Z"
REQUIRED = ("run.json", "summary.json", "normalized-posts.json", "candidates.json",
            "all-threshold-qualifiers.json")
OPTIONAL = ("listing-exclusions.json", "verification-holds.json", "temporal-holds.json", "publication-intersection.json", "original-source-links.json")
REASON_CODES = {"source_title_nsfw_marker", "sexual_title", "graphic_or_death_title",
                "private_allegation_title"}
COUNT_FIELDS = ("kCount", "commentCount", "oldCommentCount", "windowCommentCount",
                "postWindowCommentCount")
PACKAGE_FILES = (
    "VERSION", "README.md", "RUNNER.md", "src/core.py", "src/checkpoint.py", "src/browser-macro.js", "src/supported_tool_runner.js",
    "src/export_public.py", "src/supervisor_state.py", "src/supervised_tick.js", "SUPERVISOR.md", "tests/test_supervisor_state.py", "tests/test_supervised_tick.cjs", "tests/test_supervisor_integration.cjs", "src/runtime_state.py", "tests/test_runtime_state.py", "tests/README.md", "tests/audit_snapshot.py",
    "tests/test_core.py", "tests/test_checkpoint.py", "tests/test_run_configuration.py",
    "tests/test_browser_macro.cjs", "tests/test_supported_tool_runner.cjs", "tests/test_export_public.py", "tests/title-safety-cases.json",
    "history/README.md", "history/compare_history.py", "history/test_compare_history.py",
)


def identity(value):
    return re.sub(r"[_-]\d+$", "", str(value or "").removeprefix("aagag-"))


def count(value):
    return value if type(value) is int and value >= 0 else None


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value if parsed.tzinfo is not None else None
    except ValueError:
        return None


def http_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def post_url(row):
    """Return only the observed aagag URL with the same identity, never synthesize."""
    value = http_url(row.get("url"))
    if not value:
        return None
    parsed = urlsplit(value)
    observed_id = parse_qs(parsed.query).get("idx", [None])[0]
    if parsed.hostname not in ("aagag.com", "www.aagag.com") or parsed.path.rstrip("/") != "/issue":
        return None
    return value if observed_id and identity(observed_id) == identity(row.get("id")) else None


def short_title(value):
    """Whitespace-based 25-word maximum; no other source text is exported."""
    words = str(value or "").split()
    return " ".join(words[:25]), len(words) > 25


def read_checkpoint(run):
    """Reject torn writes, duplicate identities, stale holds and row loss."""
    for _ in range(5):
        names = list(REQUIRED) + [name for name in OPTIONAL if (run / name).exists()]
        blobs = {name: (run / name).read_bytes() for name in names}
        data = {name: json.loads(blob) for name, blob in blobs.items()}
        stable = all((run / name).read_bytes() == blob for name, blob in blobs.items())
        stable &= all((run / name).exists() == (name in blobs) for name in OPTIONAL)
        summary = data["summary.json"]
        norm = data["normalized-posts.json"]
        candidates = data["candidates.json"]
        qualifiers = data["all-threshold-qualifiers.json"]
        holds = data.get("verification-holds.json", [])
        temporal = data.get("temporal-holds.json", [])
        excluded = data.get("listing-exclusions.json", [])
        nmap = {identity(row.get("id")): row for row in norm}
        cids = [identity(row.get("id")) for row in candidates]
        qids = [identity(row.get("id")) for row in qualifiers]
        held_ids = {identity(row.get("id")) for row in holds}
        excluded_ids = {identity(row.get("id")) for row in excluded}
        consistent = (
            summary.get("window") == data["run.json"].get("window")
            and len(nmap) == len(norm)
            and len(set(cids)) == len(cids) and len(set(qids)) == len(qids)
            and summary.get("observedRecords") == len(norm)
            and summary.get("candidates") == len(candidates)
            and summary.get("qualifiers") == len(qualifiers)
            and set(summary.get("candidateIDs", [])) == {r.get("id") for r in candidates}
            and all(nmap.get(identity(row.get("id"))) == row for row in candidates + qualifiers)
            and set(cids).issubset(qids)
            and not (set(cids) & (held_ids | excluded_ids))
            and not any(row.get("exclusions") for row in candidates)
            and held_ids == {identity(i) for i in summary.get("verificationHeldIDs", [])}
            and len(holds) == summary.get("verificationHeldCount", 0)
            and {identity(row.get("id")) for row in temporal} == {identity(i) for i in summary.get("temporalVerificationHeldIDs", [])}
            and len(temporal) == summary.get("temporalVerificationHeldCount", 0)
            and excluded_ids == {identity(i) for i in summary.get("policyExcludedIDs", [])}
            and len(excluded) == summary.get("policyExcludedCount", 0)
        )
        if stable and consistent:
            hashes = {name: {"sha256": hashlib.sha256(blob).hexdigest(), "byteSize": len(blob)}
                      for name, blob in blobs.items()}
            return data, hashes
        time.sleep(0.2)
    raise RuntimeError("Checkpoint changed or is inconsistent. Rerun after checkpoint writing finishes; no export written.")


def captured_original_links(row, captured):
    """Only the separate captured-link evidence can supply original host URLs."""
    entry = captured.get(identity(row.get("id"))) or captured.get(row.get("id"))
    entries = entry if isinstance(entry, list) else [entry]
    result = []
    for link in entries:
        if not isinstance(link, dict):
            continue
        url = http_url(link.get("url"))
        verified_at = timestamp(link.get("verifiedAt"))
        if not url or not verified_at or urlsplit(url).hostname in ("aagag.com", "www.aagag.com"):
            continue
        result.append({"url": url, "verifiedAt": verified_at,
                       "originalPublishedAt": timestamp(link.get("originalPublishedAt")),
                       "originalHostBodyVerified": link.get("bodyVerified") is True})
    return result


def public_media(raw):
    """Keep captured body-media order and metadata, never text or binaries."""
    result = []
    for item in raw if isinstance(raw, list) else []:
        kind = item.get("type")
        media = {"type": kind if kind in ("image", "video", "embed") else "unknown",
                 "order": count(item.get("order")), "url": http_url(item.get("url"))}
        if kind == "image":
            media.update({"naturalWidth": count(item.get("width")),
                          "naturalHeight": count(item.get("height")),
                          "loadComplete": item.get("complete") if type(item.get("complete")) is bool else None})
        elif kind == "video":
            media.update({"width": count(item.get("width")), "height": count(item.get("height")),
                          "poster": http_url(item.get("poster"))})
        result.append(media)
    return result


def verified_lower_bound(row):
    """Independently validate the declared floor without exporting native rows."""
    minimum=count(row.get("knownLiteralKMinimum"))
    if (minimum is None or minimum<11 or row.get("thresholdQualified") is not True
            or row.get("thresholdEvidence")!="observed_lower_bound"
            or row.get("nativeCountEvidenceTrusted") is not True
            or row.get("candidateVerificationHeld") is not True
            or row.get("kCountVerified") is not False
            or row.get("commentsAllSelected") is not True
            or row.get("commentConflicts") or row.get("invalidCommentCountIDs")):
        return None
    if row.get("status")!="observed" and not (row.get("status") in ("failed","blocked","blocked_or_missing") and timestamp(row.get("commentEvidenceObservedAt"))):
        return None
    raw=row.get("commentCounts")
    if not isinstance(raw,list) or not raw:return None
    native={}
    for comment in raw:
        if not isinstance(comment,dict) or type(comment.get("id")) not in (str,int) or not str(comment["id"]).strip():return None
        amount=count(comment.get("kCount"))
        if amount is None:return None
        key=str(comment["id"]);evidence=(amount,comment.get("date"))
        if key in native and native[key]!=evidence:return None
        native[key]=evidence
    return minimum if sum(value[0] for value in native.values())==minimum else None


TEMPORAL_HOLD_REASON="relisted_after_cutoff_original_exact_time_unknown"

def public_temporal_evidence(row):
    evidence=row.get("initialListingEvidence")
    held=(row.get("temporalMembershipUncertain") is True and row.get("temporalVerificationHeld") is True
          and row.get("temporalHoldReason")==TEMPORAL_HOLD_REASON and row.get("inWindow") is None
          and isinstance(evidence,dict) and timestamp(evidence.get("observedAt")) is not None)
    if not held:return False,None
    if evidence.get("phase")!="initial" or identity(evidence.get("id"))!=identity(row.get("id")) or count(evidence.get("page")) is None or evidence["page"]<1 or post_url({"id":row.get("id"),"url":evidence.get("url")}) is None:return False,None
    age=evidence.get("age")
    if not isinstance(age,str) or not re.fullmatch(r"\d+\s*(?:초|분|시간|일|개월|년)\s*전",age):return False,None
    safe={"id":evidence.get("id"),"page":count(evidence.get("page")),"phase":"initial",
          "observedAt":timestamp(evidence.get("observedAt")),"age":age,
          "url":post_url({"id":row.get("id"),"url":evidence.get("url")})}
    return True,safe

def field_observation_time(row,key,captured):
    return timestamp(row.get(key)) if key in row else (timestamp(row.get("observedAt")) if captured else None)


def public_candidate(row, captured, comparison=None):
    title, truncated = short_title(row.get("title"))
    verified = (row.get("kCountVerified") is True and row.get("commentsComplete") is True
                and row.get("status") == "observed" and count(row.get("kCount")) is not None
                and count(row.get("commentCount")) is not None)
    lower_bound = verified_lower_bound(row) if not verified else None
    temporal_held,temporal_evidence=public_temporal_evidence(row)
    comparison_public=public_comparison_row(comparison)
    partitions = [count(row.get(key)) for key in COUNT_FIELDS[2:]]
    dates_verified = verified and all(n is not None for n in partitions) and sum(partitions) == row["commentCount"]
    observed = len(row["sources"]) if isinstance(row.get("sources"), list) else None
    reported = count(row.get("sourcesExpected"))
    source_gap = observed != reported if observed is not None and reported is not None else None
    complete = (row.get("inspectionComplete") is True and verified and dates_verified and post_url(row) is not None
                and timestamp(row.get("listedAt")) is not None and timestamp(row.get("observedAt")) is not None
                and row.get("sourcesComplete") is True and source_gap is False and row.get("mediaComplete") is True)
    result = {
        "id": row.get("id"), "canonicalId": identity(row.get("id")), "title": title,
        "titleTruncated": truncated, "titleWordCount": len(title.split()), "url": post_url(row),
        "observedAt": timestamp(row.get("observedAt")), "listedAt": timestamp(row.get("listedAt")),
        "commentEvidenceObservedAt": field_observation_time(row,"commentEvidenceObservedAt",verified or lower_bound is not None),
        "sourceListObservedAt": field_observation_time(row,"sourceListObservedAt",row.get("sourcesExpanded") is True),
        "mediaObservedAt": field_observation_time(row,"mediaObservedAt",isinstance(row.get("media"),list)),
        "temporalMembershipUncertain": temporal_held, "temporalHoldReason": TEMPORAL_HOLD_REASON if temporal_held else None,
        "initialListingEvidence": temporal_evidence, "latestListedAt": timestamp(row.get("listedAt")) if temporal_held else None,
        "originalExactListedAt": None,
        "inFixedListingWindow": row.get("inWindow") if type(row.get("inWindow")) is bool else None,
        "kCount": count(row.get("kCount")) if verified else None,
        "commentCount": count(row.get("commentCount")) if verified else None,
        "kCountVerified": verified,
        "thresholdQualified": row["kCount"] >= 11 if verified else (True if lower_bound is not None else None),
        "thresholdEvidence": "exact_native_total" if verified else ("observed_lower_bound" if lower_bound is not None else None),
        "knownLiteralKMinimum": count(row.get("kCount")) if verified else lower_bound,
        "candidateVerificationHeld": lower_bound is not None or temporal_held,
        "candidateVerificationHoldReasons": ((["native_comment_total_unverified"]+([] if row.get("sourcesComplete") is True else ["source_list_unverified"])+([] if row.get("mediaComplete") is True else ["media_metadata_unverified"])) if lower_bound is not None else [])+([TEMPORAL_HOLD_REASON] if temporal_held else []),
        "oldCommentCount": partitions[0] if dates_verified else None,
        "windowCommentCount": partitions[1] if dates_verified else None,
        "postWindowCommentCount": partitions[2] if dates_verified else None,
        "commentDatePartitionVerified": dates_verified,
        "sourceCountObserved": observed, "sourceCountReported": reported,
        "sourceGapFlag": source_gap, "sourceListChecked": row.get("sourcesExpanded") is True,
        "sourceListComplete": row.get("sourcesComplete") is True and source_gap is False,
        "media": public_media(row.get("media")), "mediaMetadataComplete": row.get("mediaComplete") is True,
        "originalSourceLinks": captured_original_links(row, captured),
        "safetyStatus": "title_rules_only; visual_and_context_review_required_before_publication",
        "verificationStatus": "verification_held" if lower_bound is not None or temporal_held else ("captured_metadata_complete" if complete else "verification_incomplete"),
        "metadataReady": complete,
        "readyForIndependentReview": complete and comparison_public["status"]=="current_captured_history" and comparison_public.get("alreadyPublishedIdentityMatch") is False,
        "publicReady": False,
        "duplicateIDs": list(dict.fromkeys(match["id"] for match in comparison_public.get("matches",[]) if match.get("identityMatch") is True and isinstance(match.get("id"),str))),
        "publicationComparison": comparison_public,
    }
    return result


def public_comparison_row(row):
    if row is None:
        return {"status": "unavailable_or_stale", "alreadyPublishedIdentityMatch": None, "matches": []}
    matches = []
    for match in row.get("publicationMatches", []):
        matches.append({"id": match.get("id"), "editionId": match.get("editionId"),
                        "publicationClass": match.get("publicationClass"),
                        "identityMatch": match.get("identityMatch") is True,
                        "githubUrl": http_url(match.get("githubUrl")),
                        "publicDataUrl": http_url(match.get("publicDataUrl"))})
    return {"status": "current_captured_history", "alreadyPublishedIdentityMatch": row.get("alreadyPublishedIdentityMatch") is True,
            "publishedCommunityEditionMatch": row.get("publishedCommunityEditionMatch") is True,
            "legacyPublicFeedMatch": row.get("legacyPublicFeedMatch") is True,
            "mediaOverlapFlag": row.get("mediaMatch") is True, "titleOverlapFlag": row.get("titleMatch") is True,
            "matches": matches}


def read_comparison(directory, hashes, candidates):
    names = ("comparison-summary.json", "candidate-comparison.json")
    if not all((directory / name).is_file() for name in names):
        return {"status": "missing", "candidateIdentityOverlapCount": None}, {}
    blobs = {name: (directory / name).read_bytes() for name in names}
    summary, rows = (json.loads(blobs[name]) for name in names)
    fresh = all((directory / name).read_bytes() == blob for name, blob in blobs.items())
    for name in (*REQUIRED, "original-source-links.json"):
        expected = hashes.get(name, {}).get("sha256")
        if expected != summary.get("inputs", {}).get(name, {}).get("sha256"):
            fresh = False
    expected_ids = {row.get("id") for row in candidates}
    fresh &= len(rows) == len(candidates) and {row.get("id") for row in rows} == expected_ids
    fresh &= len({row.get("id") for row in rows}) == len(rows)
    if not fresh:
        return {"status": "stale_or_inconsistent", "candidateIdentityOverlapCount": None,
                "reason": "Recompute history comparison from the current checkpoint before interpreting overlaps."}, {}
    old = summary.get("old0830KSTEdition", {})
    initial_overlaps = [row.get("id") for row in rows if any(
        match.get("identityMatch") is True and match.get("editionId") == old.get("editionId")
        for match in row.get("publicationMatches", []))]
    report = {"status": "current_captured_history", "generatedAt": timestamp(summary.get("generatedAt")),
              "sourceCheckpointAt": timestamp(summary.get("sourceCheckpointAt")),
              "publishedSnapshotCapturedAt": timestamp(summary.get("publishedSnapshotCapturedAt")),
              "publishedCommitSha": summary.get("publishedCommitSha"),
              "publishedRecordCount": count(summary.get("publishedRecordCount")),
              "publishedCanonicalIdCount": count(summary.get("publishedCanonicalIdCount")),
              "candidateIdentityOverlapCount": sum(row.get("alreadyPublishedIdentityMatch") is True for row in rows),
              "candidateIdentityUnmatchedCount": sum(row.get("alreadyPublishedIdentityMatch") is not True for row in rows),
              "candidateCommunityOverlapCount": sum(row.get("publishedCommunityEditionMatch") is True for row in rows),
              "candidateLegacyFeedOverlapCount": sum(row.get("legacyPublicFeedMatch") is True for row in rows),
              "old0830KSTEdition": {"editionId": old.get("editionId"), "cutoffAt": timestamp(old.get("cutoffAt")),
                                   "publishedStoryCount": count(old.get("publishedStoryCount")),
                                   "publishedIds": old.get("publishedIds", []),
                                   "candidateIdentityOverlapCount": len(initial_overlaps),
                                   "candidateIdentityOverlapIds": initial_overlaps,
                                   "commentsObservedAt": [timestamp(t) for t in old.get("commentsObservedAt", [])]},
              "scope": "Captured deployed community editions and separately labelled legacy public feed; not exhaustive deleted history."}
    return report, {row["id"]: row for row in rows}


def status_row(row, status, reason):
    return {"id": row.get("id"), "status": status, "reason": reason}


def exclusion_reason(row):
    codes = sorted({entry.get("code") for field in ("matchedRules", "exclusions")
                    for entry in row.get(field, []) if entry.get("code") in REASON_CODES})
    return "; ".join(codes) or "recorded_policy_exclusion"


def build_report(data, hashes, comparison_summary, comparison_rows, run_id):
    summary = data["summary.json"]
    raw_candidates = data["candidates.json"]
    candidates = [public_candidate(row, data.get("original-source-links.json", {}), comparison_rows.get(row.get("id")))
                  for row in raw_candidates]
    holds = [status_row(row, "verification_held", "Unresolved title safety verification; prohibited content is not confirmed.")
             for row in data.get("verification-holds.json", [])]
    held_ids = {identity(row["id"]) for row in holds}
    listing_excluded = [status_row(row, "policy_excluded_before_visit", exclusion_reason(row))
                       for row in data.get("listing-exclusions.json", []) if identity(row.get("id")) not in held_ids]
    excluded_ids = {identity(row["id"]) for row in listing_excluded}
    observed_excluded = [status_row(row, "policy_excluded_observed", exclusion_reason(row))
                         for row in data["normalized-posts.json"] if row.get("exclusions")
                         and identity(row.get("id")) not in held_ids | excluded_ids]
    unresolved = []
    for row in data["normalized-posts.json"]:
        if row.get("inspectionComplete") is True or identity(row.get("id")) in held_ids | excluded_ids or row.get("exclusions"):
            continue
        reasons = []
        if row.get("commentsComplete") is not True or row.get("kCountVerified") is not True:
            reasons.append("native_comment_count_unverified")
        if not timestamp(row.get("listedAt")):
            reasons.append("exact_listing_date_unverified")
        if public_temporal_evidence(row)[0]:
            reasons.append(TEMPORAL_HOLD_REASON)
        if row.get("thresholdQualified") is True:
            if row.get("sourcesComplete") is not True:
                reasons.append("source_list_incomplete")
            if row.get("mediaComplete") is not True:
                reasons.append("body_media_metadata_incomplete")
        unresolved.append(status_row(row, "verification_held" if verified_lower_bound(row) is not None or public_temporal_evidence(row)[0] else ("verification_failed" if row.get("status") == "failed" else "verification_incomplete"),
                                     "; ".join(reasons) or "captured_inspection_incomplete"))
    pending = [status_row({"id": i}, "not_observed", "Detail verification has not been completed.")
               for i in summary.get("missingIds", []) if identity(i) not in held_ids | excluded_ids]
    metadata_rows=[row for row in candidates if row["metadataReady"]]
    published_ids=[row["id"] for row in metadata_rows if row["publicationComparison"].get("alreadyPublishedIdentityMatch") is True]
    unmatched_ids=[row["id"] for row in metadata_rows if row["publicationComparison"]["status"]=="current_captured_history" and row["publicationComparison"].get("alreadyPublishedIdentityMatch") is False]
    intersection={"metadataPassed":len(metadata_rows),"alreadyPublished":len(published_ids),"unmatched":len(unmatched_ids),"unknownComparison":len(metadata_rows)-len(published_ids)-len(unmatched_ids),"publishedIds":published_ids,"unmatchedIds":unmatched_ids,"source":"current_candidate_comparison"}
    saved_intersection=data.get("publication-intersection.json")
    matches_saved=(isinstance(saved_intersection,dict) and all(count(saved_intersection.get(key))==intersection[key] for key in ("metadataPassed","alreadyPublished","unmatched")) and all(isinstance(saved_intersection.get(key),list) and len(saved_intersection[key])==len(intersection[key]) and all(isinstance(value,str) for value in saved_intersection[key]) and set(saved_intersection[key])==set(intersection[key]) for key in ("publishedIds","unmatchedIds")) and intersection["unknownComparison"]==0)
    intersection["savedSnapshotStatus"]="matched" if matches_saved else ("not_provided" if saved_intersection is None else "not_verified_against_current_comparison")
    complete = (summary.get("complete") is True and summary.get("listingCoverageComplete") is True
                and summary.get("nativeCommentCoverageComplete") is True and not (holds or unresolved or pending)
                and all(row["verificationStatus"] == "captured_metadata_complete" for row in candidates))
    observed_times = sorted({t for row in data["normalized-posts.json"] if (t := timestamp(row.get("observedAt")))},
                            key=lambda t: dt.datetime.fromisoformat(t.replace("Z", "+00:00")))
    window = {key: summary.get("window", {}).get(key) for key in ("start", "end", "timezone", "basis")}
    for key in ("start", "end"):
        value = timestamp(window[key])
        window[key + "KST"] = dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            dt.timezone(dt.timedelta(hours=9))).isoformat() if value else None
    return {
        "schemaVersion": 1, "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runId": run_id, "checkpointAt": timestamp(summary.get("lastUpdatedAt")), "inputEvidence": hashes,
        "fullCompletion": complete, "completionScope": "Captured listing, native-comment, source-list and body-media metadata; not publication safety approval.",
        "listingCoverageComplete": summary.get("listingCoverageComplete") is True,
        "nativeCommentCoverageComplete": summary.get("nativeCommentCoverageComplete") is True,
        "fixedListingWindow": window, "threshold": {"character": "ㅋ", "minimum": 11, "scope": "ID-deduplicated native aagag comments, cumulative at actual observation"},
        "actualObservationRange": {"first": observed_times[0] if observed_times else None, "last": observed_times[-1] if observed_times else None},
        "counts": {"listedUnique": count(summary.get("listedUnique")), "observedRecords": len(data["normalized-posts.json"]),
                   "retainedCandidates": len(candidates), "lowerBoundQualifiedCandidates": sum(row["thresholdEvidence"] == "observed_lower_bound" for row in candidates), "temporallyUncertainCandidates": sum(row["temporalMembershipUncertain"] for row in candidates), "allThresholdQualifiers": len(data["all-threshold-qualifiers.json"]),
                   "listingPolicyExclusions": len(listing_excluded), "additionalObservedPolicyExclusions": len(observed_excluded),
                   "verificationHeld": len(holds), "failedOrIncomplete": len(unresolved), "notObserved": len(pending),
                   "metadataCompleteCandidates": sum(row["metadataReady"] for row in candidates), "readyForIndependentReview": sum(row["readyForIndependentReview"] for row in candidates)},
        "publicationComparison": comparison_summary, "metadataReviewIntersection":intersection, "candidates": candidates,
        "listingPolicyExclusions": listing_excluded, "additionalObservedPolicyExclusions": observed_excluded,
        "verificationHolds": holds, "failedOrIncomplete": unresolved, "notObserved": pending,
        "interpretation": [
            "All current candidates are retained in input order. Publication overlaps are annotations, never editorial removals.",
            "Observed lower-bound qualification proves the threshold from captured native rows; exact totals remain null and verification stays held.",
            "The fixed window uses latest listing/relisting timestamps, not original publication or comment age.",
            "This run's 11:03 KST cutoff and later cumulative actual observations differ from the original 08:30 KST run.",
            "Older and post-cutoff comments contribute to the cumulative literal ㅋ count and are separately counted when dates reconcile.",
            "An unmatched or newly qualifying item does not establish an omission in the original run.",
            "Expanded aagag source-list checks do not verify an original host's body. Original host URLs appear only when separately captured.",
            "Titles are capped at 25 whitespace-separated words per post. No body/comment quotations, full source-title lists, or media binaries are included.",
            "Policy exclusions, unresolved verification holds, failed observations and pending observations have distinct statuses. Unknown results never establish full completion.",
            "This is a metadata report, not a publication feed or a visual/content safety clearance.",
        ],
    }


def candidates_csv(report):
    fields = ("id", "canonicalId", "title", "titleTruncated", "url", "observedAt", "listedAt", "inFixedListingWindow",
              *COUNT_FIELDS, "kCountVerified", "thresholdQualified", "thresholdEvidence", "knownLiteralKMinimum", "candidateVerificationHeld", "candidateVerificationHoldReasons", "commentDatePartitionVerified", "sourceCountObserved",
              "sourceCountReported", "sourceGapFlag", "commentEvidenceObservedAt", "sourceListObservedAt", "mediaObservedAt", "temporalMembershipUncertain", "temporalHoldReason", "initialListingEvidence", "latestListedAt", "originalExactListedAt", "sourceListChecked", "sourceListComplete", "mediaMetadataComplete",
              "safetyStatus", "verificationStatus", "metadataReady", "readyForIndependentReview", "publicReady", "duplicateIDs", "media", "originalSourceLinks", "publicationComparison")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in report["candidates"]:
        safe = {key: json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (dict, list)) else value
                for key, value in row.items()}
        # Spreadsheet formula protection; JSON retains the unchanged short title.
        for key, value in safe.items():
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                safe[key] = "'" + value
        writer.writerow(safe)
    return output.getvalue().encode("utf-8-sig")


def source_snapshot(root):
    """Capture only allowlisted regular source/test/doc bytes for a clean package."""
    root=root.resolve();blobs={}
    for relative in PACKAGE_FILES:
        path=root/relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError(f"Required package file missing or symlinked: {relative}")
        blobs[relative]=path.read_bytes()
    version=blobs["VERSION"].decode("utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?",version):
        raise RuntimeError("VERSION must contain an explicit semantic source version")
    entries=[{"path":relative,"sha256":hashlib.sha256(data).hexdigest(),"byteSize":len(data)} for relative,data in sorted(blobs.items())]
    digest=hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    manifest={"schemaVersion":1,"package":"dailyk-cloud-macro","version":version,"hashAlgorithm":"sha256","sourceTreeSha256":digest,"files":entries,"scope":"Allowlisted source, offline tests, and documentation only; excludes raw runs, private evidence, images, videos, and history snapshots."}
    return blobs,manifest


def export(run, output, comparison_directory, root=ROOT):
    data, hashes = read_checkpoint(run)
    source_blobs,manifest=source_snapshot(root)
    manifest_bytes=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    comparison, rows = read_comparison(comparison_directory, hashes, data["candidates.json"])
    report = build_report(data, hashes, comparison, rows, run.name)
    report["sourcePackage"]={"version":manifest["version"],"sourceTreeSha256":manifest["sourceTreeSha256"],"manifest":"source-manifest.json"}
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    csv_bytes = candidates_csv(report)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".public-export-", dir=output) as temporary:
        staging = Path(temporary)
        (staging / "public-run-report.json").write_bytes(report_bytes)
        (staging / "candidates.csv").write_bytes(csv_bytes)
        (staging / "source-manifest.json").write_bytes(manifest_bytes)
        with zipfile.ZipFile(staging / "dailyk-cloud-macro.zip", "w", compression=zipfile.ZIP_DEFLATED) as package:
            for relative,blob in source_blobs.items():
                package.writestr(relative,blob)
            package.writestr("source-manifest.json",manifest_bytes)
            package.writestr("deliverables/public-run-report.json", report_bytes)
            package.writestr("deliverables/candidates.csv", csv_bytes)
        if any((root/relative).read_bytes()!=blob for relative,blob in source_blobs.items()):
            raise RuntimeError("Source changed during packaging; no export committed. Rerun after edits stop.")
        for name in ("public-run-report.json", "candidates.csv", "source-manifest.json", "dailyk-cloud-macro.zip"):
            os.replace(staging / name, output / name)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "deliverables")
    parser.add_argument("--comparison-dir", type=Path)
    args = parser.parse_args()
    comparison = args.comparison_dir or ROOT / "history" / "comparisons" / args.run_dir.name
    report = export(args.run_dir.resolve(), args.output_dir.resolve(), comparison.resolve())
    print(json.dumps({"fullCompletion": report["fullCompletion"], "checkpointAt": report["checkpointAt"],
                      "counts": report["counts"], "publicationComparisonStatus": report["publicationComparison"]["status"],
                      "sourcePackage": report["sourcePackage"], "outputDirectory": str(args.output_dir.resolve())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
