"""Run a bounded, frozen queue of project-specific commands without a shell."""
import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from common import ProjectLock, digest, inside, inventory, now, object_hash, read_json, write_json


def finite_metrics(path):
    value = read_json(path)
    metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
    if not metrics or not all(isinstance(v, (float, int)) and not isinstance(v, bool)
                              and math.isfinite(v) for v in metrics.values()):
        raise ValueError("metrics.json requires a nonempty metrics object of finite numeric scalars")


def stop_tree(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def validate_plan(root, plan):
    experiment = plan.get("experiment_id", "")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", experiment):
        raise ValueError("Invalid experiment_id")
    jobs = plan.get("jobs", [])
    limit = plan.get("max_jobs")
    total = plan.get("max_total_seconds")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or not jobs or len(jobs) > limit:
        raise ValueError("Empty queue or invalid/exceeded max_jobs")
    if not isinstance(total, (int, float)) or isinstance(total, bool) or not math.isfinite(total) or total <= 0:
        raise ValueError("max_total_seconds must be finite and positive")
    identifiers = set()
    for job in jobs:
        name = job.get("id", "")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name) or name in identifiers:
            raise ValueError("Invalid or duplicate job id")
        identifiers.add(name)
        command = job.get("command", [])
        if not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError("command must be a nonempty argv string array")
        timeout = job.get("timeout_seconds")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        outputs = job.get("required_outputs", [])
        if "metrics.json" not in outputs or len(set(outputs)) != len(outputs):
            raise ValueError("required_outputs must include metrics.json without duplicates")
        for name in outputs:
            inside(root, name)
    protocol = inside(root, plan["protocol"])
    if not protocol.is_file() or not protocol.stat().st_size:
        raise ValueError("Missing protocol")
    # List all experiment-relevant code, configs, splits and data, not generated outputs.
    inputs = inventory(root, plan.get("inputs", []))
    return {"plan": plan, "inputs": inputs, "protocol_sha256": digest(protocol)}


def validate_receipt_identity(path, receipt, job_id, fingerprint):
    if receipt.get("job_id") != job_id:
        raise ValueError(f"Receipt job ID mismatch at {path}: expected {job_id!r}, found {receipt.get('job_id')!r}")
    if receipt.get("fingerprint") != fingerprint:
        raise ValueError(f"Receipt does not match the frozen experiment: {path}")


def verified_success(run_dir, receipt):
    try:
        return (receipt["status"] == "success" and receipt["outputs"] and
                inventory(run_dir, receipt["outputs"]) == receipt["outputs"])
    except (ValueError, KeyError, TypeError):
        return False


def run(project, plan_name):
    root = Path(project).resolve()
    plan = read_json(inside(root, plan_name))
    frozen = validate_plan(root, plan)
    fingerprint = object_hash(frozen)
    base = inside(root, "runs/" + plan["experiment_id"])
    base.mkdir(parents=True, exist_ok=True)
    with ProjectLock(base / ".lock"):
        lock_path = base / "protocol.lock.json"
        if lock_path.exists():
            if object_hash(read_json(lock_path)) != fingerprint:
                raise ValueError("Frozen plan/protocol/input changed; create a new experiment_id")
        else:
            write_json(lock_path, frozen)
        budget_path = base / "budget.json"
        budget = read_json(budget_path) if budget_path.exists() else {"spent_seconds": 0.0}
        summary = {"experiment_id": plan["experiment_id"], "fingerprint": fingerprint,
                   "started_at": now(), "jobs": [], "status": "complete"}
        for job in plan["jobs"]:
            job_root = base / job["id"]
            job_root.mkdir(exist_ok=True)
            previous = sorted(job_root.glob("attempt-*/receipt.json"))
            receipts = [read_json(p) for p in previous]
            for path, receipt in zip(previous, receipts):
                if receipt.get("status") == "success":
                    validate_receipt_identity(path, receipt, job["id"], fingerprint)
            success = next(((p, r) for p, r in zip(previous, receipts)
                            if verified_success(p.parent, r)), None)
            if success:
                summary["jobs"].append({"id": job["id"], "status": "reused_verified",
                                        "receipt": str(success[0].relative_to(root))})
                continue
            if any(r.get("status") == "success" for r in receipts):
                raise ValueError("Successful output changed/missing; preserve it and use a new experiment_id")
            # A failed/timeout/aborted job is not silently retried on resume.
            if previous or list(job_root.glob("attempt-*")):
                summary["jobs"].append({"id": job["id"], "status": "needs_attention"})
                summary["status"] = "incomplete"
                continue
            remaining = plan["max_total_seconds"] - budget["spent_seconds"]
            if remaining <= 0:
                summary["status"] = "budget_exhausted"
                break
            run_dir = job_root / "attempt-0001"
            run_dir.mkdir()
            replacements = {"{python}": sys.executable, "{project}": str(root),
                            "{run_dir}": str(run_dir)}
            command = []
            for arg in job["command"]:
                for key, value in replacements.items():
                    arg = arg.replace(key, value)
                command.append(arg)
            receipt = {"job_id": job["id"], "status": "running", "command": command,
                       "started_at": now(), "fingerprint": fingerprint,
                       "python": sys.version, "platform": sys.platform,
                       "timeout_seconds": min(job["timeout_seconds"], remaining)}
            write_json(run_dir / "receipt.json", receipt)
            write_json(run_dir / "job.json", job)
            started = time.monotonic()
            # Reserve maximum permitted time before launch: interruption cannot reset budget.
            budget["spent_seconds"] += receipt["timeout_seconds"]
            write_json(budget_path, budget)
            process = None
            try:
                with (run_dir / "stdout.log").open("wb") as out, (run_dir / "stderr.log").open("wb") as err:
                    kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                              if os.name == "nt" else {"start_new_session": True})
                    process = subprocess.Popen(command, cwd=run_dir, stdout=out, stderr=err, **kwargs)
                    receipt["pid"] = process.pid
                    write_json(run_dir / "receipt.json", receipt)
                    try:
                        receipt["exit_code"] = process.wait(timeout=receipt["timeout_seconds"])
                    except subprocess.TimeoutExpired:
                        stop_tree(process)
                        receipt["exit_code"] = process.returncode
                        receipt["status"] = "timeout"
                if receipt["status"] != "timeout":
                    if receipt["exit_code"] != 0:
                        receipt["status"] = "failed"
                    else:
                        receipt["outputs"] = inventory(run_dir, job["required_outputs"])
                        finite_metrics(run_dir / "metrics.json")
                        receipt["status"] = "success"
            except KeyboardInterrupt:
                if process and process.poll() is None:
                    stop_tree(process)
                receipt["status"] = "interrupted"
            except (OSError, ValueError, TypeError, KeyError) as error:
                receipt["status"] = "failed"
                receipt["error"] = str(error)
            finally:
                elapsed = time.monotonic() - started
                budget["spent_seconds"] += elapsed - receipt["timeout_seconds"]
                write_json(budget_path, budget)
                receipt["elapsed_seconds"] = elapsed
                receipt["finished_at"] = now()
                write_json(run_dir / "receipt.json", receipt)
            summary["jobs"].append({"id": job["id"], "status": receipt["status"],
                                    "receipt": str((run_dir / "receipt.json").relative_to(root))})
            if receipt["status"] != "success":
                summary["status"] = "incomplete"
            if receipt["status"] == "interrupted":
                break
        # Detect accidental writes to frozen code/data during execution.
        if object_hash(validate_plan(root, plan)) != fingerprint:
            summary["status"] = "input_mutated"
        summary["finished_at"] = now()
        summary["spent_seconds"] = budget["spent_seconds"]
        write_json(base / "summary.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--plan", default="experiments/plan.json")
    args = parser.parse_args()
    try:
        summary = run(args.project, args.plan)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["status"] == "complete" else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
