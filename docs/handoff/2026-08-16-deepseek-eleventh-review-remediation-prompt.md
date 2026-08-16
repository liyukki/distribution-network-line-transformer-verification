# DeepSeek 第十一轮整改执行提示词：绑定首页解析角色、消除陈旧缓存与语义崩溃

> 使用方式：将本文完整交给 DeepSeek V4 及其 agent harness。本文是第十一轮可执行整改任务书，不是一般性建议。严格执行“复现红测 → 最小修复 → 分层验证 → 小提交”，不要跳过修复前失败证据。

## 1. 任务目标与硬约束

你是本项目第十一轮整改执行者。第十轮已经让首页在正常情况下做到“先校验 manifest，再解析文件”，但尚未保证“实际解析的每个文件都属于刚刚校验的集合”。本轮目标是完成这一角色绑定，同时修复缓存陈旧、语义无效但可解析的数据导致页面崩溃，以及剩余的错误边界与契约漂移。

必须遵守：

1. 以 `c12d460` 为整改基线；先确认 HEAD、分支和工作区，不得 reset、clean 或覆盖用户文件。
2. 当前以下三份未跟踪报告属于用户/其他 AI，不修改、不暂存、不提交：
   - `docs/handoff/2026-08-16-seventh-review-report.md`
   - `docs/handoff/2026-08-16-eighth-review-report.md`
   - `docs/handoff/2026-08-16-ninth-review-report.md`
3. 先写在 `c12d460` 上稳定失败的测试，再改实现。不得只补 happy-path，或让测试重复实现代码逻辑而失去独立性。
4. 不修改特征、评分、阈值、标签、物理仿真、评价口径以及 30 天/130 案例权威证据。
5. 不实现数字签名、密钥管理、数据库或远端证据服务；继续遵守第十轮确定的 SHA-256 威胁模型。
6. 不用 `except Exception` 掩盖编程错误，不通过删除断言、降低验证强度或清空 Streamlit 错误来“修复”测试。
7. 不 push，不提交 `runs/`、缓存、临时探针输出或上述三份未跟踪报告。

## 2. 基线提交与现状

### 2.1 第十轮后续提交

第十轮交接提交为 `1824f7a`。DeepSeek 已提交：

```text
aef0a6e test: reproduce tenth-review dashboard trust regressions
ac1684e fix: verify run artifacts before dashboard parsing
14d3e0d fix: require regular files at manifest boundaries and centralize names
6164c2a fix: reject missing robustness case statuses
c12d460 docs: define checksum verification threat model
```

### 2.2 已确认有效的修复

以下内容已经核实，不要回退：

- 首页会拒绝 manifest 顶层非 object、malformed manifest、非 current schema 和非 completed 状态；
- 对 manifest 已声明的产物，首页会在 parser 前调用 `verify_manifest_hashes`；
- metrics/CSV 的常见解析异常会转成 `ArtifactLoadError`；
- run 与 experiment verifier 会拒绝目录形状的已声明输出；
- legacy summary 的缺失、空白 `status` 已拒绝，带空格合法状态会被规范化；
- README/methodology/runtime 已把“验签”改为“SHA-256 哈希一致性校验”，并说明协同改写边界；
- 实验生成与 verifier 的 current 权威文件名大部分已改用常量；
- 显式 `LTVERIFY_RUN_DIR` 错误路径不会被静默替换。

### 2.3 本轮健康基线

Codex 在 `c12d460` 上实测：

```text
.venv\Scripts\python.exe -m pytest -q
# 237 passed in 75.33s

.venv\Scripts\python.exe -m ruff check src app tests scripts
# All checks passed!
```

证据闭环未变化：

```text
report_summary_byte_match=True
report_manifest_byte_match=True
experiment_manifest_level=strict
robustness_loader_state=strict_verified
robustness_rows=130
```

因此不要重跑或改写权威实验。237 项现有测试只证明现有覆盖路径通过，不证明下述新反例安全。

## 3. 第十一轮新发现摘要

| 编号 | 优先级 | 问题 | 当前后果 |
|---|---:|---|---|
| E11-1 | P1 | manifest 可省略首页实际读取的文件 | 被省略的 `metrics.json` 可伪造并直接展示 |
| E11-2 | P2 | `_load_run` 只按目录字符串缓存 | 同目录文件变化后不重新校验，页面继续显示陈旧数据和校验徽标 |
| E11-3 | P2 | 只验证 metrics 是 object，不验证字段语义；表格也无展示契约 | 哈希一致但类型错误的数据在首页/子页面产生 traceback |
| E11-4 | P2 | verifier 的 `OSError/PermissionError` 未稳定转译 | 文件在检查与哈希间失效时原始系统异常越过领域边界 |
| E11-5 | P3 | `_read_frame` 捕获所有 `Exception` | `AssertionError` 等编程错误被伪装成用户数据错误 |
| E11-6 | P3 | 自动发现把任意“非空声明”的 completed run 当结构完整 | 较新但缺少页面产物的 run 遮挡较旧有效 run |
| E11-7 | P3 | `_write_manifest` 仍用 `exists()` 并可写声明/哈希不一致清单 | 缺失文件被声明但不哈希，目录触发原始 I/O 异常 |
| E11-8 | P3 | README 的“四态兼容”与 current-only 入口冲突 | 旧版/未来版页面分支在正常入口不可达，产品政策含混 |
| E11-9 | P4 | 协同篡改测试未调用 verifier；CLI 仍硬编码 summary 名称 | 威胁模型测试不保护真实行为，单一事实源未完成 |

## 4. 已执行反例与根因

### E11-1：省略声明即可绕过首页校验（P1）

`load_run_artifacts` 当前顺序确实是：

```text
read manifest -> verify_manifest_hashes -> read hard-coded dashboard files
```

但 `verify_manifest_hashes` 只验证 manifest 自己声明的文件；loader 没有要求页面硬编码读取的文件必须出现在 `output_paths/output_sha256`。

Codex 将有效 run 复制到临时目录，同时从 manifest 两处删除 `metrics.json`，再把该文件改成：

```json
{"f1": 0.999999, "n_predicted": 999999, "automatic_coverage": 1.0}
```

当前 loader 输出：

```text
omitted_metrics_loaded_f1=0.999999
omitted_metrics_loaded_n_predicted=999999
metrics_declared=False
```

当前 Streamlit 页面输出：

```text
omitted_metric_page_errors=[]
omitted_metric_page_exceptions=[]
预测告警数=999999
F1=1.000
自动推荐覆盖率=1.000
```

这是第十轮 T10-1 的实质残留：完成了时序验证，却没有完成“被验证角色 ↔ 被解析角色”绑定。相同绕过适用于 predictions、network CSV 等所有硬编码读取文件。

### E11-2：Streamlit 缓存使校验状态陈旧（P2）

`app/streamlit_app.py` 当前：

```python
@st.cache_data(show_spinner=False)
def _load_run(directory: str) -> RunArtifacts:
    return load_run_artifacts(Path(directory))
```

缓存 key 只有目录字符串。Codex 在同一个 `AppTest` 中先加载有效 run，再修改 `metrics.json` 且不更新 manifest，随后 rerun：

```text
first_errors=[]
second_errors=[]
second_exceptions=[]
second_metrics 与第一次完全相同
```

第二次没有重新执行 manifest 校验。页面继续显示旧值和“哈希一致性已校验”文案，无法反映当前磁盘状态。即使没有展示伪造新值，这也是数据新鲜度与信任状态错误。

### E11-3：哈希一致但语义无效的数据会使页面崩溃（P2）

如果 `metrics.json` 是合法 JSON object，loader 即接受。Codex 写入：

```json
{"f1": "not-a-number", "n_predicted": []}
```

并同步更新 manifest 哈希。页面结果：

```text
semantic_metric_errors=[]
semantic_metric_exceptions=["int() argument must be ... not 'list'"]
```

崩溃发生在：

```python
int(metrics.get("n_predicted", 0))
float(metrics.get("f1"))
```

同理，可解析但缺列的 predictions、observed measurements、network tables 和错误形状的 confusion matrix 会在子页面/plotting 中以 `KeyError/IndexError/TypeError` 崩溃。哈希一致性证明字节与当前清单一致，不证明数据满足页面 schema。

### E11-4：验证阶段的系统 I/O 异常未收口（P2）

`load_run_artifacts` 只捕获 verifier 的 `ValueError/TypeError`；鲁棒性 loader 也相同。模拟哈希阶段发生权限错误：

```text
verification_oserror_type=PermissionError
verification_oserror_wrapped=False
robustness_verify_oserror_type=PermissionError
```

静态 `is_file()` 不能消除检查与读取之间的竞态。文件可能在检查后被删除、替换、锁定或变为不可读；对外 loader 必须仍然只暴露 `ArtifactLoadError/RobustnessLoadError`。

### E11-5：解析器 catch-all 掩盖编程错误（P3）

`_read_frame` 使用：

```python
except Exception as exc:
    raise ArtifactLoadError(...) from exc
```

Codex 让 `pd.read_csv` 抛 `AssertionError("programmer bug")`，当前结果：

```text
parser_assertion_type=ArtifactLoadError
parser_assertion_cause=AssertionError
```

这会让真正的代码回归在页面测试中看起来像“用户文件坏了”。应只转译已知 I/O/解析异常，程序错误必须继续失败并暴露给测试。

### E11-6：自动发现没有真正检查结构完整性（P3）

`discover_completed_run_dir` 只要求 `output_paths` 是非空 list、`output_sha256` 是 dict。Codex 构造较新的 completed run，仅声明并保留 `metrics.json`，同时保留较旧完整 run，得到：

```text
discovered_incomplete=run-20260816T999999-incomplete
```

这与函数 docstring 的“structurally valid”及 T10 验收不符。应用随后选择不完整 run 并报错，旧的可用 completed run 被遮挡。

### E11-7：清单写入侧仍未要求全部输出为普通文件（P3）

`pipeline._write_manifest` 当前：

```python
manifest.output_paths = [path.name for path in output_paths]
manifest.output_sha256 = {
    path.name: file_sha256(path) for path in output_paths if path.exists()
}
```

问题：

- 缺失 path 仍进入 `output_paths`，却不会进入 `output_sha256`；
- 目录满足 `exists()`，随后 `file_sha256` 泄漏系统异常；
- 没有在修改 manifest 之前完整验证输入，失败时对象可能处于部分更新状态；
- 第十轮要求的 `_write_manifest` regular-file 红测并未添加。

### E11-8：schema 产品政策自相矛盾（P3）

首页 loader 已明确只接受 current schema-v2，旧版、新版和非法版在创建 `RunArtifacts` 前统一拒绝。但 README 仍声称：

```text
看板对 schema 采取四态兼容：旧版隐藏字段、未来版有限展示……
```

`app/pages/4_evaluation.py` 也保留 legacy/newer/invalid 分支；现有测试通过手工篡改 `RunArtifacts.manifest` 并直接注入 session state 才能覆盖这些分支，真实入口不可达。

本轮不要重新开放未验证旧 run。应明确：主入口 current-only；页面分支若保留，只是对旧 session/hot-reload 的防御性保护，不是受支持的磁盘加载能力。

### E11-9：测试和常量清理不完整（P4）

`test_coordinated_artifact_and_manifest_hash_is_internal_consistency` 的名称声称验证威胁模型，但测试只比较：

```python
manifest["output_sha256"]["metrics.json"] == file_sha256(artifact)
```

它没有构造有效 schema-v2 快照链，也没有调用 `verify_manifest_hashes`。注释甚至说明真实 verifier 会因缺少快照而失败。该测试无法防止 verifier 行为或产品解释回归。

此外 `src/ltverify/cli.py` 在 experiments 命令完成后仍硬编码读取 `"robustness_summary.csv"`，尚未使用 `CURRENT_SUMMARY_NAME`。

## 5. G0：先提交真实失败测试

先只改测试，展示这些测试在 `c12d460` 上的失败摘要，然后提交：

```text
test: reproduce eleventh-review artifact binding regressions
```

### 5.1 声明角色与实际解析角色绑定

修改 `tests/unit/test_app_data_access.py`：

1. 从有效 run 复制目录；从 manifest 的 `output_paths` 和 `output_sha256` 同时删除 `metrics.json`；伪造 metrics；`load_run_artifacts` 必须抛 `ArtifactLoadError`。
2. 参数化覆盖 loader 实际读取的每个 dashboard 文件，不能只测 metrics。
3. 断言错误发生在 `_read_frame/_read_metrics` 前，可用 monkeypatch 哨兵证明 parser 未调用。
4. 断言 manifest 可包含 dashboard 不读取的额外合法产物，避免把集合错误收紧成不兼容的“绝对精确全集”。

修改 `tests/integration/test_streamlit_smoke.py`：

1. manifest 省略 metrics、磁盘 metrics 伪造时，页面无 traceback，出现 `st.error`，不得显示 `999999/1.000`。
2. manifest 省略 predictions/network files 时，入口即拒绝，不允许子页面才崩溃。

### 5.2 缓存新鲜度红测

在同一个 `AppTest` 对象中：

1. 第一次加载有效 run，断言无错误；
2. 保持目录字符串不变，修改一个已声明产物但不更新 manifest；
3. 调用同一对象 `.run()`；
4. 第二次必须重新校验并显示哈希失败，不能返回第一次缓存结果；
5. 再测“合法更新 artifact + manifest”时页面展示新值，避免只会缓存旧对象。

### 5.3 metrics 与表格展示契约红测

至少覆盖：

- `metrics.json` 顶层 object，但 `n_predicted=[]/true/-1/1.5`；
- `f1="x"/NaN/Infinity`；
- 应允许 null 的可选指标与必须有限的首页指标要区分；
- predictions 缺 `transformer_id/decision/reported_feeder_id/recommended_feeder_id/confidence/coverage`；
- observed measurements 缺 `timestamp/transformer_id/voltage_pu/data_quality_flag`；
- candidate features 缺绘图所需列；
- network nodes/edges 缺 plotting 所需列；
- confusion matrix 不是 2×2 数值矩阵。

每个输入都先同步更新 manifest 哈希，证明失败来自语义契约而不是哈希不一致。unit loader 必须抛 `ArtifactLoadError`；至少对 metrics 和一个表格做 AppTest，断言无 traceback、显示可操作错误。

不要试图一次验证所有业务统计关系。本轮只验证页面会直接依赖的最小 schema、类型、有限性和形状。

### 5.4 I/O 异常与 catch-all 红测

1. monkeypatch run verifier/file hash 抛 `PermissionError`，loader 必须转成 `ArtifactLoadError` 并保留 cause。
2. 对 robustness loader 做相同测试，必须转成 `RobustnessLoadError`。
3. monkeypatch `pd.read_csv` 或 `pd.read_parquet` 抛已知 parser/I/O 异常，必须转成领域错误。
4. monkeypatch parser 抛 `AssertionError`，必须原样传播；测试用来禁止 `except Exception` 回归。

### 5.5 自动发现与写清单红测

1. 较新 completed 候选只声明 metrics，较旧候选完整：发现函数必须返回旧候选。
2. 较新候选声明完整集合但其中一个必要文件不存在/是目录：必须跳过。
3. 较新候选结构完整但哈希错误：发现阶段可选中，权威 loader 随后必须明确报错，不能静默回退。这与第十轮政策保持一致。
4. `_write_manifest` 接收缺失文件或目录时必须清晰失败，不写声明/哈希集合不一致的 manifest。
5. `_write_manifest` 成功后，`output_paths` 与 `output_sha256` keys 一一对应，所有条目都是普通文件。

### 5.6 威胁模型真实测试

重写而不是保留空壳测试：

1. 用有效 run fixture，保持 `config.snapshot.yaml` 完整；
2. 修改 `metrics.json`；
3. 同步更新 manifest 的 metrics 哈希；
4. 真实调用 `verify_manifest_hashes(manifest, run_dir)`；
5. 断言通过，并用 docstring 明确“只证明 sibling manifest 内部一致，不证明真实性”。

此测试通过是预期行为；它必须实际走 verifier，而不是只测试 `file_sha256` 等于自身。

## 6. G1：建立 dashboard 权威文件角色表

重点修改：

- `src/ltverify/data_access.py`
- 对应 unit/integration tests

定义一个不可变的权威映射，作为以下三件事的共同事实源：

1. manifest 必须声明的 dashboard 文件集合；
2. loader 实际读取的文件名；
3. 返回 `RunArtifacts` 字段绑定。

建议结构类似：

```python
DASHBOARD_ARTIFACT_FILES = {
    "truth": "truth_topology.csv",
    "ledger": "reported_ledger.csv",
    "observed_measurements": "observed_measurements.parquet",
    "feeder_measurements": "feeder_measurements.parquet",
    "candidate_features": "candidate_features.parquet",
    "predictions": "predictions.parquet",
    "metrics": "metrics.json",
    "confusion_matrix": "confusion_matrix.csv",
    "network_nodes": "network_nodes.csv",
    "network_edges": "network_edges.csv",
}
REQUIRED_DASHBOARD_ARTIFACTS = frozenset(DASHBOARD_ARTIFACT_FILES.values())
```

具体名称以当前 `RunArtifacts` 和页面真实消费为准。加载顺序必须是：

```text
parse manifest object/current/completed
-> validate output_paths/output_sha256 structure
-> assert REQUIRED_DASHBOARD_ARTIFACTS <= declared names
-> verify_manifest_hashes
-> parse only names taken from the same authoritative mapping
-> validate semantic display contracts
-> construct RunArtifacts
```

要求是 required subset，不是 manifest 只能含这一组；`config.snapshot.yaml`、simulation validation、transformer measurements 等额外产物仍合法并继续参与完整 manifest 哈希验证。

建议提交：

```text
fix: bind dashboard inputs to manifest declarations
```

## 7. G2：让每次 rerun 都重新建立信任状态

最小、推荐方案：移除 `_load_run` 上只按目录字符串工作的 `@st.cache_data`，每次 Streamlit rerun 调用安全 loader。先以正确性为准，当前项目规模不需要在没有测量前引入复杂缓存协议。

如果实测表明解析成本不可接受，允许采用两层设计，但必须满足：

1. 外层每次 rerun 都完整执行 manifest 与文件哈希验证；
2. 只有验证成功后，才计算包含当前已验证内容身份的 cache key；
3. 内层缓存只缓存解析结果，key 不得只有目录、mtime 或 size；
4. artifact 变化但 manifest 未变时必须在进入缓存前拒绝；
5. artifact 与 manifest 合法同步更新时 cache key 必须变化。

不要用固定 TTL、目录字符串、mtime/size 组合作为安全依据；它们最多是性能提示，不是内容身份。

建议提交：

```text
fix: reverify dashboard artifacts on every rerun
```

## 8. G3：增加最小展示语义契约

在 `data_access.py` 中把“字节可解析”和“页面可安全消费”分开。复用已有：

- `ltverify.contracts.validate_columns`
- `TRUTH_COLUMNS`
- `LEDGER_COLUMNS`
- `TRANSFORMER_MEASUREMENT_COLUMNS` 或页面所需子集
- `FEEDER_MEASUREMENT_COLUMNS`
- `ltverify.features.FEATURE_COLUMNS`
- `ltverify.scoring.PREDICTION_COLUMNS`

对 network/confusion/metrics 新增小而明确的 dashboard contract 常量或验证函数，不要把业务算法复制进 loader。

最低要求：

1. 所有页面会索引的列在 loader 返回前存在；
2. confusion matrix 是 2×2 且可转成有限数值；
3. `metrics` 是 object；`n_predicted` 为非 bool、非负整数；
4. 首页直接格式化的比例指标是有限实数，并符合当前生成口径允许的 null 政策；
5. 禁止 Python JSON 默认接受的 NaN/Infinity 进入必须有限的展示字段；
6. 空核心表若会导致 selectbox/iloc 崩溃，应在 loader 报明确错误；
7. `DataContractError/ValueError` 在数据边界转成 `ArtifactLoadError`，消息含表名和缺失字段。

不要在页面散落 `try/except` 或默认把坏值显示为 0；那会把无效证据伪装成真实指标。

建议提交：

```text
fix: validate dashboard artifact display contracts
```

## 9. G4：精确收口 I/O 异常，不吞编程错误

### 9.1 哈希阶段

为 run/experiment verifier 复用一个“普通文件 + SHA-256 + I/O 转译”小函数：

- 路径必须为普通文件；
- 哈希读取的 `OSError/PermissionError` 转成带相对文件名的 `ValueError`，保留 cause；
- loader 最外层再把 verifier 领域错误转成对应 `ArtifactLoadError/RobustnessLoadError`；
- 处理 `is_file()` 与 read 之间文件变化的竞态。

即使底层已转译，对外 loader 仍可防御性捕获 `OSError/UnicodeError`，但不要捕获所有异常。

### 9.2 parser 阶段

移除 `_read_frame` 的 `except Exception`。按当前依赖版本列出已知输入异常，例如：

- `OSError/UnicodeError`；
- `pd.errors.ParserError/EmptyDataError`；
- parquet 后端的明确 Arrow 解析/I/O 异常；
- 由坏输入触发且已通过测试确认的有限 `ValueError`。

`AssertionError`、`AttributeError`、`NameError` 等编程错误不能转成 `ArtifactLoadError`。若某后端异常类型不确定，先用坏 parquet fixture观察实际类型，再精确捕获。

建议提交：

```text
fix: preserve programming errors at artifact boundaries
```

## 10. G5：修复自动发现与清单写入契约

### 10.1 自动发现

发现阶段保持轻量，不重算所有 SHA-256，但必须检查：

- current schema、completed status；
- `REQUIRED_DASHBOARD_ARTIFACTS` 是 manifest 声明集合的子集；
- `output_paths` 与 `output_sha256` keys 结构上一一对应；
- 每个 dashboard 必要文件当前是普通文件；
- config snapshot 的必要声明存在。

完整哈希仍只在选中后由 loader 执行。结构完整但哈希错误的最新 completed run 应被选中后明确报错，不静默回退。

### 10.2 `_write_manifest`

在修改 `RunManifest` 和写 JSON 前：

1. 验证列表非空且每项为普通文件；
2. 验证 basename 唯一；
3. 对全部文件成功计算哈希到局部变量；
4. 再一次性赋值 `output_paths/output_sha256`；
5. 通过 atomic writer 写清单。

禁止 `if path.exists()` 静默省略哈希。失败时不得产生“声明集合和哈希集合不同”的持久清单。

建议提交：

```text
fix: require complete regular files when writing manifests
fix: skip structurally incomplete dashboard runs
```

## 11. G6：对齐 schema 政策、测试与常量

### 11.1 schema 政策

保持 main loader 的 current-only 决策。更新 README 为：

```text
主看板磁盘入口仅接受 current schema-v2；旧版、未来版和非法版在加载前拒绝并提示重新运行。
```

若保留 `page 4` 的多态分支，明确它们只是对旧 session/hot reload/直接页面测试的防御性保护，不构成受支持的旧 run 加载能力。相应测试名称也应体现 `defensive_session_guard`，不能再称“看板兼容旧 run”。如果没有真实需求，删除不可达分支和注入式测试是更清晰的 YAGNI 方案。

不要重新开放 legacy on-disk loader 来迎合旧 README。

### 11.2 威胁模型测试

让协同改写测试真实调用 `verify_manifest_hashes`，并保持 README/methodology 中“非数字签名”的准确边界。历史 handoff 文档中的旧措辞不改。

### 11.3 权威名称

`src/ltverify/cli.py` 的 experiments summary 读取改用 `CURRENT_SUMMARY_NAME`。生产代码中 current 实验文件名只允许在常量定义处出现；测试可以断言常量的公开契约值，但 consumer 不再硬编码。

建议提交：

```text
docs: align dashboard schema support policy
test: exercise coordinated checksum rewrite through verifier
refactor: use canonical experiment summary name in cli
```

## 12. 验收矩阵

| 场景 | 预期 |
|---|---|
| manifest 声明完整、文件有效 | 首页正常加载 |
| manifest 同时省略 metrics 的 path/hash | parser 前拒绝，不显示伪造指标 |
| manifest 省略任一 dashboard 文件 | parser 前拒绝 |
| manifest 含额外有效产物 | 允许，额外产物仍参与哈希校验 |
| 同目录首次有效、随后文件被改 | 第二次 rerun 重新校验并报错 |
| 同目录 artifact + manifest 合法更新 | 不返回旧缓存对象 |
| metrics 合法 JSON 但字段类型/有限性错误 | `ArtifactLoadError`，页面无 traceback |
| 表格可解析但缺展示列 | `ArtifactLoadError`，消息含表名/列名 |
| verifier 哈希读取 PermissionError | 对外只见领域错误，cause 保留 |
| parser 抛已知输入异常 | 转成领域错误 |
| parser 抛 AssertionError | 不吞，测试失败暴露编程错误 |
| 新 completed 但结构不完整 + 旧有效 | 自动选择旧有效 |
| 新 completed 结构完整但哈希错误 | 选中后明确报错，不静默回退 |
| `_write_manifest` 收到缺失/目录 path | 清晰失败，不写不一致清单 |
| legacy/future run 经主入口加载 | 明确 current-only 错误 |
| 协同修改文件与 manifest hash | 真实 verifier 通过，文档明确仅内部一致 |
| report 证据再生成 | 两文件继续逐字节一致 |
| 权威鲁棒性实验 | `strict` / `strict_verified` / 130 行保持不变 |

## 13. 推荐提交顺序

```text
test: reproduce eleventh-review artifact binding regressions
fix: bind dashboard inputs to manifest declarations
fix: reverify dashboard artifacts on every rerun
fix: validate dashboard artifact display contracts
fix: preserve programming errors at artifact boundaries
fix: require complete regular files when writing manifests
fix: skip structurally incomplete dashboard runs
docs: align dashboard schema support policy
test: exercise coordinated checksum rewrite through verifier
refactor: use canonical experiment summary name in cli
```

可以把强相关小项合并，但红测提交必须在实现提交之前。每个提交后跑对应小测试，不要等最后才发现范围互相影响。

## 14. 最终验证

至少运行：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src app tests scripts
git diff --check
git status --short
```

再使用临时目录复现，不覆盖仓库权威文件：

```powershell
.venv\Scripts\python.exe -m ltverify report `
  --run-dir runs/run-20260816T121851-b42381de-ca6652 `
  --output <临时目录>/default_summary.json `
  --manifest-output <临时目录>/default_manifest.json
```

要求：

```text
临时 default_summary.json == reports/metrics/default_summary.json（逐字节）
临时 default_manifest.json == reports/metrics/default_manifest.json（逐字节）
verify_experiment_manifest(... require_source_configs=True) -> strict
load_robustness_artifacts(...) -> strict_verified
summary rows -> 130
```

无需重跑 30 天流水线或 130 案例矩阵，因为本轮只改加载、契约、缓存、错误边界、文档与测试。

## 15. 最终回报格式

向 Codex 回报：

1. E11-1 至 E11-9 每项的根因、修复文件、测试名和提交；
2. 红测在 `c12d460` 上的真实失败摘要；
3. `REQUIRED_DASHBOARD_ARTIFACTS` 与 loader 解析映射如何保证单一事实源；
4. 同一 AppTest 二次 rerun 的缓存新鲜度证据；
5. metrics/表格语义坏输入如何变成页面领域错误；
6. verifier PermissionError 与 parser AssertionError 两类边界的不同结果；
7. schema current-only 产品政策的 README/UI/测试一致性；
8. 完整 pytest 数量、Ruff、`git diff --check`；
9. report 两文件字节一致、experiment strict、loader state 与 130 行结果；
10. 提交列表和最终 `git status --short`；
11. 明确三份未跟踪审查报告未修改、未提交；
12. 明确未改算法、未重跑/改写权威证据、未 push。

## 16. 完成定义

只有同时满足以下条件，才可声明第十一轮完成：

- 页面实际读取的每一个 run 文件都必须属于刚通过验证的 manifest 声明集合；
- 删除 path/hash 声明不能让未验证文件进入 `RunArtifacts`；
- 同目录 rerun 不复用过期信任状态；
- 哈希一致但语义无效的 metrics/表格在 loader 边界拒绝，页面不 traceback；
- 用户输入 I/O 异常转成领域错误，编程错误不被 catch-all 吞掉；
- 自动发现能跳过 completed 但结构不完整的候选；
- 清单写入只接受全部存在的普通文件，声明与哈希始终一一对应；
- README、真实入口与防御性页面分支对 schema 政策表述一致；
- 协同篡改测试真实调用 verifier，CLI 使用权威 summary 常量；
- 新旧测试、Ruff、diff check 和证据闭环全部通过；
- 提交范围干净，用户未跟踪文件原样保留。
