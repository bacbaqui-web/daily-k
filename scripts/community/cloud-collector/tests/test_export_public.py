"""Offline public-export privacy, completeness, retention and packaging tests."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_export_under_test", ROOT / "src" / "export_public.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def row(post_id="100", **changes):
    value = {"id": post_id, "canonicalId": exporter.identity(post_id), "title": "A short synthetic title",
             "url": f"https://aagag.com/issue/?idx={post_id}", "status": "observed",
             "observedAt": "2026-10-09T03:00:00Z", "listedAt": "2026-10-09T01:00:00Z", "inWindow": True,
             "kCount": 11, "commentCount": 3, "oldCommentCount": 1, "windowCommentCount": 1,
             "postWindowCommentCount": 1, "kCountVerified": True, "commentsComplete": True,
             "thresholdQualified": True, "candidate": True, "inspectionComplete": True,
             "sources": [{"id": "external_123", "title": "SOURCE TITLE MUST NEVER LEAK", "url": "https://external.test/untrusted"}],
             "sourcesExpected": 1, "sourcesExpanded": True, "sourcesComplete": True, "mediaComplete": True,
             "media": [{"type": "image", "order": 0, "url": "https://i.aagag.com/o/first.webp", "width": 888,
                        "height": 1234, "complete": True},
                       {"type": "video", "order": 2, "url": "https://i.aagag.com/second.mp4", "width": 800,
                        "height": 500, "poster": "https://i.aagag.com/o/second.jpg"}],
             "exclusions": [], "commentCounts": [{"id": "1", "date": "2026-10-09 10:00:00", "kCount": 11}],
             "body": "BODY SECRET", "comments": "COMMENT SECRET", "sourceRange": "SOURCE RANGE SECRET"}
    value.update(changes)
    return value


def dataset(candidates=None, normalized=None, holds=None, excluded=None, complete=False):
    candidates = candidates if candidates is not None else [row()]
    normalized = normalized if normalized is not None else candidates
    holds, excluded = holds or [], excluded or []
    window = {"start": "2026-10-08T02:03:32.390000+00:00", "end": "2026-10-09T02:03:32.390000+00:00",
              "timezone": "Asia/Seoul", "basis": "aagag latest listing/relisting timestamp, NOT original publication"}
    summary = {"window": window, "lastUpdatedAt": "2026-10-09T03:00:00Z", "listedUnique": len(normalized),
               "observedRecords": len(normalized), "candidates": len(candidates), "qualifiers": len(candidates),
               "candidateIDs": [r["id"] for r in candidates], "verificationHeldIDs": [exporter.identity(r["id"]) for r in holds],
               "verificationHeldCount": len(holds), "policyExcludedIDs": [exporter.identity(r["id"]) for r in excluded],
               "policyExcludedCount": len(excluded), "complete": complete, "listingCoverageComplete": complete,
               "nativeCommentCoverageComplete": complete, "missingIds": []}
    return {"run.json": {"window": window}, "summary.json": summary, "normalized-posts.json": normalized,
            "candidates.json": candidates, "all-threshold-qualifiers.json": candidates,
            "verification-holds.json": holds, "listing-exclusions.json": excluded, "original-source-links.json": {}}


def report(data):
    return exporter.build_report(data, {}, {"status": "missing"}, {}, "fixture")


class PublicExportTests(unittest.TestCase):
    def test_metadata_and_history_never_automatically_grant_publication_readiness(self):
        unseen=exporter.public_candidate(row(),{},comparison={"alreadyPublishedIdentityMatch":False})
        self.assertTrue(unseen["metadataReady"])
        self.assertTrue(unseen["readyForIndependentReview"])
        self.assertFalse(unseen["publicReady"])
        matched=exporter.public_candidate(row(),{},comparison={"alreadyPublishedIdentityMatch":True,"publicationMatches":[{"id":"aagag-100","identityMatch":True},{"id":"media-only","identityMatch":False}]})
        self.assertTrue(matched["metadataReady"])
        self.assertFalse(matched["readyForIndependentReview"])
        self.assertFalse(matched["publicReady"])
        self.assertEqual(matched["duplicateIDs"],["aagag-100"])
        unknown=exporter.public_candidate(row(),{})
        self.assertFalse(unknown["readyForIndependentReview"])
        self.assertFalse(unknown["publicReady"])

    def test_metadata_intersection_uses_current_comparison_and_checks_saved_snapshot(self):
        data=dataset([row("100"),row("200")])
        data["publication-intersection.json"]={"metadataPassed":2,"alreadyPublished":1,"unmatched":1,"publishedIds":["100"],"unmatchedIds":["200"]}
        compared={"100":{"alreadyPublishedIdentityMatch":True},"200":{"alreadyPublishedIdentityMatch":False}}
        result=exporter.build_report(data,{}, {"status":"current"},compared,"fixture")
        value=result["metadataReviewIntersection"]
        self.assertEqual(value["metadataPassed"],2)
        self.assertEqual(value["alreadyPublished"],1)
        self.assertEqual(value["unmatched"],1)
        self.assertEqual(value["savedSnapshotStatus"],"matched")
        self.assertEqual(value["publishedIds"],["100"])
        unavailable=exporter.build_report(data,{}, {"status":"stale"},{},"fixture")["metadataReviewIntersection"]
        self.assertEqual(unavailable["unknownComparison"],2)
        self.assertEqual(unavailable["savedSnapshotStatus"],"not_verified_against_current_comparison")
        self.assertEqual(unavailable["alreadyPublished"],0)

    def test_title_cap_whitespace_and_truncated_flag(self):
        title = "\t".join(f"word{i}" for i in range(30))
        result = exporter.public_candidate(row(title=title), {})
        self.assertEqual(result["titleWordCount"], 25)
        self.assertTrue(result["titleTruncated"])
        self.assertEqual(result["title"], " ".join(f"word{i}" for i in range(25)))
        self.assertEqual(exporter.short_title("one two"), ("one two", False))
        self.assertEqual(exporter.short_title(None), ("", False))

    def test_all_candidates_and_media_preserve_input_order(self):
        data = dataset([row("300"), row("100_1"), row("200")])
        result = report(data)
        self.assertEqual([r["id"] for r in result["candidates"]], ["300", "100_1", "200"])
        self.assertEqual(result["counts"]["retainedCandidates"], 3)
        media = result["candidates"][0]["media"]
        self.assertEqual([m["order"] for m in media], [0, 2])
        self.assertEqual(media[0]["naturalWidth"], 888)
        self.assertEqual(media[0]["naturalHeight"], 1234)
        self.assertEqual(media[1]["url"], "https://i.aagag.com/second.mp4")
        self.assertEqual(media[1]["poster"], "https://i.aagag.com/o/second.jpg")

    def test_unknown_counts_are_null_even_with_partial_numbers(self):
        for patch in ({"kCountVerified": False}, {"commentsComplete": False}, {"status": "failed"},
                      {"kCount": None}, {"commentCount": True}):
            with self.subTest(patch=patch):
                result = exporter.public_candidate(row(**patch), {})
                self.assertFalse(result["kCountVerified"])
                self.assertIsNone(result["thresholdQualified"])
                for field in exporter.COUNT_FIELDS:
                    self.assertIsNone(result[field])

    def test_comment_date_partition_must_reconcile(self):
        result = exporter.public_candidate(row(oldCommentCount=0), {})
        self.assertEqual(result["kCount"], 11)
        self.assertFalse(result["commentDatePartitionVerified"])
        self.assertEqual(result["verificationStatus"], "verification_incomplete")
        for field in exporter.COUNT_FIELDS[2:]:
            self.assertIsNone(result[field])

    def test_source_reported_count_is_never_overridden(self):
        result = exporter.public_candidate(row(sourcesExpected=17, sourcesComplete=False), {})
        self.assertEqual(result["sourceCountObserved"], 1)
        self.assertEqual(result["sourceCountReported"], 17)
        self.assertTrue(result["sourceGapFlag"])
        self.assertFalse(result["sourceListComplete"])
        self.assertEqual(result["verificationStatus"], "verification_incomplete")
        unknown = exporter.public_candidate(row(sourcesExpected=None, sources=None), {})
        self.assertIsNone(unknown["sourceCountObserved"])
        self.assertIsNone(unknown["sourceCountReported"])
        self.assertIsNone(unknown["sourceGapFlag"])

    def test_only_separately_captured_original_links_are_exported(self):
        self.assertEqual(exporter.public_candidate(row(), {})["originalSourceLinks"], [])
        links = {"100": {"url": "https://actual.test/observed?x=1", "verifiedAt": "2026-10-09T02:00:00Z",
                          "bodyVerified": False, "sourceId": "must-not-be-used-to-guess"}}
        result = exporter.public_candidate(row("100_1"), links)
        self.assertEqual(result["originalSourceLinks"][0]["url"], "https://actual.test/observed?x=1")
        self.assertFalse(result["originalSourceLinks"][0]["originalHostBodyVerified"])
        self.assertTrue(result["sourceListChecked"])
        del links["100"]["verifiedAt"]
        self.assertEqual(exporter.public_candidate(row(), links)["originalSourceLinks"], [])

    def test_post_url_is_observed_not_constructed_or_guessed(self):
        self.assertEqual(exporter.public_candidate(row("100_1"), {})["url"], "https://aagag.com/issue/?idx=100_1")
        for invalid in (None, "https://aagag.com/issue/?idx=999", "https://other.test/issue/?idx=100"):
            self.assertIsNone(exporter.public_candidate(row(url=invalid), {})["url"])

    def test_no_forbidden_raw_fields_or_full_source_titles(self):
        result = report(dataset())
        forbidden = {"body", "bodyText", "comments", "commentText", "commentCounts", "sources", "sourceTitles",
                     "sourceRange", "attempts", "error", "headerObservations", "matchedText"}
        def visit(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(result)
        serialized = json.dumps(result)
        for marker in ("BODY SECRET", "COMMENT SECRET", "SOURCE TITLE MUST NEVER LEAK", "SOURCE RANGE SECRET"):
            self.assertNotIn(marker, serialized)

    def test_excluded_and_held_records_have_only_id_status_reason(self):
        holds = [{"id": "300", "title": "PRIVATE HELD TITLE", "reason": "PRIVATE HELD TITLE", "media": [{"url": "PRIVATE MEDIA"}]}]
        excluded = [{"id": "400", "title": "PRIVATE EXCLUDED TITLE", "matchedRules": [{"code": "sexual_title", "matchedText": "PRIVATE EXCLUDED TITLE"}]}]
        additional = row("500", candidate=False, exclusions=[{"code": "private_allegation_title"}], title="PRIVATE ADDITIONAL TITLE")
        result = report(dataset(normalized=[row(), additional], holds=holds, excluded=excluded))
        for field in ("verificationHolds", "listingPolicyExclusions", "additionalObservedPolicyExclusions"):
            self.assertEqual(set(result[field][0]), {"id", "status", "reason"})
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertFalse(result["fullCompletion"])

    def test_unknown_coverage_and_verification_gaps_never_claim_completion(self):
        self.assertFalse(report(dataset())["fullCompletion"])
        complete = dataset(complete=True)
        self.assertTrue(report(complete)["fullCompletion"])
        gap = dataset([row(sourcesExpected=2, sourcesComplete=False)], complete=True)
        self.assertFalse(report(gap)["fullCompletion"])
        complete["summary.json"]["missingIds"] = ["999"]
        self.assertFalse(report(complete)["fullCompletion"])

    def test_failures_do_not_leak_error_titles_or_fake_counts(self):
        failed = row("999", status="failed", candidate=False, inspectionComplete=False, kCountVerified=False,
                     error="PRIVATE ERROR TITLE", title="PRIVATE ERROR TITLE")
        result = report(dataset(normalized=[row(), failed]))
        self.assertEqual(set(result["failedOrIncomplete"][0]), {"id", "status", "reason"})
        self.assertEqual(result["failedOrIncomplete"][0]["status"], "verification_failed")
        self.assertNotIn("PRIVATE ERROR TITLE", json.dumps(result))

    def test_csv_retains_rows_and_nested_media_with_null_empty_cells(self):
        result = report(dataset([row("100", title="=UNTRUSTED()"), row("200", kCountVerified=False)]))
        rows = list(csv.DictReader(io.StringIO(exporter.candidates_csv(result).decode("utf-8-sig"))))
        self.assertEqual([r["id"] for r in rows], ["100", "200"])
        self.assertEqual(rows[0]["title"], "'=UNTRUSTED()")
        self.assertEqual(rows[1]["kCount"], "")
        self.assertEqual(json.loads(rows[0]["media"]), result["candidates"][0]["media"])


class LowerBoundPublicExportTests(unittest.TestCase):
    def lower_bound(self, **changes):
        value = row(status="failed", kCount=None, commentCount=None, kCountVerified=False, commentsComplete=False,
                    commentsAllSelected=True, commentsExpected=2, thresholdQualified=True,
                    thresholdEvidence="observed_lower_bound", knownLiteralKMinimum=23,
                    nativeCountEvidenceTrusted=True, candidateVerificationHeld=True,
                    commentEvidenceObservedAt="2026-10-09T03:00:00Z", commentConflicts=[], invalidCommentCountIDs=[],
                    commentCounts=[{"id": "native-1", "date": "2026-10-08 12:30:00", "kCount": 23}],
                    sourcesComplete=False, sourcesExpanded=False, sources=None, sourcesExpected=None,
                    mediaComplete=False, media=None, inspectionComplete=False)
        value.update(changes)
        return value

    def test_proven_minimum_is_public_but_exact_totals_stay_null_and_verification_held(self):
        result = exporter.public_candidate(self.lower_bound(), {})
        self.assertTrue(result["thresholdQualified"])
        self.assertEqual(result["thresholdEvidence"], "observed_lower_bound")
        self.assertEqual(result["knownLiteralKMinimum"], 23)
        self.assertTrue(result["candidateVerificationHeld"])
        self.assertEqual(result["verificationStatus"], "verification_held")
        self.assertIn("native_comment_total_unverified", result["candidateVerificationHoldReasons"])
        self.assertFalse(result["kCountVerified"])
        self.assertFalse(result["commentDatePartitionVerified"])
        for name in exporter.COUNT_FIELDS:
            self.assertIsNone(result[name])
        self.assertNotIn("commentCounts", result)
        self.assertNotIn("observedKCount", result)
        self.assertNotIn("BODY SECRET", json.dumps(result))
        self.assertNotIn("COMMENT SECRET", json.dumps(result))

    def test_inconsistent_or_unproven_lower_bound_annotation_is_not_exported(self):
        patches = [
            {"knownLiteralKMinimum": 99}, {"knownLiteralKMinimum": True}, {"knownLiteralKMinimum": 10},
            {"thresholdEvidence": None}, {"nativeCountEvidenceTrusted": False},
            {"candidateVerificationHeld": False}, {"commentsAllSelected": False},
            {"commentEvidenceObservedAt": None}, {"commentConflicts": ["native-1"]},
            {"invalidCommentCountIDs": ["native-1"]}, {"commentCounts": []},
            {"commentCounts": [{"id": "native-1", "kCount": 23}, {"id": "native-1", "kCount": 24}]},
            {"commentCounts": [{"id": "native-1", "kCount": 23.0}]},
            {"status": "policy_excluded"},
        ]
        for patch in patches:
            with self.subTest(patch=patch):
                result = exporter.public_candidate(self.lower_bound(**patch), {})
                self.assertIsNone(result["knownLiteralKMinimum"])
                self.assertIsNone(result["thresholdQualified"])
                self.assertIsNone(result["kCount"])
                self.assertFalse(result["kCountVerified"])

    def test_duplicate_native_rows_cannot_inflate_exported_minimum(self):
        result = exporter.public_candidate(self.lower_bound(knownLiteralKMinimum=46, commentCounts=[{"id": "native-1", "kCount": 23}, {"id": "native-1", "kCount": 23}]), {})
        self.assertIsNone(result["knownLiteralKMinimum"])
        self.assertIsNone(result["thresholdQualified"])

    def test_lower_bound_candidate_is_retained_and_cannot_establish_full_completion(self):
        result = report(dataset([self.lower_bound()], complete=True))
        self.assertEqual(result["counts"]["retainedCandidates"], 1)
        self.assertEqual(result["counts"]["lowerBoundQualifiedCandidates"], 1)
        self.assertEqual(result["counts"]["allThresholdQualifiers"], 1)
        self.assertEqual(result["counts"]["metadataCompleteCandidates"], 0)
        self.assertFalse(result["fullCompletion"])
        self.assertEqual(result["failedOrIncomplete"][0]["status"], "verification_held")
        self.assertEqual(result["candidates"][0]["knownLiteralKMinimum"], 23)

    def test_csv_preserves_minimum_and_evidence_with_empty_exact_count_cells(self):
        result = report(dataset([self.lower_bound()]))
        rows = list(csv.DictReader(io.StringIO(exporter.candidates_csv(result).decode("utf-8-sig"))))
        self.assertEqual(rows[0]["knownLiteralKMinimum"], "23")
        self.assertEqual(rows[0]["thresholdEvidence"], "observed_lower_bound")
        self.assertEqual(rows[0]["verificationStatus"], "verification_held")
        self.assertEqual(rows[0]["kCount"], "")
        self.assertEqual(rows[0]["commentCount"], "")

    def test_exact_total_keeps_distinct_evidence_without_lower_bound_hold(self):
        result = exporter.public_candidate(row(), {})
        self.assertEqual(result["thresholdEvidence"], "exact_native_total")
        self.assertEqual(result["knownLiteralKMinimum"], 11)
        self.assertFalse(result["candidateVerificationHeld"])



class TemporalAndProvenanceExportTests(unittest.TestCase):
    def temporal(self):
        return row(kCount=12, inWindow=None, listedAt="2026-10-09T02:51:35Z", latestListedAt="2026-10-09T02:51:35Z", inspectionComplete=False, candidateVerificationHeld=True, temporalMembershipUncertain=True, temporalVerificationHeld=True, temporalHoldReason=exporter.TEMPORAL_HOLD_REASON, initialListingEvidence={"id": "100", "phase": "initial", "page": 12, "observedAt": "2026-10-09T02:07:33.954Z", "age": "22시간전", "url": "https://aagag.com/issue/?idx=100", "title": "PRIVATE ORIGINAL LISTING TITLE"}, originalExactListedAt=None)

    def test_temporal_candidate_retains_exact_count_with_uncertain_membership_and_no_old_timestamp(self):
        result = exporter.public_candidate(self.temporal(), {})
        self.assertEqual(result["kCount"], 12)
        self.assertTrue(result["thresholdQualified"])
        self.assertIsNone(result["inFixedListingWindow"])
        self.assertTrue(result["temporalMembershipUncertain"])
        self.assertEqual(result["listedAt"], "2026-10-09T02:51:35Z")
        self.assertEqual(result["latestListedAt"], "2026-10-09T02:51:35Z")
        self.assertIsNone(result["originalExactListedAt"])
        self.assertEqual(result["initialListingEvidence"]["age"], "22시간전")
        self.assertNotIn("title", result["initialListingEvidence"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(result["verificationStatus"], "verification_held")
        self.assertTrue(result["candidateVerificationHeld"])
        self.assertIn(exporter.TEMPORAL_HOLD_REASON, result["candidateVerificationHoldReasons"])
        whole = report(dataset([self.temporal()], complete=True))
        self.assertFalse(whole["fullCompletion"])
        self.assertEqual(whole["counts"]["temporallyUncertainCandidates"], 1)

    def test_supplemental_source_and_media_timestamps_do_not_overwrite_original_comment_time(self):
        original="2026-10-09T03:18:17.841Z";source="2026-10-09T03:45:00Z";media="2026-10-09T03:46:00Z"
        result=exporter.public_candidate(row(commentEvidenceObservedAt=original,sourceListObservedAt=source,mediaObservedAt=media),{})
        self.assertEqual(result["commentEvidenceObservedAt"],original)
        self.assertEqual(result["sourceListObservedAt"],source)
        self.assertEqual(result["mediaObservedAt"],media)
        self.assertEqual(result["observedAt"],"2026-10-09T03:00:00Z")

    def test_field_timestamp_fallback_requires_actual_field_capture(self):
        result=exporter.public_candidate(row(sourcesExpanded=False,sources=None,media=None),{})
        self.assertIsNone(result["sourceListObservedAt"])
        self.assertIsNone(result["mediaObservedAt"])
        missing=exporter.public_candidate(row(sourceListObservedAt=None,mediaObservedAt="invalid"),{})
        self.assertIsNone(missing["sourceListObservedAt"])
        self.assertIsNone(missing["mediaObservedAt"])



class PublicExportFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run, self.comparison, self.output = (self.base / name for name in ("fixture-run", "comparison", "deliverables"))
        self.run.mkdir()
        self.comparison.mkdir()
        self.data = dataset()
        self.save()

    def save(self):
        for name, value in self.data.items():
            (self.run / name).write_text(json.dumps(value), encoding="utf-8")

    def comparison_fixture(self):
        _, hashes = exporter.read_checkpoint(self.run)
        rows = [{"id": "100", "alreadyPublishedIdentityMatch": True, "publishedCommunityEditionMatch": True,
                 "publicationMatches": [{"id": "aagag-100", "editionId": "old", "identityMatch": True,
                                         "matches": {"title": ["PRIVATE COMPARISON TITLE"]}}]}]
        summary = {"inputs": hashes, "old0830KSTEdition": {"editionId": "old", "publishedStoryCount": 5,
                    "publishedIds": ["aagag-100"], "cutoffAt": "2026-10-09T08:30:00+09:00"}}
        (self.comparison / "comparison-summary.json").write_text(json.dumps(summary))
        (self.comparison / "candidate-comparison.json").write_text(json.dumps(rows))
        return hashes

    def test_current_comparison_distinguishes_edition_size_from_overlaps(self):
        hashes = self.comparison_fixture()
        summary, rows = exporter.read_comparison(self.comparison, hashes, self.data["candidates.json"])
        self.assertEqual(summary["status"], "current_captured_history")
        self.assertEqual(summary["old0830KSTEdition"]["publishedStoryCount"], 5)
        self.assertEqual(summary["old0830KSTEdition"]["candidateIdentityOverlapCount"], 1)
        result = exporter.build_report(self.data, hashes, summary, rows, "fixture")
        self.assertNotIn("PRIVATE COMPARISON TITLE", json.dumps(result))
        self.assertEqual(len(result["candidates"]), 1)

    def test_stale_comparison_withholds_overlap_counts(self):
        hashes = self.comparison_fixture()
        hashes["summary.json"]["sha256"] = "changed"
        summary, rows = exporter.read_comparison(self.comparison, hashes, self.data["candidates.json"])
        self.assertEqual(summary["status"], "stale_or_inconsistent")
        self.assertIsNone(summary["candidateIdentityOverlapCount"])
        self.assertEqual(rows, {})

    def test_inconsistent_checkpoint_rejected(self):
        self.data["summary.json"]["candidates"] = 99
        self.save()
        with mock.patch.object(exporter.time, "sleep"), self.assertRaises(RuntimeError):
            exporter.read_checkpoint(self.run)

    def test_candidate_matching_hold_is_rejected_without_leaking(self):
        self.data["verification-holds.json"] = [{"id": "100", "title": "PRIVATE"}]
        self.data["summary.json"].update(verificationHeldIDs=["100"], verificationHeldCount=1)
        self.save()
        with mock.patch.object(exporter.time, "sleep"), self.assertRaises(RuntimeError):
            exporter.read_checkpoint(self.run)

    def test_package_exact_allowlist_and_source_immutability(self):
        self.comparison_fixture()
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        result = exporter.export(self.run, self.output, self.comparison)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        self.assertEqual(before, after)
        self.assertEqual(result["counts"]["retainedCandidates"], 1)
        with zipfile.ZipFile(self.output / "dailyk-cloud-macro.zip") as package:
            self.assertEqual(set(package.namelist()), set(exporter.PACKAGE_FILES) |
                             {"source-manifest.json", "deliverables/public-run-report.json", "deliverables/candidates.csv"})
            for name in package.namelist():
                self.assertFalse(name.startswith("runs/"))
                self.assertFalse(name.endswith(".snapshot.json"))
                self.assertNotIn("__pycache__", name)
            self.assertEqual(package.read("deliverables/public-run-report.json"), (self.output / "public-run-report.json").read_bytes())
        self.assertLess((self.output / "dailyk-cloud-macro.zip").stat().st_size, 500_000)

    def test_versioned_source_manifest_matches_every_packaged_source_byte(self):
        result=exporter.export(self.run,self.output,self.comparison)
        manifest=json.loads((self.output/"source-manifest.json").read_text())
        self.assertEqual(manifest["version"],"0.3.0")
        self.assertEqual(manifest["hashAlgorithm"],"sha256")
        self.assertEqual({entry["path"] for entry in manifest["files"]},set(exporter.PACKAGE_FILES))
        self.assertEqual(result["sourcePackage"]["sourceTreeSha256"],manifest["sourceTreeSha256"])
        with zipfile.ZipFile(self.output/"dailyk-cloud-macro.zip") as archive:
            self.assertEqual(archive.read("VERSION").decode().strip(),"0.3.0")
            self.assertEqual(archive.read("source-manifest.json"),(self.output/"source-manifest.json").read_bytes())
            for entry in manifest["files"]:
                payload=archive.read(entry["path"])
                self.assertEqual(len(payload),entry["byteSize"])
                self.assertEqual(hashlib.sha256(payload).hexdigest(),entry["sha256"])
                self.assertFalse(entry["path"].startswith("runs/"))
                self.assertFalse(entry["path"].endswith((".png",".jpg",".mp4",".snapshot.json")))
        expected=hashlib.sha256(json.dumps(manifest["files"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        self.assertEqual(manifest["sourceTreeSha256"],expected)

    def test_source_manifest_is_stable_when_only_export_time_changes(self):
        _,first=exporter.source_snapshot(ROOT)
        _,second=exporter.source_snapshot(ROOT)
        self.assertEqual(first,second)

    def test_source_change_during_packaging_prevents_artifact_commit(self):
        copied=self.base/"source-copy"
        for name in exporter.PACKAGE_FILES:
            destination=copied/name;destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes((ROOT/name).read_bytes())
        original=zipfile.ZipFile.writestr
        def mutate_after_capture(archive,name,data,*args,**kwargs):
            result=original(archive,name,data,*args,**kwargs)
            if name=="source-manifest.json":(copied/"VERSION").write_text("0.1.1\n")
            return result
        with mock.patch.object(zipfile.ZipFile,"writestr",new=mutate_after_capture),self.assertRaisesRegex(RuntimeError,"Source changed"):
            exporter.export(self.run,self.output,self.comparison,root=copied)
        self.assertFalse((self.output/"dailyk-cloud-macro.zip").exists())
        self.assertFalse((self.output/"source-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
