# Public launch copy / 公开介绍文案

本文件保留通用介绍草稿。2026-11-04已在三个相关社区的展示区发布定制介绍，见 [发布记录与帖子链接](outreach/README.md)。继续使用草稿时，应核对目标社区当时的自荐规则。

## 中文：研究者/开发者社区

标题：我把“机器学习研究到论文”的流程做成了一条可复用 AI agent skill

做机器学习研究时，我希望文献、实验和论文之间能保持一条能核对的证据链。于是整理了 `ml-research-paper`：从文献搜集和阅读、创新点检查、实验设计与运行，到写作、审稿和反复修订，都能从指定阶段进入。

它附带几组本地 Python 工具：冻结实验输入、限制运行预算、保留失败日志、验证续跑结果，并检查论文里登记的主张能否追踪到文献或实验产物。模型负责理解和判断，脚本负责明确可检查的部分。

仓库已经公开，采用 MIT 许可。有一个不用 API Key、不装额外包的合成分类示例，克隆后运行 `python examples/quick_demo.py` 就能试工具链。完整研究仍需要合适的agent、实际材料和作者判断，不保证创新或录用。

目前最想听的是：你的研究流程最容易在哪一步断开？欢迎拿一个公开或合成的小例子提问题，也欢迎改进不同任务的实验协议。

[仓库与示例](https://github.com/ZIJIE-XUE/research-to-paper-agent-skill)

## English: developer / research tooling community

Title: An agent skill connecting ML experiments to manuscript evidence

I made my machine learning research-to-paper workflow public as an agent skill. It covers literature, research questions, experiment design and execution, writing, and revision, with entry points for individual stages.

The practical part is a small set of local Python tools: freeze experiment inputs, run bounded queues, keep failed jobs, verify reused outputs, and trace registered manuscript claims back to source files or execution receipts. The agent still judges sources and scientific meaning; the scripts check the things they can actually verify.

There is a standard-library-only synthetic classification demo: clone the repo and run `python examples/quick_demo.py`. It needs no model API key or dataset download. The full workflow does require an agent and real research inputs. Internal AI review is not independent human peer review.

MIT-licensed, with English and Chinese entry docs. I'd appreciate feedback on reproducibility, handoffs between stages, and task-specific leakage checks.

[Repository](https://github.com/ZIJIE-XUE/research-to-paper-agent-skill)

## Short English post

Made my ML research-to-paper agent skill public: literature, bounded local experiments, evidence-linked claims and revision. MIT; offline Python demo needs no API key. Feedback welcome: https://github.com/ZIJIE-XUE/research-to-paper-agent-skill

## 发布后的观察

先分享一个能实际复现的例子与遇到的问题，邀请具体反馈。收到问题后在Issues中公开答复并修正文档。隔一段时间在GitHub Traffic中比较访客、克隆、来源与后续反馈；这些指标会波动，不能把一次分享后的变化都归因于某个标签或标题。

不要购买浏览、互刷Star、编造使用者或声称已经得到第三方学术验证。后续发布优先提供新的可运行示例和真实改进。

## 渠道限制

未向Hacker News自动发帖；其 [当前规则](https://news.ycombinator.com/newsguidelines.html) 明确禁止自动发帖和生成式/AI编辑文字。以上英文草稿不应原样代发到HN。
