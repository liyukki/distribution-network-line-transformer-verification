# 第九轮代码检测报告（供 codex 九审修复）

- 审查日期: 2026-08-16（第九审）
- 审查基线: HEAD = `442c609`（八审修复含 6 个新提交，`5d46bdd..442c609`）
- 基线状态: `pytest -q` 174 passed（+38）；`ruff check src app tests scripts` 无告警
- 审查方式: 通读八审新增/改动代码（+1399/−36 行，含新模块 `robustness_loader.py`）；运行时实测: report 字节级复现、`load_robustness_artifacts` 五场景（strict/离线/旧命名/篡改/跨目录混批）、`validate_portable_relative_path` 十六种边界输入、失败运行清单自校验专项测试
- 本报告只记录问题，未做任何代码修改

---

## 第一部分: 八审备注项与隐性修复核验

八审为零缺陷轮，无编号修复项；本轮核验对象为修复方针对 U-1/U-2 备注与看板输入安全主动实施的改进：

| 项目 | 状态 | 核验证据 |
|---|---|---|
| U-1 旧命名实验清单无校验路径 | ✅ 分层解决（方案 b 变体） | `robustness_loader.py` 实现 `strict_verified` / `artifact_hashes_verified` / `legacy_unverified` 三级验证态；`verify_experiment_manifest` 新增 `require_source_configs` 参数并返回 `"strict"/"offline"`；产物哈希始终强制、源配置核验按需分级。已实测: 仓库实验目录 + 两份 configs → strict；不带 configs → offline；旧命名 → 明确"未经验签，仅供兼容展示" |
| 看板输入安全（八审未要求，主动加固） | ✅ 已实施 | 新模块集中处理: 拒绝非普通文件路径、CSV 解析异常转领域错误、聚合/明细表列契约校验（family/value 必列、status 值域）、robustness_* 必须有伴随 manifest 否则拒绝、aggregates 与 summary 强制同目录防混批。已实测: 篡改 aggregates → 验签失败；跨目录混批 → 拒绝 |
| 路径契约再收紧（主动） | ✅ 已实施 | `validate_portable_relative_path` 新增 Windows 保留设备名（CON/PRN/AUX/NUL/COM1-9/LPT1-9，含扩展名前缀）、`<>:"|?*` 非法字符、控制字符、尾随点/空格拒绝。已实测十六种输入全部按预期处理（注: `a. csv` 内部空格为合法可移植文件名，接受正确） |
| 失败运行清单自校验（主动） | ✅ 已实施 | 失败路径改为: 有 config.snapshot 则 manifest 记 [snapshot] 哈希后写入（可自校验）；无 snapshot 则删除 manifest.json（不留不可校验清单）。新增两个专项测试实测通过 |
| manifest.json 写入时机调整（主动） | ✅ 合理 | 初次写入移到 snapshot 拷贝之后，运行中途被 kill 不再留下 status=running 的孤儿 manifest——loader/report 会明确报"缺少 manifest"而非误读 |

**结论: 八审后修复方向正确且全部落地，测试 136 → 174。**

---

## 第二部分: 新发现问题（仅微瑕）

本轮**连续第二轮零功能缺陷**。以下 2 项微瑕 + 1 项管理遗留：

### V-1 (P4-微) 鲁棒性页面存在一处死代码

- 位置: `app/pages/5_robustness.py` 数值列强转后紧接的 `if aggregates[mean_column].isna().all(): st.info(...); st.stop()`
- 问题: 前三行已做 `numeric = pd.to_numeric(...)` + `if not numeric.notna().any(): error+stop`，随后把列替换为 numeric，再判断 `isna().all()`——该条件为 True 时必然已触发前面的 notna 检查，此分支永不可达（已用全非数值列实测确认）。纯冗余，删除三行即可。
- 建议修复: 删除该不可达分支。

### V-2 (P4-微) robustness_loader 的 legacy 路径不校验 aggregates-summary 命名配对

- 位置: `src/ltverify/robustness_loader.py:194-206`
- 问题: 旧命名分支接受 `experiment_` 前缀的任意 aggregates/summary 组合，未要求二者前缀一致（例如 experiment_aggregates + robustness_summary 理论上会被 robustness 分支拦截，但 experiment_summary + robustness_aggregates 会在 robustness 分支因 summary 同目录校验通过而混入——实际上 robustness 分支的 effective_summary 默认为同目录 robustness_summary.csv，用户显式传入 experiment_summary 时位于同目录也放行）。影响仅限展示层且状态为 unverified/warning，无数据损坏风险。
- 建议修复: legacy 分支校验 summary 名称也以 `experiment_` 开头；robustness 分支校验显式传入的 summary 名称以 `robustness_` 开头。两处一行级判断。

### V-3 (管理遗留) 第七/八审报告仍未入库

- `git status` 显示 `2026-08-16-seventh-review-report.md` 与 `2026-08-16-eighth-review-report.md` 均为未跟踪文件（八审 U-3 已提示，本轮修复仍未提交）。审查链文档 1~6 审在库、7~9 审在外，建议收口时一并提交。

---

## 第三部分: 九审结论与验收基线

八审后的加固（输入安全加载层、三级验证态、失败清单自校验）质量高且超出要求；本轮仅 2 项死代码/配对校验微瑕 + 1 项报告入库遗留。**维持上轮建议: 审查收口。** V-1/V-2 可与 U-3 一起作为最终收尾批次处理，无需第十轮。

收口验收基线（合并前最后确认）:

```text
.venv/Scripts\python.exe -m pytest -q                                # 174 全绿
.venv\Scripts/python.exe -m ruff check src app tests scripts
python -m ltverify run-all --config tests/fixtures/small_config.yaml
python -m ltverify report --run-dir runs\run-20260816T121851-b42381de-ca6652 --output <tmp>.json   # 与仓库 summary 全等（本轮实测通过）
git add docs/handoff/2026-08-16-{seventh,eighth,ninth}-review-report.md   # U-3/V-3
```

## 附: 确认无问题的方面（九审重点复核项）

- **load_robustness_artifacts 五场景实测**: strict（configs 全对）/ 离线（无 configs）/ legacy（无 summary，明确降级提示）/ 篡改 aggregates（验签拒绝）/ 跨目录混批（拒绝）——全部符合设计。
- **复现闭环**: HEAD 已前移 6 个提交（均为验证/展示层改动），report 对 run `20260816T121851Z-fb16e1` 仍字节级复现仓库 `default_summary.json`——验证层改动未污染数值链路。
- **失败清单自校验**: 两个专项测试（base-case 不收敛、base-case 后异常）通过，failed manifest 的 input/output 契约与 config_sha256 链完整。
- **verify_experiment_manifest 返回值变更兼容性**: 唯一调用方 robustness_loader 正确消费 "strict"/"offline"；旧调用（report.py 用的是 verify_manifest_hashes，不受影响）。
- **页面 bad-input 测试矩阵**: 新增 11 个页面级测试覆盖坏 CSV/非数值列/目录路径/缺失 status/未知 status/篡改/坏 manifest JSON/缺核心哈希——此前八轮的页面测试盲区已系统性补齐。
- **防泄漏复核**: 新模块只读实验产物与 configs，不触碰真值链路。

## 总体评价

九轮累计: 一审 14 项 → 九审 2 项微瑕，全部修复；测试 56 → 174；连续两轮零功能缺陷。项目从"看板崩溃 + 指标口径错误"起步，现已具备输入安全层、三级证据验证、失败路径自校验与字节级可复现证据链。**审查流程至此完成历史使命，建议执行 V-1/V-2/V-3 收尾后正式收口合并。**
