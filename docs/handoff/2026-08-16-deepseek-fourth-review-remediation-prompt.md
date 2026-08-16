# DeepSeek V4 Agent Harness 四审整改提示词

> 使用方式：将“主控提示词”代码块完整发送给 DeepSeek V4 Agent Harness。本文针对已完成二审整改后的当前代码，不是从零开发提示词。不得用旧版总控提示词重新执行 Task 1–15。

## 主控提示词

```text
你是 distribution-network-line-transformer-verification 项目的四审整改主控工程代理（orchestrator）。项目主体和二审整改已经完成；你的任务是依据 GLM 三审与 Codex 四审，对当前代码进行最后一轮指标正确性、物理门禁、证据可移植性和文档一致性修复。

工作区：D:\电力
四审基线：HEAD 2719431
已验证基线：72 tests passed，Ruff 全绿

测试全绿不等于四审通过。现有测试尚未覆盖 Top-k 无效候选、鲁棒性 PR-AUC、物理硬限制严重性、旧产物指标兼容和 GitHub 证据可移植性。

一、开始前必须完整阅读

1. docs/handoff/2026-08-16-fourth-review-report.md
2. docs/handoff/2026-08-16-deepseek-fourth-review-remediation-prompt.md
3. docs/handoff/2026-08-16-deepseek-secondary-review-remediation-prompt.md
4. docs/handoff/2026-08-16-code-review-report.md
5. README.md
6. docs/methodology.md
7. data/README.md

GLM 报告是三审输入，本文中的 Codex 四审裁决是本轮优先级和技术口径的最终依据。不得因为三审将某问题标为 P3，就跳过四审已运行时复现的 P1 问题。

二、开始前基线检查

修改任何文件前执行并记录：

- Get-Location
- git status --short
- git branch --show-current
- git log -8 --oneline
- .venv\Scripts\python.exe --version
- .venv\Scripts\python.exe -m pytest -q
- .venv\Scripts\python.exe -m ruff check src app tests scripts

工作区中可能存在未跟踪的 docs/handoff/2026-08-16-fourth-review-report.md。它属于其他审查代理，不得删除、覆盖或混入代码修复提交。禁止 git reset --hard、git checkout --、git clean -fd、强制推送及任何可能丢失现有工作的操作。

三、四审裁决

以下四项是发布阻断问题，必须全部修复：

1. Top-k 排名包含 NaN 或证据不足候选。当前 evaluation.py 对所有候选直接 sort_values；只有一个有限候选时，NaN 候选仍可能因原始行顺序进入 Top-2，产生虚假命中。
2. 130 组鲁棒性实验没有记录或聚合 pr_auc、scored_coverage、insufficient_data_rate，无法验证项目声明的主指标。
3. 电压越限和变压器过载无论幅度多大都固定为 warning；pipeline/experiments 只拒绝 critical，因此配置的物理硬限制没有真正形成完成门禁。
4. default_summary.json 引用被 gitignore 排除的 D:\电力\runs\... 绝对路径；GitHub 克隆后无法访问来源 manifest。逐时刻物理数字也没有进入自动生成 summary。

必须同步修复的重要一致性问题：

5. 旧运行目录缺少 anomaly_score 时，评价页面崩溃，而且会继续显示旧版硬标签 PR-AUC。不能只修复曲线 KeyError，必须避免把旧指标伪装成当前口径。
6. tests/integration/test_pages.py 的鲁棒性页面测试依赖本地 runs，干净 checkout 会 skip。
7. README 仍称权重在训练/验证场景确定，但仓库没有权重或阈值标定链路；methodology 又把未接入的 60/20/20 划分写成已执行。
8. methodology 和 data/README 没有记录 anomaly_score、Top-2、Top-k 可评价覆盖率、simulation_validation.csv、新 metrics 嵌套字段及 evidence weight。

四、对 GLM 三审建议的技术裁决

1. 旧目录兼容问题成立，但修复必须同时隐藏旧版无效 PR-AUC；单独 try/except anomaly_score 不足以解决指标误导。
2. insufficient_data 样本 anomaly_score=0 参与全样本 AP 是允许的业务设计：系统无法评分真实错误时，整体运行效果应受到惩罚。全样本 AP 保持主指标。
3. 可以增加 scored 子集 AP，但必须命名为 pr_auc_scored，仅作为诊断指标，并与 scored_coverage 同时展示。不得用 pr_auc_scored 替换或掩盖全样本 pr_auc。
4. Top-1/Top-2 机会基线可加入 README：三候选均匀随机排序的描述性期望约为 1/3 和 2/3；默认实际错误只有 5 台，必须注明样本过小，不能据此作显著性结论。
5. 分阶段 CLI 不值得在本轮新写四套实现。按 YAGNI 原则，从公开解析器中移除 simulate/corrupt/diagnose/evaluate 占位命令；保留 run-all、experiments、report。
6. report.py 的重复键策略和数据字典更新属于低风险一致性修复，应在长实验重跑前完成。

五、Agent Harness 执行方式

将任务拆为 F0–F6，按依赖顺序集成。每个任务必须经过：

1. 最小运行时复现；
2. 新增失败测试并确认失败原因正确；
3. 最小实现；
4. 目标测试；
5. 相关回归测试；
6. 全量 pytest 和 Ruff；
7. 独立方法/物理审查；
8. 修复审查意见；
9. 独立提交。

允许只读审查并行；多个实现代理不得在同一工作区同时写文件。需要并行实现时使用隔离 worktree，并由主控代理逐个审查和集成。同一代理不能既是实现者又是唯一最终审查者。

不得删除、skip、xfail 或弱化测试来获得绿灯，不得硬编码预期指标，不得在 F0–F5 完成前重跑耗时的 30 天默认运行或 130 组实验。

六、整改任务

### F0：固定四审缺陷的失败测试

在修改业务实现前增加以下最小测试：

1. 三候选中只有一个 enhanced_score 有限、其余为 NaN，真实馈线位于 NaN 行时，Top-2 不得因行顺序命中。
2. 同一组 NaN 候选交换行顺序，Top-k 结果必须不变。
3. 有效候选数少于 k 时，该设备不进入 Top-k 分母，并降低 top{k}_evaluation_coverage。
4. experiments 输出包含 pr_auc、pr_auc_scored、scored_coverage、insufficient_data_rate、n_actual_errors，并能正确聚合。
5. 电压越限或变压器过载属于配置的硬失败类型时，pipeline 和 experiment case 不得 completed。
6. 旧版 predictions 不含 anomaly_score 时，评价页面不抛异常、不绘制 PR 曲线、不展示旧版 pr_auc 为当前指标。
7. 鲁棒性页面使用 tmp_path 中合成的 experiment_aggregates.csv 渲染，在不存在 runs 目录时也不得 skip。
8. default_summary.json 不包含绝对工作区路径，包含来源 manifest 哈希和逐时刻物理汇总。
9. 运行 manifest 中列出的输出文件包含 SHA-256，并能检测产物被篡改。

测试使用 tmp_path、最小 DataFrame、monkeypatch 或小规模配置。禁止为单元测试启动完整 30 天仿真。

### F1：修复 Top-k 有效候选和分母

修改 src/ltverify/evaluation.py 及其调用链：

1. evaluate_predictions 接收 ScoringConfig，或接收等价的显式 ranking evidence threshold；不要在评价模块复制一个新的硬编码阈值。
2. 某候选只有同时满足以下条件才可进入排名：
   - enhanced_score 为有限数；
   - available_feature_weight 为有限数；
   - available_feature_weight >= scoring.evidence_weight_threshold。
3. 对每个真实错误设备和每个 k 单独计算 eligible candidate count。
4. eligible count < k 时，该设备标记为 Top-k 不可评价，不计入命中分子和分母。
5. 新增指标：
   - top{k}_correction_rate；
   - top{k}_evaluated_count；
   - top{k}_evaluation_coverage；
   - top{k}_applicable。
6. 没有可评价设备时 correction_rate 为 null，不得返回 0 或 1。
7. 全局合法候选数 <= k 时仍维持不适用；默认三馈线 Top-3 继续为 null。
8. 排名相同分数时使用稳定且明确的并列策略。推荐按 candidate_feeder_id 作确定性次序，并在方法文档说明；不得依赖原始 DataFrame 行顺序。

更新 pipeline、experiments、report 和测试中的 evaluate_predictions 调用。不得把 physical_feeder_id 用于候选过滤或排序，它只能用于最终命中评价。

### F2：补齐全样本与 scored 子集 PR-AUC

1. 保留 metrics["pr_auc"] 为全样本主指标；insufficient_data 的 anomaly_score=0.0 参与该指标。
2. 增加 metrics["pr_auc_scored"]：只在 decision != insufficient_data 的子集上计算。
3. scored 子集为空，或不同时包含正负两类时，pr_auc_scored=null，并输出适用性字段；不得让 sklearn warning 代替业务判断。
4. pr_auc_scored 只能和 scored_coverage 同时展示，并明确标注“诊断指标”。
5. experiments.py 的案例与聚合列至少加入：
   - pr_auc
   - pr_auc_scored
   - scored_coverage
   - insufficient_data_rate
   - n_actual_errors
6. 鲁棒性页面增加上述可绘制指标，并妥善处理全 null 指标。
7. 重新生成前先用小型实验确认 CSV schema、聚合均值和 null 行为。

不得根据哪一种 anomaly_score 公式在当前默认运行上 AP 更高来修改公式。本轮不重新选择异常分数、权重或阈值。

### F3：让物理限值成为真正门禁

修改 ValidationConfig、validation.py、pipeline.py、experiments.py 及测试：

1. 增加显式 critical_violation_types 配置，默认包含：
   - non_convergence
   - power_balance
   - voltage_out_of_bounds
   - transformer_overload
2. check_solved_network 根据 violation type 和配置决定 severity，不再把电压/负载率越限永久固定为 warning。
3. 若一个时刻同时存在多个违规，severity 取其中最高级别；violation_type 去重但保留所有详细 message。
4. terminate_on_critical=true 时，pipeline 和 experiment case 对任何 critical 行失败，manifest/summary 记录违规类型、时间戳和最大偏差。
5. terminate_on_critical=false 时允许继续，但必须在 metrics、summary 和 manifest 中保留违规计数，不能静默完成。
6. 实验物理汇总增加 maximum_power_balance_error_mw 和各 violation type 计数。

必须测试：轻微或严重越限的配置行为、过载案例阻止 completed、关闭终止策略后违规仍被记录。

### F4：建立可移植且可校验的证据链

修改 manifest.py、pipeline.py、report.py、实验 manifest 和报告测试：

1. RunManifest 增加 artifact_schema_version，当前新 schema 设为 2。
2. RunManifest 增加 output_sha256: {relative_artifact_path: sha256}。manifest.json 本身不需要自哈希。
3. 输出路径保存为相对 run directory 的文件名，不保存 D:\电力 或其他机器绝对路径。
4. default_summary.json 不再写绝对 manifest_path，改为包含：
   - source_run_id
   - source_manifest_sha256
   - artifact_schema_version
   - source_git_commit
   - config_sha256
   - 参与报告计算的关键产物哈希
5. report.py 读取 simulation_validation.csv，生成 time_series_validation：
   - timestamp_count
   - convergence_rate
   - voltage_min_pu
   - voltage_max_pu
   - maximum_transformer_loading_percent
   - maximum_power_balance_error_mw
   - severity_counts
   - violation_type_counts
6. default_summary 中所有 README 引用的物理数字必须来自该汇总，不得人工读取后复制。
7. 实验 manifest 额外记录 base config SHA-256 和解析后的 base config snapshot。
8. 将默认运行的小型 evidence manifest 和鲁棒性 experiment manifest 的可移植副本保存到 reports/metrics 并提交 Git；不要提交大型 runs 目录。
9. 增加产物哈希校验函数或 report 入口校验，发现不一致时给出明确错误，不生成可信报告。

旧 schema 的运行目录不得被静默升级或伪造哈希。重新运行后才能获得 schema 2 的可信证据。

### F5：旧产物兼容、干净环境测试和文档修正

1. 评价页面判断 artifact_schema_version 和 anomaly_score 是否存在。
2. 对旧运行目录：
   - 显示“旧版指标口径不兼容，请重新运行”的 warning；
   - 隐藏或标为 unavailable 的旧 pr_auc；
   - 不绘制 PR 曲线；
   - 其他不依赖新 schema 的信息可继续展示。
3. 不要用旧 confidence 或 margin 临时重算并冒充新 anomaly_score。
4. tests/integration/test_pages.py 使用 tmp_path 生成两行以上的聚合 CSV，并通过 AppTest 输入控件设置路径；删除依赖本地 runs 的 skip。
5. report.py 对 observed_measurements 的重复 timestamp-transformer 键显式抛 DataContractError，与 features.py 的数据契约保持一致。
6. 从 CLI 公开 parser 中移除未实现的 simulate/corrupt/diagnose/evaluate；同步测试和帮助文本，不实现新的分阶段流水线。
7. 更新 README：
   - 权重和阈值改为“预先固定的启发式参数，尚未经独立验证集标定”；
   - 增加描述性随机 Top-1/Top-2 机会基线，并注明 n=5 不能作显著性结论；
   - 所有物理数字引用 schema 2 的自动 summary。
8. 更新 docs/methodology.md：
   - 定义 anomaly_score；
   - 区分 pr_auc 与 pr_auc_scored；
   - 说明 insufficient_data 的全样本 AP 处理；
   - 改为 Top-1/Top-2 和逐设备可评价覆盖率；
   - 明确 60/20/20 尚未接入；
   - 区分 candidate score、evidence gate、anomaly score。
9. 更新 data/README.md：记录 available_feature_weight、anomaly_score、topk_applicable、Top-k evaluated count/coverage、simulation_validation.csv 和 manifest schema 2 字段。
10. 可顺手把本次执行触发的 Streamlit use_container_width 弃用警告改为 width="stretch"，但不得因此大规模改界面。

### F6：重新运行与最终验收

只有 F0–F5 全部实现、审查、提交后才能开始：

1. .venv\Scripts\python.exe -m pytest -q
2. .venv\Scripts\python.exe -m ruff check src app tests scripts
3. 小规模 run-all 集成运行。
4. 小规模 experiments 集成运行并核对所有新增列。
5. 所有 Streamlit 子页面 AppTest，确保没有环境依赖 skip。
6. 使用 schema 2 重跑默认 30 天流水线。
7. 用 report 命令生成新的 default_summary 和 evidence manifest。
8. 使用最终代码重跑全部 130 个鲁棒性/消融案例。
9. 将可移植 experiment manifest 复制或自动导出到 reports/metrics。
10. 核对 README、default_summary、robustness CSV、两个 evidence manifest 的 run ID、Git commit、配置哈希和指标完全一致。
11. 在没有 runs 目录的干净临时 checkout 中运行全量测试，确认页面测试不 skip、已提交证据不含绝对路径。

七、建议提交边界

每个提交只包含一类已验证修改：

1. test: reproduce fourth-review blockers
2. fix: exclude ineligible candidates from top-k metrics
3. fix: add complete robustness evaluation metrics
4. fix: enforce configured physical violation gates
5. fix: make run evidence portable and verifiable
6. fix: handle legacy artifacts and environment-independent pages
7. docs: align methodology and data contracts with implemented metrics
8. chore: regenerate schema-v2 release evidence

提交前展示 git diff --check 和拟提交文件。不得 push、创建远程 PR、部署或发布，除非用户另行授权。不得修改用户全局 Git 配置。

八、每个任务的报告格式

任务：F0/F1/.../F6 — 名称
状态：完成 / 受阻
缺陷复现：命令、构造输入和实际输出
新增失败测试：名称及修复前失败原因
修改文件：逐项列出
接口和 schema 变化：字段、配置、兼容策略
方法/物理审查：指标含义、候选资格、物理门禁、泄漏检查
验证命令：逐项列出
验证结果：通过数、失败数、skip 数、关键物理范围
证据追溯：run ID、Git commit、配置哈希、manifest 哈希
提交：哈希与提交信息
遗留风险：没有则写“无新增已知风险”
下一步：下一任务及前置条件

九、最终完成条件

以下条件必须同时满足，才能声明四审整改完成：

- Top-k 不再受 NaN 候选或 DataFrame 行顺序影响；
- Top-k 报告每个 k 的可评价样本数和覆盖率；
- 鲁棒性案例与聚合表包含全样本 PR-AUC、scored-only AP 和拒判覆盖率；
- 电压与变压器负载率硬限制能够阻止 completed；
- 全样本 PR-AUC 仍是主指标，scored-only AP 未被用于掩盖拒判样本；
- 旧运行目录不崩溃，也不显示旧版 PR-AUC 为当前口径；
- default_summary 与证据 manifest 不含本机绝对路径；
- README 中的逐时刻物理数字存在于自动生成 summary；
- 已提交证据带 schema version、配置哈希、Git commit 和关键产物哈希；
- 干净 checkout、没有 runs 目录时，所有页面测试仍执行且不 skip；
- README、methodology 和数据字典与真实实现一致；
- 全量 pytest、Ruff、小型流水线、默认运行和 130 组实验均有新鲜验证证据；
- 工作区没有误删审查报告或误跟踪大型 runs 产物。

现在开始 F0。先输出基线检查、四个发布阻断问题的最小复现和拟新增测试，不要在复现完成前修改业务实现。
```

## 中断后恢复提示词

```text
继续 D:\电力 项目的四审整改。先完整读取：

1. docs/handoff/2026-08-16-deepseek-fourth-review-remediation-prompt.md
2. docs/handoff/2026-08-16-fourth-review-report.md

不要假设上一次修改、测试、长实验或提交成功。检查 git status、当前分支、最近 10 个提交、F0–F6 任务报告和测试输出，根据提交与新鲜验证证据确定第一个未完成任务，从该任务的第一个未验证步骤恢复。

保留所有现有修改，不使用 reset --hard、checkout -- 或 clean -fd。不要重复已经由提交和测试证明完成的工作，不跳过失败测试、方法/物理审查和提交前验证。若存在同一文件上的不明未提交修改，停止写入并报告冲突。
```

## 最终独立审查代理提示词

```text
你是四审整改的独立最终审查代理。只进行只读检查和验证，不直接修改代码。

完整阅读四审整改提示词、GLM 报告、F0–F6 提交差异、测试结果、默认运行和鲁棒性实验产物。不要依赖实现代理的口头结论。

重点独立复现：

1. NaN 候选交换顺序是否仍会改变 Top-k；
2. 有效候选不足时是否仍进入 Top-k 分母；
3. 鲁棒性 CSV 是否真实包含 pr_auc、pr_auc_scored 和 scored_coverage；
4. 极端电压/过载案例是否能够阻止 completed；
5. 旧版运行目录是否隐藏旧 PR-AUC 且不崩溃；
6. 删除或临时移走 runs 后，页面测试是否仍执行；
7. default_summary 和 evidence manifest 是否含绝对路径、缺失哈希或无法解析的来源；
8. README 的权重标定、数据划分、机会基线和物理数字是否与代码及产物一致；
9. scored-only AP 是否被错误升级为主指标；
10. 测试弱化、硬编码结果、隐藏失败、数据泄漏或无关重构。

按 P0/P1/P2 输出发现，每条包含文件、行号、复现命令、影响和最小修复。只有所有完成条件均有独立证据时，才能写“四审整改质量门禁通过”，并附实际运行的命令、测试数、skip 数、run ID 和 manifest 哈希。
```
