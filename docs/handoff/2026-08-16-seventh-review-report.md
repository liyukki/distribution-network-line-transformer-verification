# 第七轮代码检测报告（供 codex 七审修复）

- 审查日期: 2026-08-16（第七审）
- 审查基线: HEAD = `26a4a55`（六审修复含 8 个新提交，`d3503fd..26a4a55`）
- 基线状态: `pytest -q` 101 passed；`ruff check src app tests scripts` 无告警
- 审查方式: 对六审报告（`docs/handoff/2026-08-16-sixth-review-report.md`）S-1~S-3 逐项核验；通读六审新增/改动代码（+1570/−504 行）；运行时实测: report 字节级复现（对仓库证据实际引用的 run `20260816T104417Z-8b3337`）、`verify_experiment_manifest` 自校验与配置哈希比对、`_resolve_base_config` 三种路径输入
- 本报告只记录问题，未做任何代码修改

---

## 第一部分: 六审条目修复核验（全部核实）

| 六审编号 | 内容 | 状态 | 核验证据 |
|---|---|---|---|
| S-1 | base-case warning 违规详情不落盘 | ✅ 已修复 | `pipeline.py:135-137` metrics 落盘 `base_case_violation_count` / `base_case_violation_types` / `base_case_violations` 三字段 |
| S-2 | base_config 相对路径按 CWD 解析 | ✅ 已修复 | 新增 `_resolve_base_config`（实验 YAML 父目录为基准）；`configs/robustness.yaml` 改为 `base_config: default.yaml`；已实测三种输入（相对/带子目录/绝对）解析均正确；新增 `test_base_config_resolves_relative_to_experiment_yaml` |
| S-3 | streamlit 1.51 下限无推导记录 | ✅ 已修复 | README 口径说明段落记录"Streamlit 最低版本 1.51"（`README.md` 结果段口径说明句） |

**结论: 六审 3 项全部实质修复。** 本轮额外加分项（超出六审要求，六审修复质量与五审持平）:

- **report 先验证后解析**: `generate_default_summary` 重构为"读 manifest → schema 分类 → 全量哈希校验 → 再加载 parquet"，篡改产物现在报完整性错误而非解析错误（新增 `test_report_verifies_before_parsing`、`test_tampered_snapshot_yields_integrity_error_not_parse_error`）；并拒绝输出路径与源运行目录任何产物碰撞（含 manifest.json / config.snapshot.yaml），防止 report 覆写证据源。
- **实验产物统一改名 + 可移植化**: `experiment_summary/aggregates/manifest` → `robustness_*`（与仓库存放名一致，消除双名歧义）；manifest 改记 `experiment_config_name/base_config_name`（文件名）替代本机绝对路径，快照内字符串统一 POSIX 分隔符——跨 OS 检出后哈希链不断。
- **新增 `verify_experiment_manifest`**: 校验 schema、安全相对路径、64 位哈希、文件字节相等、case_counts 一致性、summary 行数一致性，可对照原始配置文件验哈希。已实测: 仓库 `robustness_experiment_manifest.json` 自校验通过，且与 `configs/robustness.yaml`、`configs/default.yaml` 当前字节哈希一致。
- **schema 分类收紧为共享函数**: `classify_artifact_schema_version` 严格拒绝 bool/float/字符串/None（返回 invalid 四态），report 与 4_evaluation 页面共用同一实现，消除两处口径漂移可能；invalid 态页面 error + stop。
- **`non_convergence` 从可配置集合移除**: 与 methodology"不收敛始终硬失败"政策对齐——仿真失败行 severity 硬编码 critical、pipeline 对 failures 非空无条件终止，本就不可降级，现在配置层面也无法误配（误配旧值会在加载时被 ALLOWED_VIOLATION_TYPES 校验拒绝）。
- **字节稳定性防回归**: 新增 `.gitattributes`（`-text` 锁定 configs/fixtures/reports 证据文件行尾），`core.autocrlf` 不再破坏 `config_sha256` 哈希链；新增 `tests/unit/test_evidence.py` 让交付证据文件自校验入测试。
- **复现闭环维持**（本轮实测）: 对 run `20260816T104417Z-8b3337`（commit `7d39efb`）执行 report，再生 summary 与仓库 `default_summary.json` 逐字节一致。

---

## 第二部分: 新发现问题（仅轻微项）

### T-1 (P4) 实验产物改名无向后兼容，旧实验目录被看板"遗忘"

- 位置: `app/pages/5_robustness.py:18,57`（glob 仅匹配 `experiments-*/robustness_*.csv`）；`src/ltverify/experiments.py` `verify_experiment_manifest`（只认新文件名）
- 问题: `runs/` 下现存 3 个旧实验目录（`experiments-20260815T170948`、`20260816T054858`、`20260816T061442`）内是旧名 `experiment_summary.csv` / `experiment_aggregates.csv`。改名后: (a) 看板默认 glob 找不到它们，显示"未找到实验聚合产物，请先运行"——但产物其实存在；(b) 手动输入旧 aggregates 路径仍可绘图（列名未变），无崩溃。属 UX 退化而非故障。
- 建议修复: glob 模式同时匹配新旧两种文件名并优先取新（`experiments-*/robustness_aggregates.csv` 优先、退回 `experiments-*/experiment_aggregates.csv`），或在页面 info 文案中说明"旧命名实验目录请手动输入路径"。

### T-2 (P4-微) verify_experiment_manifest 重复检查位于循环内

- 位置: `src/ltverify/experiments.py` `verify_experiment_manifest` 中 `if len(set(output_files)) != len(output_files)` 写在 for 循环体内
- 问题: 该检查与循环变量无关，每个条目重复执行一次（O(n²) 且语义上属于前置校验）。功能正确（实测通过），纯代码卫生问题。
- 建议修复: 移到循环前，与其他结构校验并列。一行移动。

### T-3 (P4-微) 旧配置含 non_convergence 时的报错未指向迁移做法

- 位置: `src/ltverify/config.py` `validate_critical_types`（未知类型报错只列允许值）
- 问题: 用户带着六审版本生成的旧 YAML（含 `non_convergence`）升级后会收到"未知的 critical_violation_types: ['non_convergence']"，但不知道该直接删除该项（因为不收敛本来就无条件硬失败）。报错信息可以更友好。
- 建议修复: 校验器报错信息补一句"non_convergence 已改为无条件硬失败，请从列表中移除"。仅当命中该特定值时附加。

---

## 第三部分: 七审建议执行顺序与验收基线

1. T-1（看板 glob 兼容旧命名，用户可见）
2. T-3（报错文案，一行级）
3. T-2（代码卫生，随手）

验收基线（修复后必须全部满足）:

```text
.venv/Scripts/python.exe -m pytest -q                                # 全绿（≥101 用例）
.venv\Scripts\python.exe -m ruff check src app tests scripts
python -m ltverify run-all --config tests/fixtures/small_config.yaml
python -m ltverify report --run-dir <新运行目录> --output <tmp>.json   # 与仓库 summary 全等
# T-1 修复后: 看板在仅有旧命名 experiments-*/ 目录时能自动定位旧 aggregates 文件
```

## 附: 确认无问题的方面（七审重点复核项）

- **4_evaluation PR 支持判定的运算符优先级**: `required <= set(preds) | set(truth)` 按 Python 优先级解析为 `required <= (set|set)`，与意图一致（physical_feeder_id 在 truth 侧），已人工核验。
- **report 输出碰撞防护**: 覆盖 output_path==manifest_target、以及与 run_dir 全部产物（含 manifest/config.snapshot）的碰撞，两条路径均检查；新增 `test_report_rejects_output_collisions`。
- **改名一致性全链路核验**: experiments 写出 → cli 读取 → 看板 glob → plotting 报错文案 → notebook 03 → README/data README 引用，全部同步为 robustness_*，无遗漏引用（grep 确认）。
- **证据四方一致性**: README（run `20260816T104417Z-8b3337`）↔ default_summary.json ↔ runs/run-20260816T104417-*/manifest ↔ default_manifest.json；实验清单 case_counts 130/130 与 summary 行数一致（verify 实测通过）；configs 当前字节与 robustness manifest 记录的哈希一致（实测通过）。
- **allow_nan=False / _portable / .gitattributes 组合**: 交付 JSON 无 NaN 源；跨 OS 检出路径与行尾均不再破坏哈希链（-text 覆盖 configs、fixtures、reports/metrics 的 csv 与 json）。
- **防泄漏复核**: 本轮改动全部位于证据/校验/展示层，特征与评分链路零改动，无新增泄露路径。

## 总体评价

七轮累计 28 项问题（2×P1、8×P2、11×P3、7×P4）全部修复。本轮新发现仅 3 项 P4（1 项旧目录 UX 兼容、2 项文案/代码卫生），无任何功能缺陷、无指标口径问题、无泄露风险。六审修复主动补强了"先验证后解析"、产物改名可移植化与跨 OS 字节稳定三项超出要求的工程改进。**连续三轮无 P1~P3 级发现，项目已稳定收敛；建议 T-1~T-3 作为收尾批次处理后停止迭代审查。**
