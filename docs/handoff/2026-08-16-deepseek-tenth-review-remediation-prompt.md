# DeepSeek 第十轮整改执行提示词：收紧首页运行产物信任边界

> 使用方式：把本文完整交给 DeepSeek V4 及其 agent harness。本文是可执行整改任务书，不是泛化建议。请在当前仓库继续工作，严格按“红测 → 最小实现 → 全量验证 → 提交”的顺序执行。

## 1. 角色、目标与硬约束

你是本项目第十轮整改执行者。目标不是扩展算法，而是修复运行产物进入 Streamlit 首页时的信任边界，使“页面展示的数据”和“清单实际校验的数据”严格一致，并让异常输入稳定转化为用户可理解的领域错误。

必须遵守：

1. 以 `e919cb4` 为整改基线；先确认 HEAD 和工作区，不得 reset、clean 或覆盖用户文件。
2. 当前未跟踪的以下三份审查报告属于用户/其他 AI，不纳入本轮提交：
   - `docs/handoff/2026-08-16-seventh-review-report.md`
   - `docs/handoff/2026-08-16-eighth-review-report.md`
   - `docs/handoff/2026-08-16-ninth-review-report.md`
3. 先写能在 `e919cb4` 上稳定失败的回归测试，再修改实现；不得只改文案或只写 happy-path 测试。
4. 不修改特征工程、模型阈值、标签生成、评价口径和 30 天/130 案例实验数据。
5. 不实现没有密钥管理和可信根设计的“数字签名系统”。本轮只诚实描述并收紧现有 SHA-256 一致性校验。
6. 不重写历史审查文档中的旧表述；只修正当前 README、methodology、运行时消息和当前测试所代表的产品语义。
7. 不提交缓存、临时目录、运行产物或上述三份未跟踪报告；不 push。

## 2. 审查基线与已核实结果

### 2.1 基线提交

第九轮交接提交为 `c99b98a`，DeepSeek 后续提交为：

```text
330c9a6 test: reproduce ninth-review trust-boundary regressions
2678667 fix: bind robustness verification to displayed files
e456f92 fix: keep running manifests self-verifying
9884242 fix: validate manifest element types before deduplication
e919cb4 docs: clarify verified robustness artifact identity
```

第九轮要求中的以下内容已经实质修复，不要回退：

- current/legacy 实验文件角色已按精确 basename 绑定，混批与 forged 前缀文件会被拒绝；
- current 实验清单顶层非 object 会被拒绝；
- aggregates 的 `family/value` 缺失、空白和异常数值已收紧；
- running manifest 创建时已立即记录配置快照哈希；
- manifest 输入/输出路径元素会在集合去重前做字符串类型检查；
- 鲁棒性页默认发现会跳过不完整的 current 候选。

### 2.2 本轮健康基线

Codex 已在 `e919cb4` 上实测：

```text
.venv\Scripts\python.exe -m pytest -q
# 214 passed in 42.19s

.venv\Scripts\python.exe -m ruff check src app tests scripts
# All checks passed!
```

证据闭环也仍然成立：

```text
report_summary_byte_match=True
report_manifest_byte_match=True
experiment_manifest_level=strict
robustness_loader_state=strict_verified
robustness_rows=130
```

因此本轮不得重跑或改写默认 30 天数据、130 案例实验与 `reports/metrics` 权威证据。问题位于加载、验证、展示边界，不在算法证据本身。

## 3. 第十轮新发现摘要

| 编号 | 优先级 | 问题 | 当前后果 |
|---|---:|---|---|
| T10-1 | P1 | 首页 `load_run_artifacts` 完全绕过 run manifest 哈希校验 | 篡改 `metrics.json` 后仍展示伪造指标 |
| T10-2 | P2 | 首页加载器未统一校验 JSON object、普通文件与解析异常 | malformed JSON/CSV/parquet 或 list manifest 可泄漏原始异常并使页面崩溃 |
| T10-3 | P2 | 产品文案把无密钥 SHA-256 一致性校验称为“验签” | 对来源真实性和抗协同篡改能力作出过度承诺 |
| T10-4 | P2 | legacy summary 允许缺失/空白 `status` | 缺失状态被页面误报为失败案例 |
| T10-5 | P2 | 清单声明目录时，验证器只检查 `exists()` | `_file_sha256` 泄漏 `PermissionError/OSError`，页面可崩溃 |
| T10-6 | P3 | 首页默认运行目录只按名称倒序取第一个 | 新的 failed/running/incomplete run 会遮挡旧的 completed run |
| T10-7 | P4 | 已定义权威文件名常量，但生成/验证处仍有硬编码 | 单一事实源尚未真正建立 |

## 4. 可执行反例与根因

### T10-1：首页读取未校验的运行产物（P1）

调用链为：

```text
app/streamlit_app.py
  -> _load_run(directory)
  -> src/ltverify/data_access.py::load_run_artifacts
  -> 直接 read_json / read_csv / read_parquet
```

`load_run_artifacts` 读取 `manifest.json` 后，未调用 `classify_artifact_schema_version` 或 `verify_manifest_hashes`。Codex 在临时副本中只修改 `metrics.json`、不更新 manifest，得到：

```text
tampered_metrics_loaded_f1=0.999999
tampered_metrics_loaded_n_predicted=999999
manifest_hash_still_original=True
```

这意味着 report 命令和鲁棒性页虽已做到“先校验后解析”，主看板仍可把未经清单验证的指标、预测和拓扑数据放入 session state。

### T10-2：畸形输入没有收口为 `ArtifactLoadError`（P2）

实测：

```text
malformed_metrics_exception=JSONDecodeError
nonobject_run_manifest_accepted_type=list
```

主页面只捕获 `ArtifactLoadError`。因此 malformed JSON、CSV parser error、parquet/Arrow error、manifest 为 list 等输入可能产生 Streamlit traceback；list manifest 还会在后续 `.get()` 处崩溃。

### T10-3：哈希一致性不等于数字签名（P2）

现有机制没有私钥、公钥、签名值、证书链、可信远端日志或只读可信根。若同时修改 CSV 和同目录 manifest 中的对应 SHA-256，验证仍会通过。Codex 实测：

```text
coordinated_tamper_state=strict_verified
coordinated_tamper_mean_f1=0.999999
```

这不是哈希实现 bug，而是威胁模型边界。`strict_verified` 目前表示：源配置 name/hash/snapshot 与指定配置文件一致，且本地产物与同目录清单内部一致；它不证明发布者身份、来源真实性，也不能抵抗“文件和 manifest 一起被改”的攻击。

当前 `README.md`、`docs/methodology.md`、鲁棒性 loader/page 消息多处使用“验签”“篡改任一产物都会拒绝”等表述，需要改为准确术语。

### T10-4：legacy summary 的空状态被当成失败（P2）

`_validate_summary` 当前对 `status` 使用 `dropna()`，所以缺失值不会进入未知值集合。页面随后以 `status != "completed"` 统计失败，将 NaN 计入失败。实测：

```text
blank_status_loader_state=legacy_unverified
blank_status_value_isna=True
blank_status_page_exceptions=[]
blank_status_warnings=[..., "存在 1 个失败案例..."]
```

缺失不是失败，必须拒绝该输入，不能替用户猜测。

### T10-5：目录形状的“输出文件”泄漏原始 OS 异常（P2）

`verify_experiment_manifest` 与 `verify_manifest_hashes` 只检查 `path.exists()`，随后直接哈希。若 manifest 声明的路径实际是目录，实测会泄漏：

```text
directory_output_exception=PermissionError [Errno 13] ... robustness_summary.csv
```

这违反“清单输出必须是普通文件”契约，也绕过页面只捕获领域错误的保护。

### T10-6：首页默认发现未识别 completed run（P3）

`_default_run_dir()` 当前：

```python
candidates = sorted(Path("runs").glob("run-*"), reverse=True)
return str(candidates[0]) if candidates else ""
```

它没有检查候选是否为目录、manifest 是否为 object、schema/status 是否可接受、completed 运行是否具备必要结构。自动模式可能选择最新失败/运行中/空目录，导致首页报错，而更旧的完整 completed run 明明可用。

### T10-7：权威名称仍重复（P4）

`src/ltverify/experiments.py` 已有：

```python
CURRENT_AGGREGATES_NAME
CURRENT_SUMMARY_NAME
CURRENT_MANIFEST_NAME
```

但实验生成、manifest 构造、summary 读取等位置仍硬编码 `robustness_*.csv/json`。常量应成为生成与验证共同使用的唯一事实源。

## 5. G0：先补失败测试

先提交测试，不改实现。建议提交信息：

```text
test: reproduce tenth-review dashboard trust regressions
```

### 5.1 `tests/unit/test_app_data_access.py`

至少新增：

1. 从有效小型 run fixture 复制目录，仅修改 `metrics.json` 且不更新 manifest；调用 `load_run_artifacts` 必须抛 `ArtifactLoadError`，消息包含哈希/一致性失败和文件名。
2. 同样篡改 `predictions.parquet` 或一个 CSV，必须在解析业务表前拒绝。
3. 用 monkeypatch 让 `pd.read_csv`/`pd.read_parquet`/metrics reader 一旦调用就报哨兵异常；对哈希已不一致的 run 断言哨兵未触发，证明严格“先校验、后解析”。
4. `manifest.json` 为 `[]`、malformed JSON、缺失、目录时，都统一抛 `ArtifactLoadError`。
5. `metrics.json` malformed、CSV malformed、parquet malformed/读取异常时，统一抛 `ArtifactLoadError`，保留 `raise ... from exc` 异常链。
6. manifest 声明的输出路径实际为目录时，不允许泄漏 `PermissionError/OSError`。
7. 若 loader 只接受 completed current run，补 `running/failed/unknown status` 的明确拒绝测试；契约必须写进 docstring 和错误消息。

测试不要只断言“有异常”；必须断言异常类型、关键消息和 verify-before-parse 顺序。

### 5.2 `tests/integration/test_streamlit_smoke.py`

至少新增：

1. 首页指向篡改 metrics 的 run：`AppTest.exception` 为空，页面出现 `st.error`，页面中不得出现伪造的 `0.999999/999999`。
2. 首页指向 non-object/malformed manifest：无未捕获异常，显示可操作错误。
3. 首页指向 malformed CSV/parquet：无未捕获异常，显示可操作错误。
4. 自动发现目录中“较新 failed/incomplete + 较旧 completed valid”时，应选择后者。
5. 显式 `LTVERIFY_RUN_DIR` 指向错误目录时必须尊重用户选择并显示错误，不能静默回退到别的 run。

### 5.3 `tests/unit/test_robustness_loader.py` 与页面测试

至少新增：

1. legacy summary 的 `status` 为 NaN、空串、纯空格时均抛 `RobustnessLoadError`。
2. `status` 前后含空格时，选择一种明确政策：建议规范化后接受并返回清洗后的 DataFrame；若决定拒绝，也必须测试和文档一致。禁止“验证一个值、展示另一个未清洗值”。
3. current manifest 中 summary/aggregates 路径实际为目录时，loader 抛 `RobustnessLoadError`，页面无未捕获异常。
4. 验证消息使用“哈希一致性校验/源配置交叉核验”，不得把它称为数字签名或验签。

### 5.4 `tests/unit/test_manifest_security.py` / experiment manifest 测试

至少新增：

1. run manifest 声明路径为目录：`verify_manifest_hashes` 抛清晰 `ValueError`，消息含“不是普通文件”。
2. experiment manifest 声明路径为目录：`verify_experiment_manifest` 同样拒绝，不泄漏原始 OS 异常。
3. `_write_manifest` 或对应生成路径只接收普通文件作为输出清单成员。
4. 增加一个“协同修改 artifact + manifest hash 仍属内部一致”的威胁模型测试或文档断言。此测试不是要求它失败，而是防止未来再次把 checksum 误称为 signature/authenticity。

### 5.5 默认发现和常量测试

至少新增：

1. `_default_run_dir` 跳过文件伪装的 `run-*`、缺失/畸形 manifest、非 completed run 和结构不完整 run。
2. 生成实验产物后，文件名和 manifest keys 精确使用三个 current 常量；禁止测试内再复制一套硬编码集合而掩盖漂移。

完成 G0 后，展示这些新测试在未修实现上的失败摘要，再进入实现。不要为了得到红测而故意制造语法错误。

## 6. G1：建立首页唯一可信加载入口

重点修改：

- `src/ltverify/data_access.py`
- `src/ltverify/manifest.py`
- `app/streamlit_app.py`
- 相应测试

### 6.1 `load_run_artifacts` 的强制顺序

公共默认入口必须按以下顺序执行：

```text
确认 run_dir / manifest.json 是普通文件
-> 安全解析 manifest JSON
-> 确认顶层为 object
-> 分类并验证支持的 artifact schema
-> 按产品政策确认 run status（建议仅 completed 可进入首页）
-> verify_manifest_hashes(manifest, run_dir)
-> 校验成功后才读取任何 CSV/parquet/metrics
-> 做必要的返回类型/结构检查
-> 返回 RunArtifacts
```

不得由 Streamlit 页面自行拼装这套顺序；`load_run_artifacts` 是唯一默认安全入口。report 当前已有显式验证，允许暂时双重校验以保持接口安全；若为了避免重复 IO 增加内部专用“已验证”入口，必须是非公开/难以误用的，并有 verify-before-parse 测试证明调用关系。

### 6.2 异常边界

以下底层异常都必须在可信边界内转成 `ArtifactLoadError`：

- `OSError` / `PermissionError`；
- `UnicodeError`；
- `json.JSONDecodeError`；
- pandas CSV 的 `ParserError` / `EmptyDataError`；
- parquet 引擎的 Arrow/ValueError 等实际读取异常；
- manifest schema/path/hash 验证的 `ValueError/TypeError`。

消息要包含失败阶段和相对文件名，但不要泄露无关本机路径或完整 traceback。使用异常链，不要裸 `except Exception` 吞掉编程错误；若 parquet 后端异常类型难以稳定导入，可以在最小读取包装层谨慎捕获并立即转译，同时用测试限定范围。

### 6.3 返回类型

- `RunArtifacts.manifest` 必须始终是 dict，不能让 list/str 进入 dataclass。
- `metrics.json` 必须是 object；必要指标的具体数值校验可保持最小范围，但至少不能让 list/null 进入 `.get()` 调用。
- 所有声明产物必须是普通文件，并且实际读取的文件与刚通过哈希校验的文件完全相同。

### 6.4 页面行为

- 页面继续只显示领域错误，不出现 traceback；
- 在首页简洁显示“清单哈希一致性已校验”状态，避免使用“验签成功”；
- 篡改输入不得进入 `st.session_state["artifacts"]`；
- 不得用 catch-all 后继续展示部分数据。

## 7. G2：统一普通文件与路径契约

修改 `verify_manifest_hashes`、`verify_experiment_manifest` 和生成清单的共享逻辑：

1. 对每个 declared input/output，在哈希前要求 `path.is_file()`；目录、FIFO、设备等都拒绝。
2. 先完成安全相对路径解析和集合契约，再触碰文件系统。
3. 原始 `OSError` 不得越过对外 loader；底层 verifier 可以抛清晰 `ValueError` 并保留异常链。
4. `_write_manifest` 只把真实普通文件记入清单；running manifest 的配置快照哈希行为必须保留。
5. run 与 experiment 两条验证路径尽量复用同一个“普通文件 + SHA-256”小函数，避免再次漂移。

建议提交信息：

```text
fix: verify run artifacts before dashboard parsing
fix: require regular files at manifest boundaries
```

## 8. G3：修复 summary 状态规范化

把 `_validate_summary` 改成返回规范化后的 DataFrame（或拆为 `_normalize_summary`），调用者必须展示该返回值。

最低契约：

1. 必须存在 `status` 列；
2. 任一 NaN/None 拒绝；
3. 转字符串并 `str.strip()`；
4. 空串/纯空格拒绝；
5. 只允许 `completed`、`failed`；
6. 页面失败计数基于清洗后的 status；
7. current 分支仍需与 manifest `case_counts` 保持一致，legacy 分支只做格式/值域校验并明确未验证来源。

禁止继续用 `dropna()` 把缺失状态排除在未知值检查之外。

建议提交信息：

```text
fix: reject missing robustness case statuses
```

## 9. G4：明确校验能力与威胁模型

修改当前产品文档与运行时文案：

- `README.md`
- `docs/methodology.md`
- `src/ltverify/robustness_loader.py`
- `app/pages/5_robustness.py`
- 首页新增的验证状态文案
- 对应测试

统一术语：

| 不准确表述 | 建议表述 |
|---|---|
| 验签 / 签名验证 | SHA-256 哈希一致性校验 |
| 篡改任一产物都会拒绝 | 未同步更新清单的产物变化会被拒绝 |
| 已证明产物真实可信 | 产物与当前清单内部一致 |
| strict_verified 证明来源真实性 | strict_verified 额外完成指定源配置的 name/hash/snapshot 交叉核验 |

必须显式写出：

> 当前清单未使用数字签名。它能检测意外损坏或未同步更新清单的修改；如果攻击者可同时改写产物与同目录清单，单靠 SHA-256 不能证明发布者身份或来源真实性。需要更强真实性保证时，应依赖可信 Git commit/tag、发布签名或外部只读证据根。

不要在本轮临时生成一对本地密钥来制造“安全感”。没有密钥保管、轮换、发布和信任分发的签名实现不进入本项目 MVP。

可以保留内部枚举名 `strict_verified` 以减少无关改动，但 UI 必须解释其两个维度：

1. artifact ↔ sibling manifest 内部哈希一致；
2. 指定源配置 ↔ manifest name/hash/snapshot 一致。

建议提交信息：

```text
docs: define checksum verification threat model
```

## 10. G5：首页默认运行发现策略

把自动发现和显式输入区分开：

### 显式模式

若设置 `LTVERIFY_RUN_DIR` 或用户在输入框填写目录：

- 尊重该路径；
- 加载失败时显示错误；
- 不静默换成其他 run，以免用户以为正在查看指定运行。

### 自动模式

只为初始默认值寻找候选，按新到旧扫描并跳过：

- 非目录；
- 缺失/非普通 `manifest.json`；
- manifest malformed 或顶层非 object；
- 不支持的 schema；
- status 不是 `completed`；
- 明显缺少必要输出声明/文件的候选。

候选一旦被选中，仍必须由 `load_run_artifacts` 完成完整哈希校验。建议不要在自动扫描中对所有大 parquet 重复哈希；发现阶段做轻量结构筛选，加载阶段做权威校验。若最新“结构完整但哈希被篡改”的 completed 候选被选中，应明确报错，不要悄悄降级到旧运行并掩盖篡改。

为可测试性，可把候选发现抽到 `src/ltverify` 的纯函数，或让 `_default_run_dir` 接受可注入的 runs root。

建议提交信息：

```text
fix: select completed runs for dashboard defaults
```

## 11. G6：完成权威名称单一事实源

在 `src/ltverify/experiments.py` 中用：

```python
CURRENT_AGGREGATES_NAME
CURRENT_SUMMARY_NAME
CURRENT_MANIFEST_NAME
```

替换生成、manifest 构造、验证和 summary 读取处对应的硬编码 current 文件名。legacy 名称也使用已有常量。README 示例字符串无需为了“零字面量”机械拼接。

这是小范围清理，不要顺手大规模重构实验模块。

建议提交信息：

```text
refactor: centralize robustness artifact names
```

## 12. 验收矩阵

| 场景 | 预期 |
|---|---|
| 有效 completed current run | 首页正常加载，显示哈希一致性状态 |
| metrics 被改、manifest 未改 | 解析前拒绝；页面无伪造指标、无 traceback |
| predictions/CSV 被改、manifest 未改 | 解析前拒绝 |
| manifest 是 list/null/malformed | `ArtifactLoadError`，页面显示错误 |
| manifest 声明目录为输出 | 清晰拒绝“不是普通文件”，无 PermissionError 泄漏 |
| metrics/CSV/parquet malformed | 统一领域错误，页面无 traceback |
| 显式错误 `LTVERIFY_RUN_DIR` | 报该目录错误，不静默回退 |
| 自动发现：新 failed + 旧 completed | 选择旧 completed |
| 自动发现：最新 completed 哈希不一致 | 选中后明确报错，不掩盖 |
| legacy summary status 缺失/空白 | 拒绝，不误报成 failed |
| current 鲁棒性权威三件套 | 仍返回当前验证状态，130 行证据不变 |
| artifact + manifest 协同改写 | 文档明确仅能证明内部一致，不声称数字签名真实性 |
| report 再生成 | summary/manifest 与仓库证据逐字节一致 |

## 13. 最终验证命令

实现完成后至少运行：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src app tests scripts
git diff --check
git status --short
```

再执行证据复现，但不要覆盖仓库文件：

```powershell
.venv\Scripts\python.exe -m ltverify report `
  --run-dir runs/run-20260816T121851-b42381de-ca6652 `
  --output <临时目录>/default_summary.json `
  --manifest-output <临时目录>/default_manifest.json
```

要求临时文件与以下仓库文件逐字节一致：

```text
reports/metrics/default_summary.json
reports/metrics/default_manifest.json
```

并以真实配置执行：

```text
verify_experiment_manifest(..., require_source_configs=True) -> strict
load_robustness_artifacts(...) -> strict_verified
summary rows -> 130
```

如果全量测试数量因新增测试而上升，最终报告写实际数字，不要预填。任何失败都先给根因和最小复现，不得删除测试或放宽断言来“变绿”。

## 14. 提交范围和最终回报格式

建议保持小提交，可按以下主题拆分：

```text
test: reproduce tenth-review dashboard trust regressions
fix: verify run artifacts before dashboard parsing
fix: require regular files at manifest boundaries
fix: reject missing robustness case statuses
fix: select completed runs for dashboard defaults
refactor: centralize robustness artifact names
docs: define checksum verification threat model
```

实际提交可合理合并，但测试提交应先于修复提交。提交前运行：

```powershell
git diff --cached --name-status
git diff --cached --stat
```

确保没有三份未跟踪 review report、`runs/`、缓存、临时证据和用户文件进入提交。

最终向 Codex 回报：

1. 每个 T10 编号的根因、修复文件和对应测试名；
2. 新红测在修复前如何失败、修复后如何通过；
3. 首页 verify-before-parse 的调用顺序证据；
4. 哈希一致性校验的准确威胁模型；
5. 完整 pytest 数量、Ruff、`git diff --check` 结果；
6. report 两文件字节一致结果、experiment strict 结果、loader 状态与 130 行结果；
7. 提交列表与最终 `git status --short`；
8. 明确声明三份未跟踪审查报告未被修改、未被提交；
9. 明确声明未重跑/改写 30 天与 130 案例权威证据、未 push。

## 15. 完成定义

只有同时满足以下条件，才可声明第十轮整改完成：

- 首页所有运行产物先通过清单与普通文件校验，再进入任何 parser 和 session state；
- 页面不再接受篡改 metrics/predictions/CSV，也不泄漏畸形输入的原始异常；
- legacy status 缺失/空白被拒绝，不再伪装成 failed；
- 默认发现跳过 failed/running/incomplete 候选，同时尊重显式路径；
- 当前文档与 UI 不再把 unsigned checksum 称为数字签名；
- 权威文件名常量用于生成和验证；
- 新旧测试全绿、Ruff 全绿、证据复现结果不变；
- 提交范围干净，用户未跟踪文件完整保留。
