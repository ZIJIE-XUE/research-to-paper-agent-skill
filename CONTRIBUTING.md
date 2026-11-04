# Contributing

Thanks for trying ML Research & Paper. Small, reproducible improvements are welcome.

## Useful contributions

- Report a failure with a minimal public or synthetic example.
- Improve task-specific research protocols, particularly leakage checks and fair baselines.
- Improve English/Chinese instructions without adding unsupported capability claims.
- Add meaningful tests for provenance, execution or checkpoint failure cases.
- Share a reproducible example with clear data permissions and honest limitations.

## Before opening a pull request

1. Explain the problem and the resulting behavior. Keep one change focused.
2. Run `python -m unittest discover -s tests -v`.
3. If execution/provenance behavior changes, also run `python examples/quick_demo.py --project work/contribution-demo` with a fresh output path.
4. Keep documents and actual behavior aligned. Do not describe an agent protocol as a mechanically enforced guarantee.
5. Do not commit credentials, private manuscripts, restricted datasets, generated study outputs or personal paths.

Report bugs through [Issues](https://github.com/ZIJIE-XUE/research-to-paper-agent-skill/issues). Include Python/OS, the command or mode, expected behavior and the smallest relevant error. Please use synthetic examples instead of uploading confidential research.

This repository is MIT-licensed. Contributions should be your own work or material you are authorized to contribute under compatible terms. Third-party datasets and papers keep their own licenses.
