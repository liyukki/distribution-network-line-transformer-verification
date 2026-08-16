# 第四轮代码检测报告（供 codex 四审修复）

- 审查日期: 2026-08-16（第四审）
- 审查基线: HEAD = `2719431`（二审修复含 10 个新提交，`25913e7..2719431`）
- 基线状态: `pytest -q` 72 passed；`ruff check src app tests scripts` 无告警
- 审查方式: 对一审报告（`docs/handoff/2026-08-16-code-review-report.md`）全部条目逐项核验修复，再通读二审新增/改动代码（+1715/−379 行）与再生证据文件，查找修复引入的新问题
- 本报告只记录问题，未做任何代码修改

---

## 第一部分: 一审条目修复核验（全部核实）

| 一审编号 | 内容 | 状态 | 核验证据 |
|---|---|---|---|
| P1-1 | 鲁棒性看板 KeyError | ✅ 已修复 | `5_robustness.py:16-18` 改加载 `experiment_aggregates.csv`；`plotting.py:191-197` 显式校验列并抛中文 ValueError；新增 `test_pages.py`、`test_plotting.py` 回归测试 |
| P1-2 | PR-AUC 用硬标签 | ✅ 已修复 | `evaluation.py:51-56` 强制要求 `anomaly_score` 连续分并传入 AP；`scoring.py:182-189` 新增 anomaly_score（coverage × min(1−current, max(margin,0))）；看板 PR 曲线 (`4_evaluation.py:46`) 与 metrics.json 口径统一 |
| P2-1 | 无证据输出 no_change | ✅ 已修复 | `scoring.py:136-150` evidence_complete 闸门：coverage/current/best/margin/current_weight 任一 NaN 或低于阈值 → `insufficient_data` |
| P2-2 | margin 输出不完整 | ✅ 已修复 | `scoring.py:131-135` 两分数有限即计算，与 decision 解耦 |
| P2-3 | minimum_pairs 硬编码 | ✅ 已修复 | `config.py:53` 入 ScoringConfig，pipeline/experiments 透传，`features.py` 全路径带参 |
| P2-4 | pivot 无重复容错 | ✅ 已修复 | `features.py:109-116` 显式查重抛 DataContractError；feeder_p 改 pivot_table |
| P2-5 | CLI 空壳子命令 | ✅ 已如实标注 | `cli.py:24-28,44-49` help 注明"暂未实现"，执行时 stderr 提示并返回 1（功能缺口保留，见 R-5） |
| P2-6 | 非收敛 init 级联 | ✅ 已修复 | `simulation.py:61,68,92` last_step_failed → 回退 flat start；新增逐时刻 validation 记录并落盘 `simulation_validation.csv` |
| P3-1 | README 超额声明 | ✅ 已修复 | README:75-77 拆分"已实现/规划中"，明确随机森林与 60/20/20 划分为规划项 |
| P3-2 | default_summary 不可追溯 | ✅ 已修复 | 新增 `report.py` + `python -m ltverify report`；已核验 `default_summary.json` 的 run_id/git_commit 与 `runs/run-20260816T061442-91e44475-7efe30/manifest.json` 完全一致，指标数值与 README 引文逐项吻合 |
| P3-3 | 死代码 | ✅ 已处理 | q_wide 保留并注明规划用途（`preprocessing.py:66-68`）；`_run_directory` 无用参数已删；`2_diagnosis.py` 不可达分支已删 |
| P3-4 | 隐性配置约束 | ✅ 已修复 | INTERPOLATION_LIMIT/ROLLING_WINDOW/EVENT_QUANTILE 入 ScoringConfig（`config.py:53-57`）；鲁棒性图数值排序（`plotting.py:199-201`）；feeder_count 感知相位（`profiles.py:131-134`）；`feeder_color` 支持 >3 馈线（`plotting.py:12-26`）；interval_minutes 整除校验（`profiles.py:96-101`） |
| P3-5 | 测试缺口 | ✅ 大部分补齐 | 新增 test_pages/test_report/test_simulation 等 13 个测试文件改动，56→72 用例（残留见 R-4） |
| P3-6 | O(n²) set 重建 | ✅ 已修复 | `corruption.py:83-86` 预计算 missing_set |

**结论: 一审 14 项全部实质修复，无假修复。** 额外加分项: 候选馈线集合改为取自 feeder_measurements 而非台账（`features.py:125-127`，消除 corrupted ledger 缩减合法候选集的隐患）；实验缓存改为"校验通过才入缓存"（`experiments.py:175-190`）；实验产物增加 sha256 manifest；演示模式外拓扑图中性着色防真值泄露（`1_network.py`）。

---

## 第二部分: 新发现与残留问题（供四审修复）

### R-1 (P2) 看板对修复前的旧运行目录不向后兼容

- 位置: `app/pages/4_evaluation.py:46` `merged["anomaly_score"]`
- 问题: `runs/` 下现存 90+ 个修复前生成的运行目录，其 `predictions.parquet` 无 `anomaly_score` 列。用户在侧栏输入旧目录并开启演示评价模式时，该行抛 `KeyError: 'anomaly_score'`，整页崩溃（其他页面正常，问题更隐蔽）。
- 建议修复: 捕获 KeyError 转为 `st.warning("该运行目录由旧版本生成，缺少 anomaly_score，无法绘制 PR 曲线")`；或在 `data_access.load_run_artifacts` 中做 schema 版本校验并给出明确错误。

### R-2 (P3) insufficient_data 行的 anomaly_score=0 参与 PR-AUC 有方法学张力

- 位置: `scoring.py:182-189`、`evaluation.py:56`
- 问题: 数据不足的样本（无论真实是否误联）anomaly_score 一律 0.0，被排到排序最底部参与 AP 计算。这与项目"无证据 ≠ 正常"的保守原则存在张力——真实误联但数据不足的样本会直接压低 PR-AUC。属设计选择而非 bug，但 `docs/methodology.md` 未记录该口径。
- 建议修复: 二选一——(a) 在 methodology.md 中明确记录"数据不足按最低异常分处理"的理由与影响；(b) 在 evaluate_predictions 中同时输出仅 scored 子集上的 PR-AUC 作为对照指标。

### R-3 (P3) Top-1/Top-2 数字缺少随机基线参照

- 位置: `README.md` 结果段（Top-1 0.2、Top-2 0.4）
- 问题: 三候选场景下随机排序的期望 Top-1 命中率约 1/3、Top-2 约 2/3；当前 0.2/0.4 均低于随机水平（与"特征无信号"的诚实结论一致，n=5 样本噪声大）。README 引用这些数字时未给出机会水平参照，面试中易被追问"0.4 好不好"。
- 建议修复: README 结果段补一句机会基线说明（与既有"诚实结论与失败边界"段落风格一致，改动一行）。

### R-4 (P3) 鲁棒性页面测试依赖本地产物，干净环境静默跳过

- 位置: `tests/integration/test_pages.py:37-40`
- 问题: `test_robustness_page_renders_with_real_aggregates` 在无 `runs/experiments-*` 产物时 `pytest.skip`——P1-1 的页面级回归防护在干净 checkout/CI 上不生效（单测层面的 ValueError 路径已有覆盖，风险已降低但页面端到端仍依赖环境）。
- 建议修复: fixture 中合成一个两行 `experiment_aggregates.csv` 写入 tmp_path，页面文本框传入该路径，使测试环境无关。

### R-5 (P3-遗留) CLI 分阶段子命令仍为占位

- 位置: `src/ltverify/cli.py:14,44-49`
- 问题: `simulate/corrupt/diagnose/evaluate` 仍是提示性占位（已如实标注，非缺陷）。若四审范围允许，建议要么实现分阶段执行（复用 pipeline 内部函数代价不大），要么从 `_SUBCOMMANDS` 移除并在 README 命令清单中注明仅支持 run-all/experiments/report。

### R-6 (P4-微) report.py 的 pivot 口径与 features.py 不一致

- 位置: `src/ltverify/report.py:33-35` 用严格 `.pivot`
- 问题: 数据来自本仓库流水线，重复键实际不可能出现，风险极低；但二审已把 `features.py` 统一为"显式查重 + DataContractError"，report.py 未跟进同一口径。顺手统一即可。

### R-7 (P4-微) metrics.json 出现嵌套结构

- 位置: `evaluation.py:88-95`（`topk_applicable` 为嵌套 dict、`top3_correction_rate: null`）
- 问题: 现有消费者（4_evaluation 页面、report.py）均按键安全取值，无实际故障；但 metrics.json 的隐含"扁平 float"契约被打破，未来消费者若直接 `float(v)` 遍历会踩 null。建议在 `data/README.md` 数据字典中补记新字段语义（topk_applicable、anomaly_score、scored_coverage、simulation_validation.csv 全套字段）。

---

## 第三部分: 四审建议执行顺序与验收基线

1. R-1（旧目录兼容，用户可见崩溃，改动小）
2. R-3（README 一行补充，零代码风险）
3. R-2（methodology 记录口径或对照指标）
4. R-4（测试环境无关化）
5. R-5 / R-6 / R-7 按余量处理

验收基线（修复后必须全部满足）:

```text
.venv/Scripts/python.exe -m pytest -q          # 全绿（含新增测试）
.venv/Scripts/python.exe -m ruff check src app tests scripts
python -m ltverify run-all --config tests/fixtures/small_config.yaml
python -m ltverify report --run-dir <新运行目录> --output <tmp>.json
# 看板: 旧运行目录 + demo 模式下 4_evaluation 页给出提示而非异常
```

## 附: 确认无问题的方面（四审重点复核项）

- 防泄漏链路复核: truth 仍只进 evaluation；候选集合来自 feeder_measurements 而非台账；演示模式外拓扑中性着色——无新增泄露路径。
- 复现链路复核: README 数字 ↔ `default_summary.json` ↔ `runs/run-20260816T061442-*/manifest.json` 三方一致（run_id、git_commit、全部指标逐项核对通过）。
- 数值稳健性复核: `pd.DataFrame` 混合 None/float 列自动转 float64+NaN，实验聚合 `.mean()` 不受 top-k null 影响（已实测验证）；anomaly_score 对 NaN margin/coverage 经 mask 隔离，无传播路径。
- 一审 P1-1 修复的绘图入口已带显式列校验，且页面 try/except ValueError 兜底，双重防护到位。
