# DeepSeek V4 Agent Harness 第九轮整改提示词

> 用途：把本文件完整交给 DeepSeek V4 及其 Agent Harness，在仓库内执行第九轮整改。
>
> 本文件是 Codex 对 `442c609` 及
> `docs/handoff/2026-08-16-ninth-review-report.md` 的独立复核结果。该报告把本轮判断为
> “零功能缺陷、仅两项微瑕”，但运行时反例已证明这个结论不成立。

---

## 一、任务身份与不可突破的边界

你现在是项目 `distribution-network-line-transformer-verification` 的实现负责人。

请在仓库 `D:\电力` 中执行第九轮整改。必须先建立能在 `442c609` 上失败的回归测试，再修改业务代码、运行全量验证并创建本地提交。不要只给建议，也不要用现有 174 个绿测替代本文反例。

必须遵守：

1. 不得执行 `git reset --hard`、`git clean`、`git checkout --` 等破坏性命令；
2. 不得回滚、覆盖或删除其他执行者的修改；
3. 不得擅自提交、删除或改写当前三个未跟踪报告：
   - `docs/handoff/2026-08-16-seventh-review-report.md`
   - `docs/handoff/2026-08-16-eighth-review-report.md`
   - `docs/handoff/2026-08-16-ninth-review-report.md`
4. 第九轮报告中的 V-3“把报告一并入库”不在本轮授权范围内，不执行；
5. 不得 push、开 PR 或修改远端；只创建本地、主题清晰的提交；
6. 不得通过降低验签强度、默默降级、捕获后忽略异常或删除测试来变绿；
7. 本轮不改模型算法、实验矩阵或默认配置，不重跑 30 天默认流水线和 130 案例实验；
8. 如果实现范围意外触及完成态证据格式，先停止并说明影响，不得手工编辑证据伪装重跑。

开始前执行：

```powershell
git status --short --branch
git log --oneline --decorate -15
git diff --check
```

期望基线：

```text
HEAD = 442c609
pytest = 174 passed
ruff = All checks passed!
```

若实际状态不同，先解释新增差异并保护现场。

---

## 二、第九轮独立审核结论

当前权威交付证据内容仍然正确：

- `.venv\Scripts\python.exe -m pytest -q`：`174 passed in 42.36s`；
- Ruff：`All checks passed!`；
- 默认 `default_summary.json` 和 `default_manifest.json` 可由源运行逐字节复现；
- 权威实验清单严格验证返回 `strict`；
- 权威鲁棒性加载返回 `strict_verified`。

但 Codex 构造出的反例表明，新加载器会把**未写入 manifest 的文件**标为严格验签，页面也仍有未捕获异常，中断态运行清单仍违反上一轮明确契约：

```text
forged_aggregate_state= strict_verified
forged_aggregate_family= FORGED
forged_summary_state= strict_verified
forged_summary_case= FORGED

mixed_family_exceptions=
  ["'<' not supported between instances of 'float' and 'str'"]

nonobject_manifest_exceptions=
  ["'list' object has no attribute 'get'"]

interrupt_manifest_exists= True
interrupt_snapshot_exists= True
interrupt_status= running
interrupt_output_paths= []
interrupt_manifest_verify=REJECTED

input_paths=[[1]] -> TypeError: unhashable type: 'list'
input_paths=[{"name": "default.yaml"}] -> TypeError: unhashable type: 'dict'
```

本轮问题分级：

| 编号 | 优先级 | 问题 |
|---|---:|---|
| N9-1 | P1 | 加载器验签固定权威文件，却读取任意同目录 `robustness_*` 文件并标记 `strict_verified` |
| N9-2 | P2 | 有效 JSON 但顶层不是 object 时，鲁棒性页面抛未捕获 `AttributeError` |
| N9-3 | P2 | `family` 混有空值时，页面排序抛未捕获 `TypeError` |
| N9-4 | P2 | `KeyboardInterrupt/SystemExit/进程终止` 可留下已有快照却不可自验证的 `running` manifest |
| N9-5 | P3 | 清单元素类型校验顺序错误，嵌套 list/dict 触发底层 `TypeError` |
| N9-6 | P3 | 自动发现会优先选择缺 manifest 的不完整 current 目录，阻断较旧但完整的有效目录 |
| N9-7 | P4 | 页面存在已证实不可达分支；legacy/current 文件角色配对未严格限定 |

N9-1 是证据边界错误，不是第九轮报告所称的“一行级命名微瑕”。`strict_verified` 必须描述**实际返回并展示的 DataFrame 字节**，不能描述同目录另两份未被读取的文件。

---

## 三、G0：先建立必失败回归测试

### G0.1 严格状态不得覆盖未入清单文件

在临时目录复制当前权威三件套：

```text
robustness_aggregates.csv
robustness_summary.csv
robustness_experiment_manifest.json
```

然后额外创建：

```python
forged_aggregates = artifact_dir / "robustness_forged.csv"
pd.DataFrame(
    {
        "family": ["FORGED"],
        "value": ["999"],
        "mean_precision": [0.999],
        "std_precision": [0.0],
    }
).to_csv(forged_aggregates, index=False)
```

调用：

```python
load_robustness_artifacts(
    forged_aggregates,
    artifact_dir / "robustness_summary.csv",
    experiment_config_path=ROOT / "configs/robustness.yaml",
    base_config_path=ROOT / "configs/default.yaml",
)
```

当前会返回 `strict_verified` 并展示 `FORGED`。新测试必须断言 `RobustnessLoadError`，原因明确为 aggregates 文件名/角色不属于 manifest 权威输出。

再创建一个未入清单的 `robustness_forged_summary.csv`，与真实 aggregates 组合；同样必须拒绝，不能读取伪造 summary 后返回 `strict_verified`。

至少覆盖以下组合：

| aggregates | summary | 期望 |
|---|---|---|
| `robustness_aggregates.csv` | `robustness_summary.csv` | current，可验签 |
| `robustness_forged.csv` | `robustness_summary.csv` | 拒绝 |
| `robustness_aggregates.csv` | `robustness_forged_summary.csv` | 拒绝 |
| `robustness_aggregates.csv` | `experiment_summary.csv` | 拒绝 |
| `experiment_aggregates.csv` | `experiment_summary.csv` | legacy，可兼容但未验证 |
| `experiment_aggregates.csv` | `robustness_summary.csv` | 拒绝 |
| `experiment_fake.csv` | 空 | 拒绝 |

不要只检查前缀；必须检查文件的**完整 basename 和角色**。

### G0.2 manifest 顶层类型必须安全拒绝

为 sibling `robustness_experiment_manifest.json` 参数化写入合法 JSON：

```json
[]
null
"manifest"
42
true
```

直接加载器测试必须断言：

```python
with pytest.raises(RobustnessLoadError, match="object|对象|字典|manifest|清单"):
    load_robustness_artifacts(...)
```

对应 `AppTest` 必须断言：

```python
assert len(app_test.exception) == 0
assert len(app_test.error) >= 1
assert len(app_test.get("plotly_chart")) == 0
```

验证器本身也应对非 mapping 输入给出明确领域错误，不能依赖 `.get` 自然抛 `AttributeError`。

### G0.3 `family/value` 的混合空值与类型边界

至少增加以下 legacy 输入测试，确保它们真正进入 CSV 解析和 schema 校验，不要使用缺 manifest 的 current 文件名提前短路：

```text
family = ["missing_rate", null]
family = ["missing_rate", "   "]
family = [null, null]
value  = ["0.1", null]
```

全部必须：

- 无未捕获异常；
- 缺失/空白 family 时明确拒绝；
- 不进入 `sorted()` 后才失败；
- 不绘图。

再覆盖：

- `mean_precision = inf/-inf`；
- `std_precision = inf/-inf`；
- `std_precision < 0`；
- `std_precision` 非数值。

均应得到明确“不适用/非法数值”提示，不得把无限值或负标准差交给 Plotly。

注意：当前 `test_robustness_page_handles_bad_aggregates` 和
`test_robustness_page_handles_non_numeric_metric` 使用无 manifest 的
`robustness_aggregates.csv`，实际可能只测试了“缺 manifest”错误，并没有到达 CSV/数值逻辑。必须调整测试夹具，使断言验证目标分支。

### G0.4 中断态 running manifest 必须自验证

在 `tests/integration/test_pipeline.py` 增加：

```python
def interrupted_build_network(*args: object, **kwargs: object) -> object:
    raise KeyboardInterrupt("probe")
```

运行流水线并在测试外层捕获 `KeyboardInterrupt`。断言：

```text
config.snapshot.yaml 存在
manifest.json 存在
manifest.status == "running"
manifest.output_paths 含 config.snapshot.yaml
output_sha256["config.snapshot.yaml"] == config_sha256
verify_manifest_hashes(manifest, run_dir) 通过
```

再用 `SystemExit` 覆盖一个未进入 `except Exception` 的终止路径。无需捕获 `BaseException` 并伪写 `failed`；正确目标是让最初持久化的 `running` manifest 从写入那一刻起就可验证。

### G0.5 清单元素类型必须在去重前验证

在 `tests/unit/test_manifest.py` 参数化：

```python
bad_input_paths = [
    [["default.yaml"]],
    [{"name": "default.yaml"}],
]

bad_output_paths = [
    [["config.snapshot.yaml"]],
    [{"name": "config.snapshot.yaml"}],
    [1],
]
```

所有用例必须抛出信息明确的 `ValueError`，分别点名 `input_paths` 或 `output_paths`；不得泄漏 `unhashable type`、混合类型排序错误或 `KeyError`。

同时测试：

- `output_sha256` 非字典；
- `output_sha256` 值非字符串；
- `output_paths` 非列表；
- 正常列表的重复路径仍被拒绝。

### G0.6 自动发现跳过不完整 current 目录

创建：

```text
runs/experiments-new/robustness_aggregates.csv      # 无 summary/manifest
runs/experiments-old/robustness_aggregates.csv
runs/experiments-old/robustness_summary.csv
runs/experiments-old/robustness_experiment_manifest.json
```

默认页面应选择 `experiments-old` 的完整 current 三件套，而不是选中不完整目录后直接报错。

再测试没有完整 current 时回退完整 legacy：

```text
runs/experiments-legacy/experiment_aggregates.csv
runs/experiments-legacy/experiment_summary.csv
```

默认发现只负责选择结构完整的候选；内容哈希仍由加载器验证。

---

## 四、G1：让验签对象与实际读取对象完全一致

当前根因是 `src/ltverify/robustness_loader.py` 使用：

```python
if aggregates_path.name.startswith("robustness_"):
    verify_experiment_manifest(manifest, artifact_dir, ...)
    aggregates = _read_csv_safely(aggregates_path)
```

`verify_experiment_manifest` 固定验签 manifest 中的
`robustness_aggregates.csv` 和 `robustness_summary.csv`，但随后读取的可能是其他同前缀文件。

修复要求：

1. current aggregates 只允许 basename 精确等于 `robustness_aggregates.csv`；
2. current summary 只允许 basename 精确等于 `robustness_summary.csv`；
3. legacy aggregates 只允许 `experiment_aggregates.csv`；
4. legacy summary 只允许 `experiment_summary.csv`；
5. 两者仍必须位于同一目录；
6. current 的 effective summary 无论显式或默认，都必须是 manifest 中被验签的同一文件；
7. 不得把 `startswith` 当成证据归属判断；
8. 返回 `strict_verified` 前，实际返回的两个 DataFrame 必须逐一对应刚刚验签的两个路径；
9. legacy 仍显示 `legacy_unverified`，但不能混合 current 文件；
10. 文件角色错误应在读取内容前拒绝。

建议把权威文件名定义成单一来源常量，供实验生成、验证器、加载器和页面默认发现共同使用，避免字符串再次漂移。例如：

```python
CURRENT_AGGREGATES_NAME = "robustness_aggregates.csv"
CURRENT_SUMMARY_NAME = "robustness_summary.csv"
CURRENT_MANIFEST_NAME = "robustness_experiment_manifest.json"
LEGACY_AGGREGATES_NAME = "experiment_aggregates.csv"
LEGACY_SUMMARY_NAME = "experiment_summary.csv"
```

不要为任意 `robustness_*` 扩展一个“部分可信”状态；项目当前公开契约只有这两份核心输出。

---

## 五、G1：加固 manifest 与 CSV 的外部输入边界

### 5.1 manifest 顶层对象

在进入 `verify_experiment_manifest` 前检查：

```python
if not isinstance(manifest, dict):
    raise RobustnessLoadError("实验清单顶层必须是 JSON object")
```

验证器公共入口也应有对应检查，避免其他调用方再次遇到 `AttributeError`。如果接受 `Mapping[str, object]`，类型签名、运行时检查和测试必须一致。

加载器应把以下边界异常转换为 `RobustnessLoadError`：

- JSON 读取/解码错误；
- manifest 类型和字段契约错误；
- 权威文件不是普通文件；
- 验签过程中的文件读取错误；
- CSV 读取、编码和解析错误。

不得捕获后继续展示，也不得用裸 `except Exception: pass`。

### 5.2 聚合表规范化

建议让 `_validate_aggregates` 返回规范化副本，而不是只做部分检查：

1. `family` 转 pandas string dtype 并 `str.strip()`；
2. 任一缺失或空白值都拒绝；
3. `value` 任一缺失值拒绝，并规范化为稳定展示字符串；
4. 页面 selectbox 只接收清洗后的纯字符串列表；
5. 选中 metric 的 mean/std 都转换为数值；
6. mean/std 必须有限；
7. std 必须非负；
8. 全空 metric 可显示“不适用”，但不得与纯非数值或无限值混为一谈。

页面中这段已不可达：

```python
if aggregates[mean_column].isna().all():
    st.info(...)
    st.stop()
```

前面 `if not numeric.notna().any()` 已覆盖同一条件。删除死分支，并把有限性/标准差校验放到可测试的加载或绘图边界。

### 5.3 测试必须命中目标分支

对每个坏输入测试，断言具体错误文本，例如“缺 family”“非有限数值”“负标准差”，不要只写：

```python
assert len(app_test.error) + len(app_test.warning) >= 1
```

否则“缺 manifest”也会让完全错误的实现通过测试。

---

## 六、G1：让初始 running manifest 从第一刻起可验证

当前流水线顺序是：

```python
shutil.copyfile(config_path, run_dir / "config.snapshot.yaml")
_write_manifest(manifest, run_dir, [])
artifacts = build_network(...)
```

这仍会在快照存在后写出空 `output_paths`。普通 `Exception` 会被异常分支修复，但 `KeyboardInterrupt`、`SystemExit`、进程被终止或机器掉电不会进入该分支。

修复为：

```python
snapshot = run_dir / "config.snapshot.yaml"
shutil.copyfile(config_path, snapshot)
_write_manifest(manifest, run_dir, [snapshot])
```

要求：

1. 初始 running manifest 声明并哈希 snapshot；
2. snapshot hash 等于 `config_sha256`；
3. caught failure manifest 继续使用同一最小证据集合；
4. completed manifest 继续声明全部完成产物；
5. snapshot 复制失败时不留下伪 schema-v2 manifest；
6. 不用捕获 `BaseException` 改写用户中断语义；
7. 不把运行中 manifest 错标为 completed 或 failed；
8. 文档说明被外部中断的目录可能保持 `status=running`，但其配置来源仍可验签。

第九轮报告声称“运行中途被 kill 不再留下 status=running 的孤儿 manifest”，这与当前代码不符。不要把这句错误描述继续写入文档或交接报告。

---

## 七、G1：先验证元素类型，再执行集合操作

`verify_manifest_hashes` 当前在验证元素类型前执行：

```python
len(input_paths) != len(set(input_paths))
len(paths) != len(set(paths))
```

JSON 数组可以合法包含 object/array，因此原始清单边界不能假设元素可哈希。

正确顺序：

1. 字段存在性；
2. 容器类型；
3. 元素逐项为字符串；
4. 字符串路径合法性；
5. 再执行去重或使用只接收已验证字符串的 `seen`；
6. 再比较 `output_paths` 与 `output_sha256` 键集合；
7. 最后读取文件和计算哈希。

`output_sha256` 也应明确为 `dict[str, str]`，不要依赖 `str(value)` 隐式转换掩盖错误类型。

错误必须稳定、领域化，例如：

```text
input_paths[0] 必须是字符串
output_paths[0] 必须是字符串
output_sha256['metrics.json'] 必须是 64 位十六进制字符串
```

---

## 八、G2：默认发现只选择结构完整的候选

`_default_experiment_paths` 不应只看 aggregates 是否存在。实验生成在 CSV 已写、manifest 尚未写时中断，会留下不完整的较新目录；当前逻辑会让它阻断所有较旧有效证据。

建议候选条件：

- current：aggregates、summary、manifest 三者均为普通文件；
- legacy：aggregates 为普通文件，summary 可选；若 summary 存在必须为普通文件且命名正确；
- current 仍优先于 legacy；
- 同一类别内按目录名/时间倒序；
- 内容与哈希不在发现阶段解析，仍由 loader 统一负责。

页面输入框手工指定不完整目录时仍应显示明确错误；默认自动选择则应跳过明显不完整候选。

---

## 九、文档与证据策略

按实际修复更新：

- `README.md`
- `docs/methodology.md`
- `data/README.md`
- 相关 docstring

只需说明：

1. `strict_verified` 只适用于实际读取的精确权威文件；
2. arbitrary same-prefix 文件不会继承 sibling manifest 的信任状态；
3. running/failed/completed manifest 在快照成功后均保留快照哈希闭环；
4. 非对象 JSON、混合空值 family 和非法数值会安全拒绝；
5. legacy 只接受精确旧文件名并始终标为未验证。

证据策略：

- 不改算法、配置和完成态产物格式，因此不重跑默认 30 天流水线；
- 不改实验生成内容，因此不重跑 130 案例；
- 修复后重新执行默认报告字节复现和权威实验严格加载；
- 不提交第七、八、九轮未跟踪审查报告；
- 不手工修改 `reports/metrics` 下的证据。

---

## 十、推荐实施顺序与提交拆分

### 提交 1：复现证据对象错配和输入崩溃

```text
test: reproduce ninth-review trust-boundary regressions
```

只加入 G0.1、G0.2、G0.3 的失败测试，保存修复前输出。

### 提交 2：绑定权威文件角色并加固加载器

```text
fix: bind robustness verification to displayed files
```

完成精确 basename、manifest object、CSV schema/数值边界和页面死代码修复。

### 提交 3：修复中断态 manifest

```text
fix: keep running manifests self-verifying
```

加入 G0.4 测试并让初始 manifest 哈希 snapshot。

### 提交 4：收紧原始 manifest 类型契约

```text
fix: validate manifest element types before deduplication
```

加入 G0.5 测试并调整验证顺序。

### 提交 5：完善默认发现与文档

```text
fix: skip incomplete experiment directories
docs: clarify verified robustness artifact identity
```

可以拆成两个提交，确保每个提交都可单独审查。

每个提交前后执行相关专项测试；最终执行：

```powershell
git diff --check
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src app tests scripts
git status --short
```

---

## 十一、最终验收矩阵

| 验收项 | 必须结果 |
|---|---|
| 权威 current 文件 | 精确 canonical aggregate + summary 才可验签 |
| 同目录 `robustness_forged.csv` | 拒绝，不得返回任何 verified 状态 |
| current aggregate + legacy/伪造 summary | 拒绝，不得混批 |
| legacy 精确文件对 | 可展示，状态始终 `legacy_unverified` |
| manifest 顶层为 list/null/string/number/bool | 加载器领域错误，页面无 exception |
| family 含 null/空白 | 明确拒绝，页面无排序异常 |
| mean/std 为 inf 或 std 为负 | 明确拒绝，不交给 Plotly |
| `KeyboardInterrupt` 后 running manifest | snapshot 入哈希且 verifier 通过 |
| 普通 failed manifest | 继续自验证并保留 failure_summary |
| input/output path 含 list/dict | 明确 ValueError，不泄漏 unhashable TypeError |
| 较新不完整 current 目录 | 默认发现跳过 |
| 较旧完整 current 目录 | 可被默认选择并正常验签 |
| 页面死分支 | 删除，不降低“不适用”提示能力 |
| 权威实验清单 | strict 验证通过 |
| 权威鲁棒性加载 | `strict_verified` |
| 默认报告 | summary/manifest 逐字节复现 |
| 全量测试 | 全绿，数量不得少于当前 174 |
| Ruff | `All checks passed!` |
| 工作树 | 仅保留原有未跟踪报告，不混入提交 |

---

## 十二、最终回报格式

完成后按以下结构回报：

```text
1. 基线与工作树保护
   - 开始 HEAD/status
   - 保留的未跟踪报告

2. 红灯复现
   - forged aggregate/summary 的修复前 strict_verified 输出
   - 非对象 manifest 和 mixed family 的页面 exception
   - interrupted running manifest 的 verifier 失败
   - unhashable path 元素错误

3. 实际修改
   - 文件路径
   - 精确文件角色契约
   - manifest/CSV 边界
   - running manifest 生命周期

4. 绿灯验证
   - 每组专项测试
   - AppTest 无 exception 证据
   - failed/running manifest 自验证证据

5. 交付证据复核
   - 默认 report 字节复现
   - 实验 strict 验证
   - loader strict_verified
   - 未重跑 30 天/130 案例的理由

6. 全量质量门禁
   - pytest 完整结果
   - Ruff 完整结果
   - git diff --check

7. 提交
   - 每个 commit hash 与主题
   - 最终 git status
   - 明确未提交三个报告、未 push

8. 下一轮独立检查建议
   - 只列仍需 Codex 复核的边界，不得自行宣布收口
```

完成标准不是删除第九轮报告列出的两行微瑕，而是让“验签的字节”和“展示的字节”成为同一对象，让所有已写出 manifest 在配置快照存在后都能通过自身验证，并让合法但恶意形状的 JSON/CSV 输入全部转为可解释的页面错误而非 traceback。
