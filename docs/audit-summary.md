# 公开审计摘要

## 项目定位

这是一个面向电网/能源数字化实习的可复现研究型原型。项目使用合成配电网数据，通过时序潮流仿真、可解释统计特征和保守判定规则，演示“10 kV 馈线—配电变压器”台账错误校验的完整链路。

## 主要信任边界

- **真值隔离**：`physical_feeder_id` 与 `is_mislinked` 只进入评价/展示流程，不进入模型特征。
- **Manifest checksum**：运行产物通过 `manifest.json` 的 SHA-256 哈希声明进行一致性校验。页面和报告采用“先校验、后解析”顺序。
- **Current schema**：主看板磁盘入口只接受 current schema-v2 的 completed 运行；旧版、未来版和非法版在加载前拒绝。
- **Verify-before-parse**：首页在读取任何 CSV/Parquet/metrics 前，先验证 manifest 声明、哈希和普通文件契约。
- **Dashboard artifact binding**：首页实际读取的每个文件都必须属于 manifest 声明的权威集合；删除声明不能绕过校验。
- **Cross-artifact semantic binding**：loader 在返回前还会校验 truth/ledger/predictions/metrics/confusion matrix 之间的 ID、计数、coverage 与 precision/recall/F1 一致性。
- **Public default evidence bundle**：`reports/evidence/default_run/` 包含一份已通过 manifest 校验的合成默认运行，全新 clone 无需访问本机 ignored `runs/` 即可逐字节复现规范报告。

## 典型修复案例

- **Label leakage**：早期评审发现物理真值可能进入特征链路，已通过数据字典和测试固定隔离边界。
- **NaN 排名**：Top-k 排名会排除 NaN 与正负无穷候选，避免非有限分数参与推荐。
- **证据可复现**：默认报告与清单可由固定命令逐字节复现；实验清单支持严格源配置交叉核验。
- **Dashboard artifact binding**：修复了“清单只校验声明文件，但页面读取未声明文件”的绕过路径，使展示数据与验证数据一致。

## 最终测试与证据状态

- 全量测试通过，覆盖率保持在 90% 以上。
- 默认 `default_summary.json` 与 `default_manifest.json` 可由公开证据包或源运行目录逐字节复现。
- 权威实验清单严格验证返回 `strict`。
- 鲁棒性加载返回 `strict_verified`。
- 鲁棒性实验矩阵保持 130 行。

## Checksum 不是数字签名

当前机制使用 SHA-256 哈希一致性校验。它能检测意外损坏或未同步更新清单的修改；如果攻击者可同时改写产物与同目录清单，单靠 SHA-256 不能证明发布者身份或来源真实性。需要更强真实性保证时，应依赖可信 Git commit/tag、发布签名或外部只读证据根。

## 未解决的研究限制

- 合成数据的电压特征区分度有限，默认参数化下 F1 仅约 0.167，PR-AUC 约 0.378。
- 当前版本不处理三相不平衡、相别识别或户变关系。
- 尚未接入真实电网数据，不能宣称现场部署或生产准确率。
- 训练/验证/测试的 60/20/20 分组工具已实现，但尚未接入生产链路。
