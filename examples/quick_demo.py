"""Offline synthetic classification demo. Standard library only; no model API."""
import argparse
import csv
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/ml-research-paper/scripts"))
from common import read_json, write_json
import pipeline
import run_experiments
import audit_integrity

TRAINER = '''import argparse,csv,json,math,platform,random
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--data');p.add_argument('--model',choices=['majority','centroid']);p.add_argument('--seed',type=int);p.add_argument('--output-dir')
a=p.parse_args();out=Path(a.output_dir)
with open(a.data,encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
random.Random(a.seed).shuffle(train)
features=lambda r:[float(r[k]) for k in ('x1','x2','x3')]
label=lambda r:int(r['label'])
majority=max((0,1),key=lambda c:sum(label(r)==c for r in train))
centroids={c:[sum(features(r)[j] for r in train if label(r)==c)/sum(label(r)==c for r in train) for j in range(3)] for c in (0,1)}
predictions=[]
for row in test:
 pred=majority if a.model=='majority' else min((0,1),key=lambda c:sum((x-y)**2 for x,y in zip(features(row),centroids[c])))
 predictions.append((row['id'],label(row),pred))
accuracy=sum(y==p for _,y,p in predictions)/len(predictions)
(out/'metrics.json').write_text(json.dumps({'metrics':{'test_accuracy':accuracy},'model':a.model,'seed':a.seed,'scope':'synthetic tool demo'}),encoding='utf-8')
with (out/'predictions.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['id','true','predicted']);w.writerows(predictions)
(out/'environment.json').write_text(json.dumps({'python':platform.python_version(),'dependencies':'standard library only'}),encoding='utf-8')
'''


def jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(ROOT / "work/demo"), help="Fresh output directory; existing files are never overwritten")
    args = parser.parse_args()
    root = Path(args.project).resolve()
    if root.exists() and any(root.iterdir()):
        parser.error("Use a fresh --project directory; the demo will not overwrite existing work")
    pipeline.init(root)
    project = read_json(root / "research/project.json")
    project.update(title="Offline synthetic classification tool demo", task_type="classification",
                   research_question="Does the local tool chain preserve and audit synthetic task outputs?")
    write_json(root / "research/project.json", project)
    rng = random.Random(17)
    dataset = root / "data/processed/synthetic.csv"
    with dataset.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "split", "x1", "x2", "x3", "label"])
        for split, size in (("train", 120), ("test", 40)):
            for index in range(size):
                label = index % 2
                values = [rng.gauss((2 * label - 1) * 0.8, 1.0) for _ in range(3)]
                writer.writerow([f"{split}-{index}", split, *values, label])
    (root / "src/train.py").write_text(TRAINER, encoding="utf-8")
    (root / "experiments/protocol.md").write_text(
        "# Synthetic software demo\n\nFixed seed 17; 120 train and 40 test rows; "
        "three generated features. Majority and nearest-centroid classifiers, ordering seeds 0/1. "
        "Primary output: test accuracy. Both estimators are deterministic apart from immaterial "
        "training-row order. These seeds are tool checks, not independent scientific replications. "
        "No hyperparameter selection, literature search or real study is performed.\n", encoding="utf-8")
    jobs = []
    for model in ("majority", "centroid"):
        for seed in (0, 1):
            jobs.append({"id": f"{model}-{seed}", "command": ["{python}", "{project}/src/train.py",
                         "--data", "{project}/data/processed/synthetic.csv", "--model", model,
                         "--seed", str(seed), "--output-dir", "{run_dir}"], "timeout_seconds": 20,
                         "required_outputs": ["metrics.json", "predictions.csv", "environment.json"]})
    plan = {"experiment_id": "synthetic-demo-v1", "protocol": "experiments/protocol.md",
            "inputs": ["experiments/protocol.md", "src/train.py", "data/processed/synthetic.csv"],
            "max_jobs": 4, "max_total_seconds": 90, "jobs": jobs}
    write_json(root / "experiments/plan.json", plan)
    summary = run_experiments.run(root, "experiments/plan.json")
    if summary["status"] != "complete":
        raise RuntimeError("Demo queue failed; inspect runs/synthetic-demo-v1/summary.json")
    reused = run_experiments.run(root, "experiments/plan.json")
    if not all(job["status"] == "reused_verified" for job in reused["jobs"]):
        raise RuntimeError("Demo reuse verification failed")
    claims, display = [], []
    for index, job in enumerate(jobs, 1):
        run = f"runs/synthetic-demo-v1/{job['id']}/attempt-0001"
        metrics = read_json(root / run / "metrics.json")["metrics"]
        text = f"{job['id']}: test accuracy = {metrics['test_accuracy']:.3f} on the fixed synthetic split."
        display.append(text)
        claims.append({"id": f"C{index:03d}", "claim": text, "kind": "empirical", "status": "supported",
                       "scope": "Synthetic software demonstration only", "provenance_type": "local_run",
                       "run_receipts": [run + "/receipt.json"], "reference_ids": [],
                       "evidence": [{"path": run + "/metrics.json", "locator": "metrics.test_accuracy"}]})
    jsonl(root / "results/claims.jsonl", claims)
    jsonl(root / "literature/records.jsonl", [])
    jsonl(root / "literature/citation-checks.jsonl", [])
    jsonl(root / "reviews/issues.jsonl", [])
    (root / "manuscript/draft.md").write_text(
        "# Synthetic software demonstration\n\n" + "\n\n".join(display) +
        "\n\nThis is not a scientific paper or evidence of real-world performance.\n", encoding="utf-8")
    report = audit_integrity.audit(root, "pre_review")
    if report["verdict"] != "pass":
        raise RuntimeError("Audit failed: " + json.dumps(report["blockers"]))
    pipeline.passport(root)
    print("\n".join(display))
    print("\n4 jobs completed; 4 outputs verified and reused; registered-object audit passed.")
    print("Output:", root)
    print("Research phases were not performed; the project remains at scope.")


if __name__ == "__main__":
    main()
