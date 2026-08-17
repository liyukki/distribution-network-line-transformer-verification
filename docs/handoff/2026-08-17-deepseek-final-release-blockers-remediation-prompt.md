# GitHub 上架最终阻塞项整改 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 使用可用的 test-driven development 与逐任务执行能力完成本文；若 harness 提供等价的 subagent-driven-development 或 executing-plans，请逐项执行并在每个任务后进行独立 review gate。步骤使用复选框跟踪。完成后必须从公开工作树删除本文，但不得改写 Git 历史。

**Goal:** 修复合法零错误运行被拒绝、畸形 Parquet 泄漏非领域异常以及 Top-k 元数据关系不完整三个最终发布阻塞项，使项目达到 GitHub 公开上架的本地发布标准。

**Architecture:** 保持现有 manifest verify-before-parse 与跨产物绑定架构不变；在任何 `unique()`、`set()`、排序或 merge 前验证对象列为非空标量字符串，并让验证器完整接受 `evaluation.py` 能产生的所有合法状态。Top-k 契约以 `candidate_feeder_count`、`n_actual_errors`、evaluated count、coverage 和 rate 的确定关系为唯一口径。

**Tech Stack:** Python 3.11/3.12、pandas、NumPy、PyArrow、pytest、Streamlit AppTest、Ruff、GitHub Actions。

## Global Constraints

- 审改代码基线为 `ae53f1f docs: make public reproduction self-contained`；本文会作为其后的一笔纯文档提交，因此执行时当前 HEAD 不必等于 `ae53f1f`，但该提交必须是当前 HEAD 的祖先。
- 开始前确认分支为 `main`，除本文外工作区干净，仍无 Git remote；如有其他用户变更，先报告并保护，不得覆盖。
- 不修改特征、评分权重、阈值、标签、仿真参数、默认 30 天结果、公开证据包字节或 130 案例结果。
- 不重跑默认 30 天流水线和 130 案例实验；只允许运行小型 fixture、公开证据复现和现有验证命令。
- 不降低 current schema 的严格性，不通过自动裁剪、强制转换或默认填充值掩盖非法产物。
- 不把 list、dict、NumPy array、bytes、数字或 null 转成字符串后接受；对象标识和 decision 必须本来就是非空 `str`。
- 所有坏产物必须统一转成 `ArtifactLoadError`；Streamlit 不得出现未捕获 traceback。
- 不修改默认失败边界：F1 `0.167`、PR-AUC `0.378`。
- 不配置 remote、不 push、不创建 release、不猜测用户身份或 LICENSE 署名。
- 不执行 `reset --hard`、rebase、squash、filter-repo、orphan branch 或其他历史改写。
- 任一强制门禁失败时必须输出 `PUBLIC_READY=NO`。

---

## 1. 当前已通过基线

Codex 于 2026-08-17 在 `ae53f1f` fresh 验证：

```text
pytest: 378 passed in 338.57s
coverage: 91.17%（1857 statements，164 miss）
ruff format --check: 58 files already formatted
ruff check: All checks passed!
wheel: 0.1.0 wheel 构建成功，51,030 bytes
Notebook 01/02/03: 均从头执行成功
公开证据包: 14 个 tracked 文件
公开 manifest verify: success
public summary byte match: True
public manifest byte match: True
experiment verification: strict
robustness loader: strict_verified
robustness rows: 130
本机路径、明显凭据、内部 handoff/plan/spec: 当前公开树无命中
工作区: clean
remote: 未配置
```

以上通过项不得被本轮修改破坏，但它们不能证明当前代码已经可上架，因为现有测试漏掉以下反例。

当前判定：

```text
PUBLIC_READY=NO
```

---

## 2. Codex 已复现的阻塞问题

### R1（P1）：项目自身生成的合法零错误 run 被拒绝

用 `tests/fixtures/small_config.yaml` 生成小型运行，仅把：

```yaml
corruption:
  ledger_error_rate: 0.0
```

生产器得到：

```text
n_actual_errors=0
topk_applicable={'top1': True, 'top2': True, 'top3': False}
top1_correction_rate=None
top1_evaluation_coverage=None
top1_evaluated_count=0
```

这是 `src/ltverify/evaluation.py` 的合法输出：候选馈线数量使 Top-1/Top-2 方法定义上适用，但没有实际错误样本可评价，因此 rate 与 coverage 均为 null、count 为 0。

当前 `src/ltverify/data_access.py` 却返回：

```text
ZERO_ERROR_VALID_RUN=REJECTED
ArtifactLoadError: top1 适用时 evaluation_coverage 不能为 null
```

生产器与验证器契约不一致，属于正常业务状态不可用，不是恶意输入问题。

### R2（P1）：对象列在类型校验前进入 hash/unique 集合运算

将 hash 已同步的 `predictions.parquet` 的 `decision` 整列写成 Parquet list 类型后：

```text
UNHASHABLE_DECISION=TypeError: unhashable type: 'numpy.ndarray'
IS_DOMAIN_ERROR=False
```

Streamlit AppTest 实测：

```text
APP_EXCEPTION_COUNT=1
APP_ERROR_COUNT=0
```

traceback 位于：

```python
decisions = set(predictions["decision"].unique())
```

同样，将 `predictions.transformer_id` 写成 list 类型后：

```text
UNHASHABLE_TRANSFORMER_ID=TypeError: unhashable type: 'numpy.ndarray'
IS_DOMAIN_ERROR=False
```

对应代码在逐元素类型验证前执行：

```python
ids = [set(frame["transformer_id"]) for frame in (truth, ledger, predictions)]
```

### R3（P2，必须与本轮一并修复）：Top-k 元数据仍可自相矛盾

在公开证据包副本中只修改并重新计算 `metrics.json` 哈希：

```text
top1_evaluated_count=999
top1_evaluation_coverage=1.0
n_actual_errors=5
```

当前 loader 仍接受：

```text
TOPK_COUNT_MISMATCH=ACCEPTED:count=999,n_errors=5
```

现有校验没有固定：

- `evaluated_count <= n_actual_errors`；
- 有错误样本时 `evaluation_coverage == evaluated_count / n_actual_errors`；
- `topk_applicable.topK == (candidate_feeder_count > K)`；
- `evaluated_count == 0` 与 `correction_rate is None` 的对应关系。

### R4（P3，文档一致性）：README 结果章节仍保留旧命令

README 前部的公开证据复现命令已经正确使用：

```text
reports/evidence/default_run
--manifest-output
```

但“结果”章节仍写：

```text
.venv/Scripts/python.exe -m ltverify report --run-dir <运行目录> --output reports/metrics/default_summary.json
```

该命令会直接写仓库规范文件，且没有指定规范 manifest 输出名。应引用前面的安全临时目录命令，不再保留第二套含糊口径。

---

### Task 1: 建立生产器—loader 零错误闭环测试

**Files:**

- Modify: `tests/unit/test_app_data_access.py`
- Test: `tests/unit/test_app_data_access.py`

**Interfaces:**

- Consumes: 现有 `_fixture_run`、`run_pipeline`、`load_run_artifacts`。
- Produces: 可配置 `ledger_error_rate` 的小型 fixture，以及合法零错误 run 必须被 loader 接受的端到端回归测试。

- [ ] **Step 1: 让 fixture helper 接受错误率参数**

将现有 helper 改为：

```python
def _fixture_run(
    tmp_path: Path,
    *,
    ledger_error_rate: float = 0.20,
) -> Path:
    config = tmp_path / "small.yaml"
```

上面只展示需替换的函数头和现有实现第一行；从现有 `config.write_text` 调用到 `return run_pipeline(config)` 的实现原样保留，仅按下一段替换 YAML 中的固定错误率。

生成 YAML 时使用实际参数：

```python
f"  ledger_error_rate: {ledger_error_rate}\n"
```

默认值必须保持 `0.20`，现有测试行为不变。

- [ ] **Step 2: 写合法零错误运行红测**

```python
def test_load_run_artifacts_accepts_valid_zero_error_run(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path, ledger_error_rate=0.0)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["n_actual_errors"] == 0
    assert metrics["topk_applicable"]["top1"] is True
    assert metrics["top1_correction_rate"] is None
    assert metrics["top1_evaluation_coverage"] is None
    assert metrics["top1_evaluated_count"] == 0

    artifacts = load_run_artifacts(run_dir)
    assert artifacts.metrics["n_actual_errors"] == 0
```

- [ ] **Step 3: 运行并确认修复前真实失败**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_app_data_access.py::test_load_run_artifacts_accepts_valid_zero_error_run -q
```

预期：修复前 FAIL，错误为 `top1 适用时 evaluation_coverage 不能为 null`。不得通过修改生产器把合法 null 伪造成 0。

- [ ] **Step 4: 只提交红测**

```text
test: reproduce valid zero-error dashboard rejection
```

---

### Task 2: 统一 Top-k 状态机与算术关系

**Files:**

- Modify: `src/ltverify/data_access.py`
- Modify: `tests/unit/test_app_data_access.py`
- Test: `tests/unit/test_app_data_access.py`

**Interfaces:**

- Consumes: `_require_nullable_ratio_metric`、`_require_count_metric`、`n_actual_errors`、`candidate_feeder_count`。
- Produces: `_validate_metrics` 接受生产器的全部合法 Top-k 状态，并拒绝计数、coverage、适用性自相矛盾的状态。

- [ ] **Step 1: 先解析依赖计数，再验证 Top-k**

当前 Top-k 循环发生在 `n_actual_errors` 与 `candidate_feeder_count` 解析之前。重排 `_validate_metrics`，先得到：

```python
n_total = _require_count_metric(metrics, "n_total", positive=True)
n_actual_errors = _require_count_metric(metrics, "n_actual_errors", positive=False)
candidate_feeder_count = _require_count_metric(
    metrics,
    "candidate_feeder_count",
    positive=True,
)
```

然后再验证 Top-1、Top-2、Top-3。不要二次读取并转换同一字段。

- [ ] **Step 2: 实现唯一 Top-k 状态规则**

对 `k in (1, 2, 3)`：

```python
expected_applicable = candidate_feeder_count > k
```

若记录值与 `expected_applicable` 不同，抛 `ArtifactLoadError`。

不适用状态必须是：

```text
applicable=False
evaluated_count=0
evaluation_coverage=None
correction_rate=None
```

适用且 `n_actual_errors == 0` 的合法状态必须是：

```text
applicable=True
evaluated_count=0
evaluation_coverage=None
correction_rate=None
```

适用且 `n_actual_errors > 0` 时：

```python
if evaluated_count > n_actual_errors:
    raise ArtifactLoadError(
        f"metrics.{count_key} 不能大于 metrics.n_actual_errors"
    )

expected_coverage = evaluated_count / n_actual_errors
```

`evaluation_coverage` 必须是非 null ratio，并通过：

```python
math.isclose(
    coverage,
    expected_coverage,
    rel_tol=0.0,
    abs_tol=1e-12,
)
```

rate 关系：

```text
evaluated_count == 0 -> correction_rate is None
evaluated_count > 0  -> correction_rate 是非 null [0,1] ratio
```

- [ ] **Step 3: 添加 Top-k 关系坏样例**

在每个坏样例中更新 `metrics.json` 的 manifest 哈希。至少覆盖：

```python
@pytest.mark.parametrize(
    "mutator",
    [
        lambda m: m.update({"top1_evaluated_count": m["n_actual_errors"] + 1}),
        lambda m: m.update({"top1_evaluation_coverage": 0.0}),
        lambda m: m.update({
            "candidate_feeder_count": 1,
            "topk_applicable": {"top1": True, "top2": False, "top3": False},
        }),
        lambda m: m.update({"top1_evaluated_count": 0, "top1_correction_rate": 0.5}),
    ],
)
def test_loader_rejects_inconsistent_topk_metadata(
    tmp_path: Path,
    mutator: object,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    mutator(metrics)
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="top1|Top-1|applicable|coverage"):
        load_run_artifacts(run_dir)
```

第三个样例必须同步调整 top2/top3 的 null/count 状态，只保留“candidate count 与 applicable 不一致”这一单一失败原因。

- [ ] **Step 4: 运行 Top-k 和评价测试**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_app_data_access.py tests/unit/test_evaluation.py -q
```

- [ ] **Step 5: 提交修复**

```text
fix: align top-k validation with zero-error semantics
```

---

### Task 3: 为对象列添加集合运算前标量字符串验证

**Files:**

- Modify: `src/ltverify/data_access.py`
- Modify: `tests/unit/test_app_data_access.py`
- Modify: `tests/integration/test_streamlit_smoke.py`
- Test: `tests/unit/test_app_data_access.py`
- Test: `tests/integration/test_streamlit_smoke.py`

**Interfaces:**

- Consumes: 已解析且通过列存在性检查的 pandas DataFrame。
- Produces: `_require_nonempty_string_series`；所有 ID、feeder ID 与 decision 在 `duplicated`、`unique`、`set`、排序和 merge 前被收紧为非空字符串契约。

- [ ] **Step 1: 先写两个 loader 红测**

使用完整 fixture 或 `reports/evidence/default_run` 的临时副本。不要修改仓库权威证据。

`decision` list 列：

```python
predictions["decision"] = [
    [str(value)] for value in predictions["decision"]
]
predictions.to_parquet(predictions_path)
_update_manifest_hash(run_dir, "predictions.parquet")

with pytest.raises(ArtifactLoadError, match="decision.*非空字符串"):
    load_run_artifacts(run_dir)
```

`transformer_id` list 列：

```python
predictions["transformer_id"] = [
    [str(value)] for value in predictions["transformer_id"]
]
predictions.to_parquet(predictions_path)
_update_manifest_hash(run_dir, "predictions.parquet")

with pytest.raises(ArtifactLoadError, match="transformer_id.*非空字符串"):
    load_run_artifacts(run_dir)
```

这两个测试修复前必须得到 raw `TypeError`，修复后必须得到 `ArtifactLoadError`。

- [ ] **Step 2: 添加通用字符串列验证 helper**

```python
def _require_nonempty_string_series(
    frame: pd.DataFrame,
    column: str,
    label: str,
) -> pd.Series:
    values = frame[column]
    valid = values.map(lambda value: isinstance(value, str) and bool(value))
    if not bool(valid.all()):
        raise ArtifactLoadError(f"{label}.{column} 必须全部为非空字符串")
    return values
```

不要使用 `astype(str)`；不要在错误消息中输出整列或本机文件路径。

- [ ] **Step 3: 在任何集合运算前调用 helper**

`_validate_transformer_identity_contracts` 至少验证：

```text
truth_topology.csv.transformer_id
truth_topology.csv.physical_feeder_id
reported_ledger.csv.transformer_id
reported_ledger.csv.reported_feeder_id
predictions.parquet.transformer_id
```

`_validate_prediction_metric_consistency` 在 `.unique()` / `set()` 前验证：

```text
predictions.parquet.decision
```

如果后续对其他 object 列执行 hash、排序、集合或字典键操作，也必须先用同一 helper 收紧。

- [ ] **Step 4: 避免对未经验证值排序**

完成字符串验证后才允许：

```python
decisions = set(decision_values)
unknown = sorted(decisions - allowed_decisions)
```

ID 集合也只能从已验证的 string series 构造。

- [ ] **Step 5: 添加 Streamlit AppTest**

用 hash 已同步的 list-valued `decision` Parquet 启动首页：

```python
app_test.run()
assert len(app_test.exception) == 0
assert len(app_test.error) >= 1
assert "decision" in " ".join(element.value for element in app_test.error)
```

- [ ] **Step 6: 扩展类型参数**

直接 helper 单元测试或完整 loader 测试至少覆盖：

```text
None
[]
{}
numpy.ndarray
1
True
b"T001"
""
```

全部拒绝；正常非空字符串接受。

- [ ] **Step 7: 运行目标测试**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_app_data_access.py tests/integration/test_streamlit_smoke.py -q
```

- [ ] **Step 8: 提交修复**

```text
fix: validate artifact strings before collection operations
```

---

### Task 4: 统一 README 结果章节复现口径

**Files:**

- Modify: `README.md`
- Modify: `tests/unit/test_documentation.py`
- Test: `tests/unit/test_documentation.py`

**Interfaces:**

- Consumes: README“质量与复现”章节的公开证据临时目录命令。
- Produces: “结果”章节只引用该权威命令，不再给出会覆盖仓库文件且漏掉 manifest 输出的第二套命令。

- [ ] **Step 1: 修改结果章节首句**

将旧句改为以下确定表述：

```markdown
以下数字可由“质量与复现”章节的公开证据包命令逐字节复现；
该命令从 `reports/evidence/default_run/` 读取历史权威 run，
并同时生成临时 `default_summary.json` 与 `default_manifest.json`，
不会覆盖仓库中的规范证据文件。
```

不要在此处再次复制一条省略 `--manifest-output` 的命令。

- [ ] **Step 2: 收紧文档测试**

现有测试只检查 README 任意位置出现一次 `--manifest-output`，无法阻止旧命令残留。增加：

```python
def test_readme_has_no_report_command_without_manifest_output() -> None:
    text = _readme()
    assert "--run-dir <运行目录> --output reports/metrics/default_summary.json" not in text
```

并保留公开证据路径与 Markdown 链接检查。

- [ ] **Step 3: 运行并提交**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_documentation.py -q
```

```text
docs: unify public evidence reproduction instructions
```

---

### Task 5: 删除本交接文档并执行最终发布门禁

**Files:**

- Delete: `docs/handoff/2026-08-17-deepseek-final-release-blockers-remediation-prompt.md`

**Interfaces:**

- Consumes: 前四个任务的已提交结果。
- Produces: 无内部 handoff 的公开工作树，以及带真实证据的 `PUBLIC_READY` 判定。

- [ ] **Step 1: 删除本文但保留历史**

通过普通 Git 删除本文。禁止清理历史对象。确认：

```powershell
git log --all --oneline -- docs/handoff/2026-08-17-deepseek-final-release-blockers-remediation-prompt.md
```

仍能找到加入本文的历史提交。

- [ ] **Step 2: 执行 Ruff 与全量测试**

```powershell
.venv\Scripts\python.exe -m ruff format --check src app tests scripts
.venv\Scripts\python.exe -m ruff check src app tests scripts
.venv\Scripts\python.exe -m pytest --cov=ltverify --cov-report=term-missing --cov-fail-under=90 -q
git diff --check
```

- [ ] **Step 3: 运行指定回归矩阵**

最终报告逐项给出：

```text
合法 ledger_error_rate=0 run -> loader accepted
合法零错误 Top-1/Top-2 null/count 状态 -> accepted
top1_evaluated_count=999,n_actual_errors=5 -> ArtifactLoadError
Top-k coverage 与 count/n_errors 不一致 -> ArtifactLoadError
candidate_feeder_count 与 topk_applicable 不一致 -> ArtifactLoadError
decision list/array -> ArtifactLoadError，不是 TypeError
transformer_id list/array -> ArtifactLoadError，不是 TypeError
Streamlit malformed decision -> exception=0,error>=1
```

- [ ] **Step 4: 重新验证公开证据**

```text
公开 bundle tracked 文件数 = 14
verify_manifest_hashes = success
public summary byte match = True
public manifest byte match = True
experiment verification = strict
robustness loader = strict_verified
robustness rows = 130
两个历史 evidence commit 仍存在
```

- [ ] **Step 5: 重新执行三个 Notebook**

输出到系统临时目录，要求三本成功、无 error output、无本机绝对路径。不得覆盖已提交 Notebook，除非代码输出确有需要且经过单独审查。

- [ ] **Step 6: 构建 wheel**

wheel 输出到系统临时目录。如构建在仓库产生 ignored `build/`，确认绝对路径正是仓库 `build/` 后删除；最终不得残留。

- [ ] **Step 7: 检查公开树**

```text
当前树无 docs/handoff
当前树无 docs/superpowers/plans 或 specs
公开 Markdown/Notebook 无 D:\电力 或 C:\Users\
无 tracked .env、私钥、build、dist、runs、.venv
README 本地链接全部存在
git status --short 无输出
remote 仍未配置
未 push
```

- [ ] **Step 8: 提交 handoff 清理**

```text
docs: remove final release blocker handoff
```

---

## 3. 分阶段提交纪律

每个任务遵循：

```text
写失败测试
-> 运行并记录真实失败
-> 最小实现
-> 运行目标测试
-> 运行受影响集成测试
-> git diff --check
-> 只暂存当前任务文件
-> git diff --cached --name-status/stat
-> 提交
```

推荐提交序列：

```text
test: reproduce valid zero-error dashboard rejection
fix: align top-k validation with zero-error semantics
fix: validate artifact strings before collection operations
docs: unify public evidence reproduction instructions
docs: remove final release blocker handoff
```

不得把业务修复、测试、README 和 handoff 删除混入同一提交。

---

## 4. 禁止的伪修复

不得采用以下做法：

- 把零错误状态的 `null` 强制改写为 `0.0`，从而改变“不适用”和“零命中”的语义；
- 为让测试通过而修改 `evaluation.py` 的既有合法输出口径；
- 对对象列使用 `astype(str)`；
- 用宽泛 `except Exception` 吞掉所有校验错误而不修复类型顺序；
- 只在 Streamlit 外层捕获 `TypeError`，而让 loader 继续泄漏非领域异常；
- 删除或跳过恶意 Parquet 测试；
- 降低 manifest 哈希验证；
- 修改公开证据包字节并同步哈希来掩盖测试失败；
- 改写历史以整理提交；
- 在 GitHub Actions 未真实运行前添加绿色 badge。

---

## 5. 最终回报格式

DeepSeek 最终必须按以下结构回报：

### A. 修复提交

- 从本文基线到最终 HEAD 的全部新 commit hash/subject；
- 每个提交修改文件；
- 明确未 rebase/squash/filter history。

### B. 零错误语义

- 生产器实际 metrics；
- loader 修复前错误；
- loader 修复后接受结果；
- Top-1/Top-2/Top-3 的完整状态规则。

### C. 类型边界

- 新增 string-series helper；
- helper 应用列清单；
- decision 与 transformer_id list/array 的异常类型；
- Streamlit exception/error 数量。

### D. Top-k 关系

- count 上界；
- coverage 算式与容差；
- candidate count/applicable 算式；
- 四个指定坏样例结果。

### E. 文档与发布门禁

- README 旧命令是否移除；
- Ruff、pytest 数量、失败数、coverage；
- wheel、三本 Notebook；
- public evidence byte match；
- strict / strict_verified / 130；
- 最终工作区、remote、push 状态。

### F. 用户仍需亲自完成

- 配置 GitHub verified email 与公开姓名；
- 决定 LICENSE 署名；
- 创建 GitHub repository 和 origin；
- 首次 push；
- 确认 Python 3.11/3.12 GitHub Actions 实际通过；
- CI 通过后添加真实 badge；
- 可选添加真实 Streamlit 截图；
- 决定是否创建 `v0.1.0` tag/release。

### G. 发布判定

只有本地强制门禁全部通过、本文已从当前树删除、剩余事项仅为用户身份/远端/首次 CI/可选截图时，输出：

```text
PUBLIC_READY=YES
```

否则输出：

```text
PUBLIC_READY=NO
```

并列出具体失败测试、异常类型、文件和复现命令。

---

## 6. 完成定义

只有以下全部满足，才可声明完成：

- 项目自身生成的合法零错误 run 能由 loader 和 Streamlit 正常加载；
- Top-k 对零错误、无可评价样本、正常样本和不适用状态的 null/count/coverage/rate 语义一致；
- Top-k count、coverage 和 applicable 的算术矛盾均被拒绝；
- 所有参与集合运算的对象 ID/decision 在运算前验证为非空字符串；
- list/dict/array/null/数字/bool/bytes/空字符串统一触发 `ArtifactLoadError`；
- Streamlit 对畸形 Parquet 无 traceback；
- README 不再保留省略 manifest 输出的旧复现命令；
- Ruff、全测、coverage、wheel、Notebook、公开证据和鲁棒性门禁全部 fresh 通过；
- 公开证据包、默认失败边界和 130 案例未变化；
- 当前公开树不含本文或其他内部 handoff；
- 历史未改写，remote 未配置，Agent 未 push；
- 最终报告给出有命令证据支持的 `PUBLIC_READY=YES/NO`。
