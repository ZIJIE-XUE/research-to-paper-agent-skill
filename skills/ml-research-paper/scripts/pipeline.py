"""Initialize research workspaces and record evidence-backed stage checkpoints."""
import argparse
import json
from pathlib import Path
from common import ProjectLock, inside, inventory, now, object_hash, read_json, write_json

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
            matches = inventory(root, receipt["artifacts"]) == receipt["artifacts"]
        except ValueError:
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
    for action in ("init", "status", "checkpoint"):
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
