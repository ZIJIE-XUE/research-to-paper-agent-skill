# ML Research & Paper v1.1.0 — First public release

A reusable agent skill for machine learning research, local experiments, manuscript evidence and revision.

## Start here

```bash
git clone https://github.com/ZIJIE-XUE/research-to-paper-agent-skill.git
cd research-to-paper-agent-skill
python examples/quick_demo.py
```

The offline demo uses only the Python standard library. It runs four synthetic classification tasks, verifies reuse and audits registered claims against local execution receipts. It does not call a model API or perform a real research study.

## Included

- Full research-to-paper protocol and focused modes for individual stages.
- Budgeted local experiment queue with frozen input hashes, logs and failure retention.
- Checkpoints, stale-material detection and a material passport for handoffs.
- Pre-review and final structural/provenance checks of registered evidence.
- English and Chinese entry docs, a contribution guide and MIT license.
- Behavioral tests and a public CI workflow.

## Limits

Semantic source support, scientific correctness, raw-data authenticity and complete manuscript claim extraction are not proven by the tools. Internal AI review is not independent human peer review. See the validation record and mode references for the tested scope.

Feedback and small reproducible issues are welcome at the repository's Issues page.
