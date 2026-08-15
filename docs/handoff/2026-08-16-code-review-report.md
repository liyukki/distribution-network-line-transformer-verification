# 代码检测报告（供 codex 二审与修复）

- 审查日期: 2026-08-16
- 审查范围: `src/ltverify` 全部 20 个模块、`app` 全部 6 个页面、`configs`、`tests`、`scripts`、`notebooks`、`reports/metrics`
- 基线状态: `pytest -q` 56 passed；`ruff check src app tests scripts` 无告警
- 审查方式: 静态通读 + 针对性运行时验证（关键 bug 均已实际复现，标注见下）
- 本报告只记录问题，未做任何代码修改。codex 请先逐条二审确认，再按优先级修复。

---

## P1 — 严重问题（已运行时复现，必须修复）

### P1-1 鲁棒性看板页面运行时崩溃 (KeyError)

- 位置: `app/pages/5_robustness.py:31,44-47` 配合 `src/ltverify/plotting.py:158-161`
- 问题: 页面默认加载并传入**原始** `experiment_summary.csv`（列为 `precision`/`f1`/...），但 `robustness_line_figure` 读取 `mean_{metric}` / `std_{metric}` 列，这两列只存在于 `experiment_aggregates.csv`。
- 复现证据（已执行）:

  ```text
  python -c "import pandas as pd; from ltverify.plotting import robustness_line_figure; \
    df = pd.read_csv('runs/experiments-20260815T170948-e22672/experiment_summary.csv'); \
    robustness_line_figure(df, 'ledger_error_rate', 'f1')"
  → KeyError: 'mean_f1'
  ```

- 漏测原因: `tests/integration/test_streamlit_smoke.py` 用 `AppTest.from_file` 只执行入口 `streamlit_app.py`，`st.navigation` 的子页面不会被执行，因此该崩溃未被捕获。
- 建议修复: 页面改为加载 `experiment_aggregates.csv`（glob `experiments-*/experiment_aggregates.csv`），或在 `robustness_line_figure` 内兼容原始表自动聚合；同时补充子页面级测试（直接调用绘图函数断言不抛错，或 AppTest 支持时跑页面文件）。

### P1-2 PR-AUC 计算方法学错误（硬标签当分数）

- 位置: `src/ltverify/evaluation.py:49`
- 问题:

  ```python
  pr_auc = average_precision_score(actual.astype(int), predicted.astype(int))
  ```

  把 0/1 硬预测当作 score 传入 `average_precision_score`，AP 退化为单点 precision，不是真正的 PR 曲线下面积。默认运行 `pr_auc=0.1889`（恰等于单点值），且低于基线 0.2083——"增强方法 PR-AUC 反而更差"是该伪影的直接后果，会误导结论。
- 连带不一致: `app/pages/4_evaluation.py:43-44` 画 PR 曲线用的是 `confidence` 作为分数——同一项目存在两套 PR 口径（metrics.json 一套、看板一套），二者数值互不可比。
- 建议修复: 在 `evaluate_predictions` 中用连续分数计算 AP（候选: `margin`、`confidence`、或 `1 - current_score` 归一化），保持与看板一致；`average_precision_score` 的第二参数绝不能是二值预测。同时更新 README 第 91 行引用的 PR-AUC 数字并在报告中重新表述与基线的对比。

---

## P2 — 逻辑与边界缺陷

### P2-1 diagnose 无证据时输出 "no_change"

- 位置: `src/ltverify/scoring.py:101-112`
- 问题: 当 `coverage ≥ minimum_coverage` 但 `current_score` 为 NaN（典型场景: 台账馈线在 corrupted ledger 中成员数 < 2 → `peer_count < 2` → 该候选全部特征 NaN）时，`elif` 条件不成立，decision 停留在 `no_change`。没有证据却输出"不变"，与项目"保守判定、数据不足不强行结论"的设计原则相悖。应归为 `insufficient_data` 或新增独立状态。
- 同源问题: `coverage` 本身可能为 NaN（`features.py:109` `prepared.coverage.get(transformer_id, np.nan)`），而 `coverage < cfg.minimum_coverage` 对 NaN 返回 False，会直接绕过数据不足闸门。建议显式 `pd.isna(coverage)` 判断。

### P2-2 margin 字段输出不完整

- 位置: `src/ltverify/scoring.py:107-112`
- 问题: `margin = best_score - current_score` 只在 `current_score < threshold` 分支内计算；阈值以上时 `best_score` 明明已知，`margin` 却留 NaN，削弱 predictions.parquet 的可解释性。建议无论判定结果如何，只要两分数有效就输出 margin。

### P2-3 safe_corr 的 minimum_pairs 硬编码

- 位置: `src/ltverify/features.py:29`（默认 16）与调用处 `131`
- 问题: 最小有效点数 16 不可配置；`tests/fixtures/small_config.yaml`（1 天、6 小时间隔 = 4 点）下所有相关特征理论上都会 NaN，冒烟测试能通过依赖馈线馈功率路径长度凑巧 ≥16 之外的巧合路径。建议把 `minimum_pairs` 提升为 ScoringConfig 或函数参数，并补一条短窗口行为的显式测试。

### P2-4 feeder_measurements.pivot 无重复容错

- 位置: `src/ltverify/features.py:99-101`
- 问题: `DataFrame.pivot` 遇到重复 `(timestamp, feeder_id)` 直接抛异常；`preprocessing.py:56-61` 对同类数据用的是 `pivot_table(aggfunc="first")` 容错口径。两处不一致，建议统一（推荐 pivot_table 或先显式查重抛 DataContractError，任选其一但保持一致）。

### P2-5 CLI 四个子命令是空壳占位符

- 位置: `src/ltverify/cli.py:14-21, 66-69`
- 问题: `simulate` / `corrupt` / `diagnose` / `evaluate` 子命令只检查配置文件存在后打印 `"prerequisites satisfied"`，不执行任何实际阶段。用户按名字调用会误以为已产出结果。建议：实现分阶段执行，或在 argparse 中明确标注"预留"并在帮助文本与输出中声明未实现（当前输出语句有误导性）。

### P2-6 仿真非收敛后的 init 级联风险

- 位置: `src/ltverify/simulation.py:63-74`
- 问题: 时刻 k 非收敛后，时刻 k+1 仍用 `init="results"`（此刻是 k-1 的旧结果）初始化，可能连锁失败；且失败时刻的量测行直接缺失，无任何 `data_quality_flag` 标记，下游只能靠 coverage 间接吸收，失败不可追溯（与模块 docstring "never silently dropped" 的承诺有出入——failures 表有记录，但量测缺失本身在量测表中无标记）。建议非收敛后下一时刻回退 `init="auto"`，并评估是否需要在量测中标记。

---

## P3 — 文档与实现不一致、死代码、质量项

### P3-1 README 实验能力声明超出实现（重要）

- 位置: `README.md:75-77`
- 问题: 声称 "E0–E9 核心实验、E1 方法对比（Pearson/增强/随机森林）、60/20/20 场景分组划分"。实际：
  - 仓库内无任何随机森林代码（全仓 grep `RandomForest` 0 命中）；
  - `grouped_scenario_split`（`evaluation.py:100`）在生产链路零调用，仅单元测试使用；
  - 实际实现的只有鲁棒性矩阵 + 消融（`experiments.py`）。
- 建议修复: 或者补齐 E1/E7 实现，或者把 README 改为如实描述"当前版本仅实现鲁棒性与消融矩阵，train/val/test 划分与随机森林对比为规划项"。面试场景下该不一致风险很高。

### P3-2 reports/metrics/default_summary.json 不可追溯

- 问题: 该文件含 `baseline_comparison` 与中文 `finding` 字段，但全仓无任何脚本生成它（grep `baseline_comparison` 仅此文件自身），违背 README:87 "以下数字均可由固定命令复现" 的承诺。建议补一个生成脚本（scripts/ 或 CLI 子命令）或注明手工拼装来源。

### P3-3 死代码与无用计算

- `src/ltverify/preprocessing.py:74-76`: `q_wide` 插值后无任何下游消费（features 只用 p_wide），删去或注明保留理由。
- `src/ltverify/pipeline.py:26-30`: `_run_directory(config_path, config_sha256)` 的 `config_path` 参数未使用。
- `app/pages/2_diagnosis.py:44-48`: `value_counts()` 结果永非空（至少含 "clean"），`else` 分支不可达。

### P3-4 隐性配置约束未防护

- `src/ltverify/pipeline.py:21-23`: `INTERPOLATION_LIMIT / ROLLING_WINDOW / EVENT_QUANTILE` 硬编码，与"配置化加权"设计不对称；`experiments.py:21` 又从 pipeline 导入常量，形成反向依赖（experiments → pipeline）。建议进 ScoringConfig/ProfileConfig。
- `src/ltverify/plotting.py:158-161`: 鲁棒性图 x 轴 `value` 为字符串，按字典序排列；当前水位 (0,1,2,4 / 0.0–4.0) 恰好安全，但出现 `10` 会排在 `2` 之前。建议按数值排序或使用有序分类。
- `src/ltverify/plotting.py:7`: `FEEDER_COLORS` 仅 3 条馈线；`NetworkConfig.feeder_count` 允许 ≥2 无上限，≥4 时全部灰色。建议生成式色板。
- `src/ltverify/profiles.py:96`: `periods = days*24*60 // interval_minutes` 整除截断无告警；`profiles.py:126` 相位偏移硬编码 `/3.0`，feeder_count≠3 时相位不再是均匀分布（行为仍确定但设计意图失效）。

### P3-5 测试覆盖缺口清单

- 子页面零测试（P1-1 即漏网）；建议至少为每个 page 的核心绘图调用建立直接单测。
- 无 `diagnose` 的 NaN current_score / NaN coverage 边界用例（对应 P2-1）。
- 无 `evaluation.pr_auc` 连续分数语义的断言（对应 P1-2，修复时必须新增）。
- `tests/unit/test_plotting.py` 未覆盖 `robustness_line_figure` 的输入列契约。

### P3-6 性能小项

- `src/ltverify/corruption.py:83-84`: `[i for i in range(row_count) if i not in set(missing_indices)]` 每次迭代重建 set，O(n²)；30 天 2880×24=69120 行时可感知。预计算 `missing_set = set(missing_indices.tolist())` 即可。

---

## 二审与修复建议顺序

1. P1-1（看板崩溃，改动小、收益直接）
2. P1-2（指标口径，影响结论表述，需同步 README 与报告数字）
3. P2-1 / P2-2（diagnose 边界，注意补测试）
4. P3-1（README 如实化，零代码风险）
5. P2-3 ~ P2-6、P3-2 ~ P3-6 按余量处理

修复验收基线: `pytest -q` 全绿（含新增测试）、`ruff check` 无告警、`python -m ltverify run-all --config tests/fixtures/small_config.yaml` 成功、看板 5_robustness 页面用现有 `runs/experiments-*` 数据可正常渲染。

## 附: 确认无问题的方面

- 真值隔离（truth 只进 evaluation）、台账腐蚀不改物理网络、peer 中心排除自身——防泄漏设计整体到位。
- 原子写（tmp+replace）、manifest 失败记录、实验失败案例保留 error_type/message——工程可靠性良好。
- `disturb_measurements` 的 deep copy 与 RNG 顺序确定，缓存键 `(seed, pv_scale)` 与仿真的实际依赖集合一致，未发现缓存污染。
