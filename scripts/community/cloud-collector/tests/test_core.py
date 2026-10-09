"""Independent offline contract tests; run with python -m unittest discover -s tests."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

# Loading must not write cache files into src while the live collector is running.
sys.dont_write_bytecode = True
MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "core.py"
spec = importlib.util.spec_from_file_location("collector_core_under_test", MODULE_PATH)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

START = core.utc("2026-10-08T01:00:00Z")
END = core.utc("2026-10-09T01:00:00Z")


def record(**updates):
    data = {
        "id": "100", "requestedId": "100", "status": "observed",
        "title": "재미있는 이야기", "listedAtRaw": "2026-10-08 12:00:00",
        "commentsExpected": 1, "commentsAllSelected": True,
        "commentCounts": [{"id": "native-1", "date": "2026-10-08 12:30:00", "kCount": 11}],
        "sourcesExpected": 1, "sourcesExpanded": True,
        "sources": [{"id": "source-1", "site": "test", "title": "원문", "url": "https://example.test/source"}],
        "media": [{"type": "image", "url": "https://example.test/image.jpg", "width": 640, "height": 480, "complete": True}],
    }
    data.update(copy.deepcopy(updates))
    return data


def normalize(data=None):
    return core.normalize(record() if data is None else data, START, END)


def listings(*ids):
    return [
        {"phase": phase, "page": 1, "boundaryConfirmed": True,
         "items": [{"id": identity} for identity in ids]}
        for phase in ("initial", "resweep")
    ]


class ThresholdAndIdentityTests(unittest.TestCase):
    def test_ten_k_is_not_qualified(self):
        actual = normalize(record(commentCounts=[{"id": "1", "kCount": 10}]))
        self.assertEqual(actual["kCount"], 10)
        self.assertFalse(actual["thresholdQualified"])
        self.assertFalse(actual["candidate"])

    def test_eleven_k_is_qualified(self):
        actual = normalize()
        self.assertEqual(actual["kCount"], 11)
        self.assertTrue(actual["thresholdQualified"])
        self.assertTrue(actual["candidate"])

    def test_repeated_native_comment_ids_do_not_double_count(self):
        comment = {"id": "native-1", "kCount": 6}
        actual = normalize(record(commentCounts=[comment, dict(comment)]))
        self.assertEqual(actual["commentCount"], 1)
        self.assertEqual(actual["duplicateCommentRows"], 1)
        self.assertEqual(actual["kCount"], 6)
        self.assertTrue(actual["commentsComplete"])
        self.assertFalse(actual["thresholdQualified"])

    def test_distinct_native_comment_ids_are_counted_even_with_identical_content(self):
        actual = normalize(record(commentsExpected=2, commentCounts=[
            {"id": "native-1", "kCount": 6}, {"id": "native-2", "kCount": 6}
        ]))
        self.assertEqual(actual["commentCount"], 2)
        self.assertEqual(actual["kCount"], 12)
        self.assertTrue(actual["thresholdQualified"])

    def test_conflicting_duplicate_native_comments_are_incomplete(self):
        actual = normalize(record(commentCounts=[
            {"id": "native-1", "kCount": 6}, {"id": "native-1", "kCount": 12}
        ]))
        self.assertEqual(actual["commentConflicts"], ["native-1"])
        self.assertFalse(actual["commentsComplete"])
        self.assertFalse(actual["inspectionComplete"])

    def test_comment_without_native_id_is_not_counted_and_blocks_completion(self):
        actual = normalize(record(commentCounts=[{"kCount": 50}]))
        self.assertEqual(actual["observedCommentCount"], 0)
        self.assertEqual(actual["observedKCount"], 0)
        self.assertIsNone(actual["commentCount"])
        self.assertIsNone(actual["kCount"])
        self.assertIn("missing_comment_id", actual["commentConflicts"])
        self.assertFalse(actual["inspectionComplete"])

    def test_numeric_post_suffixes_canonicalize(self):
        for identity in ("100", "100_1", "100-2"):
            with self.subTest(identity=identity):
                self.assertEqual(core.post_id(identity), "100")
                self.assertEqual(normalize(record(id=identity))["canonicalId"], "100")

    def test_non_numeric_suffix_is_preserved(self):
        self.assertEqual(core.post_id("100_source"), "100_source")

    def test_listing_post_suffixes_deduplicate_across_passes(self):
        actual = core.coverage(listings("100", "100_1", "100-2"), [normalize()], START, END)
        self.assertEqual(actual["listedUnique"], 1)
        self.assertEqual(actual["missingIds"], [])
        self.assertTrue(actual["complete"])

    def test_input_record_is_not_changed(self):
        source = record()
        before = copy.deepcopy(source)
        normalize(source)
        self.assertEqual(source, before)


class TimeWindowTests(unittest.TestCase):
    def test_start_and_end_are_inclusive(self):
        for time in ("2026-10-08 10:00:00", "2026-10-09 10:00:00"):
            with self.subTest(time=time):
                self.assertTrue(normalize(record(listedAtRaw=time))["inWindow"])

    def test_one_second_outside_either_bound_is_excluded(self):
        for time in ("2026-10-08 09:59:59", "2026-10-09 10:00:01"):
            with self.subTest(time=time):
                actual = normalize(record(listedAtRaw=time))
                self.assertFalse(actual["inWindow"])
                self.assertFalse(actual["candidate"])

    def test_korean_listed_time_is_converted_to_utc(self):
        self.assertEqual(core.listed_time("등록일 2026-10-08 10:00:00"), START)

    def test_missing_or_relative_listed_time_blocks_completion(self):
        for time in (None, "", "1시간 전"):
            with self.subTest(time=time):
                actual = normalize(record(listedAtRaw=time))
                self.assertIsNone(actual["inWindow"])
                self.assertFalse(actual["inspectionComplete"])
                self.assertFalse(actual["candidate"])

    def test_comment_dates_do_not_change_cumulative_native_count(self):
        actual = normalize(record(commentsExpected=4, commentCounts=[
            {"id": "old", "date": "2026-10-08 09:59:59", "kCount": 3},
            {"id": "start", "date": "2026-10-08 10:00:00", "kCount": 3},
            {"id": "end", "date": "2026-10-09 10:00:00", "kCount": 3},
            {"id": "after", "date": "2026-10-09 10:00:01", "kCount": 3},
        ]))
        self.assertEqual(actual["kCount"], 12)
        self.assertEqual((actual["oldCommentCount"], actual["windowCommentCount"], actual["postWindowCommentCount"]), (1, 2, 1))

    def test_relative_age_is_only_an_upper_bound(self):
        self.assertEqual(core.age_upper_timestamp("1시간 전", "2026-10-09T01:00:00Z"), core.utc("2026-10-09T00:00:00Z"))
        self.assertIsNone(core.age_upper_timestamp("unknown", "2026-10-09T01:00:00Z"))


class SafetyTests(unittest.TestCase):
    def test_shared_title_classifier_fixture(self):
        cases = json.loads((Path(__file__).parent / "title-safety-cases.json").read_text())
        for case in cases:
            with self.subTest(title=case["title"]):
                self.assertEqual(core.classify_title(case["title"]), case["expected"])

    def test_failed_count_extraction_preserves_known_membership_but_not_threshold(self):
        actual = normalize(record(status="failed", commentsExpected=2, commentCounts=[{"id": "native-1", "date": "2026-10-08 12:30:00", "kCount": 11}]))
        self.assertTrue(actual["inWindow"])
        self.assertIsNotNone(actual["listedAt"])
        self.assertEqual(actual["observedKCount"], 11)
        self.assertEqual(actual["observedCommentCount"], 1)
        self.assertIsNone(actual["kCount"])
        self.assertIsNone(actual["thresholdQualified"])
        self.assertIsNone(actual["thresholdExclusion"])
        self.assertFalse(actual["kCountVerified"])
        self.assertFalse(actual["inspectionComplete"])

    def test_each_nsfw_marker_on_any_source_excludes(self):
        for marker in ("ㅇㅎ", "ㅎㅂ", "ㅇㅎㅂ"):
            with self.subTest(marker=marker):
                actual = normalize(record(sources=[{"id": "unsafe-source", "title": f"[{marker}] 원문"}]))
                self.assertFalse(actual["candidate"])
                self.assertIn({"code": "source_title_nsfw_marker", "sourceId": "unsafe-source", "marker": marker}, actual["exclusions"])

    def test_aggregator_title_marker_also_excludes(self):
        actual = normalize(record(title="제목 [ㅇㅎ]"))
        self.assertFalse(actual["candidate"])
        self.assertTrue(actual["exclusions"])

    def test_safe_title_does_not_override_marked_second_source(self):
        actual = normalize(record(sourcesExpected=2, sources=[
            {"id": "safe", "title": "일반 제목"}, {"id": "unsafe", "title": "ㅎㅂ 원문"},
        ]))
        self.assertTrue(actual["sourcesComplete"])
        self.assertFalse(actual["candidate"])

    def test_longer_consonant_run_is_not_treated_as_standalone_marker(self):
        actual = normalize(record(title="ㅎㅎㅎㅂㅋㅋ"))
        self.assertFalse(actual["exclusions"])


class CoverageTests(unittest.TestCase):
    def test_complete_evidence_is_complete(self):
        actual = core.coverage(listings("100"), [normalize()], START, END)
        self.assertTrue(actual["complete"])
        self.assertEqual(actual["passes"], {"initial": True, "resweep": True})

    def test_missing_listed_row_prevents_full_coverage(self):
        actual = core.coverage(listings("100", "101_2"), [normalize()], START, END)
        self.assertEqual(actual["missingIds"], ["101"])
        self.assertFalse(actual["complete"])

    def test_missing_resweep_prevents_full_coverage(self):
        actual = core.coverage(listings("100")[:1], [normalize()], START, END)
        self.assertFalse(actual["passes"]["resweep"])
        self.assertFalse(actual["complete"])

    def test_missing_page_or_unconfirmed_boundary_prevents_full_coverage(self):
        for change in ({"page": 2}, {"boundaryConfirmed": False}):
            with self.subTest(change=change):
                pages = listings("100")
                pages[-1].update(change)
                self.assertFalse(core.coverage(pages, [normalize()], START, END)["complete"])

    def test_missing_comment_rows_prevent_full_coverage(self):
        self.assert_incomplete(record(commentsExpected=2))

    def test_unselected_all_comments_prevent_full_coverage(self):
        self.assert_incomplete(record(commentsAllSelected=False))

    def test_missing_source_rows_prevent_full_coverage(self):
        self.assert_incomplete(record(sourcesExpected=2))

    def test_collapsed_sources_prevent_full_coverage(self):
        self.assert_incomplete(record(sourcesExpanded=False))

    def test_unloaded_or_empty_dimension_image_prevents_full_coverage(self):
        for image in (
            {"type": "image", "url": "https://example.test/image.jpg", "complete": False, "width": 640, "height": 480},
            {"type": "image", "url": "https://example.test/image.jpg", "complete": True, "width": 0, "height": 480},
            {"type": "image", "url": "https://example.test/image.jpg", "complete": True, "width": 640, "height": 0},
        ):
            with self.subTest(image=image):
                self.assert_incomplete(record(media=[image]))

    def test_unloaded_video_prevents_full_coverage(self):
        # Regression: video dimensions are captured by the browser macro but ignored by core.
        self.assert_incomplete(record(media=[{"type": "video", "width": 0, "height": 0, "url": ""}]))

    def test_absent_media_evidence_is_not_equivalent_to_a_text_only_post(self):
        data = record()
        del data["media"]
        self.assert_incomplete(data)

    def test_explicit_empty_media_list_is_valid_for_a_text_only_post(self):
        self.assertTrue(normalize(record(media=[]))["inspectionComplete"])

    def test_loaded_video_with_dimensions_and_url_is_complete(self):
        self.assertTrue(normalize(record(media=[{"type": "video", "width": 640, "height": 480, "url": "https://example.test/movie.mp4"}]))["mediaComplete"])

    def test_missing_media_url_is_incomplete(self):
        self.assert_incomplete(record(media=[{"type": "image", "width": 640, "height": 480, "complete": True}]))

    def test_failed_record_prevents_full_coverage(self):
        self.assert_incomplete(record(status="failed"))

    def assert_incomplete(self, data):
        actual = normalize(data)
        self.assertFalse(actual["inspectionComplete"])
        coverage = core.coverage(listings("100"), [actual], START, END)
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["failedOrIncomplete"], ["100"])


class BelowThresholdScopeTests(unittest.TestCase):
    def scoped_record(self, k_count=10, **updates):
        data = record(
            verificationScope="comments_only_below_threshold",
            commentCounts=[{"id": "native-1", "kCount": k_count}],
            sources=[], sourcesExpected=5, sourcesExpanded=False,
        )
        del data["media"]
        data.update(updates)
        return data

    def test_verified_below_threshold_comments_can_skip_sources_and_media(self):
        for k_count in (0, 10):
            with self.subTest(k_count=k_count):
                actual = normalize(self.scoped_record(k_count))
                self.assertTrue(actual["inspectionComplete"])
                self.assertFalse(actual["sourceMediaVerificationRequired"])
                self.assertFalse(actual["thresholdQualified"])
                self.assertEqual(actual["thresholdExclusion"], "literal_k_below_11")
                self.assertFalse(actual["candidate"])
                self.assertTrue(core.coverage(listings("100"), [actual], START, END)["complete"])

    def test_eleven_k_cannot_skip_verification_using_scope_flag(self):
        actual = normalize(self.scoped_record(11))
        self.assertTrue(actual["thresholdQualified"])
        self.assertTrue(actual["sourceMediaVerificationRequired"])
        self.assertFalse(actual["inspectionComplete"])
        self.assertFalse(core.coverage(listings("100"), [actual], START, END)["complete"])

    def test_skip_still_requires_complete_native_comments(self):
        for updates in (
            {"commentsExpected": 2},
            {"commentsAllSelected": False},
            {"commentCounts": [{"kCount": 0}]},
            {"commentCounts": [{"id": "native-1", "kCount": 0}, {"id": "native-1", "kCount": 1}]},
        ):
            with self.subTest(updates=updates):
                self.assertFalse(normalize(self.scoped_record(**updates))["inspectionComplete"])

    def test_real_zero_native_comments_is_complete(self):
        actual = normalize(self.scoped_record(commentCounts=[], commentsExpected=0))
        self.assertTrue(actual["commentsComplete"])
        self.assertTrue(actual["inspectionComplete"])
        self.assertFalse(actual["thresholdQualified"])

    def test_null_loading_count_is_not_treated_as_zero(self):
        actual = normalize(self.scoped_record(commentCounts=[], commentsExpected=None))
        self.assertFalse(actual["commentsComplete"])
        self.assertFalse(actual["inspectionComplete"])
        self.assertFalse(core.coverage(listings("100"), [actual], START, END)["complete"])

    def test_incomplete_counts_never_claim_a_below_threshold_exclusion(self):
        for updates in (
            {"commentsExpected": None, "commentCounts": []},
            {"commentsExpected": 2},
            {"commentsAllSelected": False},
            {"status": "failed"},
        ):
            with self.subTest(updates=updates):
                actual = normalize(self.scoped_record(**updates))
                self.assertFalse(actual["kCountVerified"])
                self.assertIsNone(actual["kCount"])
                self.assertIsNone(actual["commentCount"])
                self.assertIsNone(actual["thresholdQualified"])
                self.assertIsNone(actual["thresholdExclusion"])
                self.assertIn("observedKCount", actual)
                self.assertFalse(actual["candidate"])
                self.assertFalse(actual["inspectionComplete"])

    def test_skip_still_requires_exact_timestamp_and_observed_status(self):
        for updates in ({"listedAtRaw": None}, {"status": "failed"}):
            with self.subTest(updates=updates):
                self.assertFalse(normalize(self.scoped_record(**updates))["inspectionComplete"])

    def test_legacy_below_threshold_records_do_not_require_a_scope_flag(self):
        for scope in (None, "full_candidate", "comments_only", "unknown"):
            with self.subTest(scope=scope):
                self.assertTrue(normalize(self.scoped_record(verificationScope=scope))["inspectionComplete"])


class LowerBoundQualificationTests(unittest.TestCase):
    def partial(self, **changes):
        data = record(status="failed", commentsExpected=11, commentsAllSelected=True,
            commentEvidenceObservedAt="2026-10-09T01:00:00Z",
            commentCounts=[{"id": str(index), "date": "2026-10-08 12:30:00", "kCount": amount} for index, amount in enumerate([0, 0, 0, 1, 19, 0, 3, 0, 0, 0], 1)],
            sources=[], sourcesExpected=None, sourcesExpanded=False)
        del data["media"]
        data.update(changes)
        return data

    def test_observed_23_minimum_qualifies_without_claiming_11_comments_or_exact_total(self):
        actual = normalize(self.partial())
        self.assertEqual(actual["observedCommentCount"], 10)
        self.assertEqual(actual["observedKCount"], 23)
        self.assertEqual(actual["knownLiteralKMinimum"], 23)
        self.assertEqual(actual["thresholdEvidence"], "observed_lower_bound")
        self.assertTrue(actual["thresholdQualified"])
        self.assertTrue(actual["nativeCountEvidenceTrusted"])
        self.assertTrue(actual["candidate"])
        self.assertTrue(actual["candidateVerificationHeld"])
        self.assertIn("native_comment_total_unverified", actual["candidateVerificationHoldReasons"])
        self.assertIn("source_list_unverified", actual["candidateVerificationHoldReasons"])
        self.assertIn("media_metadata_unverified", actual["candidateVerificationHoldReasons"])
        self.assertIsNone(actual["commentCount"])
        self.assertIsNone(actual["kCount"])
        self.assertFalse(actual["kCountVerified"])
        self.assertFalse(actual["commentsComplete"])
        self.assertFalse(actual["inspectionComplete"])
        self.assertFalse(core.coverage(listings("100"), [actual], START, END)["complete"])

    def test_minimum_eleven_qualifies_but_ten_remains_unknown(self):
        for amount in (10, 11):
            with self.subTest(amount=amount):
                actual = normalize(self.partial(commentCounts=[{"id": "1", "kCount": amount}]))
                self.assertEqual(actual["knownLiteralKMinimum"], amount)
                self.assertIs(actual["thresholdQualified"], True if amount == 11 else None)
                self.assertIsNone(actual["thresholdExclusion"])
                self.assertIsNone(actual["kCount"])

    def test_duplicate_rows_cannot_inflate_the_lower_bound(self):
        actual = normalize(self.partial(commentCounts=[{"id": "1", "kCount": 6}, {"id": "1", "kCount": 6}]))
        self.assertEqual(actual["knownLiteralKMinimum"], 6)
        self.assertIsNone(actual["thresholdQualified"])

    def test_conflicting_or_missing_native_ids_cannot_establish_lower_bound(self):
        for comments in ([{"id": "1", "kCount": 23}, {"id": "1", "kCount": 24}], [{"kCount": 23}], [{"id": " ", "kCount": 23}], [{"id": True, "kCount": 23}]):
            with self.subTest(comments=comments):
                actual = normalize(self.partial(commentCounts=comments))
                self.assertIsNone(actual["knownLiteralKMinimum"])
                self.assertIsNone(actual["thresholdQualified"])
                self.assertFalse(actual["candidate"])

    def test_unknown_negative_or_noninteger_counts_never_establish_lower_bound(self):
        for invalid in (None, -1, True, "23", 23.0):
            with self.subTest(invalid=invalid):
                actual = normalize(self.partial(commentCounts=[{"id": "1", "kCount": 23}, {"id": "2", "kCount": invalid}]))
                self.assertIsNone(actual["knownLiteralKMinimum"])
                self.assertIsNone(actual["thresholdQualified"])
                self.assertFalse(actual["kCountVerified"])
                self.assertFalse(actual["inspectionComplete"])

    def test_partial_rows_require_all_comments_selected(self):
        actual = normalize(self.partial(commentsAllSelected=False))
        self.assertIsNone(actual["knownLiteralKMinimum"])
        self.assertIsNone(actual["thresholdQualified"])

    def test_failed_partial_rows_require_a_real_capture_timestamp(self):
        for stamp in (None, "", "invalid", "2026-10-09T01:00:00"):
            with self.subTest(stamp=stamp):
                actual = normalize(self.partial(commentEvidenceObservedAt=stamp))
                self.assertIsNone(actual["knownLiteralKMinimum"])
                self.assertIsNone(actual["thresholdQualified"])

    def test_empty_runtime_failure_cannot_become_a_zero_or_lower_bound_result(self):
        actual = normalize({"requestedId": "100", "status": "failed", "error": "Runtime.evaluate timed out", "attempts": []})
        self.assertIsNone(actual["knownLiteralKMinimum"])
        self.assertIsNone(actual["thresholdQualified"])
        self.assertIsNone(actual["thresholdExclusion"])
        self.assertIsNone(actual["kCount"])
        self.assertIsNone(actual["commentCount"])

    def test_exact_verified_counts_have_separate_evidence_and_no_lower_bound_hold(self):
        actual = normalize()
        self.assertEqual(actual["thresholdEvidence"], "exact_native_total")
        self.assertEqual(actual["knownLiteralKMinimum"], 11)
        self.assertEqual(actual["kCount"], 11)
        self.assertFalse(actual["candidateVerificationHeld"])

    def test_lower_bound_does_not_bypass_window_or_safety_filters(self):
        for changes in ({"listedAtRaw": "2026-10-09 10:00:01"}, {"title": "[ㅇㅎ] 제목"}):
            with self.subTest(changes=changes):
                actual = normalize(self.partial(**changes))
                self.assertTrue(actual["thresholdQualified"])
                self.assertFalse(actual["candidate"])
                self.assertFalse(actual["inspectionComplete"])


class OutsideWindowHeaderTests(unittest.TestCase):
    def header(self, **changes):
        value = {"status": "outside_window", "id": "100", "url": "https://aagag.com/issue/?idx=100", "title": "관찰된 제목", "listedAtRaw": "2026-10-08 09:59:59", "observedAt": "2026-10-09T01:30:00Z"}
        value.update(changes)
        return value

    def test_exact_outside_headers_resolve_required_scope_without_any_counts(self):
        for stamp in ("2026-10-08 09:59:59", "2026-10-09 10:00:01"):
            with self.subTest(stamp=stamp):
                actual = normalize(self.header(listedAtRaw=stamp))
                self.assertTrue(actual["outsideWindowVerified"])
                self.assertTrue(actual["inspectionComplete"])
                self.assertFalse(actual["inWindow"])
                self.assertEqual(actual["verificationScope"], "exact_header_outside_window")
                self.assertTrue(actual["nativeCommentsNotInspected"])
                for field in ("kCount", "commentCount", "observedKCount", "observedCommentCount", "commentsExpected", "knownLiteralKMinimum", "oldCommentCount", "windowCommentCount", "postWindowCommentCount", "thresholdQualified", "thresholdEvidence", "thresholdExclusion"):
                    self.assertIsNone(actual[field], field)
                self.assertFalse(actual["kCountVerified"])
                self.assertFalse(actual["candidate"])
                self.assertTrue(core.coverage(listings("100"), [actual], START, END)["complete"])

    def test_inclusive_window_edges_and_unknown_dates_cannot_skip_inspection(self):
        for stamp in ("2026-10-08 10:00:00", "2026-10-09 10:00:00", "2026-10-08 12:00:00", None, "1시간 전"):
            with self.subTest(stamp=stamp):
                actual = normalize(self.header(listedAtRaw=stamp))
                self.assertFalse(actual["outsideWindowVerified"])
                self.assertFalse(actual["inspectionComplete"])
                self.assertIsNone(actual["kCount"])
                self.assertIsNone(actual["thresholdQualified"])

    def test_actual_title_id_url_and_observation_time_are_required(self):
        for changes in ({"title": None}, {"id": None, "requestedId": "100"}, {"url": None}, {"url": "https://aagag.com/issue/?idx=999"}, {"url": "https://other.test/issue/?idx=100"}, {"observedAt": None}, {"observedAt": "2026-10-09T01:30:00"}, {"status": "failed"}):
            with self.subTest(changes=changes):
                actual = normalize(self.header(**changes))
                self.assertFalse(actual["outsideWindowVerified"])
                self.assertFalse(actual["inspectionComplete"])


class CheckpointTests(unittest.TestCase):
    def test_atomic_checkpoint_roundtrips_and_can_resume(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "nested" / "checkpoint.json"
            first = {"cursor": 1, "records": [normalize()], "phase": "initial", "label": "유머"}
            core.atomic_write(path, first)
            resumed = json.loads(path.read_text())
            self.assertEqual(resumed, first)
            resumed["cursor"] = 2
            resumed["records"].append(normalize(record(id="101")))
            core.atomic_write(path, resumed)
            self.assertEqual(json.loads(path.read_text()), resumed)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_interrupted_replace_preserves_last_valid_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "checkpoint.json"
            prior = {"cursor": 1, "records": ["100"]}
            core.atomic_write(path, prior)
            with mock.patch.object(core.os, "replace", side_effect=OSError("simulated interrupted rename")):
                with self.assertRaises(OSError):
                    core.atomic_write(path, {"cursor": 2, "records": ["100", "101"]})
            self.assertEqual(json.loads(path.read_text()), prior)
            # A later successful checkpoint can replace the abandoned temp safely.
            later = {"cursor": 3, "records": ["100", "101", "102"]}
            core.atomic_write(path, later)
            self.assertEqual(json.loads(path.read_text()), later)


if __name__ == "__main__":
    unittest.main()
