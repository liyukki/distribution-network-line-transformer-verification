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

候选特征表（12 列，含 peer_count 与 8 个特征 + coverage）、判定结果表（decision/confidence 等）与评价指标（precision/recall/f1/pr_auc/top1/top3/coverage/拒判率）。

## 隐私与边界

全部数据为合成数据，不含真实电网敏感信息；台账错误与真值只用于基准评价，不得用于任何生产系统。
