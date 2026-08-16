# 第六轮代码检测报告（供 codex 六审修复）

- 审查日期: 2026-08-16（第六审）
- 审查基线: HEAD = `67aaeb3`（五审修复含 9 个新提交，`c12c434..67aaeb3`）
- 基线状态: `pytest -q` 94 passed；`ruff check src app tests scripts` 无告警
- 审查方式: 对五审报告（`docs/handoff/2026-08-16-fifth-review-report.md`）N-1~N-4 逐项核验；通读五审新增/改动代码（+1318/−232 行）；对新证据做**字节级复现验证**与针对性运行时实验（含自构造数据验证 excluded_candidate_count 语义）；查询 Streamlit 官方文档核验依赖声明
- 本报告只记录问题，未做任何代码修改

---

## 第一部分: 五审条目修复核验（全部核实）

| 五审编号 | 内容 | 状态 | 核验证据 |
|---|---|---|---|
| N-1 | streamlit 依赖下限不匹配 | ✅ 已修复 | `pyproject.toml` 与 `requirements.txt` 同步上抬至 `>=1.51,<2`；已对照官方 v1.61 文档确认 `width="stretch"` 为现行标准参数（`use_container_width` 已标记 deprecated），1.51 处于该参数引入之后，声明安全（残留事项见 S-3） |
| N-2 | warning 严重级不可达/策略未文档化 | ✅ 已修复 | 三层落实: (a) `config.py` 新增 `ALLOWED_VIOLATION_TYPES` 校验器——未知类型加载即失败、重复类型去重；(b) `pipeline.py` base-case 改为仅 `severity == critical` 且 `terminate_on_critical` 时终止，warning 不再一刀切中断，`metrics["base_case_severity"]` 落盘；(c) methodology.md 新增"物理校验策略"节，明确零容忍默认与降级语义 |
| N-3 | legacy 识别对未来 schema 误报 | ✅ 已修复 | `4_evaluation.py` 改三态: legacy（缺失/解析失败/<2）/ current（=2）/ newer（>2，提示"未验证的 schema 版本"仅展示有限字段）；新增 `test_schema_three_state_branches` |
| N-4 | report 意外落 default_manifest.json | ✅ 已修复 | `report.py` 副本路径改为 `<输出词干>.manifest.json`，并新增 `--manifest-output` CLI 参数显式指定；CLI 默认值帮助文本同步更新 |

**结论: 五审 4 项全部实质修复。** 本轮额外加分项（超出五审要求）:

- **指标适用性显式化**（已实测）: 单类别真值时 `pr_auc` 输出 `null + pr_auc_applicable=false + pr_auc_unavailable_reason`（single_class_all_positive / single_class_all_negative），杜绝"NaN 冒充 0"；新增两个单类别边界测试。
- **Top-k 非有限值防御**: `np.isfinite` 同时过滤 NaN 与 ±Inf 的 enhanced_score/available_feature_weight，被排除候选计入 `excluded_candidate_count`；我构造含 inf/−inf/NaN 的候选分实测，排除与不可评价行为符合文档描述。
- **manifest 校验大幅强化**: `verify_manifest_hashes` 现在强制 output_paths 与 output_sha256 一一对应、拒绝绝对路径/盘符/`..` 穿越、校验 64 位十六进制格式、并把 `config.snapshot.yaml` 纳入哈希链（必须等于顶层 config_sha256）；pipeline 把 config.snapshot.yaml 计入 outputs（13 个产物全哈希，已核验 default_manifest.json）。
- **JSON 序列化收紧**: `write_json_atomic` 加 `allow_nan=False`，NaN/Inf 无法再静默写入产物 JSON。
- **实验清单补强**: experiment_manifest 增加 base_config 的 sha256 与解析后快照（篡改基础配置可被检测）。
- **复现闭环维持**（本轮实测）: `python -m ltverify report --run-dir runs/run-20260816T083229-* --manifest-output <tmp>` 再生 summary 与 `reports/metrics/default_summary.json` 逐字节一致；README 引文（run `20260816T083229Z-1c17b5`）与仓库证据一致；130/130 案例全 completed，robustness summary 无 null pr_auc。
- **鲁棒性看板补全指标**: pr_auc/pr_auc_scored/scored_coverage/insufficient_data_rate 入选指标下拉，列缺失或全 NaN 时 info 提示而非报错，配 caption 说明双口径解读。

---

## 第二部分: 新发现问题（均为轻微项）

### S-1 (P4) base-case warning 违规详情不落盘

- 位置: `src/ltverify/pipeline.py:63-68,133`（metrics 仅记录 `base_case_severity`）
- 问题: N-2 修复后 base-case 出现 warning（如电压越限被降级）时流水线继续运行，但 `base_case.violations` 的具体消息未写入 metrics.json 或任何产物——运行者只知道"有 warning"，不知道为什么。时序工况有 simulation_validation.csv 全量记录，base-case 没有对应物。
- 建议修复: metrics 增加 `base_case_violation_count` 与 `base_case_violations`（或至少前 N 条消息），一行改动。

### S-2 (P4-微) 实验清单的 base_config 路径依赖当前工作目录（遗留）

- 位置: `src/ltverify/experiments.py`（`load_config(Path(raw["base_config"]))` 与 `_file_sha256(Path(raw["base_config"]))`）
- 问题: `base_config: configs/default.yaml` 是相对路径，按进程 CWD 解析而非按实验配置文件所在目录解析。从其他目录执行 `python -m ltverify experiments --config D:\...\configs\robustness.yaml` 会 FileNotFoundError。属一至五审均未覆盖的遗留问题（非本轮修复引入），出现概率低。
- 建议修复: 以实验配置文件父目录为基准拼接 `raw["base_config"]`（仅当相对路径时）。

### S-3 (P4-微) streamlit 1.51 下限缺乏推导记录

- 位置: `pyproject.toml:18` / `requirements.txt`
- 问题: 官方文档只标注参数"现状"，未标注引入版本；1.51 声明本身安全（参数引入时间线早于 1.51），但仓库内无任何记录说明该下限如何得出，未来维护者无从判断能否下调。
- 建议修复: 在 pyproject 依赖行加一句注释（如 `# width='stretch' in all app pages; verified against 1.51`），或在 methodology/README 口径说明段落引用验证方法。零代码风险。

---

## 第三部分: 六审建议执行顺序与验收基线

1. S-1（一行级补全，可观测性收益直接）
2. S-3（注释级，零风险）
3. S-2（按余量处理，注意同时修 load_config 与 _file_sha256 两处）

验收基线（修复后必须全部满足）:

```text
.venv/Scripts/python.exe -m pytest -q                                # 全绿（≥94 用例）
.venv/Scripts/python.exe -m ruff check src app tests scripts
python -m ltverify run-all --config tests/fixtures/small_config.yaml
python -m ltverify report --run-dir <新运行目录> --output <tmp>.json   # 与仓库 summary 全等
# S-2 修复后: 从非仓库根目录执行 experiments --config <绝对路径> 能正确解析 base_config
```

## 附: 确认无问题的方面（六审重点复核项）

- **excluded_candidate_count 语义**: 代码中该计数在每个 k 循环内重置，看似可疑；已用自构造数据实测——资格集合与 k 无关，逐 k 计数相同，最终值为"被排除的（设备,候选）对数"，语义正确（测试断言 >= 2 与实测 2 一致）。
- **证据四方一致性**: README ↔ default_summary.json（run `20260816T083229Z-1c17b5`，commit `94ee059`）↔ runs/run-20260816T083229-*/manifest ↔ default_manifest.json（schema 2、13 产物哈希、config.snapshot.yaml 入链）逐项核对通过；report 命令字节级复现成功。
- **allow_nan=False 的边界**: 全部 JSON 产物路径（metrics/manifest/summary）审查无 NaN 来源；failure_boundary 的 np.nanmean 在 feeder_count≥2 下不可能为空集；severity_counts 的 numpy 标量经 pandas to_dict 原生化（复现成功即证）。
- **防泄漏复核**: truth 合并仍限 evaluation；实验清单快照含的是配置而非真值；新增校验代码不触碰特征链路。
- **新增测试质量**: 单类别 PR-AUC 双向、Top-k 非有限值、schema 三态、base-case warning 不中断、manifest 篡改拒绝——断言均到具体行为，94 用例无仅"不抛错"的空壳断言。

## 总体评价

六轮累计 25 项问题（2×P1、8×P2、11×P3、4×P4）已全部修复；五审修复质量为历轮最高——不仅覆盖全部条目，还主动补强了指标适用性、Top-k 有限值防御与清单哈希链。本轮无任何 P1/P2/P3 级新发现，仅 3 项 P4 微瑕（1 项可观测性、1 项遗留路径解析、1 项注释记录）。**项目已连续两轮无实质缺陷，建议本轮融资式审查可以收口**；若执行 S-1~S-3 后即合并，可不再进行第七轮。
