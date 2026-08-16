# 第五轮代码检测报告（供 codex 五审修复）

- 审查日期: 2026-08-16（第五审）
- 审查基线: HEAD = `6405518`（四审修复含 10 个新提交，`7140d20..6405518`）
- 基线状态: `pytest -q` 80 passed；`ruff check src app tests scripts` 无告警
- 审查方式: 对四审报告（`docs/handoff/2026-08-16-fourth-review-report.md`）R-1~R-7 逐项核验；通读四审新增/改动代码（+1430/−260 行）；对证据文件做**字节级复现验证**与运行时验证（详见下文）
- 本报告只记录问题，未做任何代码修改

---

## 第一部分: 四审条目修复核验（全部核实）

| 四审编号 | 内容 | 状态 | 核验证据 |
|---|---|---|---|
| R-1 | 旧运行目录看板崩溃 | ✅ 已修复 | `4_evaluation.py` 按 `artifact_schema_version != 2` 或缺 `anomaly_score` 列识别 legacy run，warning 提示且不绘制 PR 曲线；新增 `test_legacy_run_page_4_shows_warning_without_crash` 回归测试 |
| R-2 | insufficient_data=0 参与 PR-AUC 的口径张力 | ✅ 已修复 | 双管齐下: (a) `evaluation.py:58-69` 新增 `pr_auc_scored`（scored 子集诊断指标，两类不全时 null）+ `scored_coverage`；(b) `methodology.md` 明确记录"证据不足样本按 0.0 惩罚"的理由 |
| R-3 | Top-k 缺机会基线参照 | ✅ 已修复 | README 结果段新增"机会基线参照"小节（Top-1≈1/3、Top-2≈2/3，n=5 不可作显著性结论） |
| R-4 | 鲁棒性页面测试依赖本地产物 | ✅ 已修复 | `test_pages.py:38-66` 改为 tmp_path 合成 aggregates fixture，环境无关 |
| R-5 | CLI 占位子命令 | ✅ 已移除 | `simulate/corrupt/diagnose/evaluate` 从 parser 整体删除，描述注明仅支持 run-all/experiments/report |
| R-6 | report.py pivot 口径 | ✅ 已修复 | `_residual_correlation_means` 前置显式查重抛 DataContractError，与 features.py 同口径 |
| R-7 | metrics.json 嵌套结构未入字典 | ✅ 已修复 | `data/README.md` 补记 metrics.json 全部新字段语义（含"消费方须按键安全取值，不得整体 float 遍历"警告）、simulation_validation.csv 全套字段、manifest schema 2 说明 |

**结论: 四审 7 项全部实质修复。** 本轮额外加分项:

- **证据可复现性闭环**（已实测验证）: `python -m ltverify report --run-dir runs/run-20260816T071854-*` 重新生成的 summary 与 `reports/metrics/default_summary.json` **逐字节一致**（排除 generated_by 静态串后全等，实际该串也相同）；旧 schema 目录执行 report 以明确中文错误退出 1（已实测）。
- **产物完整性**: manifest schema 2 新增 `output_sha256`，`verify_manifest_hashes` 在 report 生成前校验全部产物哈希；default_summary 改为可移植形式（哈希替代机器本地绝对路径）。
- **Top-k 评价更严谨**: 候选须同时满足 enhanced_score 有限且 available_feature_weight ≥ 证据门槛才入排名；同分按 candidate_feeder_id 升序破平（消除行序依赖）；新增 top{k}_evaluated_count / top{k}_evaluation_coverage。
- **物理校验更完整**: 实验表新增 4 类违规计数与最大平衡误差列；130/130 案例在更严格的 critical 门下全部完成（已核验 robustness_summary.csv）。

---

## 第二部分: 新发现问题（供五审修复）

### N-1 (P3) Streamlit 依赖下限与代码不匹配（本轮最重要发现）

- 位置: `pyproject.toml:18` 与 `requirements.txt` 声明 `streamlit>=1.38,<2`；但全部 6 个页面共 12 处调用点已改用 `width='stretch'`（`app/pages/*.py`，grep 已确认无残留 `use_container_width`）
- 问题: `width='stretch'` 语法是 streamlit 较新版本（约 1.4x 后期/1.49 起）才支持的参数形式；当前环境 1.61.1 运行正常（80 测试全绿），但按声明下限 1.38 全新安装的环境会在**每个图表/表格处抛 TypeError**——依赖声明承诺的兼容区间与实际不符。安装越旧崩得越彻底（整个看板不可用）。
- 建议修复: 确定 `st.dataframe`/`st.plotly_chart` 同时支持 `width='stretch'` 的最低版本（建议在干净 venv 中二分验证 1.44/1.46/1.49），将 pyproject 与 requirements 的下限同步上抬（如 `>=1.49`）；或退回 `use_container_width=True`（旧版本警告但兼容）。二选一，不可两者并存。

### N-2 (P4) 默认配置下 warning 严重级不可达，语义收紧未在文档强调

- 位置: `config.py:32-37` 默认 `critical_violation_types` 含全部四类违规（voltage_out_of_bounds、transformer_overload 由前版的 warning 升为 critical）
- 问题: 非缺陷——可配置且有 commit（`237ac14 enforce configured physical violation gates`）支撑，行为是"任一物理违规即终止流水线/实验案例"。但两点值得跟进: (a) `check_solved_network` 的 warning 分支在默认配置下为死代码，仅自定义配置可触达，代码读者会困惑；(b) 语义较前版大幅收紧（前版电压越限/过载仅记录不终止），README"物理检查"段与 methodology 未说明默认策略已是"零容忍"。
- 建议修复: methodology.md 评价与校验节补一句"默认 critical_violation_types 覆盖全部四类违规，即任一违规终止；可通过配置降级为 warning"；或维持现状但接受文档缺口。

### N-3 (P4-微) legacy 识别条件对假想中的未来 schema 误报

- 位置: `app/pages/4_evaluation.py:13-16` `artifact_schema_version != 2` 即判 legacy
- 问题: 若未来出现 schema 3（同样含 anomaly_score），页面会误显示"旧版本生成"提示。保守方向正确（宁可不给图也不崩溃），但提示语不准确。
- 建议修复: 条件改为 `int(version or 0) < 2`（向前兼容更高 schema），或消息区分"低于当前 schema"。改动一行。

### N-4 (P4-微) report.py 每次运行都覆写 default_manifest.json

- 位置: `src/ltverify/report.py` 末尾 `write_json_atomic(artifacts.manifest, output_path.parent / "default_manifest.json")`
- 问题: 输出目录固定为 `output` 的父目录，若用户 `--output` 指向自定义路径（如实验对比目录），会在该目录意外多出一个 `default_manifest.json`。行为可接受但非预期副作用，且 README 未说明该伴生文件。
- 建议修复: 文档补一句（data/README 已有 manifest 说明，加一句"report 命令会在输出同目录写入源 manifest 副本"），或把副本路径并入 `--output` 语义明示。

---

## 第三部分: 五审建议执行顺序与验收基线

1. N-1（依赖下限，影响全新安装环境的可用性声明；先验证最低支持版本再改声明）
2. N-3（一行改动）
3. N-2 / N-4（文档补充，零代码风险，按余量处理）

验收基线（修复后必须全部满足）:

```text
.venv/Scripts/python.exe -m pytest -q                                # 全绿
.venv/Scripts/python.exe -m ruff check src app tests scripts
python -m ltverify run-all --config tests/fixtures/small_config.yaml
python -m ltverify report --run-dir <新运行目录> --output <tmp>.json   # 与仓库 summary 全等
# N-1 修复后: 按新声明下限在干净 venv 安装并启动 streamlit，全部页面无 TypeError
```

## 附: 确认无问题的方面（五审重点复核项）

- **证据三方一致性**: README 引文 ↔ `reports/metrics/default_summary.json`（run `20260816T071854Z-305edb`，commit `b24c9f8`）↔ `runs/run-20260816T071854-*/manifest.json` 全部指标逐项核对通过，含 pr_auc_scored 0.378 / scored_coverage 1.0 / Top-1 0.2 / Top-2 0.4 与机会基线段。
- **复现闭环**: report 命令字节级复现成功（本轮实测）；`robustness_experiment_manifest.json` 记录 130/130 completed 与产物 sha256，与 summary CSV 一致。
- **防泄漏复核**: 候选集合仍来自 feeder_measurements；top-k 排名新增的证据门槛过滤只读打分产物，不触碰真值；truth 合并仍限 evaluation 模块。
- **数值稳健性**: 实验表 130 行 pr_auc_scored 无 null（scored_coverage 均 1.0）；`severity_counts` 的 numpy int 经 pandas to_dict 原生化后 JSON 序列化正常（复现成功即证）。
- 四审修复引入的新测试（test_pages legacy 用例、test_evaluation top-k 资格、test_report 哈希校验）质量良好，断言到具体行为而非仅"不抛错"。

## 总体评价

项目经四轮修复后已达到可对外展示状态: 一至四审全部 21 项问题（2×P1、8×P2、11×P3/P4）均已实质修复且有回归测试；证据链从"手工拼装"演进为"命令复现 + 哈希校验 + 字节级可验证"。本轮仅余 1 项 P3（依赖声明）与 3 项文档级微瑕，无任何阻断性缺陷。
