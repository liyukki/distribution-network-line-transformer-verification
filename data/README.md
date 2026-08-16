# 数据字典

本目录保存生成数据（默认不入 Git）。所有字段的说明如下；"是否可进入模型特征"为否的字段只允许评价或展示模块读取。

## transformer_measurements.parquet（干净配变量测）

| 字段 | 单位 | 含义与正方向 | 生成方式 | 可进入模型特征 |
|---|---|---|---|---|
| timestamp | datetime | 量测时刻，15 分钟网格，无时区民用本地时间 | 时序潮流采样 | 是 |
| transformer_id | string | 配变唯一编号 T001–T024 | 网络构造 | 是 |
| voltage_pu | p.u. | 低压侧电压标幺值 | 潮流结果 res_bus.vm_pu | 是 |
| p_mw | MW | 配变高压侧净有功，正=消耗，负=反送 | res_trafo.p_hv_mw | 是 |
| q_mvar | Mvar | 配变高压侧净无功，正=消耗 | res_trafo.q_hv_mvar | 是 |
| data_quality_flag | string | 质量标记（clean/noisy/missing/spike/shifted，可组合） | 扰动阶段 | 是 |

## feeder_measurements.parquet（馈线量测）

| 字段 | 单位 | 含义与正方向 | 生成方式 | 可进入模型特征 |
|---|---|---|---|---|
| timestamp | datetime | 量测时刻 | 时序潮流采样 | 是 |
| feeder_id | string | 馈线编号 F01–F03 | 网络构造 | 是 |
| head_voltage_pu | p.u. | 馈线首端母线电压标幺值 | res_bus.vm_pu | 是 |
| p_mw | MW | 首端线路流入功率，正=馈线从母线吸收 | res_line.p_from_mw | 是 |
| q_mvar | Mvar | 首端线路流入无功 | res_line.q_from_mvar | 是 |

## reported_ledger.csv（业务台账）

| 字段 | 单位 | 含义 | 生成方式 | 可进入模型特征 |
|---|---|---|---|---|
| transformer_id | string | 配变编号 | 网络构造 | 是 |
| reported_feeder_id | string | 台账记录的馈线归属（含注入错误） | 错误注入副本 | 是 |
| transformer_capacity_kva | kVA | 配变容量（默认 400） | 网络参数 | 是 |
| customer_type | string | 客户类型 residential/commercial/mixed | 网络构造 | 是 |

## truth_topology.csv（物理真值）

| 字段 | 单位 | 含义 | 生成方式 | 可进入模型特征 |
|---|---|---|---|---|
| transformer_id | string | 配变编号 | 网络构造 | 否（仅评价/演示模式） |
| physical_feeder_id | string | 真实物理馈线 | 网络构造 | 否（仅评价/演示模式） |
| transformer_capacity_kva | kVA | 配变容量 | 网络参数 | 否 |
| customer_type | string | 客户类型 | 网络构造 | 否 |

## observed_measurements.parquet（扰动后量测）

字段与干净量测一致，数值经噪声、缺失、尖峰与时间错位扰动；data_quality_flag 记录扰动类型。主算法输入。

## candidate_features.parquet / predictions.parquet / metrics.json

- candidate_features（打分后产物）：候选特征 12 列 + baseline_score/enhanced_score + available_feature_weight（该行可用特征权重占比，0–1；低于 scoring.evidence_weight_threshold 的候选不参与 best-feeder 比较）。
- predictions：判定结果表，含 decision（insufficient_data/automatic_recommendation/no_change）、confidence（决策解释字段）与 anomaly_score（连续风险分，公式 coverage × min(1 − current_score, max(margin, 0))，证据不足样本为 0.0）。
- metrics.json：precision/recall/f1（二值判定口径）、pr_auc（全样本主指标，连续 anomaly_score；单类别真值时为 null 且 pr_auc_applicable=false、pr_auc_unavailable_reason 说明原因）、pr_auc_scored（scored 子集诊断指标，不可用为 null，附 pr_auc_scored_applicable 与原因字段）、scored_coverage、insufficient_data_rate、top{k}_correction_rate / top{k}_evaluated_count / top{k}_evaluation_coverage（k=1,2,3）、topk_applicable（嵌套 dict）、excluded_candidate_count（被排除的非有限或低证据候选数）、candidate_feeder_count、automatic_coverage、n_total/n_actual_errors/n_actual_correct/n_predicted、base_case_*（含 base_case_severity）。注意 metrics.json 含 null 与嵌套字段，消费方须按键安全取值，不得整体按 float 遍历。

## simulation_validation.csv（逐时刻物理校验）

| 字段 | 含义 |
|---|---|
| timestamp | 量测时刻 |
| converged | 该时刻潮流是否收敛 |
| voltage_min_pu / voltage_max_pu | 全网络电压范围 |
| maximum_transformer_loading_percent | 最大变压器负载率 |
| absolute_power_balance_error_mw | 功率平衡误差 |
| violation_type | 违规类型（\| 连接、去重），空表示无违规 |
| message | 违规详情（\| 连接） |
| severity | ok / warning / critical；critical_violation_types 中的类型为 critical，terminate_on_critical=true 时流水线与实验案例失败 |

## manifest.json（schema 2）

artifact_schema_version=2；output_paths 只存相对安全文件名（禁止绝对路径与 .. 穿越），与 output_sha256 严格一一对应（64 位十六进制 SHA-256）；config.snapshot.yaml 的哈希必须等于顶层 config_sha256（配置快照纳入哈希闭环，篡改后 verify_manifest_hashes 与报告生成都会拒绝）；另含 git_commit、python_version、package_versions、random_seed、status、failure_summary。实验清单（robustness_experiment_manifest.json）额外含 artifact_schema_version、experiment_config_name/sha256/snapshot、base_config_name/sha256/snapshot（解析后的基础配置）与输出文件哈希（robustness_summary.csv / robustness_aggregates.csv），可用 verify_experiment_manifest 校验。

## 隐私与边界

全部数据为合成数据，不含真实电网敏感信息；台账错误与真值只用于基准评价，不得用于任何生产系统。
