"""End-to-end checkpoint fixtures; never reads or writes the live run directory."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from test_core import core, record

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("collector_checkpoint_under_test", Path(__file__).resolve().parents[1] / "src" / "checkpoint.py")
checkpoint = importlib.util.module_from_spec(spec)
with mock.patch.dict(sys.modules, {"core": core}):
    spec.loader.exec_module(checkpoint)


class CheckpointIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.run_patch = mock.patch.object(checkpoint, "RUN", self.run)
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)
        checkpoint.initialize_run(checkpoint.DEFAULT_END.isoformat(), self.run)
        for phase in ("initial", "resweep"):
            self.write(f"listings/{phase}-01.json", {"phase": phase, "page": 1, "items": [{"id": "100", "url": "https://example.test/?idx=100"}]})
            self.write(f"listings/{phase}-02.json", {"phase": phase, "page": 2, "items": [{"id": "200", "url": "https://example.test/?idx=200"}]})
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00"))
        self.write("posts/200.json", record(id="200", listedAtRaw="2026-10-08 10:00:00"))

    def write(self, name, data):
        (self.run / name).write_text(json.dumps(data, ensure_ascii=False))

    def read(self, name):
        return json.loads((self.run / name).read_text())

    def test_full_checkpoint_rebuilds_from_raw_and_resumes_idempotently(self):
        summary, pending = checkpoint.update()
        self.assertTrue(summary["complete"])
        self.assertEqual(pending, [])
        self.assertEqual(summary["candidateIDs"], ["100"])
        normalized = self.read("normalized-posts.json")
        qualifiers = self.read("all-threshold-qualifiers.json")
        resumed, resumed_pending = checkpoint.update()
        self.assertTrue(resumed["complete"])
        self.assertEqual(resumed_pending, [])
        self.assertEqual(self.read("normalized-posts.json"), normalized)
        self.assertEqual(self.read("all-threshold-qualifiers.json"), qualifiers)

    def test_source_gap_preserves_native_and_listing_coverage_but_not_overall(self):
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00", sourcesExpected=2))
        summary, _ = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertTrue(summary["nativeCommentCoverageComplete"])
        self.assertEqual(summary["nativeCommentIncompleteIDs"], [])
        self.assertFalse(summary["complete"])

    def test_media_gap_preserves_native_coverage_but_not_overall(self):
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00", media=[{"type": "image", "url": "https://example.test/x.jpg", "complete": False, "width": 0, "height": 0}]))
        summary, _ = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertTrue(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])

    def test_native_count_gap_cannot_claim_complete_native_coverage(self):
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00", commentsExpected=2))
        summary, _ = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertEqual(summary["nativeCommentIncompleteIDs"], ["100"])
        self.assertFalse(summary["complete"])

    def test_missing_interior_post_preserves_listing_only_coverage(self):
        (self.run / "posts/100.json").unlink()
        summary, _ = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])

    def test_native_coverage_requires_exact_listing_dates(self):
        self.write("posts/100.json", record(id="100", listedAtRaw=None))
        summary, _ = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertEqual(summary["nativeCommentIncompleteIDs"], ["100"])

    def test_native_coverage_requires_both_listing_passes(self):
        for path in (self.run / "listings").glob("resweep-*.json"):
            path.unlink()
        summary, _ = checkpoint.update()
        self.assertFalse(summary["listingCoverageComplete"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])

    def test_missing_raw_post_is_pending_and_coverage_is_false(self):
        (self.run / "posts/100.json").unlink()
        summary, pending = checkpoint.update()
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["missingIds"], ["100"])
        self.assertEqual([item["id"] for item in pending], ["100"])

    def test_missing_exact_boundary_detail_prevents_completion(self):
        self.write("posts/200.json", record(id="200", listedAtRaw=None))
        summary, _ = checkpoint.update()
        self.assertFalse(summary["complete"])
        self.assertFalse(summary["passes"]["initial"])
        self.assertFalse(summary["passes"]["resweep"])

    def test_all_rows_on_boundary_page_must_have_exact_old_dates(self):
        for phase in ("initial", "resweep"):
            self.write(f"listings/{phase}-02.json", {"phase": phase, "page": 2, "items": [{"id": "200"}, {"id": "201"}]})
        self.write("posts/201.json", record(id="201", listedAtRaw="2026-10-09 09:00:00"))
        summary, _ = checkpoint.update()
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["passes"], {"initial": False, "resweep": False})

    def test_safety_held_threshold_qualifiers_are_retained(self):
        self.write("posts/100.json", record(id="100", title="[ㅇㅎ] 원문", listedAtRaw="2026-10-09 10:00:00"))
        summary, _ = checkpoint.update()
        self.assertEqual(summary["qualifiers"], 1)
        self.assertEqual(summary["excludedQualifiers"], 1)
        self.assertEqual(summary["candidates"], 0)
        self.assertEqual([p["canonicalId"] for p in self.read("all-threshold-qualifiers.json")], ["100"])

    def test_failed_browser_record_without_id_does_not_break_checkpoint(self):
        self.write("posts/100.json", {
            "requestedId": "100", "requestedUrl": "https://example.test/?idx=100",
            "status": "failed", "error": "transient", "attempts": [{"attempt": 1}, {"attempt": 2}],
        })
        summary, _ = checkpoint.update()
        self.assertFalse(summary["complete"])
        self.assertIn("100", summary["incompleteIDs"])
        self.assertTrue((self.run / "summary.json").exists())

    def test_incomplete_record_is_visible_but_not_repeated_in_initial_queue(self):
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00", commentsExpected=2))
        summary, pending = checkpoint.update()
        self.assertFalse(summary["complete"])
        self.assertIn("100", summary["incompleteIDs"])
        self.assertNotIn("100", [core.post_id(item["id"]) for item in pending])

    def test_pending_post_suffixes_are_deduplicated(self):
        (self.run / "posts/100.json").unlink()
        for phase in ("initial", "resweep"):
            self.write(f"listings/{phase}-01.json", {"phase": phase, "page": 1, "items": [{"id": "100"}, {"id": "100_1"}, {"id": "100-2"}]})
        _, pending = checkpoint.update()
        self.assertEqual([item["id"] for item in pending], ["100"])

    def test_canonical_duplicate_raw_post_files_produce_one_qualifier(self):
        self.write("posts/100_1.json", record(id="100_1", listedAtRaw="2026-10-09 10:00:00"))
        summary, _ = checkpoint.update()
        self.assertEqual(summary["qualifiers"], 1)
        self.assertEqual([p["canonicalId"] for p in self.read("all-threshold-qualifiers.json")], ["100"])

    def test_canonical_selection_uses_newest_comments_complete_observation(self):
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00", observedAt="2026-10-09T02:00:00Z"))
        self.write("posts/100_1.json", record(id="100_1", listedAtRaw="2026-10-09 10:00:00", observedAt="2026-10-09T02:01:00Z", commentCounts=[{"id": "native-1", "kCount": 15}]))
        _, posts = checkpoint.load()
        selected = next(p for p in posts if p["canonicalId"] == "100")
        self.assertEqual(selected["id"], "100_1")
        self.assertEqual(selected["kCount"], 15)
        self.assertTrue((self.run / "posts/100.json").exists())
        self.assertTrue((self.run / "posts/100_1.json").exists())

    def test_newer_incomplete_alias_does_not_replace_complete_observation(self):
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00", observedAt="2026-10-09T02:00:00Z"))
        self.write("posts/100_1.json", record(id="100_1", listedAtRaw="2026-10-09 10:00:00", observedAt="2026-10-09T02:01:00Z", commentsExpected=2))
        _, posts = checkpoint.load()
        selected = next(p for p in posts if p["canonicalId"] == "100")
        self.assertEqual(selected["id"], "100")
        self.assertTrue(selected["inspectionComplete"])

    def test_without_complete_alias_selection_uses_newest_observation(self):
        self.write("posts/100.json", record(id="100", observedAt="2026-10-09T02:00:00Z", commentsExpected=2))
        self.write("posts/100_1.json", record(id="100_1", observedAt="2026-10-09T02:01:00Z", commentsExpected=3))
        _, posts = checkpoint.load()
        selected = next(p for p in posts if p["canonicalId"] == "100")
        self.assertEqual(selected["id"], "100_1")
        self.assertFalse(selected["inspectionComplete"])

    def test_newer_threshold_crossing_is_selected_despite_incomplete_sources(self):
        self.write("posts/100.json", record(id="100", listedAtRaw="2026-10-09 10:00:00", observedAt="2026-10-09T02:00:00Z", commentCounts=[{"id": "native-1", "kCount": 10}]))
        self.write("posts/100_1.json", record(id="100_1", listedAtRaw="2026-10-09 10:00:00", observedAt="2026-10-09T02:01:00Z", sourcesExpected=2))
        summary, _ = checkpoint.update()
        selected = next(p for p in self.read("normalized-posts.json") if p["canonicalId"] == "100")
        self.assertEqual(selected["id"], "100_1")
        self.assertEqual(selected["kCount"], 11)
        self.assertTrue(selected["kCountVerified"])
        self.assertFalse(selected["inspectionComplete"])
        self.assertEqual(summary["qualifiers"], 1)
        self.assertFalse(summary["complete"])
        self.assertTrue(selected["observationSelection"]["selectedIsLatestKnownAttempt"])

    def test_newer_incomplete_alias_is_explicit_in_selection_metadata(self):
        self.write("posts/100.json", record(id="100", observedAt="2026-10-09T02:00:00Z"))
        self.write("posts/100_1.json", record(id="100_1", observedAt="2026-10-09T02:01:00Z", commentsExpected=2))
        _, posts = checkpoint.load()
        selected = next(p for p in posts if p["canonicalId"] == "100")
        evidence = selected["observationSelection"]
        self.assertEqual(selected["id"], "100")
        self.assertEqual(evidence["strategy"], "newest_comments_complete_else_newest")
        self.assertEqual(evidence["rawAliasCount"], 2)
        self.assertFalse(evidence["selectedIsLatestKnownAttempt"])
        self.assertTrue(evidence["allAliasTimestampsKnown"])
        self.assertEqual(evidence["latestKnownAttempt"]["rawFile"], "100_1.json")
        self.assertEqual([a["rawFile"] for a in evidence["newerIncompleteAliases"]], ["100_1.json"])
        self.assertFalse(evidence["newerIncompleteAliases"][0]["commentsComplete"])

    def test_failed_alias_attempt_timestamp_is_retained_for_freshness(self):
        self.write("posts/100.json", record(id="100", observedAt="2026-10-09T02:00:00Z"))
        self.write("posts/100_1.json", {"requestedId": "100_1", "status": "failed", "attempts": [{"attempt": 1, "at": "2026-10-09T02:02:00Z"}]})
        _, posts = checkpoint.load()
        selected = next(p for p in posts if p["canonicalId"] == "100")
        evidence = selected["observationSelection"]
        self.assertEqual(selected["id"], "100")
        self.assertFalse(evidence["selectedIsLatestKnownAttempt"])
        self.assertEqual(evidence["latestKnownAttempt"]["evidenceAt"], "2026-10-09T02:02:00+00:00")
        self.assertEqual(evidence["newerIncompleteAliases"][0]["status"], "failed")

    def test_unknown_alias_timestamp_is_disclosed(self):
        self.write("posts/100_1.json", record(id="100_1", commentsExpected=2))
        _, posts = checkpoint.load()
        selected = next(p for p in posts if p["canonicalId"] == "100")
        self.assertFalse(selected["observationSelection"]["allAliasTimestampsKnown"])
        self.assertIsNone(selected["observationSelection"]["selectedIsLatestKnownAttempt"])

    def add_marked_listing(self, identity="300_1", title="펌) ㅇㅎ) 크킄 어리석은 인간드라", page_number=1):
        for phase in ("initial", "resweep"):
            name = f"listings/{phase}-{page_number:02d}.json"
            page = self.read(name)
            page["observedAt"] = "2026-10-09T02:00:00Z"
            page["items"].append({"id": identity, "title": title, "url": f"https://example.test/?idx={identity}"})
            self.write(name, page)

    def test_all_existing_title_safety_rules_preexclude_listing_visits(self):
        samples = [("차에서 섹스하다…", "sexual_title", "섹스"), ("참수 영상", "graphic_or_death_title", "참수"), ("불륜 이야기", "private_allegation_title", "불륜")]
        for index, (title, code, matched) in enumerate(samples):
            self.add_marked_listing(identity=str(400 + index), title=title)
        summary, pending = checkpoint.update()
        self.assertEqual(summary["policyExcludedCount"], 3)
        self.assertFalse(any(core.post_id(item["id"]) in {"400", "401", "402"} for item in pending))
        exclusions = {item["canonicalId"]: item for item in self.read("listing-exclusions.json")}
        for index, (title, code, matched) in enumerate(samples):
            excluded = exclusions[str(400 + index)]
            self.assertEqual(excluded["title"], title)
            self.assertEqual(excluded["reason"], "known_listing_title_safety_exclusion")
            self.assertIn({"code": code, "matchedText": matched}, excluded["matchedRules"])
            self.assertIsNone(excluded["commentCount"])
            self.assertIsNone(excluded["kCount"])
            self.assertIsNone(excluded["listedAt"])
        self.assertTrue(summary["complete"])

    def test_marked_listing_is_excluded_before_visiting_and_not_pending(self):
        self.add_marked_listing()
        summary, pending = checkpoint.update()
        self.assertNotIn("300", [core.post_id(item["id"]) for item in pending])
        self.assertEqual(summary["policyExcludedCount"], 1)
        self.assertEqual(summary["policyExcludedIDs"], ["300"])
        self.assertNotIn("300", summary["missingIds"])
        self.assertEqual(summary["listedUnique"], 3)
        self.assertEqual(summary["eligibleListedUnique"], 2)
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertTrue(summary["nativeCommentCoverageComplete"])
        self.assertTrue(summary["complete"])
        self.assertFalse((self.run / "posts/300_1.json").exists())

    def test_listing_exclusion_has_exact_evidence_and_no_invented_count_or_date(self):
        title = "펌) ㅇㅎ) 크킄 어리석은 인간드라"
        self.add_marked_listing(title=title)
        checkpoint.update()
        exclusions = self.read("listing-exclusions.json")
        self.assertEqual(len(exclusions), 1)
        excluded = exclusions[0]
        self.assertEqual(excluded["title"], title)
        self.assertEqual(excluded["url"], "https://example.test/?idx=300_1")
        self.assertEqual(excluded["id"], "300_1")
        self.assertEqual(excluded["sourceListingPage"], 1)
        self.assertEqual(excluded["sourceListingObservedAt"], "2026-10-09T02:00:00Z")
        self.assertEqual(excluded["marker"], "ㅇㅎ")
        self.assertEqual(excluded["reason"], "known_listing_nsfw_marker")
        self.assertIsNone(excluded["commentCount"])
        self.assertIsNone(excluded["kCount"])
        self.assertIsNone(excluded["thresholdQualified"])
        self.assertIsNone(excluded["listedAt"])
        self.assertFalse(excluded["dateVerified"])
        self.assertFalse(excluded["candidate"])
        self.assertEqual(len(excluded["listingEvidence"]), 2)
        self.assertNotIn("300", [p["canonicalId"] for p in self.read("all-threshold-qualifiers.json")])

    def test_marked_boundary_row_needs_no_visit_if_eligible_older_witness_exists(self):
        self.add_marked_listing(page_number=2)
        summary, _ = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertTrue(summary["complete"])
        self.assertFalse((self.run / "posts/300_1.json").exists())

    def test_excluded_only_boundary_page_does_not_invent_an_older_witness(self):
        for phase in ("initial", "resweep"):
            self.write(f"listings/{phase}-02.json", {"phase": phase, "page": 2, "items": [{"id": "300", "title": "[ㅎㅂ] 제목", "url": "https://example.test/?idx=300"}]})
        summary, _ = checkpoint.update()
        self.assertFalse(summary["listingCoverageComplete"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])

    def test_policy_exclusion_does_not_hide_missing_eligible_rows(self):
        self.add_marked_listing()
        (self.run / "posts/100.json").unlink()
        summary, pending = checkpoint.update()
        self.assertEqual(summary["missingIds"], ["100"])
        self.assertEqual([item["id"] for item in pending], ["100"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])

    def test_marker_on_one_alias_excludes_unmarked_canonical_alias_too(self):
        self.add_marked_listing(identity="300_1")
        page = self.read("listings/initial-01.json")
        page["items"].append({"id": "300", "title": "일반 제목", "url": "https://example.test/?idx=300"})
        self.write("listings/initial-01.json", page)
        summary, pending = checkpoint.update()
        self.assertEqual(summary["policyExcludedCount"], 1)
        self.assertNotIn("300", [core.post_id(item["id"]) for item in pending])

    def test_prior_failed_excluded_record_is_not_a_retry_or_coverage_failure(self):
        self.add_marked_listing()
        self.write("posts/300_1.json", {"requestedId": "300_1", "status": "failed", "attempts": []})
        summary, _ = checkpoint.update()
        self.assertTrue(summary["complete"])
        self.assertNotIn("300_1", summary["incompleteIDs"])
        self.assertNotIn("300", summary["nativeCommentIncompleteIDs"])
        self.assertNotIn("300", summary["failedOrIncomplete"])

    def test_previously_observed_marked_record_is_not_exported_as_a_qualifier(self):
        self.add_marked_listing()
        self.write("posts/300_1.json", record(id="300_1", listedAtRaw="2026-10-09 10:00:00"))
        summary, _ = checkpoint.update()
        self.assertEqual(summary["qualifiers"], 1)
        self.assertNotIn("300", [p["canonicalId"] for p in self.read("all-threshold-qualifiers.json")])
        self.assertTrue((self.run / "posts/300_1.json").exists())

    def set_hold(self, identity="300_1", title="모호한 제목", reason="verification blocked; meaning unresolved"):
        hold = {"id": identity, "title": title, "url": f"https://example.test/?idx={identity}", "reason": reason, "heldAt": "2026-10-09T02:50:00Z"}
        self.write("verification-holds.json", [hold])
        return hold

    def test_manual_hold_skips_pending_but_remains_missing_and_unresolved(self):
        self.add_marked_listing(identity="300", title="모호한 제목")
        hold = self.set_hold()
        summary, pending = checkpoint.update()
        self.assertNotIn("300", [core.post_id(item["id"]) for item in pending])
        self.assertEqual(summary["verificationHeldIDs"], ["300"])
        self.assertEqual(summary["verificationHeldCount"], 1)
        self.assertEqual(summary["verificationHolds"][0]["reason"], hold["reason"])
        self.assertEqual(summary["verificationHolds"][0]["title"], hold["title"])
        self.assertEqual(summary["missingIds"], ["300"])
        self.assertEqual(summary["policyExcludedCount"], 0)
        self.assertEqual(self.read("listing-exclusions.json"), [])
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])
        self.assertFalse((self.run / "posts/300.json").exists())
        self.assertFalse((self.run / "posts/300_1.json").exists())

    def test_hold_does_not_claim_sexual_classification_or_invent_counts(self):
        self.add_marked_listing(identity="300", title="모호한 제목")
        hold = self.set_hold()
        summary, _ = checkpoint.update()
        evidence = summary["verificationHolds"][0]
        self.assertEqual(evidence, {**hold, "canonicalId": "300"})
        self.assertNotIn("matchedRules", evidence)
        self.assertNotIn("kCount", evidence)
        self.assertNotIn("commentCount", evidence)
        self.assertEqual(self.read("verification-holds.json"), [hold])

    def test_hold_canonicalizes_aliases_and_deduplicates_held_id_count(self):
        self.add_marked_listing(identity="300", title="모호한 제목")
        first = self.set_hold("300")
        second = {**first, "id": "300_1", "reason": "additional unresolved review"}
        self.write("verification-holds.json", [first, second])
        summary, pending = checkpoint.update()
        self.assertEqual(summary["verificationHeldCount"], 1)
        self.assertEqual(summary["verificationHeldIDs"], ["300"])
        self.assertEqual(len(summary["verificationHolds"]), 2)
        self.assertNotIn("300", [core.post_id(item["id"]) for item in pending])

    def test_explicit_hold_takes_precedence_over_automatic_policy_resolution(self):
        self.add_marked_listing()
        self.set_hold(title="펌) ㅇㅎ) 크킄 어리석은 인간드라")
        summary, pending = checkpoint.update()
        self.assertEqual(summary["policyExcludedCount"], 0)
        self.assertEqual(summary["verificationHeldIDs"], ["300"])
        self.assertEqual(summary["missingIds"], ["300"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])
        self.assertEqual(self.read("listing-exclusions.json"), [])
        self.assertEqual(pending, [])

    def test_hold_on_observed_post_still_blocks_completion_and_candidate_export(self):
        self.set_hold("100", title="일반 제목")
        summary, _ = checkpoint.update()
        self.assertEqual(summary["missingIds"], [])
        self.assertEqual(summary["verificationHeldIDs"], ["100"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])
        self.assertNotIn("100", summary["candidateIDs"])
        self.assertNotIn("100", [p["canonicalId"] for p in self.read("all-threshold-qualifiers.json")])
        self.assertTrue((self.run / "posts/100.json").exists())

    def test_held_failed_post_is_not_in_retry_facing_incomplete_ids(self):
        self.set_hold("100", title="일반 제목")
        self.write("posts/100.json", {"requestedId": "100", "status": "failed"})
        summary, pending = checkpoint.update()
        self.assertNotIn("100", summary["incompleteIDs"])
        self.assertIn("100", summary["verificationHeldIDs"])
        self.assertIn("100", summary["failedOrIncomplete"])
        self.assertFalse(summary["complete"])
        self.assertNotIn("100", [core.post_id(item["id"]) for item in pending])

    def test_held_boundary_row_is_reported_outside_eligible_boundary_proof(self):
        self.add_marked_listing(identity="300", title="모호한 제목", page_number=2)
        self.set_hold()
        summary, _ = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertTrue(summary["boundaryHeldDatesUnverified"])
        self.assertEqual(summary["boundaryHeldIDs"], ["300"])
        self.assertEqual(summary["boundaryHeldIDsByPass"], {"initial": {"page": 2, "heldIDs": ["300"]}, "resweep": {"page": 2, "heldIDs": ["300"]}})
        self.assertEqual(summary["missingIds"], ["300"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])
        self.assertFalse((self.run / "posts/300.json").exists())

    def test_held_only_boundary_page_still_needs_an_eligible_older_witness(self):
        for phase in ("initial", "resweep"):
            self.write(f"listings/{phase}-02.json", {"phase": phase, "page": 2, "items": [{"id": "300", "title": "모호한 제목", "url": "https://example.test/?idx=300"}]})
        self.set_hold()
        summary, _ = checkpoint.update()
        self.assertTrue(summary["boundaryHeldDatesUnverified"])
        self.assertEqual(summary["boundaryHeldIDs"], ["300"])
        self.assertFalse(summary["listingCoverageComplete"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])

    def test_held_boundary_row_does_not_relax_dates_for_other_eligible_rows(self):
        self.add_marked_listing(identity="300", title="모호한 제목", page_number=2)
        self.set_hold()
        for listed_at in (None, "2026-10-09 10:00:00"):
            with self.subTest(listed_at=listed_at):
                self.write("posts/200.json", record(id="200", listedAtRaw=listed_at))
                summary, _ = checkpoint.update()
                self.assertTrue(summary["boundaryHeldDatesUnverified"])
                self.assertFalse(summary["listingCoverageComplete"])
                self.assertFalse(summary["nativeCommentCoverageComplete"])
                self.assertFalse(summary["complete"])

    def test_cleared_hold_file_restores_unobserved_row_to_pending(self):
        self.add_marked_listing(identity="300", title="모호한 제목")
        self.set_hold()
        checkpoint.update()
        self.write("verification-holds.json", [])
        summary, pending = checkpoint.update()
        self.assertEqual(summary["verificationHeldIDs"], [])
        self.assertEqual([item["id"] for item in pending], ["300"])
        self.assertEqual(summary["missingIds"], ["300"])

    def test_malformed_hold_file_is_not_silently_ignored(self):
        for invalid in ({"id": "300"}, [{"id": "300"}], [None]):
            with self.subTest(invalid=invalid):
                self.write("verification-holds.json", invalid)
                with self.assertRaisesRegex(ValueError, "verification-holds.json"):
                    checkpoint.update()

    def test_partial_lower_bound_qualifier_is_retained_without_complete_coverage(self):
        self.write("posts/100.json", record(id="100", status="failed", listedAtRaw="2026-10-09 10:00:00", commentsExpected=2, commentEvidenceObservedAt="2026-10-09T02:00:00Z", commentCounts=[{"id": "native-1", "kCount": 23}], sources=[], sourcesExpanded=False, sourcesExpected=None, media=[]))
        summary, _ = checkpoint.update()
        self.assertEqual(summary["qualifiers"], 1)
        self.assertEqual(summary["candidateIDs"], ["100"])
        candidate = self.read("candidates.json")[0]
        self.assertTrue(candidate["candidateVerificationHeld"])
        self.assertEqual(candidate["knownLiteralKMinimum"], 23)
        self.assertIsNone(candidate["kCount"])
        self.assertIsNone(candidate["commentCount"])
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])

    def test_outside_header_only_row_resolves_coverage_without_native_count_claim(self):
        self.write("posts/200.json", {"status": "outside_window", "id": "200", "url": "https://aagag.com/issue/?idx=200", "title": "관찰된 옛 제목", "listedAtRaw": "2026-10-08 10:00:00", "observedAt": "2026-10-09T02:30:00Z"})
        summary, pending = checkpoint.update()
        self.assertTrue(summary["listingCoverageComplete"])
        self.assertTrue(summary["nativeCommentCoverageComplete"])
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["outsideWindowHeaderVerified"], 1)
        self.assertEqual(summary["nativeCommentIncompleteIDs"], [])
        self.assertEqual(pending, [])
        outside = next(p for p in self.read("normalized-posts.json") if p["id"] == "200")
        self.assertIsNone(outside["commentCount"])
        self.assertIsNone(outside["kCount"])
        self.assertFalse(outside["kCountVerified"])
        self.assertIsNone(outside["thresholdQualified"])

    def test_inside_header_only_row_stays_incomplete(self):
        self.write("posts/100.json", {"status": "outside_window", "id": "100", "url": "https://aagag.com/issue/?idx=100", "title": "관찰된 제목", "listedAtRaw": "2026-10-09 10:00:00", "observedAt": "2026-10-09T02:30:00Z"})
        summary, _ = checkpoint.update()
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])
        self.assertIn("100", summary["nativeCommentIncompleteIDs"])

    def set_temporal_hold(self):
        page = self.read("listings/initial-01.json")
        page["observedAt"] = "2026-10-09T02:00:00Z"
        page["items"][0].update({"age": "22시간전", "url": "https://aagag.com/issue/?idx=100"})
        self.write("listings/initial-01.json", page)
        hold = {"id": "100", "url": "https://aagag.com/issue/?idx=100", "reason": checkpoint.TEMPORAL_HOLD_REASON, "heldAt": "2026-10-09T03:00:00Z", "initialListingEvidence": {"page": 1, "observedAt": page["observedAt"], "age": "22시간전", "url": page["items"][0]["url"]}, "originalExactListedAt": None, "currentVerifiedKCount": 999}
        self.write("temporal-holds.json", [hold])
        self.write("posts/100.json", record(id="100", url="https://aagag.com/issue/?idx=100", listedAtRaw="2026-10-09 12:00:00", observedAt="2026-10-09T03:00:10Z", commentCounts=[{"id": "native-1", "kCount": 12}]))
        return hold

    def test_temporal_hold_retains_verified_qualifier_without_inventing_original_date(self):
        self.set_temporal_hold()
        summary, pending = checkpoint.update()
        self.assertEqual(summary["candidateIDs"], ["100"])
        self.assertEqual(summary["qualifiers"], 1)
        self.assertEqual(summary["temporalVerificationHeldIDs"], ["100"])
        self.assertEqual(summary["unknownWindowMembership"], 1)
        self.assertFalse(summary["nativeCommentCoverageComplete"])
        self.assertFalse(summary["complete"])
        self.assertEqual(pending, [])
        candidate = self.read("candidates.json")[0]
        self.assertEqual(candidate["kCount"], 12)
        self.assertTrue(candidate["kCountVerified"])
        self.assertTrue(candidate["thresholdQualified"])
        self.assertIsNone(candidate["inWindow"])
        self.assertIsNone(candidate["originalExactListedAt"])
        self.assertEqual(candidate["listedAtRaw"], "2026-10-09 12:00:00")
        self.assertEqual(candidate["listedAt"], "2026-10-09T03:00:00+00:00")
        self.assertEqual(candidate["latestListedAt"], candidate["listedAt"])
        self.assertTrue(candidate["candidateVerificationHeld"])
        self.assertIn(checkpoint.TEMPORAL_HOLD_REASON, candidate["candidateVerificationHoldReasons"])
        self.assertEqual(candidate["initialListingEvidence"]["age"], "22시간전")
        self.assertNotIn("100", summary["incompleteIDs"])
        _, loaded = checkpoint.load()
        self.assertIsNone(next(p for p in loaded if p["id"] == "100")["inWindow"])

    def test_temporal_hold_cannot_override_source_title_safety_or_manual_title_hold(self):
        self.set_temporal_hold()
        self.set_hold("100", title="모호한 제목")
        summary, _ = checkpoint.update()
        self.assertEqual(summary["candidateIDs"], [])
        self.assertFalse(summary["complete"])

    def test_temporal_hold_must_match_stored_initial_listing_evidence(self):
        hold = self.set_temporal_hold()
        hold["initialListingEvidence"]["age"] = "20시간전"
        self.write("temporal-holds.json", [hold])
        with self.assertRaisesRegex(ValueError, "does not match"):
            checkpoint.update()

    def test_temporal_hold_clearing_restores_actual_latest_date_classification(self):
        self.set_temporal_hold()
        checkpoint.update()
        self.write("temporal-holds.json", [])
        summary, _ = checkpoint.update()
        self.assertEqual(summary["candidateIDs"], [])
        self.assertEqual(summary["temporalVerificationHeldIDs"], [])
        value = next(p for p in self.read("normalized-posts.json") if p["id"] == "100")
        self.assertFalse(value["inWindow"])
        self.assertNotIn("temporalMembershipUncertain", value)

    def test_interrupted_output_regenerates_from_raw_on_resume(self):
        original_write = checkpoint.atomic_write
        def interrupt_one_file(path, data):
            if Path(path).name == "normalized-posts.json":
                raise OSError("simulated interruption")
            return original_write(path, data)
        with mock.patch.object(checkpoint, "atomic_write", side_effect=interrupt_one_file):
            with self.assertRaises(OSError):
                checkpoint.update()
        summary, pending = checkpoint.update()
        self.assertTrue(summary["complete"])
        self.assertEqual(pending, [])
        self.assertEqual(len(self.read("normalized-posts.json")), 2)
        self.assertEqual(len(self.read("candidates.json")), 1)


if __name__ == "__main__":
    unittest.main()
