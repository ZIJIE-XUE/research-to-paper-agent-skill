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
import audit_integrity


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
        report = {"stage": stage, "verdict": verdict,
                   "artifacts": [artifact], "checks": [{"name": "content inspected",
                   "status": "pass", "evidence": [artifact], "note": "Test fixture evidence"}]}
        if stage in ("review", "final"):
            seed_integrity(self.root)
            phase = "pre_review" if stage == "review" else "final"
            audit_integrity.audit(self.root, phase)
            report["integrity_report"] = "research/integrity-" + phase + ".json"
        write_json(self.root / path, report)
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


def jsonl(root, name, rows):
    (root / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def seed_integrity(root):
    (root / "manuscript/draft.md").write_text("Synthetic tool fixture: one plus one is two.", encoding="utf-8")
    (root / "research/proof.md").write_text("Synthetic arithmetic fixture: 1+1=2.", encoding="utf-8")
    claim = {"id": "C001", "claim": "One plus one is two", "kind": "theoretical", "status": "supported",
             "scope": "Synthetic software fixture", "evidence": [{"path": "research/proof.md", "locator": "line 1"}]}
    jsonl(root, "results/claims.jsonl", [claim])
    jsonl(root, "literature/records.jsonl", [])
    jsonl(root, "literature/citation-checks.jsonl", [])
    jsonl(root, "reviews/issues.jsonl", [])
    return claim


class IntegrityTests(unittest.TestCase):
    setUp = ProjectTests.setUp
    tearDown = ProjectTests.tearDown
    plan = ProjectTests.plan
    run_plan = ProjectTests.run_plan

    def cited_claim(self):
        claim = seed_integrity(self.root)
        claim.update(kind="literature", reference_ids=["L001"])
        jsonl(self.root, "results/claims.jsonl", [claim])
        jsonl(self.root, "literature/records.jsonl", [{"id": "L001", "title": "Synthetic fixture, not a real paper"}])
        check = {"id": "V001", "claim_id": "C001", "reference_id": "L001", "existence": "verified",
                 "metadata": "verified", "support": "supported", "locator": "line 1",
                 "checked_at": "test-fixture", "method": "fixture inspection", "evidence": ["research/proof.md"]}
        jsonl(self.root, "literature/citation-checks.jsonl", [check])
        return check

    def test_citation_trace_and_report_freshness(self):
        self.cited_claim()
        report = audit_integrity.audit(self.root, "pre_review")
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["coverage"]["registered_citation_checks"], 1)
        pipeline.integrity_artifacts(self.root, "research/integrity-pre_review.json", "pre_review")
        (self.root / "research/proof.md").write_text("Changed source", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"):
            pipeline.integrity_artifacts(self.root, "research/integrity-pre_review.json", "pre_review")

    def test_unavailable_reference_is_not_verified(self):
        check = self.cited_claim()
        check["existence"] = "unavailable"
        jsonl(self.root, "literature/citation-checks.jsonl", [check])
        self.assertEqual(audit_integrity.audit(self.root, "pre_review")["verdict"], "fail")

    def test_orphan_citation_relation_fails(self):
        check = self.cited_claim()
        check["claim_id"] = "unknown"
        jsonl(self.root, "literature/citation-checks.jsonl", [check])
        self.assertEqual(audit_integrity.audit(self.root, "pre_review")["verdict"], "fail")

    def test_final_unresolved_major_blocks(self):
        seed_integrity(self.root)
        jsonl(self.root, "reviews/issues.jsonl", [{"id": "R001", "severity": "major", "status": "partial"}])
        self.assertEqual(audit_integrity.audit(self.root, "final")["verdict"], "fail")

    def test_invalid_review_fields_do_not_silently_pass(self):
        seed_integrity(self.root)
        jsonl(self.root, "reviews/issues.jsonl", [{"id": "R001", "severity": "Major", "status": "done"}])
        self.assertEqual(audit_integrity.audit(self.root, "final")["verdict"], "fail")

    def test_external_results_are_declared_not_certified(self):
        claim = seed_integrity(self.root)
        claim.update(kind="empirical", provenance_type="external_reported")
        jsonl(self.root, "results/claims.jsonl", [claim])
        result = audit_integrity.audit(self.root, "pre_review")
        self.assertEqual(result["verdict"], "pass")
        self.assertTrue(result["warnings"])
        self.assertEqual(result["coverage"]["verified_local_receipts"], 0)

    def test_local_receipt_verified_and_tampering_blocks(self):
        self.plan()
        self.run_plan()
        claim = seed_integrity(self.root)
        name = "runs/test-v1/job-0/attempt-0001/receipt.json"
        claim.update(kind="empirical", provenance_type="local_run", run_receipts=[name])
        jsonl(self.root, "results/claims.jsonl", [claim])
        result = audit_integrity.audit(self.root, "pre_review")
        self.assertEqual(result["verdict"], "pass", result["blockers"])
        self.assertEqual(result["coverage"]["verified_local_receipts"], 1)
        write_json(self.root / "runs/test-v1/job-0/attempt-0001/metrics.json", {"metrics": {"score": 1}})
        self.assertEqual(audit_integrity.audit(self.root, "pre_review")["verdict"], "fail")

    def test_local_input_change_blocks_audit(self):
        self.plan()
        self.run_plan()
        claim = seed_integrity(self.root)
        claim.update(kind="empirical", provenance_type="local_run",
                     run_receipts=["runs/test-v1/job-0/attempt-0001/receipt.json"])
        jsonl(self.root, "results/claims.jsonl", [claim])
        (self.root / "src/train.py").write_text("# modified", encoding="utf-8")
        self.assertEqual(audit_integrity.audit(self.root, "pre_review")["verdict"], "fail")

    def test_missing_claim_population_cannot_pass(self):
        seed_integrity(self.root)
        jsonl(self.root, "results/claims.jsonl", [])
        self.assertEqual(audit_integrity.audit(self.root, "pre_review")["verdict"], "fail")

    def test_passport_reports_stale_material(self):
        helper = ProjectTests.report
        pipeline.checkpoint(self.root, "scope", helper(self, "scope"))
        first = pipeline.passport(self.root)
        self.assertEqual(first["valid_stages"], ["scope"])
        self.assertIn("research/scope.md", first["artifact_hashes"])
        (self.root / "research/scope.md").write_text("changed", encoding="utf-8")
        second = pipeline.passport(self.root)
        self.assertIn("scope", second["invalid_stages"])

    def test_review_gate_requires_integrity(self):
        for stage in pipeline.STAGES[:10]:
            pipeline.checkpoint(self.root, stage, ProjectTests.report(self, stage))
        report_path = ProjectTests.report(self, "review")
        report = read_json(self.root / report_path)
        del report["integrity_report"]
        write_json(self.root / report_path, report)
        with self.assertRaisesRegex(ValueError, "requires integrity_report"):
            pipeline.checkpoint(self.root, "review", report_path)

    def test_legacy_review_receipt_requires_revalidation(self):
        for stage in pipeline.STAGES[:-1]:
            pipeline.checkpoint(self.root, stage, ProjectTests.report(self, stage))
        path = self.root / "research/state.json"
        state = read_json(path)
        del state["checkpoints"]["review"]["integrity_report"]
        write_json(path, state)
        self.assertIn("review", pipeline.status(self.root)["invalid_stages"])

    def test_integrity_report_phase_cannot_be_swapped(self):
        seed_integrity(self.root)
        audit_integrity.audit(self.root, "final")
        with self.assertRaisesRegex(ValueError, "passing report"):
            pipeline.integrity_artifacts(self.root, "research/integrity-final.json", "pre_review")


if __name__ == "__main__":
    unittest.main()
