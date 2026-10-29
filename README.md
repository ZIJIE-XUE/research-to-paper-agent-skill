# 机器学习研究及论文生成 Skill

面向可复用的机器学习研究：文献搜集与阅读 → 研究问题与创新检验 → 框架与初稿 → 数据获取 → 实验设计 → 自动运行 → 证据解释 → 正式拟稿 → 润色 → 审稿 → 修订与复审 → 交付。

技能名：`ml-research-paper`。适用于分类、回归、时间序列预测、表格学习、计算机视觉、自然语言处理及其他能够明确数据、任务和评价协议的机器学习实证研究。它不内置某篇论文的数据、模型、领域指标或结论。

这是由 AI agent 执行的技能包，附带确定性的项目初始化、检查点与实验运行工具。Python 工具不调用语言模型；文献理解、选题、实验实现、写作和审稿由加载技能的 agent 完成。它不保证创新、正结果、论文录用，也不会在聊天结束后自行持续运行。

## 安装

需要 Git、Python 3.10+，以及支持 `SKILL.md` 的 agent。实验所需库由各研究项目单独管理。

```powershell
git clone https://github.com/ZIJIE-XUE/research-to-paper-agent-skill.git
$skillSource = Join-Path (Get-Location) 'research-to-paper-agent-skill/skills/ml-research-paper'
$skillTarget = Join-Path $env:USERPROFILE '.codex/skills/ml-research-paper'
# 首次安装，目标目录应不存在；更新前先比较并备份自己的修改。
Copy-Item -LiteralPath $skillSource -Destination $skillTarget -Recurse
```

其他 agent 可将同一技能目录放入其支持的技能发现路径。私有仓库需要已获授权的 GitHub 登录。

## 使用

在研究项目所在目录打开一个新聊天，例如：

> 使用 $ml-research-paper，研究小样本表格分类中的类别不平衡问题。从文献搜集开始，找出可检验的研究问题，在现有电脑上设计并运行实验，形成中文论文。总实验预算先设为 2 小时，只使用可合法取得的公开数据。

> 使用 $ml-research-paper，继续这个项目。先读取 research/state.json 和最近的检查点，复核当前结果后进入下一阶段。

> 使用 $ml-research-paper，只审稿当前论文：核查文献、数据划分、基线公平性、结果与结论，并输出可执行的修改清单。

可以从任一阶段进入。已有材料先核验，缺什么补什么；不会为了从头走流程重复下载和重跑。默认单代理分阶段工作。仅在用户或运行环境明确授权时采用子代理，并记录审查方式。

## 自动化边界

技能将完整工作流写入 [SKILL.md](skills/ml-research-paper/SKILL.md)，并按阶段加载参考文件。初始化和断点工具见 [pipeline.py](skills/ml-research-paper/scripts/pipeline.py)，实验队列工具见 [run_experiments.py](skills/ml-research-paper/scripts/run_experiments.py)。

实验运行器支持串行队列、总时限、单任务超时、输入/协议哈希、失败回执、输出校验和安全续跑。训练程序由 agent 为具体课题实现；运行器不会自动猜测模型、数据集或主要指标。测试样本不可用于选模型或调参。写作中的数值必须能够回到实际输出。

自动推进以现有授权和计算预算为界。遇到数据不可得、许可受限、预算不足或科学证据不足时保存成果与明确缺口。常规内部阶段无需逐步批准；付费资源、正式投稿、对外联系和另行公开材料遵循用户授权。

模型可由用户选择。此版按 GPT-6.1 Sol 与极高推理的使用需求设计，技能不会自行切换当前聊天的模型。模型选择不替代检索、实验、检查和作者判断。

## 验证

```powershell
python -m unittest discover -s tests -v
```

测试覆盖检查点失效、路径边界、实验失败/超时、输入变更、输出篡改、续跑与预算。合成演示仅检验工具链，不作为任何实证研究结论。

版本：1.0.0。仓库仅包含通用技能、模板、工具和测试，不包含用于提炼经验的私人论文、文献全文、研究数据或个人凭据。
