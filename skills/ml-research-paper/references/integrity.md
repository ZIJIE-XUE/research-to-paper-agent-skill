# 完整性检查、材料护照与信息流

## 两个检查时点

**审稿前**：完成当前论文、主张台账与引用核验后，先核查，再交给审稿阶段。**最终交付前**：针对实际修改后的版本重新执行，不按报告年龄或“此前通过”豁免；版本和文件哈希一致才可复用确定性检查。单阶段审稿也先做适合现有材料的核查，缺口作为审稿范围说明，不伪造整条流水线已通过。

核查项目包括：引用存在及支持性、数据/标签/划分来源、运行证据与论文一致性、指标及图表忠实度、研究问题/方法在修订中是否漂移、主张支持程度、未关闭的关键审稿问题，以及输出包/声明和实际交付是否一致。按任务明确不适用项，不把声明完整当作真实世界真实性证明。

## 引用核查四层

1. **存在**：从一手出版页、作者仓库、DOI或可用学术索引核验，记录渠道和日期；检索无结果不自动等于虚构。
2. **元数据**：题名、作者、年份、版本、DOI与引用条目匹配；预印本与正式版的定位分开。
3. **定位**：页/节/表/公式/段落定位到实际已取得的文本；扫描件需要可用OCR或视觉核查时明确覆盖。
4. **支持**：把论文中具体主张与原文比较，区分支持、部分支持、不支持、未知；一篇文献真实存在不能证明它支持当前主张。

`literature/citation-checks.jsonl` 每行登记一个实际引用关系：

```json
{"id":"V001","claim_id":"C001","reference_id":"L001","existence":"verified","metadata":"verified","support":"supported","locator":"实际版本的页/节/表","evidence":["literature/excerpts/L001.txt"],"checked_at":"实际核验时间","method":"实际查询与原文核对方式"}
```

字段值来自实际核查。`existence` 可为 verified/not_found/unavailable，`metadata` 可为 verified/mismatch/unknown，`support` 可为 supported/partial/unsupported/unknown。不通过外部 API 自动填 verified；脚本不会查询外部索引或判断语义。

## 主张与运行来源

`results/claims.jsonl` 继续使用既有 id、claim、kind、status、scope 和 evidence；补充 `reference_ids` 数组，标明实际引用关系。empirical 主张增加来源类型：

- `provenance_type: local_run`，附 `run_receipts` 相对路径数组，指向本运行器产生的成功回执。脚本核验回执的任务 ID 与目录及冻结计划是否一致，并检查冻结输入、输出哈希和有限数值契约。恢复备份后应重新运行审计。
- `provenance_type: external_reported`，原始日志/输出/协议作为 evidence，并说明由谁声明、如何取得、实际核验覆盖。只能证明交接材料存在及支持关系的声明，不能写成本工具验证了执行。

每项 evidence 使用 `{"path":"相对路径","locator":"表/行/公式等定位"}`。文献性主张需要 `reference_ids`，理论/解释性主张关联证明、假设或支持性分析。最终通过要求台账内正式断言的实际措辞有支持；尚未检验的假设放在提案或局限中，不冒充已证实结论。

## 确定性审计命令

```text
python <skill>/scripts/audit_integrity.py --project <project> --phase pre_review
python <skill>/scripts/audit_integrity.py --project <project> --phase final
```

默认读 `manuscript/draft.md`，可用 `--manuscript` 指定项目相对路径。输出 `research/integrity-pre_review.json` 或 `research/integrity-final.json`。退出码 0 表示已登记对象的结构/追踪检查通过，1 表示阻断项，2 表示配置错误。报告保留登记总数、已检查数量、问题、警告与实际读取文件哈希。全论文的语义抽取完整性、引用语义判定质量和数据真实程度仍未知；不宣称全论文100%正确。

本工具不解析任意 BibTeX/Word/LaTeX 文内引用；agent 必须先把当前稿中的事实主张和引用关系登记到台账，再核对没有遗漏。citation-check 模式输出台账后，脚本才有可核验的对象。预审阶段的未知项也会阻止声明该完整性检查通过，但可带缺口交付研究稿或范围受限的独立审稿报告。

完整流程的 review/final 检查点须在 gate 报告中填写 `integrity_report` 路径。pipeline 工具检查相应 phase、pass结论及版本哈希；任何被核验文件变动都会使该检查失效。不要在 pre_review 报告中绑定随后会被审稿改写的问题台账；最终检查才绑定最终问题台账。

## 材料护照与信息访问

```text
python <skill>/scripts/pipeline.py passport --project <project>
```

导出 `research/passport.json`，记录有效/失效阶段、当前产物哈希、现有台账、实验汇总和交接文件，供新会话核对。护照是交接清单，不打包原始数据，不是隔离机制，也不证明生成式输出可逐字节重播。变更材料后重新生成；状态仍由当前实际文件验证。

从实验移交时，结合 [实验交接记录](design-execution.md#实验交接记录) 登记计划/实际偏差、负面结果与已知限制；若该记录作为证据使用，应在相应检查点artifacts中登记后再导出护照。护照不会自动收集未登记的任意文件。修订后的论断强度与范围按 [写作复审指引](writing-review.md#修订中的论断变化) 人工/agent核查，文件一致不能替代语义核查。

训练/数据核查可读取获得授权的原始材料；写作优先使用已核验的汇总及必要原文；审稿读取冻结论文、必要证据与原意见；编辑综合优先使用问题台账和定位。按阶段提供必要信息，但不声称文件权限被脚本强制隔离。测试集隔离由实验设计/代码实现，不能用“写作只见汇总”代替训练防泄漏。

文献查询只向所选服务发送必要关键词、题名或标识，不默认上传私人全文。运行器执行的训练代码可能联网，它不是网络沙箱。跨模型/第三方上传需覆盖具体内容与费用的授权；仓库上传也不自动包含研究数据和私人论文。

## 过程记录

最终写 `research/process-record.md`：研究问题演变、文献核验范围、方案版本和探索/验证边界、数据取得与处理、实验成功/失败及预算、模型与工具的已知配置、主要人工/AI决策、审稿轮次与回应、实际复现范围、未解决问题及输出版本。不捏造运行时长、人工阅读或模型身份，不用未经校准的评分表示录用概率。
