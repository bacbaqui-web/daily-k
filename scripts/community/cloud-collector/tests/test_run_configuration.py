"""Fixed-window initialization and CLI resume tests, isolated from the live run."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_checkpoint import checkpoint

SOURCE = Path(__file__).resolve().parents[1] / "src" / "checkpoint.py"
ANCHOR = "2027-02-03T12:34:56.123Z"
START = "2027-02-02T12:34:56.123000+00:00"
END = "2027-02-03T12:34:56.123000+00:00"


class RunConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.run = self.root / "new-run"

    def cli(self, *args, run_env=None):
        env = dict(os.environ)
        env.pop("DAILYK_RUN_DIR", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if run_env is not None:
            env["DAILYK_RUN_DIR"] = str(run_env)
        return subprocess.run([sys.executable, "-B", str(SOURCE), *map(str, args)], env=env, capture_output=True, text=True, timeout=20)

    def test_init_persists_explicit_fixed_24_hour_window(self):
        run, manifest = checkpoint.initialize_run(ANCHOR, self.run)
        self.assertEqual(run, self.run)
        self.assertEqual(manifest["window"]["start"], START)
        self.assertEqual(manifest["window"]["end"], END)
        self.assertEqual(manifest["anchorBasis"], "explicit_initial_observation")
        self.assertEqual(json.loads((run / "run.json").read_text()), manifest)
        self.assertTrue((run / "posts").is_dir())
        self.assertTrue((run / "listings").is_dir())
        self.assertFalse((run / ".initializing").exists())

    def test_same_anchor_init_is_idempotent_including_creation_metadata(self):
        checkpoint.initialize_run(ANCHOR, self.run)
        original = (self.run / "run.json").read_bytes()
        checkpoint.initialize_run(END, self.run)
        self.assertEqual((self.run / "run.json").read_bytes(), original)

    def test_changed_anchor_cannot_move_existing_cutoff(self):
        checkpoint.initialize_run(ANCHOR, self.run)
        original = (self.run / "run.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "immutable"):
            checkpoint.initialize_run("2027-02-04T12:34:56.123Z", self.run)
        self.assertEqual((self.run / "run.json").read_bytes(), original)
        self.assertFalse((self.run / ".initializing").exists())

    def test_resume_reuses_manifest_not_legacy_constants_or_current_time(self):
        checkpoint.initialize_run(ANCHOR, self.run)
        first, _ = checkpoint.update(self.run)
        with mock.patch.object(checkpoint, "START", checkpoint.utc("2030-01-01T00:00:00Z")), mock.patch.object(checkpoint, "END", checkpoint.utc("2030-01-02T00:00:00Z")):
            resumed, _ = checkpoint.update(self.run)
        self.assertEqual(first["window"], resumed["window"])
        self.assertEqual(resumed["window"]["start"], START)
        self.assertEqual(resumed["window"]["end"], END)

    def test_cli_environment_run_initialization_and_resume(self):
        initialized = self.cli("init", "--end", ANCHOR, run_env=self.run)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.assertEqual(json.loads(initialized.stdout)["runDir"], str(self.run))
        summary = self.cli(run_env=self.run)
        self.assertEqual(summary.returncode, 0, summary.stderr)
        self.assertEqual(json.loads(summary.stdout)["window"]["end"], END)
        pending = self.cli("pending", "12", run_env=self.run)
        self.assertEqual(pending.returncode, 0, pending.stderr)
        self.assertEqual(json.loads(pending.stdout), [])
        self.assertEqual(json.loads((self.run / "run.json").read_text())["window"]["end"], END)

    def test_cli_explicit_run_directory_overrides_environment(self):
        checkpoint.initialize_run(ANCHOR, self.run)
        other = self.root / "other"
        checkpoint.initialize_run("2027-03-01T00:00:00Z", other)
        result = self.cli("summary", "--run-dir", self.run, run_env=other)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["window"]["end"], END)
        before_command = self.cli("--run-dir", self.run, "pending", "0", run_env=other)
        self.assertEqual(before_command.returncode, 0, before_command.stderr)
        self.assertEqual(json.loads(before_command.stdout), [])

    def test_cli_init_requires_explicit_end(self):
        result = self.cli("init", "--run-dir", self.run)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--end", result.stderr)
        self.assertFalse(self.run.exists())

    def test_cli_reinitialization_rejects_different_cutoff(self):
        checkpoint.initialize_run(ANCHOR, self.run)
        result = self.cli("init", "--end", "2027-03-01T00:00:00Z", "--run-dir", self.run)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("immutable", result.stderr)
        self.assertEqual(json.loads((self.run / "run.json").read_text())["window"]["end"], END)

    def test_custom_run_without_manifest_refuses_default_cutoff(self):
        result = self.cli("summary", "--run-dir", self.run)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no run.json", result.stderr)
        self.assertFalse((self.run / "summary.json").exists())

    def test_anchor_rejects_naive_non_utc_and_invalid_values(self):
        for value in ("2027-02-03T12:34:56", "2027-02-03T12:34:56+09:00", "2027-02-03", "invalid", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                checkpoint.initialize_run(value, self.run)
        self.assertFalse(self.run.exists())

    def test_generated_directory_uses_anchor_not_current_date(self):
        env = dict(os.environ)
        env.pop("DAILYK_RUN_DIR", None)
        with mock.patch.object(checkpoint, "ROOT", self.root), mock.patch.dict(os.environ, env, clear=True):
            run, _ = checkpoint.initialize_run(ANCHOR)
        self.assertEqual(run, self.root / "runs/20270203T123456.123000Z")

    def test_existing_legacy_default_remains_exact_and_read_only(self):
        run, start, end = checkpoint.resolve_run(checkpoint.DEFAULT_RUN)
        self.assertEqual(run, checkpoint.DEFAULT_RUN.resolve())
        self.assertEqual(start, checkpoint.utc("2026-10-08T02:03:32.390Z"))
        self.assertEqual(end, checkpoint.utc("2026-10-09T02:03:32.390Z"))

    def test_existing_raw_evidence_cannot_receive_a_new_manifest_anchor(self):
        (self.run / "posts").mkdir(parents=True)
        evidence = self.run / "posts/100.json"
        evidence.write_text('{"id":"100"}')
        with self.assertRaisesRegex(ValueError, "existing uninitialized run"):
            checkpoint.initialize_run(ANCHOR, self.run)
        self.assertEqual(evidence.read_text(), '{"id":"100"}')
        self.assertFalse((self.run / "run.json").exists())

    def test_initialization_lock_prevents_competing_initializer(self):
        self.run.mkdir()
        lock = self.run / ".initializing"
        lock.write_text("existing initializer")
        with self.assertRaisesRegex(ValueError, "already in progress"):
            checkpoint.initialize_run(ANCHOR, self.run)
        self.assertEqual(lock.read_text(), "existing initializer")
        self.assertFalse((self.run / "run.json").exists())

    def test_manifest_with_invalid_duration_cannot_be_resumed(self):
        self.run.mkdir()
        (self.run / "run.json").write_text(json.dumps({"version": 1, "window": {"start": "2027-02-01T00:00:00Z", "end": ANCHOR}}))
        with self.assertRaisesRegex(ValueError, "exactly 24 hours"):
            checkpoint.update(self.run)
        self.assertFalse((self.run / "summary.json").exists())

    def test_malformed_manifest_cannot_fall_back_to_legacy_cutoff(self):
        self.run.mkdir()
        (self.run / "run.json").write_text("not json")
        result = self.cli("--run-dir", self.run)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.run / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
