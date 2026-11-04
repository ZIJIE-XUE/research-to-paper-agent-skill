# A research skill with source-bound checkpoints and an offline demo (MIT)

I'm sharing [ML Research & Paper](https://github.com/ZIJIE-XUE/research-to-paper-agent-skill), an independent skill for ML research, local experiments and manuscript revision. I maintain the repo and would appreciate feedback on the **skill/tool boundary and portability**.

The package uses one `SKILL.md`, focused reference files and standard-library Python helpers. The agent chooses the task-specific research method and implements training/analysis code; the helpers handle bounded execution, immutable input manifests, output receipts and checkpoint hashes. They make no model API calls.

One concrete design choice: a passing integrity report is bound to the exact files it checked. The corresponding review/final checkpoint includes those evidence hashes. A stale report cannot be reused after the cited material changes. A material passport exports the current file/version inventory for a later session; it is our own handoff format, not a proposed standard or an assertion of compatibility with another project's schema.

To evaluate the tools without setting up an agent:

```bash
git clone https://github.com/ZIJIE-XUE/research-to-paper-agent-skill.git
cd research-to-paper-agent-skill
python examples/quick_demo.py
```

The demo creates synthetic classification data, runs four local tasks, verifies result reuse and audits registered claims against their receipts. It uses Python 3.10+ with no additional dependencies. Windows/Ubuntu CI covers 28 tests plus the demo.

The boundaries matter: hashes don't validate scientific meaning, a completed queue isn't a correct study, and the scripts aren't permission/network isolation. Full research needs an agent, actual materials and author judgment. The documented installation targets Codex; other hosts need their own testing. Entry docs are English/Chinese, with most detailed protocols still Chinese.

Questions for skill authors:

1. Would you keep protocol instructions and deterministic artifact validation in this shape, or separate their entry points further?
2. What minimal provenance should a receiving host verify before trusting a handoff?
3. If you try this on a different skill host, which instructions or path assumptions break?

Disclosure: this is my project and the implementation/docs/post were prepared with AI assistance. I'm sharing a concrete implementation for feedback, not claiming conformance certification or measured reviewer accuracy.
