# ML Research & Paper v1.1.1 — Public launch compatibility fix

The first public CI run exposed a Windows path-alias issue: a temporary directory may appear as both an 8.3 short path and a full path. Integrity-report binding now resolves the project root before computing relative artifact paths.

- Fix equivalent-path handling in integrity reports.
- Add a regression test that exercises a noncanonical project path.
- Retain the MIT license, bilingual README, offline demo and public CI introduced with the public launch.

Try it with Python 3.10+:

```bash
git clone https://github.com/ZIJIE-XUE/research-to-paper-agent-skill.git
cd research-to-paper-agent-skill
python examples/quick_demo.py
```

The demo needs no extra packages, API key or dataset download. It validates the local tool chain using synthetic data; it is not a real study or evidence of scientific correctness.

Existing projects keep their files and checkpoint format. Updating the skill does not switch the current agent's model.
