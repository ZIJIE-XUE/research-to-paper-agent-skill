"""Audit registered claim/citation provenance; does not judge scientific truth."""
import argparse
import json
from pathlib import Path
from common import digest, inside, inventory, now, object_hash, read_json, write_json
from run_experiments import finite_metrics, validate_plan


def audit(project, phase, manuscript="manuscript/draft.md"):
    root = Path(project).resolve()
    hashes, blockers, warnings = {}, [], []

    def remember(name, nonempty=True):
        path = inside(root, name)
        if not path.is_file() or (nonempty and not path.stat().st_size):
            raise ValueError("Missing or empty material: " + str(name))
        hashes[path.relative_to(root).as_posix()] = digest(path)
        return path

    def ledger(name):
        rows, seen = [], set()
        try:
            path = remember(name, nonempty=False)
            for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or row["id"] in seen:
                    raise ValueError(f"Invalid/duplicate id at {name}:{number}")
                seen.add(row["id"])
                rows.append(row)
        except (OSError, ValueError, TypeError) as error:
            blockers.append(str(error))
        return rows

    def evidence(entries):
        if not isinstance(entries, list) or not entries:
            raise ValueError("Claim needs evidence with path and locator")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("locator"), str) or not entry["locator"].strip():
                raise ValueError("Evidence needs an explicit locator")
            remember(entry["path"])

    try:
        remember(manuscript)
    except (OSError, ValueError) as error:
        blockers.append(str(error))
    claims = ledger("results/claims.jsonl")
    references = ledger("literature/records.jsonl")
    checks = ledger("literature/citation-checks.jsonl")
    if not claims:
        blockers.append("No registered claims; completeness cannot be assessed")
    ref_ids = {r["id"] for r in references}
    claim_ids = {c["id"] for c in claims}
    by_pair = {}
    for row in checks:
        pair = (row.get("claim_id"), row.get("reference_id"))
        if pair in by_pair or pair[0] not in claim_ids or pair[1] not in ref_ids:
            blockers.append("Duplicate/orphan citation check: " + row["id"])
        by_pair[pair] = row
    citation_pairs = set()
    verified_receipts = set()
    checked_claims = 0
    for claim in claims:
        try:
            if not isinstance(claim.get("claim"), str) or not claim["claim"].strip() or not claim.get("scope"):
                raise ValueError("Claim text and scope are required")
            if claim.get("kind") not in ("empirical", "literature", "theoretical", "interpretive"):
                raise ValueError("Unknown claim kind")
            if claim.get("status") != "supported":
                raise ValueError("Registered assertion is not supported; qualify wording or supply evidence")
            evidence(claim.get("evidence"))
            reference_ids = claim.get("reference_ids", [])
            if not isinstance(reference_ids, list) or len(set(reference_ids)) != len(reference_ids):
                raise ValueError("reference_ids must be a unique list")
            if claim["kind"] == "literature" and not reference_ids:
                raise ValueError("Literature claim has no reference_ids")
            for ref_id in reference_ids:
                pair = (claim["id"], ref_id)
                citation_pairs.add(pair)
                check = by_pair.get(pair)
                if ref_id not in ref_ids or not check:
                    raise ValueError("Missing reference or citation check: " + str(ref_id))
                if any(check.get(k) != v for k, v in (("existence", "verified"), ("metadata", "verified"), ("support", "supported"))):
                    raise ValueError("Citation existence/metadata/support unresolved: " + str(ref_id))
                if not check.get("locator") or not check.get("checked_at") or not check.get("method"):
                    raise ValueError("Citation check needs locator, checked_at and method")
                if not isinstance(check.get("evidence"), list) or not check["evidence"]:
                    raise ValueError("Citation check needs actual source evidence")
                for name in check["evidence"]:
                    remember(name)
            if claim["kind"] == "empirical":
                origin = claim.get("provenance_type")
                if origin == "external_reported":
                    warnings.append(claim["id"] + ": external declared results; actual execution not verified")
                elif origin == "local_run" and claim.get("run_receipts"):
                    for name in claim["run_receipts"]:
                        path = remember(name)
                        receipt = read_json(path)
                        if receipt.get("status") != "success" or receipt.get("exit_code") != 0:
                            raise ValueError("Local execution receipt is not successful: " + name)
                        outputs = receipt.get("outputs", {})
                        if not outputs or inventory(path.parent, outputs) != outputs:
                            raise ValueError("Local execution outputs changed: " + name)
                        finite_metrics(path.parent / "metrics.json")
                        lock_path = path.parents[2] / "protocol.lock.json"
                        remember(lock_path.relative_to(root))
                        frozen = read_json(lock_path)
                        if object_hash(frozen) != receipt.get("fingerprint") or validate_plan(root, frozen["plan"]) != frozen:
                            raise ValueError("Frozen local inputs/protocol no longer match: " + name)
                        for output in outputs:
                            remember((path.parent / output).relative_to(root))
                        for input_name in frozen["inputs"]:
                            remember(input_name)
                        remember(frozen["plan"]["protocol"])
                        verified_receipts.add(name)
                else:
                    raise ValueError("Empirical claim needs local_run receipts or external_reported provenance")
            checked_claims += 1
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            blockers.append(claim["id"] + ": " + str(error))
    for pair in by_pair:
        if pair not in citation_pairs:
            blockers.append("Citation check is not a registered claim/reference relation: " + str(pair))
    if phase == "final":
        for issue in ledger("reviews/issues.jsonl"):
            if issue.get("severity") not in ("critical", "major", "minor", "optional") or issue.get("status") not in ("open", "resolved", "partial", "declined"):
                blockers.append("Invalid review severity/status: " + issue["id"])
            if issue.get("severity") in ("critical", "major") and issue.get("status") != "resolved":
                blockers.append("Unresolved critical/major review issue: " + issue["id"])
    report = {"schema_version": 1, "phase": phase, "created_at": now(),
              "verdict": "fail" if blockers else "pass", "scope": "Registered-object structural/provenance checks only",
              "coverage": {"registered_claims": len(claims), "claims_passing_checks": checked_claims,
                           "registered_references": len(references), "registered_citation_checks": len(checks),
                           "cited_pairs_encountered": len(citation_pairs), "verified_local_receipts": len(verified_receipts)},
              "unknown": ["Semantic extraction completeness", "Source-support judgment accuracy", "Raw-data authenticity"],
              "blockers": blockers, "warnings": warnings, "artifact_hashes": hashes}
    write_json(root / f"research/integrity-{phase}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--phase", choices=("pre_review", "final"), required=True)
    parser.add_argument("--manuscript", default="manuscript/draft.md")
    args = parser.parse_args()
    try:
        report = audit(args.project, args.phase, args.manuscript)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["verdict"] == "pass" else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
