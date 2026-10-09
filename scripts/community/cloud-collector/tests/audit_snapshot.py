"""Read-only independent raw/normalized snapshot audit. Writes only requested stdout.

Usage: python tests/audit_snapshot.py runs/<run-id>
Uses no collector implementation and no external dependencies.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys


def audit(run):
    summary = json.loads((run / "summary.json").read_text())
    normalized = json.loads((run / "normalized-posts.json").read_text())
    start = datetime.fromisoformat(summary["window"]["start"])
    end = datetime.fromisoformat(summary["window"]["end"])
    kst = timezone(timedelta(hours=9))
    counters = Counter()
    defects = []
    old_dependent = []
    def parse(value):
        if not value:
            return None
        match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value)
        if not match:
            return None
        return datetime.strptime(match.group(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=kst)
    for rec in normalized:
        raw_file = run / "posts" / (str(rec.get("id") or rec.get("requestedId")) + ".json")
        if not raw_file.exists():
            counters["raw_file_unavailable"] += 1
            continue
        raw = json.loads(raw_file.read_text())
        if raw.get("observedAt") != rec.get("observedAt"):
            counters["raw_changed_since_normalization"] += 1
            continue
        counters["matched_records"] += 1
        comments = {}
        for comment in raw.get("commentCounts", []):
            if comment.get("id"):
                comments[comment["id"]] = comment
        totals = Counter()
        for comment in comments.values():
            date = parse(comment.get("date"))
            key = "unknown" if date is None else "old" if date < start else "after" if date > end else "window"
            totals[key] += 1
            totals[key + "_k"] += comment["kCount"]
        expected = {
            "commentCount" if rec.get("kCountVerified", True) else "observedCommentCount": len(comments),
            "kCount" if rec.get("kCountVerified", True) else "observedKCount": sum(comment["kCount"] for comment in comments.values()),
            "oldCommentCount": totals["old"],
            "windowCommentCount": totals["window"],
            "postWindowCommentCount": totals["after"],
        }
        listed = parse(raw.get("listedAtRaw"))
        expected["inWindow"] = None if listed is None else start <= listed <= end
        for key, value in expected.items():
            if rec.get(key) != value:
                defects.append({"id": rec.get("id"), "field": key, "actual": rec.get(key), "expected": value})
        counters.update(totals)
        if rec.get("thresholdQualified") and rec.get("inWindow") and totals["old"] and totals["window_k"] < 11:
            old_dependent.append({"id": rec.get("id"), "cumulativeK": sum(comment["kCount"] for comment in comments.values()), "inWindowCommentK": totals["window_k"], "oldCommentK": totals["old_k"]})
    return {
        "source_summary_at": summary.get("lastUpdatedAt"),
        "normalized_records": len(normalized),
        "audit_totals": dict(counters),
        "discrepancies": defects,
        "qualifiers_with_less_than_11_window_comment_k_and_old_comments": old_dependent,
        "scope": "Read-only snapshot audit. A passing audit does not assert listing coverage, media content safety, or a completed live run.",
    }


if __name__ == "__main__":
    result = audit(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["discrepancies"]))
