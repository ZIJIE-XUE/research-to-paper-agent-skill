"""Initialize research workspaces and record evidence-backed stage checkpoints."""
import argparse
import json
from pathlib import Path
from common import ProjectLock, digest, inside, inventory, now, object_hash, read_json, write_json

STAGES = ("scope", "literature", "novelty", "framework", "data", "design",
          "experiments", "conclusions", "draft", "polish", "review", "final")
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def init(project):
    root = Path(project).resolve()
    state_path = root / "research/state.json"
    if state_path.exists() or (root / "research/project.json").exists():
        raise ValueError("Project already initialized; use status, do not overwrite")
    for directory in ("research/gates", "literature", "data/raw", "data/processed",
                      "experiments", "src", "results", "manuscript/versions",
                      "reviews", "delivery"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    # Exclusive writes preserve pre-existing user artifacts, even in partial setups.
    for destination, source in (("research/project.json", "project.json"),
                                ("experiments/plan.example.json", "plan.example.json")):
        with (root / destination).open("x", encoding="utf-8") as out:
            out.write((ASSETS / source).read_text(encoding="utf-8"))
    handoff = root / "research/handoff.md"
    if not handoff.exists():
        handoff.write_text("# Research handoff\n\nStatus: initialized.\n"
                           "Next: inspect existing materials and fill research/project.json.\n",
                           encoding="utf-8")
    write_json(state_path, {"schema_version": 1, "created_at": now(),
                            "checkpoints": {}, "history": []})
    return {"project": str(root), "next_stage": "scope"}


def valid_stages(root, state):
    """A changed upstream artifact invalidates every downstream active receipt."""
    valid, invalid = {}, {}
    upstream_valid = True
    for stage in STAGES:
        receipt = state["checkpoints"].get(stage)
        if not receipt:
            upstream_valid = False
            continue
        try:
            matches = all(inside(root, name).is_file() and digest(inside(root, name)) == expected
                          for name, expected in receipt["artifacts"].items())
            if stage in ("review", "final") and not receipt.get("integrity_report"):
                matches = False  # v1.0 receipts remain historical, not current v1.1 gates.
        except (OSError, ValueError):
            matches = False
        upstream = {s: object_hash(valid[s]) for s in STAGES[:STAGES.index(stage)] if s in valid}
        if upstream_valid and matches and receipt["upstream"] == upstream:
            valid[stage] = receipt
        else:
            invalid[stage] = "Changed/missing artifact or invalid upstream checkpoint"
            upstream_valid = False
    return valid, invalid


def status(project):
    root = Path(project).resolve()
    state = read_json(root / "research/state.json")
    valid, invalid = valid_stages(root, state)
    return {"valid_stages": list(valid), "invalid_stages": invalid,
            "next_stage": next((s for s in STAGES if s not in valid), None),
            "review_verdict": valid.get("review", {}).get("verdict"),
            "note": "Structural provenance checks only; not a scientific quality certificate."}


def integrity_artifacts(root, name, phase):
    """Bind the integrity report AND every material that report actually checked."""
    if not isinstance(name, str) or not name:
        raise ValueError("review/final checkpoint requires integrity_report")
    path = inside(root, name)
    report = read_json(path)
    if report.get("phase") != phase or report.get("verdict") != "pass" or report.get("blockers"):
        raise ValueError("Integrity report is not a passing report for " + phase)
    hashes = report.get("artifact_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("Integrity report has no bound materials")
    for artifact, expected in hashes.items():
        target = inside(root, artifact)
        if not target.is_file() or digest(target) != expected:
            raise ValueError("Integrity report is stale: " + artifact)
    return {**hashes, path.relative_to(root).as_posix(): digest(path)}


def passport(project):
    root = Path(project).resolve()
    with ProjectLock(root / "research/.checkpoint.lock"):
        state = read_json(root / "research/state.json")
        valid, invalid = valid_stages(root, state)
        names = {"research/state.json", "research/project.json"}
        for receipt in valid.values():
            names.update(receipt["artifacts"])
        for name in ("research/handoff.md", "research/process-record.md", "literature/records.jsonl",
                     "literature/citation-checks.jsonl", "results/claims.jsonl", "reviews/issues.jsonl",
                     "research/integrity-pre_review.json", "research/integrity-final.json",
                     "data/manifest.json", "experiments/plan.json", "experiments/protocol.md"):
            if inside(root, name).is_file():
                names.add(name)
        for path in (root / "runs").glob("*/summary.json"):
            names.add(path.relative_to(root).as_posix())
        material_hashes = {name: digest(inside(root, name)) for name in sorted(names)}
        result = {"schema_version": 1, "created_at": now(), "valid_stages": list(valid),
                  "invalid_stages": invalid, "next_stage": next((s for s in STAGES if s not in valid), None),
                  "artifact_hashes": material_hashes,
                  "scope": "Material inventory only; not execution isolation or a scientific certificate"}
        write_json(root / "research/passport.json", result)
        return result


def checkpoint(project, stage, report_name):
    root = Path(project).resolve()
    with ProjectLock(root / "research/.checkpoint.lock"):
        state = read_json(root / "research/state.json")
        report_path = inside(root, report_name)
        report = read_json(report_path)
        verdict = report.get("verdict")
        if report.get("stage") != stage or verdict not in ("pass", "revise"):
            raise ValueError("Report must name the stage and verdict pass/revise")
        if verdict == "revise" and stage != "review":
            raise ValueError("Only review may record verdict revise")
        checks = report.get("checks", [])
        if not checks or not all(isinstance(c, dict) and c.get("name") and
                                  c.get("status") in ("pass", "not_applicable")
                                  and c.get("note") for c in checks):
            raise ValueError("Every check needs name, pass/not_applicable status and explanatory note")
        evidence = list(report.get("artifacts", []))
        for check in checks:
            paths = check.get("evidence", [])
            if check["status"] == "pass" and not paths:
                raise ValueError("A passed check requires evidence paths")
            evidence.extend(paths)
        if not evidence:
            raise ValueError("A stage requires substantive artifacts")
        artifacts = inventory(root, evidence + [report_name])
        if stage in ("review", "final"):
            phase = "pre_review" if stage == "review" else "final"
            artifacts.update(integrity_artifacts(root, report.get("integrity_report"), phase))
        valid, _ = valid_stages(root, state)
        index = STAGES.index(stage)
        required = STAGES[:index]
        if any(s not in valid for s in required):
            raise ValueError("Missing/stale earlier stages; inspect status first")
        if stage == "final" and valid["review"]["verdict"] != "pass":
            raise ValueError("Review requires revision; final cannot pass")
        receipt = {"stage": stage, "time": now(), "verdict": verdict,
                   "artifacts": artifacts,
                   "upstream": {s: object_hash(valid[s]) for s in required}}
        if stage in ("review", "final"):
            receipt["integrity_report"] = report["integrity_report"]
        invalidated = []
        for later in STAGES[index:]:
            previous = state["checkpoints"].pop(later, None)
            if previous:
                state["history"].append(previous)
                invalidated.append(later)
        state["checkpoints"][stage] = receipt
        write_json(root / "research/state.json", state)
        return {"recorded": stage, "verdict": verdict, "invalidated": invalidated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("init", "status", "passport", "checkpoint"):
        cmd = commands.add_parser(action)
        cmd.add_argument("--project", required=True)
        if action == "checkpoint":
            cmd.add_argument("--stage", choices=STAGES, required=True)
            cmd.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        result = (checkpoint(args.project, args.stage, args.report)
                  if args.action == "checkpoint" else globals()[args.action](args.project))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
