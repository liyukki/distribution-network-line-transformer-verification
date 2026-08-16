# 第八轮代码检测报告（供 codex 八审修复）

- 审查日期: 2026-08-16（第八审）
- 审查基线: HEAD = `c74d75b`（七审修复含 8 个新提交，`c09e174..c74d75b`）
- 基线状态: `pytest -q` 136 passed（+35）；`ruff check src app tests scripts` 无告警
- 审查方式: 对七审报告（`docs/handoff/2026-08-16-seventh-review-report.md`）T-1~T-3 逐项核验；通读七审新增/改动代码（+1231/−58 行）；运行时实测: report 对新 run `20260816T121851Z-fb16e1` 字节级复现、`verify_experiment_manifest` 含快照等价比对的完整校验、看板默认路径选择逻辑三场景模拟（仓库实况/仅旧命名/混合）、`validate_portable_relative_path` 九种恶意输入拒绝测试
- 本报告只记录问题，未做任何代码修改

---

## 第一部分: 七审条目修复核验（全部核实）

| 七审编号 | 内容 | 状态 | 核验证据 |
|---|---|---|---|
| T-1 | 看板 glob 不认旧命名实验目录 | ✅ 已修复 | `_default_experiment_paths` 全局优先 robustness_*、按目录回退 experiment_*、两路径同目录防混批。已实测三场景: 仓库实况正确选中 `experiments-20260816T104606-7e16a9/robustness_*`；仅旧命名环境回退成功；混合环境优先新命名。新增页面测试覆盖 |
| T-2 | 重复检查在循环内 | ✅ 已修复（超额） | 未止于移出循环——升级为 `REQUIRED_EXPERIMENT_OUTPUTS` 精确集合校验（缺失/多余均报错），比建议方案更严 |
| T-3 | non_convergence 报错无迁移提示 | ✅ 已修复 | `config.py` 命中该值时追加"已改为无条件硬失败，请从列表中移除" |

**结论: 七审 3 项全部实质修复。** 本轮额外加分项（超出七审要求）:

- **共享路径契约**: 新增 `validate_portable_relative_path`（拒绝盘符/反斜杠/UNC/绝对/空段/点段/`..`，POSIX 语义防跨平台绕过），run 与 experiment 两套清单统一复用。已实测九种恶意输入全部拒绝、正常相对路径通过。
- **清单可移植性收口**: `input_paths` 只记配置文件名（如 `default.yaml`），不再泄露本机绝对路径；`RunManifest.failure_summary` 放宽为 object 以承载结构化失败上下文。
- **失败上下文结构化**: base-case 终止型失败时 `failure_summary` 附带 stage/severity/violation_count/violation_types/violations，README/methodology/data README 三处同步记录。
- **verify_experiment_manifest 大幅强化**: 校验配置 name+哈希+**快照内容等价**（与原始 YAML/解析配置逐一比对）、case_counts 类型严格化（拒 bool/负数/非整）、summary status 值域与 completed/failed 计数一致性。已实测仓库清单 + 两份原始配置全链路校验通过。
- **测试增长**: 101 → 136 用例，新增覆盖路径契约、失败上下文、页面默认路径、证据文件自校验扩展。
- **复现闭环维持**（本轮实测）: run `20260816T121851Z-fb16e1`（commit `533b64a`）report 再生 summary 与仓库证据逐字节一致；README 引文同步更新。

---

## 第二部分: 新发现问题（仅备注级，无缺陷）

本轮**未发现任何功能缺陷、口径问题或泄露风险**。以下为两条备注与一条仓库管理事项，均不构成必须修复项：

### U-1 (备注) 旧命名实验清单无校验路径

- `verify_experiment_manifest` 现严格要求 output_files 精确等于 `{robustness_summary.csv, robustness_aggregates.csv}`，旧命名清单（如 `runs/experiments-20260815T170948/` 内的 legacy manifest 结构）无法用新校验器验证。这与"权威命名"政策及 schema 版本化一致，属有意取舍；如需给旧证据提供验真手段，可加 legacy 名称兼容分支（输出弃用警告），优先级极低。

### U-2 (备注) 看板默认路径"命名优先于新近"

- `_default_experiment_paths` 在混合环境下会选**较旧目录中的 robustness_** 产物而非**最新目录中的 legacy** 产物。docstring 已声明该意图（避免混批、优先权威命名），行为正确；仅提示使用者知悉"默认展示的不一定是时间上最新的实验"。

### U-3 (仓库管理) 第七审报告未入库

- `git ls-files docs/handoff` 显示第 1~6 审报告均已提交，但 `2026-08-16-seventh-review-report.md` 仍为未跟踪状态（七审修复只提交了 remediation prompt）。建议随本批修复一并提交，保持审查链完整。

---

## 第三部分: 结论与验收基线

七审 T-1~T-3 全部修复且质量超出要求；本轮零编号缺陷。**建议: 项目审查正式收口。** 若处理 U-3（提交报告文件）后合并即可，无需第九轮。

收口验收基线（合并前最后确认）:

```text
.venv/Scripts/python.exe -m pytest -q                                # 136 全绿
.venv\Scripts\python.exe -m ruff check src app tests scripts
python -m ltverify run-all --config tests/fixtures/small_config.yaml
python -m ltverify report --run-dir <运行目录> --output <tmp>.json    # 与仓库 summary 全等
python -c "from ltverify.experiments import verify_experiment_manifest; ..."  # 证据自校验通过
```

## 附: 确认无问题的方面（八审重点复核项）

- **路径契约攻击面**: 九种恶意/畸形输入（盘符正反斜杠、UNC、绝对、`..`、`.`、空段、空串、None）全部拒绝，POSIX 语义确保 Windows 分隔符无法在 Linux 主机上绕过。
- **快照等价校验的边界**: experiment 快照走 `_portable(yaml.safe_load(...))`、base 快照走 `_portable(load_config(...).model_dump())`，与生成侧完全同构（实测等价通过）；YAML 键序不影响 dict 等价。
- **failure_summary 序列化**: 结构化字段均为 str/list/int，`model_dump(mode="json")` 安全；`allow_nan=False` 不受影响。
- **证据四方一致性**: README（run `20260816T121851Z-fb16e1`）↔ default_summary.json ↔ runs/run-20260816T121851-*/manifest ↔ default_manifest.json 逐项核对通过；实验清单与 configs 当前字节哈希及快照内容一致（实测）。
- **防泄漏复核**: 本轮改动集中于清单契约、失败上下文与看板默认路径，特征/评分/评价链路零改动。

## 总体评价

八轮累计 31 项问题（2×P1、8×P2、11×P3、10×P4）全部修复；连续四轮无 P1~P3 级发现，本轮首次实现**零编号缺陷**。工程质量指标（测试 56→136、证据可字节级复现、篡改即拒、跨 OS 可移植）已达到并超出原始验收要求。**审查流程至此完成使命，建议收口。**
