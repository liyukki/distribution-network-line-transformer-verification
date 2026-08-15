# DeepSeek V4 Agent Harness 二审整改提示词

> 使用方式：把“主控提示词”代码块完整发送给 DeepSeek V4 Agent Harness。不要只发送问题清单；主控提示词中的执行顺序、测试门禁、指标口径和禁止事项同样属于任务要求。

## 主控提示词

```text
你是 distribution-network-line-transformer-verification 项目的整改主控工程代理（orchestrator）。项目主体已经完成；你的任务不是从零重写，也不是盲目增加模型，而是依据 GLM 初审和 Codex 二审，对现有实现进行证据驱动、测试驱动的修复，使代码、指标、电力系统物理检查、看板和 README 保持一致。

工作区：D:\电力

一、开始前必须阅读

完整阅读以下文件后才能修改代码：

1. docs/handoff/2026-08-16-code-review-report.md
2. docs/handoff/2026-08-16-deepseek-secondary-review-remediation-prompt.md
3. docs/superpowers/specs/2026-08-15-line-transformer-verification-design.md
4. docs/superpowers/plans/2026-08-15-line-transformer-verification.md
5. README.md

GLM 报告是初审记录；本提示词中的“Codex 二审裁决”是本轮整改的最终优先级。如果二者冲突，以本提示词为准。原设计和实施计划用于理解业务边界，但不能用来维持已经被运行时证据证明有误的实现。

二、开始前基线检查

在修改任何文件之前执行并记录：

- Get-Location
- git status --short
- git branch --show-current
- git log -5 --oneline
- .venv\Scripts\python.exe --version
- .venv\Scripts\python.exe -m pytest -q
- .venv\Scripts\python.exe -m ruff check src app tests scripts

当前已知基线是 56 tests passed、Ruff 全绿，但这不代表实现正确。现有测试没有覆盖本提示词列出的运行时和方法学缺陷。

保留用户及其他 AI 的所有未提交工作。特别注意：docs/handoff/2026-08-16-code-review-report.md 在交接时可能是未跟踪文件，不得删除、覆盖或擅自改写。禁止使用 git reset --hard、git checkout --、git clean -fd、强制推送或任何会丢失现有工作的命令。

三、Agent Harness 组织方式

将整改分为 R0 至 R6 七个任务，严格按依赖顺序集成。可以让只读审查代理并行工作，但多个实现代理不得同时编辑同一工作区。若要并行实现，必须使用隔离分支或 git worktree，并由主控代理逐个审查和集成。

每个整改任务至少使用以下三个角色：

- 实现代理：先写失败测试，再完成最小修复；
- 方法/物理审查代理：检查指标定义、数据泄漏、电力系统物理含义和实验口径；
- 主控代理：核对差异、运行验证、处理审查意见并提交。

同一代理不能既完成实现又作为唯一最终审查者。

每项修改严格执行：复现缺陷 → 写失败测试 → 确认因目标缺陷失败 → 最小实现 → 目标测试 → 相关回归 → 全量测试 → Ruff → 审查 → 修正 → 再验证。

不得删除、跳过、xfail 或弱化测试来获得绿灯，不得硬编码预期指标，不得顺手重构无关模块。

四、Codex 二审裁决

以下四项为发布阻断问题：

1. src/ltverify/evaluation.py 当前把二值 predicted 传给 average_precision_score。该 PR-AUC 不是连续风险排序意义上的 AP，并且与 app/pages/4_evaluation.py 使用 confidence 的口径不一致。
2. src/ltverify/simulation.py 接收 validation_cfg，却没有对每个时刻的潮流结果执行电压、变压器负载率、功率平衡检查；当前静态校验发生在零负荷网络上，只能视为拓扑/基础收敛检查。
3. app/pages/5_robustness.py 默认读取 experiment_summary.csv，但 src/ltverify/plotting.py 的鲁棒性折线需要 experiment_aggregates.csv 中的 mean_* 和 std_* 字段，可稳定触发 KeyError: mean_f1。
4. 默认系统只有三个候选馈线，Top-3 必然为 1.0，没有评价意义，不能作为性能证据。

以下为必须修复的重要问题：

5. diagnose 对 NaN coverage/current_score/best_score/margin 可能保留 no_change；无证据必须输出 insufficient_data。
6. margin 只在低 current_score 分支计算，导致其他合法样本缺失解释字段。
7. 候选馈线全集来自 corrupted ledger 的 reported_feeder_id；扰动可能让一个合法馈线从候选集中完全消失。合法候选应来自 feeder_measurements.feeder_id。
8. 评分对每行可用特征重新归一化，但没有证据权重门槛，导致证据量不同的候选分数不可直接比较。
9. experiments.py 没有在缓存和标记完成前检查 simulation.failures 与时序物理违规，部分失败实验仍可能进入汇总。
10. README 声称实际使用 60/20/20 场景划分和随机森林，但 grouped_scenario_split 没进入生产链路，仓库也没有随机森林实现。
11. 非 demo 模式的网络页面仍按 physical_feeder_id 给线路着色，与“物理真值仅在演示/评估模式展示”的界面承诺不一致。

二审对 GLM 低优先级意见的补充裁决：

- reports/metrics/default_summary.json 并非完全没有分析来源，Notebook 中存在基线计算；但已提交 summary 的拼装过程没有正式生成命令，因此仍需自动化。
- q_wide 暂不因“当前未使用”而删除。若它属于既有数据契约或近期无功扩展接口，请加注释和契约测试；只有确认无任何契约消费者后才可删除。
- 第一版不要为了匹配旧 README 临时加入随机森林。优先如实修正文档，把模型比较列为后续工作。

五、整改任务

### R0：建立缺陷复现与回归测试

目标：在修改实现之前，用测试固定所有关键缺陷。

必须新增或改写以下测试：

1. 连续 anomaly_score 与二值 predicted 产生不同 AP 的构造样例，并断言 evaluate_predictions 使用连续分数。
2. coverage、current_score、best_score 或关键证据为 NaN 时，diagnose 返回 insufficient_data。
3. 两个分数有限时，无论最终 decision 是什么，margin 都有有限值。
4. 合法馈线在 corrupted ledger 中没有成员时，仍出现在候选特征表中。
5. 候选证据权重不足时不能形成自动推荐。
6. 三候选馈线下 Top-3 返回 NaN/None 或明确的 not_applicable，而不是 1.0。
7. robustness 页面使用现有 experiments-* 结果可以正常渲染；同时测试绘图函数的输入列契约。
8. 时序潮流电压越限、变压器过载、功率平衡异常和不收敛均可被记录。
9. 某时刻不收敛后，下一个时刻回退到 init="auto"。
10. 实验包含失败或严重物理违规时，不得被静默当成正常完成。

测试应使用最小构造数据或 monkeypatch，不要为单元测试运行完整 30 天仿真。

### R1：修复诊断证据和候选集合

修改 src/ltverify/features.py、src/ltverify/scoring.py、配置模型及相关测试：

1. 合法候选全集使用 feeder_measurements["feeder_id"].unique()；台账只负责构造 reported peer group。
2. 即使候选台账邻居不足，也应在馈线测量存在时独立计算 active_power_corr；需要 peer group 的电压形状特征可以保持缺失。
3. 将 safe_corr 的 minimum_pairs 放入明确配置，短窗口行为必须可预测且有测试。
4. 对 feeder_measurements 重复 (timestamp, feeder_id) 采用明确的数据契约。推荐检测后抛出包含重复键示例的 DataContractError；如果选择聚合，必须在文档中说明聚合规则，不能静默使用不明的 first。
5. 输出 available_feature_weight 或 feature_weight_coverage，只有达到配置门槛的候选才能参与 best feeder 比较。
6. coverage/current_score/best_score/margin/证据权重任一关键值非有限时，decision=insufficient_data。
7. current_score 和 best_score 有限时始终计算 margin。

不得读取 physical_feeder_id、is_mislinked 或错误注入种子作为特征或候选生成依据。

### R2：统一异常分数、PR-AUC 和 Top-k

修改 src/ltverify/evaluation.py、预测产物、评估页面及相关测试：

1. 在 predictions 中增加统一的连续 anomaly_score。第一版采用：

   anomaly_score = coverage * min(1 - current_score, max(margin, 0))

   只对关键输入有限且证据门槛通过的样本按公式计算；证据不足样本的 anomaly_score 明确设为 0.0，使其进入最低风险层，同时单独报告有效评分覆盖率。实现时应使用向量化，不能让 NaN 被 sklearn 静默丢弃。

2. 该公式是基于“当前归属不相似”与“替代归属有正向优势”两个条件的连续化，不得根据测试集上哪个公式 AP 更高而改选公式。若发现数值范围或业务含义不成立，暂停实现，给出反例和替代公式，由用户决定。
3. metrics.json 的 PR-AUC、评估页 PR 曲线和所有报告统一使用 anomaly_score；confidence 仅保留为决策解释字段，不得形成第二套 PR 口径。
4. binary Precision/Recall/F1 继续使用最终告警 decision，不得用连续分数偷偷替代二值判定。
5. 当合法候选数 <= k 时，Top-k 标记为 not_applicable，不进入性能结论。默认三馈线项目重点报告 Top-1 和 Top-2。
6. 指标输出增加 scored_coverage、candidate_feeder_count 和适用性字段，使使用者能够解释为什么某项指标缺失。

修复后必须重新生成指标，旧 PR-AUC 和 Top-3 数字不得继续出现在 README 或总结文件中。

### R3：增加时序电力系统物理校验

修改 src/ltverify/validation.py、src/ltverify/simulation.py、pipeline、experiments、配置与测试：

1. 从 run_static_validation 中提取“检查已求解网络结果”的可复用函数，避免静态与时序检查复制两套规则。
2. 每个成功 runpp 的时间点至少记录：timestamp、converged、voltage_min_pu、voltage_max_pu、maximum_transformer_loading_percent、absolute_power_balance_error_mw、violation_type、message、severity。
3. 电压上下限使用 ValidationConfig；变压器过载默认以 100% 为界；功率平衡容差进入 ValidationConfig，不再散落硬编码。
4. SimulationResult 增加 validation/violations DataFrame。无违规也要有可追溯的逐时刻摘要，不能只在失败时记录。
5. runpp 不收敛时记录 failure；紧接着的下一个时间点必须使用 init="auto"，只有上一个时间点成功时才允许 init="results"。
6. pipeline 的零负荷静态检查在文档和 manifest 中改称 topology/base-case validation；不得把它描述成时序运行范围内的完整物理验证。
7. 默认流水线和实验运行器根据显式策略处理物理违规：严重违规或不收敛使案例状态失败；非严重警告进入结果并在汇总中计数。策略必须配置化并有测试。

不得因为默认数据当前电压落在 0.90 至 1.10 p.u. 内就省略检查；本任务要求的是可执行的约束和证据，而不是对一次输出做人工观察。

### R4：修复鲁棒性页面和实验可信度

1. app/pages/5_robustness.py 的折线图加载 experiment_aggregates.csv。
2. experiment_summary.csv 只用于案例明细、失败原因和原始指标展示。
3. plotting 函数显式校验 required columns，错误信息包含缺失列和预期输入文件类型。
4. x 轴 value 在绘图前按数值排序，避免 10 排在 2 前面。
5. experiments.py 在写缓存和 completed 状态前检查 failures 与 violations。
6. 实验汇总增加 convergence_rate、violation_count、voltage_min_pu、voltage_max_pu、maximum_transformer_loading_percent 等物理字段。
7. 每次实验写 experiment_manifest.json，至少包含完整配置、覆盖参数、随机种子、Git commit、Python/依赖版本、输入和输出哈希、案例总数、成功数、失败数、开始/完成时间。
8. 补充真实子页面测试，不能只执行 streamlit_app.py 入口后就声称全部页面通过。

### R5：报告自动化、README 如实化和界面真值隔离

1. 增加正式 CLI 命令或 scripts 脚本，根据指定 run directory 和 experiment directory 自动生成 reports/metrics/default_summary.json。
2. baseline_comparison、finding、指标值、run ID 和 manifest 路径必须由产物计算或引用，禁止手工复制数字。
3. README 删除“已经完成随机森林”和“已经实际执行 60/20/20 划分”的表述；可明确列为未来工作。
4. README 不再把默认三馈线 Top-3=1.0 当作结果证据。
5. README 明确区分：拓扑/基础收敛检查、逐时刻物理校验、合成数据算法评估。
6. 普通模式下网络线路使用中性色，不展示 physical_feeder_id 配色；仅 demo/evaluation 模式可显示物理真值。
7. CLI 中 simulate/corrupt/diagnose/evaluate 若仍是占位命令，必须从公开命令中移除或明确返回“not implemented”且使用非零退出码。优先实现真正的分阶段命令，但不要为此复制 pipeline 逻辑。
8. 清理确认无用的参数和死分支；q_wide 按本提示词前述裁决处理。

### R6：重新实验和最终验收

只有 R0 至 R5 的实现、测试和审查全部完成后，才允许重跑较长实验。

按顺序执行：

1. .venv\Scripts\python.exe -m pytest -q
2. .venv\Scripts\python.exe -m ruff check src app tests scripts
3. 使用 tests/fixtures/small_config.yaml 运行小型端到端流水线。
4. 对所有 Streamlit 子页面执行可自动化的冒烟测试。
5. 重跑默认固定种子流水线，确认 manifest completed、无未解释失败，且时序物理校验产物完整。
6. 重跑鲁棒性/消融实验，保留成功、失败和物理违规案例，不得只筛选成功案例。
7. 用新生成命令重建 default_summary.json。
8. 核对 README、metrics.json、default_summary.json 和看板展示是否来自同一批 run ID。
9. 在干净临时环境完成一次安装与小型流水线验证。
10. 检查 git status，确认没有 runs、大型 HTML、缓存或临时数据被误提交。

六、提交策略

建议按以下边界提交，每次提交只包含已验证的相关文件：

1. test: reproduce secondary-review defects
2. fix: enforce evidence-aware feeder diagnosis
3. fix: align anomaly score and evaluation metrics
4. fix: validate time-series power-flow results
5. fix: repair robustness dashboard and experiment status
6. docs: automate evidence summary and correct claims
7. chore: regenerate verified release evidence

提交前必须展示 git diff --check 和拟提交文件列表。不得 push、创建远程 PR、部署服务或发布包，除非用户另行明确授权。如果 Git 缺少作者信息，使用单次 git -c user.name=... -c user.email=...，不要修改用户全局 Git 配置。

七、不得违反的约束

- 不引入 GNN、DTW、深度学习或随机森林来掩盖基础指标和物理校验问题。
- 不读取 physical_feeder_id、is_mislinked 或注入种子作为特征。
- 不把合成仿真结果宣传成现场生产准确率。
- 不虚构、保留或手工调整任何性能数字。
- 不基于最终测试集选择异常分数公式、阈值、权重或超参数。
- 不把 Accuracy 作为不平衡异常检测的主要结论。
- 不静默丢弃潮流失败、物理违规、缺失数据或实验失败。
- 不让 Streamlit 页面重新实现算法；界面只读取统一产物和调用公共绘图函数。
- 不改动真实物理网络来配合错误台账标签；错误注入只作用于台账副本和量测副本。
- 不做与二审整改无关的大规模重构、依赖升级或格式化。

八、每个任务的报告格式

任务：R0/R1/.../R6 — 名称
状态：完成 / 受阻
复现证据：命令、失败信息、涉及文件和行号
新增测试：测试名称及其在修复前为何失败
修改文件：逐项列出
实现说明：接口、字段、配置和数据流变化
方法/物理审查：指标语义、泄漏检查、物理合理性
验证命令：逐项列出
验证结果：通过数、失败数、关键物理范围
提交：哈希与提交信息
遗留风险：没有则写“无新增已知风险”
下一步：下一任务及前置条件

九、真正的完成条件

只有同时满足以下条件，才可声明二审整改完成：

- 所有发布阻断和重要问题都有失败测试、修复和回归证据；
- 全量 pytest 与 Ruff 通过；
- PR-AUC 只使用统一连续 anomaly_score，页面和文件口径一致；
- 三馈线 Top-3 不再作为有效性能指标；
- 无证据样本输出 insufficient_data；
- 合法馈线不会因 corrupted ledger 而从候选集合消失；
- 每个时刻都有收敛和物理校验记录；
- 实验失败及违规不会被静默计为 completed；
- 鲁棒性子页面能读取真实聚合产物并渲染；
- README 不再包含未实现能力和旧指标；
- default_summary.json 可由固定命令重新生成；
- 新默认运行、实验结果、README 和看板均可追溯到同一批 run/manifest；
- git 工作区没有误删用户文件，也没有误跟踪大型运行产物。

现在开始执行 R0。先报告基线检查和逐项最小复现，不要在复现证据完整前修改业务实现。
```

## 中断后恢复提示词

```text
继续 D:\电力 的二审整改。先重新读取：

1. docs/handoff/2026-08-16-deepseek-secondary-review-remediation-prompt.md
2. docs/handoff/2026-08-16-code-review-report.md

不要假设上一次修改、测试或提交成功。检查 git status、当前分支、最近 7 个提交、R0-R6 报告和测试结果，根据可验证的提交与测试证据确定第一个未完成任务。从该任务的第一个未验证步骤恢复。

保留所有现有修改，不使用 reset --hard、checkout -- 或 clean -fd，不重复已验证工作，不跳过测试驱动、方法/物理审查和提交前验证。若存在同一文件上的不明未提交修改，先停止写入并报告冲突。
```

## 最终独立审查代理提示词

```text
你是该项目二审整改的独立最终审查代理。你只进行只读检查和验证，不直接修改代码。

完整阅读：

- docs/handoff/2026-08-16-deepseek-secondary-review-remediation-prompt.md
- docs/handoff/2026-08-16-code-review-report.md
- 本轮 R0-R6 的提交差异、测试和运行产物

逐项核验所有完成条件，重点寻找：

1. PR-AUC 是否仍有任何路径使用二值预测或另一套分数字段；
2. anomaly_score 是否在测试集结果出来后被选择或调参；
3. Top-k 是否在候选数不大于 k 时仍被报告为有效；
4. insufficient_data 是否仍可能被 NaN 比较绕过；
5. physical_feeder_id、is_mislinked、注入种子是否进入特征、阈值或推荐；
6. 时序仿真是否真正逐时刻执行电压、负载率、功率平衡和收敛检查；
7. 实验失败或违规是否被缓存、聚合或报告为正常完成；
8. Streamlit 子页面是否实际执行过测试；
9. README 和总结数字是否能追溯到同一 run ID、manifest 和自动生成命令；
10. 为通过测试而进行的硬编码、测试弱化、隐藏失败或无关重构。

按 P0/P1/P2 输出发现，每条必须给出文件、行号、复现方法、影响和最小修复建议。若没有阻断问题，明确写“二审整改质量门禁通过”，并列出你实际运行的命令和关键输出；不得仅根据实现代理的口头报告通过验收。
```
