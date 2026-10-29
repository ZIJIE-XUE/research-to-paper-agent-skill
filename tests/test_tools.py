"""Behavioral tests: provenance, resumption, failure handling and budgets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/ml-research-paper/scripts"
sys.path.insert(0, str(SCRIPTS))
from common import inside, read_json, write_json
import pipeline
import run_experiments as runner


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ml-skill-test-")
        self.root = Path(self.temp.name)
        pipeline.init(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def report(self, stage, verdict="pass"):
        artifact = "research/" + stage + ".md"
        (self.root / artifact).write_text("Actual evidence for " + stage, encoding="utf-8")
        path = "research/gates/" + stage + ".json"
        write_json(self.root / path, {"stage": stage, "verdict": verdict,
                   "artifacts": [artifact], "checks": [{"name": "content inspected",
                   "status": "pass", "evidence": [artifact], "note": "Test fixture evidence"}]})
        return path

    def test_init_never_overwrites(self):
        with self.assertRaises(ValueError):
            pipeline.init(self.root)
        self.assertEqual(pipeline.status(self.root)["next_stage"], "scope")

    def test_path_escape(self):
        for name in ("../outside.txt", str(self.root.resolve())):
            with self.assertRaises(ValueError):
                inside(self.root, name)

    def test_checkpoint_requires_prior_evidence(self):
        with self.assertRaises(ValueError):
            pipeline.checkpoint(self.root, "literature", self.report("literature"))
        pipeline.checkpoint(self.root, "scope", self.report("scope"))
        pipeline.checkpoint(self.root, "literature", self.report("literature"))
        (self.root / "research/scope.md").write_text("changed", encoding="utf-8")
        status = pipeline.status(self.root)
        self.assertEqual(status["valid_stages"], [])
        self.assertIn("literature", status["invalid_stages"])

    def test_recheckpoint_invalidates_and_archives(self):
        pipeline.checkpoint(self.root, "scope", self.report("scope"))
        pipeline.checkpoint(self.root, "literature", self.report("literature"))
        pipeline.checkpoint(self.root, "scope", self.report("scope"))
        state = read_json(self.root / "research/state.json")
        self.assertNotIn("literature", state["checkpoints"])
        self.assertEqual(len(state["history"]), 2)

    def test_review_needing_revision_blocks_final(self):
        for stage in pipeline.STAGES[:-1]:
            pipeline.checkpoint(self.root, stage, self.report(stage, "revise" if stage == "review" else "pass"))
        with self.assertRaisesRegex(ValueError, "requires revision"):
            pipeline.checkpoint(self.root, "final", self.report("final"))
        pipeline.checkpoint(self.root, "review", self.report("review"))
        pipeline.checkpoint(self.root, "final", self.report("final"))
        self.assertIsNone(pipeline.status(self.root)["next_stage"])

    def plan(self, code=None, jobs=1, total=10, timeout=3):
        (self.root / "experiments/protocol.md").write_text("Frozen synthetic tool check", encoding="utf-8")
        default = ("import json\nfrom pathlib import Path\n"
                   "Path('metrics.json').write_text(json.dumps({'metrics':{'score':0.5}}))\n")
        (self.root / "src/train.py").write_text(code or default, encoding="utf-8")
        plan = {"experiment_id": "test-v1", "protocol": "experiments/protocol.md",
                "inputs": ["src/train.py", "experiments/protocol.md"],
                "max_jobs": 5, "max_total_seconds": total,
                "jobs": [{"id": "job-" + str(i), "command": ["{python}", "{project}/src/train.py"],
                          "timeout_seconds": timeout, "required_outputs": ["metrics.json"]} for i in range(jobs)]}
        write_json(self.root / "experiments/plan.json", plan)
        return plan

    def run_plan(self):
        return runner.run(self.root, "experiments/plan.json")

    def test_success_and_verified_resume(self):
        self.plan()
        first = self.run_plan()
        self.assertEqual(first["status"], "complete")
        self.assertEqual(first["jobs"][0]["status"], "success")
        resumed = self.run_plan()
        self.assertEqual(resumed["jobs"][0]["status"], "reused_verified")
        self.assertEqual(first["spent_seconds"], resumed["spent_seconds"])

    def test_changed_input_requires_new_experiment(self):
        self.plan()
        self.run_plan()
        (self.root / "src/train.py").write_text("print('changed')", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.run_plan()

    def test_tampered_success_is_not_reused(self):
        self.plan()
        self.run_plan()
        output = self.root / "runs/test-v1/job-0/attempt-0001/metrics.json"
        write_json(output, {"metrics": {"score": 1}})
        with self.assertRaisesRegex(ValueError, "output changed"):
            self.run_plan()

    def test_failed_job_is_preserved_without_auto_retry(self):
        self.plan("raise RuntimeError('expected failure')\n")
        summary = self.run_plan()
        self.assertEqual(summary["jobs"][0]["status"], "failed")
        self.assertEqual(self.run_plan()["jobs"][0]["status"], "needs_attention")
        self.assertEqual(len(list((self.root / "runs/test-v1/job-0").glob("attempt-*"))), 1)

    def test_nonfinite_metrics_fail(self):
        self.plan("from pathlib import Path\nPath('metrics.json').write_text('{\"metrics\":{\"score\":NaN}}')\n")
        self.assertEqual(self.run_plan()["jobs"][0]["status"], "failed")

    def test_missing_output_fails_even_when_exit_zero(self):
        self.plan("print('No output')\n")
        self.assertEqual(self.run_plan()["jobs"][0]["status"], "failed")

    def test_timeout_and_cumulative_budget(self):
        self.plan("import time\ntime.sleep(10)\n", jobs=2, total=0.2, timeout=0.2)
        summary = self.run_plan()
        self.assertEqual(summary["status"], "budget_exhausted")
        self.assertEqual(summary["jobs"][0]["status"], "timeout")
        self.assertFalse((self.root / "runs/test-v1/job-1/attempt-0001").exists())
        resumed = self.run_plan()
        self.assertEqual(resumed["status"], "budget_exhausted")

    def test_mutated_input_is_detected(self):
        code = ("import json\nfrom pathlib import Path\n"
                "Path(__file__).write_text('# changed during run')\n"
                "Path('metrics.json').write_text(json.dumps({'metrics':{'x':1}}))\n")
        self.plan(code)
        self.assertEqual(self.run_plan()["status"], "input_mutated")

    def test_plan_cannot_exceed_job_cap(self):
        plan = self.plan()
        plan["max_jobs"] = 0
        with self.assertRaises(ValueError):
            runner.validate_plan(self.root, plan)


if __name__ == "__main__":
    unittest.main()
