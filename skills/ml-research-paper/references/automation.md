# 工具、契约与恢复

工具只依赖 Python 3.10+ 标准库；从任意当前目录使用脚本的绝对路径。`<skill>` 是安装后的技能目录，`<project>` 是研究项目目录；以下尖括号参数需替换。

## 项目初始化

```text
python <skill>/scripts/pipeline.py init --project <project>
python <skill>/scripts/pipeline.py status --project <project>
```

初始化不覆盖已有项目或用户产物。`research/project.json` 中的模型/推理值是偏好，不更改当前聊天配置；实际运行模型仅在确知时填写。资源预算为初始建议，执行前应按用户约束调整，并将实验计划上限同步到不超过研究总剩余预算。

## 阶段报告与检查点

写实质报告与证据后，创建 `research/gates/<stage>-v1.json`：

```json
{
  "stage": "scope",
  "verdict": "pass",
  "artifacts": ["research/brief.md"],
  "checks": [
    {"name": "问题可回答且终点明确", "status": "pass", "evidence": ["research/brief.md"], "note": "列明比较对象、单位、范围和证伪条件"}
  ]
}
```

```text
python <skill>/scripts/pipeline.py checkpoint --project <project> --stage scope --report research/gates/scope-v1.json
```

阶段顺序：scope、literature、novelty、framework、data、design、experiments、conclusions、draft、polish、review、final。中途进入可核验已有产物后登记先前阶段；实际不适用的检查写 `not_applicable` 并解释原因，不能伪造已执行的实验/阅读。仅记录单阶段审稿时，也可直接按技能执行并交付审稿报告，无须为使用工具捏造全流程状态。

checkpoint 要求前序阶段有效、证据文件非空、通过检查有路径，保存产物和上游回执哈希。文件变动会使该阶段及后续状态失效。重做某阶段时先修复所有上游失效项，使用新报告版本登记；旧回执保留在 state.history。旧稿内容的版本保留由 agent 在改稿前完成，工具不会替作者存档稿件本体。

review 可记录 `verdict: revise`，表示审查已执行但需修订；此时 final 被拒绝。修订从最早受影响阶段重新登记，重走必要检查，review 最终通过后才可能 final。脚本不读懂科学语义、不自动评判创新或重大问题；这些由报告及问题台账支持，不能将结构检查当质量证明。

## 训练程序契约

agent 实现项目专用训练/评估代码，接收配置、种子和输出目录。计划中 `command` 为参数数组，以 `shell=False` 运行；支持 `{python}`、`{project}`、`{run_dir}` 三个占位。进程工作目录为本任务的新输出目录；输入必须显式定位。工具执行普通本地代码，不是权限沙箱，也不自动禁止联网。

训练程序按计划输出 `metrics.json`：

```json
{"metrics":{"test_primary":0.75,"validation_primary":0.72},"split":"固定划分标识","seed":0,"metric_definition":"在协议中定义的指标和方向"}
```

这里只是格式示例，不是实测值。`metrics` 内为非空、有限数值标量。按任务额外输出预测、学习曲线、模型/配置、数据划分和环境版本；列在 `required_outputs`。缺失、空文件、非法数值或非零退出码均不是成功。运行器仅对数值契约和文件哈希作检查，模型是否正确训练、指标是否合理由 agent 验证。

## 冻结运行与续跑

复制并适配 `experiments/plan.example.json` 为 `experiments/plan.json`。`inputs` 显式列出所有相关代码、数据、配置和划分文件；目录不能代替文件，未列出的依赖不会自动跟踪。若输入是外部大数据，先在项目中存放不可变快照或可核验版本清单并解释覆盖边界。不要把凭据写入命令、协议或产物。

```text
python <skill>/scripts/run_experiments.py --project <project> --plan experiments/plan.json
```

首次执行锁定计划、协议及输入哈希；每个任务仅启动一次，按总时间与单任务超时限制。退出码 0 表示全部任务契约通过，1 表示队列未完成，2 表示配置/冻结状态错误。日志和回执在 `runs/<experiment_id>/<job_id>/attempt-0001/`，汇总在该实验的 `summary.json`。

续跑同一命令会复核成功产物哈希并跳过已完成任务。失败、超时或被中断任务保留并标为需处理，不自动重复消耗预算；诊断后用新的实验ID建立明确的补跑计划，只包含必要任务，历史失败仍需汇总。修改已锁定计划、协议、输入或成功输出时拒绝旧ID复用。新ID不自动继承跨实验预算，agent 须从项目总预算中扣除已有消耗。

工具串行运行，避免多任务挤占单机资源。超时会终止所启动进程组/树；如果 agent 或机器整体中断，残留锁和 `running` 回执不能标成功。先核查锁文件PID、停止/确认对应进程已退出、保留回执，再手动移除确认无主的 `.lock`；避免两个 writer 并发。执行前预留最长允许耗时，异常中断时保守计入预算。新实验前重算剩余预算。

## 报告与复现

每次新实验确认依赖版本与硬件，训练程序输出 `environment.json`；需要精确环境时保存依赖锁文件。只登记不含凭据的必要环境字段，不把全部环境变量上传。汇总失败与成功任务，引用回执路径、输入哈希、输出和统计方法。生成论文表图时读取固定结果版本，不让手工数值变成第二份事实来源。

调度、外部模型 API、云 GPU、数据付费和期刊投稿均由当前用户授权与环境工具决定；工具本身不会购买、发消息、上传论文或创建自动任务。
