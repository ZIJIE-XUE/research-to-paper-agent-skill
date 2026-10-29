# 快速使用指南

## 选择入口

在研究目录打开聊天，说明方向、已有材料、数据/算力、语言和预算；不清楚创新点也可开始。

```text
使用 $ml-research-paper，mode=plan。
我关注时间序列预测的跨数据集泛化，只有一台普通电脑。
先检查已有文献和数据，再把问题收敛为可执行的小规模研究。
```

完整流程使用pipeline；仅审稿使用review。无需为单阶段任务登记虚假的全流程状态。

## 工具命令

agent通常会代为执行。在PowerShell手动查看时：

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex/skills/ml-research-paper'
$projectDir = (Get-Location).Path
python "$skillDir/scripts/pipeline.py" init --project $projectDir
python "$skillDir/scripts/pipeline.py" status --project $projectDir
```

init仅首次执行；填写research/project.json，将预算与用户约束同步。阶段报告样例见 [automation.md](../skills/ml-research-paper/references/automation.md)。

先核验文献与创新，确定数据、切分、基线、指标和统计协议。agent实现并验证训练代码，将plan.example.json适配为正式计划：

```powershell
python "$skillDir/scripts/run_experiments.py" --project $projectDir --plan experiments/plan.json
```

改协议或补跑失败任务时使用新实验ID，保留历史并扣除已用预算。运行成功后仍需检查实现、切分和指标。

agent汇总结果，登记主张与引用核验，形成正式稿；字段见 [integrity.md](../skills/ml-research-paper/references/integrity.md)。

```powershell
python "$skillDir/scripts/audit_integrity.py" --project $projectDir --phase pre_review
```

先修复缺失或不支持关系，不能把unknown直接改填verified。审稿时保持稿件只读，产生问题和验收标准，再修订与复审。

```powershell
python "$skillDir/scripts/audit_integrity.py" --project $projectDir --phase final
python "$skillDir/scripts/pipeline.py" passport --project $projectDir
```

review/final的gate报告填写对应integrity_report。完成交付清单与过程记录，再生成最终护照；需要DOCX/PDF时实际渲染检查。

## 常见情况

- 文献访问失败：记录已读范围，寻找合法版本或缩小论断，不虚构全文阅读。
- 数据/算力缺失：完成可用的文献和设计，列出下一步条件，不用模拟值填补实测结果。
- 负结果：按原方案汇总，讨论精度与范围，可定位为复制/评估研究。
- 检查失败：按报告中的blockers修复对象，再对当前版本检查，不反复重训无关模型。
- 更换会话/模型：使用resume，核对当前文件、state与passport，不依赖历史口头PASS。
- v1.0项目：保留旧材料，下一次review/final前补齐新版台账和报告。

更多边界见 [架构说明](architecture.md)。
