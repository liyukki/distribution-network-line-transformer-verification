# GitHub 公开发布终审整改 Implementation Plan

> **For agentic workers:** 按本文逐项执行，强制使用测试驱动流程：先写能复现问题的失败测试，再做最小修复。若 harness 提供等价的计划执行或代码审查能力，请在每个任务后运行独立 review gate。本文执行完成后必须从公开工作树删除自身，但不得改写 Git 历史。

**Goal:** 修复本轮终审发现的指标语义绑定与公开证据可复现缺口，使仓库达到可公开上传 GitHub、可用于电网/能源数字化实习展示的本地发布标准。

**Architecture:** 保留现有 manifest “先校验、后解析”边界，在解析完成后增加 metrics、predictions、truth、ledger 与 confusion matrix 的跨产物语义一致性验证；同时把已存在且哈希闭环完整的默认合成运行复制为小型公开证据包，使全新 clone 无需访问本机 ignored `runs/` 即可逐字节复现规范报告。公开 UI 只显示安全的运行标识，README 使用明确的虚拟环境解释器和真实 Markdown 链接。

**Tech Stack:** Python 3.11/3.12、pandas、NumPy、pytest、pytest-cov、Streamlit AppTest、Ruff、GitHub Actions、SHA-256 manifest。

## Global Constraints

- 代码审查锚点为 `b9fc8b7 docs: prepare readme for public portfolio release`；本文将作为锚点之后的一笔纯文档提交，因此当前 HEAD 不必等于该锚点，但 `b9fc8b7` 必须是当前 HEAD 的祖先。
- 开始前确认分支为 `main`、工作区除本文外无未提交变更、仍未配置 remote；如存在其他用户变更，先报告并保护，不得覆盖。
- 不修改算法特征、评分权重、阈值、标签、仿真参数、默认 30 天结果或 130 案例结果。
- 不重跑默认 30 天流水线和 130 案例实验；公开默认证据包必须逐字节复制现有已验证运行。
- 不伪造截图、指标、CI 状态、真实电网数据、生产部署或准确率声明。
- 不猜测用户姓名、GitHub 用户名、邮箱、远端地址或 LICENSE 署名。
- 不配置 remote、不创建 GitHub 仓库、不 push、不发布 release。
- 不执行 `reset --hard`、根 rebase、squash、filter-repo、orphan main 或任何历史改写。
- 保留默认失败边界：F1 `0.167`、PR-AUC `0.378`；不得以本轮工程修复改变研究结论。
- 所有新增校验必须先通过 manifest 哈希验证，再解析和检查业务语义；不得倒退 verify-before-parse 顺序。
- 最终任一强制门禁未通过时，只能输出 `PUBLIC_READY=NO`。

---

## 1. Codex 终审基线

### 1.1 DeepSeek 已完成的提交

锚点 `09fe324` 之后已存在以下 8 个整改提交：

```text
8c8ac95 test: reproduce github-release manifest and metric regressions
3f0be55 fix: validate manifest declarations and dashboard metric ranges
d0c9b7d build: ignore local build and notebook artifacts
04be660 style: apply ruff formatting before public release
a89b09e docs: make executed notebooks portable
1ba4ec1 ci: add python quality and test workflow
8d2deb2 docs: add public AI usage and audit summary
b9fc8b7 docs: prepare readme for public portfolio release
```

本轮已确认上一轮两个原始缺陷得到修复：

- 非字符串或不可哈希的 `output_paths` 不再泄漏 `TypeError`；
- 重复声明的新 run 会在 discovery 阶段被跳过；
- `f1`、`top1_correction_rate`、`automatic_coverage` 的越界值会被拒绝；
- manifest 声明验证已抽取到 `validate_output_declarations`。

### 1.2 本轮 fresh 通过项

Codex 于 2026-08-17 在 Windows / Python 3.12.13 实际执行：

```text
pytest + coverage: 305 passed in 172.38s
coverage: 91.82%（1724 statements，141 miss）
ruff format --check: 57 files already formatted
ruff check: All checks passed!
git diff --check: passed
wheel: 0.1.0 wheel 构建成功，49,112 bytes
Notebook 01/02/03: 均从头执行成功
Notebook error output: 0
Notebook 本机 D:\ / C:\Users\ 路径: 0
default_summary byte match: True
default_manifest byte match: True
experiment verification: strict
robustness loader: strict_verified
robustness rows: 130
历史证据提交 533b64a... / 59a623e...: 均仍为 commit
当前树明显私钥/API token 扫描: 无命中
本地 Markdown 链接存在性检查: 通过
```

这些通过项是本轮起点，不代表已经可以公开发布。

---

## 2. 终审发现与发布判定

当前判定：

```text
PUBLIC_READY=NO
```

### R1（P1，发布阻塞）：公开 clone 无法复现默认权威报告

当前 README 声称默认数字可由固定命令复现，`docs/audit-summary.md` 也说明默认 summary/manifest 可从源运行逐字节复现；但源运行只存在于 ignored 本机目录：

```text
runs/run-20260816T121851-b42381de-ca6652/
```

该目录包含 14 个文件、总计约 `4.58 MiB`，最大单文件约 `2.01 MiB`。当前 Git 只跟踪：

```text
reports/metrics/default_summary.json
reports/metrics/default_manifest.json
```

却不跟踪 `default_manifest.json` 声明的 13 个源产物。将 manifest 副本放在 `reports/metrics/` 直接验证时，所有相对产物都不存在。因此只有当前本机能运行逐字节复现，全新 GitHub clone 无法完成同一证据门禁。

README 当前命令还省略：

```text
--manifest-output reports/metrics/default_manifest.json
```

默认行为会生成 `default_summary.manifest.json`，不是仓库中的规范文件名 `default_manifest.json`。

### R2（P1，发布阻塞）：模型评估页展示指标未完整校验

`src/ltverify/data_access.py::_validate_metrics` 只验证：

```text
f1
top1_correction_rate
automatic_coverage
n_total
n_predicted
n_actual_errors（若存在）
```

但 `app/pages/4_evaluation.py` 还直接展示：

```text
precision
recall
pr_auc
pr_auc_scored
scored_coverage
top2_correction_rate
insufficient_data_rate
n_actual_errors
```

Codex 使用哈希已同步更新的 `metrics.json` 实测，loader 全部接受：

```text
precision=ACCEPTED:999.0
recall=ACCEPTED:-1.0
top2_correction_rate=ACCEPTED:999.0
scored_coverage=ACCEPTED:999.0
insufficient_data_rate=ACCEPTED:-1.0
```

这不是 checksum 攻击问题，而是哈希闭环内部缺少完整的 current-schema 业务契约；生产器错误或手工同步 manifest 后，页面会把语义非法值当作可信证据展示。

### R3（P1，发布阻塞）：跨产物指标可以互相矛盾

Codex 在同一哈希已更新的 fixture 上实测，以下三组矛盾仍被接受：

```text
n_total_vs_predictions=ACCEPTED:n_total=999
coverage_vs_counts=ACCEPTED:n_predicted=0,automatic_coverage=1.0
f1_vs_confusion_matrix=ACCEPTED:f1=1.0,confusion_matrix 对应 F1=0.0
```

当前 `_validate_dashboard_contracts` 只检查列存在、非空和 confusion matrix 为有限 `2×2`，没有绑定：

- truth / ledger / predictions 的 transformer ID 集合；
- predictions 行数与 `n_total`；
- `predicted_is_mislinked` 与 `n_predicted`；
- decision 与 automatic/scored/insufficient coverage；
- confusion matrix 与实际/预测计数；
- confusion matrix 与 precision/recall/F1。

### R4（P2）：主页公开显示服务器绝对路径

`app/streamlit_app.py` 当前包含：

```python
st.caption(f"运行目录: {artifacts.run_dir.resolve()}；清单 SHA-256 哈希一致性已校验（非数字签名）")
```

真实截图或公开部署会暴露 `D:\电力\...`、Linux home 或容器路径。Notebook 已做可移植处理，主页也应遵循同一公开展示边界。

### R5（P2）：README 的公开执行链仍不够自洽

1. README 创建并安装 `.venv` 后没有激活环境，后续却使用裸 `python` / `streamlit`；在全新机器上可能调用全局解释器。
2. 默认证据命令没有 `--manifest-output`，无法生成规范 manifest 文件名。
3. `AI_USAGE.md`、`docs/audit-summary.md`、`docs/design.md` 只是反引号文本，不是可点击 Markdown 链接，未完全满足上一轮“链接公开文档”的要求。
4. README 应明确区分“公开证据包逐字节复现”和“重新运行默认仿真产生一个新的 run”，避免把两者混为一谈。

### R6（P3，历史记录）：测试提交混入大量文档删除

`8c8ac95 test: reproduce github-release manifest and metric regressions` 同时删除了约 8,000 行内部 handoff/plan/spec 文档，违反上一轮“测试、代码、文档清理分开提交”的原子提交要求。

不要为修正这一历史瑕疵执行 rebase 或改写历史。最终报告如实记录即可；本轮后续提交必须恢复原子性。

### R7（用户发布前事项，不由 Agent 执行）

- 当前没有 Git remote，因此 GitHub Actions 尚无真实 runner 结果；
- 当前 109 个提交作者均为 DeepSeek/Codex 身份；AI 使用已披露，但用户仍需用自己的 verified email 创建最终发布提交；
- LICENSE 仍为 `Project Contributors`，用户决定是否换成公开姓名或 GitHub handle；
- 当前没有真实 Streamlit 截图，属于可选展示项，不得伪造。

---

## 3. Task 1：为完整展示指标写红测

**Files:**

- Modify: `tests/unit/test_app_data_access.py`
- Modify: `tests/integration/test_streamlit_smoke.py`
- Test: `tests/unit/test_app_data_access.py`
- Test: `tests/integration/test_streamlit_smoke.py`

**Interfaces:**

- Consumes: 现有 `_fixture_run`、`_update_manifest_hash`、`load_run_artifacts`、Streamlit `AppTest`。
- Produces: current schema 所有公开展示 metrics 的失败样例与页面无 traceback 断言。

- [ ] **Step 1: 添加未覆盖比例字段的参数化红测**

至少覆盖以下字段：

```python
DISPLAYED_REQUIRED_RATIOS = (
    "precision",
    "recall",
    "f1",
    "automatic_coverage",
    "insufficient_data_rate",
    "scored_coverage",
)

DISPLAYED_NULLABLE_RATIOS = (
    "pr_auc",
    "pr_auc_scored",
    "top1_correction_rate",
    "top2_correction_rate",
    "top3_correction_rate",
    "top1_evaluation_coverage",
    "top2_evaluation_coverage",
    "top3_evaluation_coverage",
)
```

对非空值参数化：

```python
INVALID_RATIOS = (-0.01, 1.01, 999.0, "0.8", True, float("nan"), float("inf"))
```

每个测试修改 `metrics.json` 后必须调用 `_update_manifest_hash(run_dir, "metrics.json")`，证明失败来自业务契约而非 checksum。

- [ ] **Step 2: 添加 current-schema 必填键与 applicability 红测**

至少覆盖：

```text
precision / recall / f1 缺失
pr_auc_applicable 不是 bool
pr_auc_applicable=True 但 pr_auc=null
pr_auc_applicable=False 但 pr_auc 非 null
pr_auc_scored_applicable 与 pr_auc_scored 同类矛盾
topk_applicable 不是 object
topk_applicable 缺 top1/top2/top3
topk_applicable 的值不是 bool
```

`*_unavailable_reason` 的契约：适用时必须为 `null`；不适用时必须为非空字符串。

- [ ] **Step 3: 添加计数与派生比例元数据红测**

必须验证：

```text
n_actual_correct 为非 bool 非负整数
n_actual_errors + n_actual_correct == n_total
top1/2/3_evaluated_count 为非 bool 非负整数
excluded_candidate_count 为非 bool 非负整数
candidate_feeder_count 为非 bool 正整数
scored_coverage + insufficient_data_rate == 1（容差 1e-12）
```

- [ ] **Step 4: 添加模型评估页 AppTest**

构造 hash 一致但 `precision=999.0`、`top2_correction_rate=999.0` 的 current run，要求：

```python
assert len(app_test.exception) == 0
assert len(app_test.error) >= 1
assert "999" not in rendered_evaluation_page_text
```

如 AppTest 导航 API 不能稳定进入子页，至少先用 loader 测试锁定拒绝，再保留一个首页无 traceback 测试；不得为了测试方便在页面静默裁剪非法值。

- [ ] **Step 5: 运行红测并记录真实失败**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_app_data_access.py -k "precision or recall or top2 or coverage or applicability" -q
```

预期修复前：新增测试 FAIL，且能看到 loader 接受了至少一个非法字段。不得用语法错误制造红测。

- [ ] **Step 6: 仅提交测试**

```text
test: reproduce displayed metric contract gaps
```

---

## 4. Task 2：实现完整 current-schema metrics 契约

**Files:**

- Modify: `src/ltverify/data_access.py`
- Test: `tests/unit/test_app_data_access.py`
- Test: `tests/integration/test_streamlit_smoke.py`

**Interfaces:**

- Consumes: `_require_ratio_metric`、`_require_count_metric`、`ArtifactLoadError`。
- Produces: `_validate_metrics(metrics)` 对所有公开展示字段和 applicability 元数据执行严格验证。

- [ ] **Step 1: 区分缺失、null 与非法类型**

不要继续只用 `metrics.get(key)` 区分必填字段，因为缺失和显式 `null` 会被混为一谈。必填键先做：

```python
if key not in metrics:
    raise ArtifactLoadError(f"metrics 缺少必填字段: {key}")
```

所有 JSON number 均显式拒绝 bool、字符串与非有限值。

- [ ] **Step 2: 扩展 ratio helper**

实现两个明确入口：

```python
def _require_ratio_metric(metrics: dict[str, object], key: str) -> float:
    """Require a present, non-bool, finite JSON number in [0, 1]."""

def _require_nullable_ratio_metric(
    metrics: dict[str, object], key: str
) -> float | None:
    """Require a present null or a valid ratio."""
```

不要通过 `float("0.8")` 接受数字字符串。

- [ ] **Step 3: 验证 applicability 三元组**

为 `pr_auc` 与 `pr_auc_scored` 编写共享 helper，输入 value key、applicable key、reason key：

```text
applicable=True  -> value 是 [0,1] ratio，reason is None
applicable=False -> value is None，reason 是非空字符串
```

`topk_applicable` 必须是只含 `top1`、`top2`、`top3` 的 dict，值均为严格 bool。每个 Top-k rate/coverage 必须存在并满足 nullable ratio 契约；不适用时 rate/coverage 为 null 且 evaluated_count 为 0。

- [ ] **Step 4: 验证计数和内部关系**

验证所有计数后执行：

```python
if n_actual_errors + n_actual_correct != n_total:
    raise ArtifactLoadError(...)

if not math.isclose(
    scored_coverage + insufficient_data_rate,
    1.0,
    rel_tol=0.0,
    abs_tol=1e-12,
):
    raise ArtifactLoadError(...)
```

对 `n_actual_errors == 0` 的 Top-k coverage/null 语义保持与 `evaluation.py` 当前生产逻辑一致。

- [ ] **Step 5: 运行小测试与页面测试**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_app_data_access.py tests/integration/test_streamlit_smoke.py -q
```

- [ ] **Step 6: 提交最小实现**

```text
fix: validate every displayed dashboard metric
```

---

## 5. Task 3：增加跨产物语义绑定红测

**Files:**

- Modify: `tests/unit/test_app_data_access.py`
- Test: `tests/unit/test_app_data_access.py`

**Interfaces:**

- Consumes: hash 已更新的完整 fixture run。
- Produces: 对 ID、计数、coverage、confusion matrix 与 F1 的跨文件矛盾回归测试。

- [ ] **Step 1: 添加 ID 集合红测**

分别构造并同步相关文件哈希：

```text
truth_topology.csv transformer_id 重复
reported_ledger.csv transformer_id 重复
predictions.parquet transformer_id 重复
truth / ledger / predictions 的 transformer_id 集合不一致
```

loader 必须在返回 `RunArtifacts` 前抛 `ArtifactLoadError`。

- [ ] **Step 2: 添加 predictions 语义红测**

覆盖：

```text
len(predictions) != metrics.n_total
predicted_is_mislinked 不是严格 bool dtype/值
decision 含 no_change / insufficient_data / automatic_recommendation 之外的值
predicted_is_mislinked=True 但 decision != automatic_recommendation
decision=automatic_recommendation 但 predicted_is_mislinked=False
sum(predicted_is_mislinked) != metrics.n_predicted
automatic recommendation 比例 != metrics.automatic_coverage
insufficient_data 比例 != metrics.insufficient_data_rate
非 insufficient_data 比例 != metrics.scored_coverage
```

- [ ] **Step 3: 添加 truth/ledger 与 confusion matrix 红测**

覆盖：

```text
由 ledger.reported_feeder_id != truth.physical_feeder_id 得到的错误数 != n_actual_errors
confusion matrix 含负数
confusion matrix 含非整数值
confusion matrix 总和 != n_total
confusion matrix 实际正例行和 != n_actual_errors
confusion matrix 预测正例列和 != n_predicted
由 TN/FP/FN/TP 计算的 precision/recall/f1 与 metrics 不一致
```

F1 零分母按现有 sklearn `zero_division=0` 口径取 `0.0`。

- [ ] **Step 4: 运行红测**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_app_data_access.py -k "cross or consistency or confusion or transformer_ids" -q
```

修复前至少应复现：`n_total=999`、`automatic_coverage=1.0`、`f1=1.0` 被接受。

- [ ] **Step 5: 提交红测**

```text
test: reproduce cross-artifact dashboard inconsistencies
```

---

## 6. Task 4：实现跨产物语义一致性校验

**Files:**

- Modify: `src/ltverify/data_access.py`
- Test: `tests/unit/test_app_data_access.py`
- Test: `tests/integration/test_streamlit_smoke.py`

**Interfaces:**

- Consumes: 已通过列契约的 truth、ledger、predictions、metrics、confusion matrix。
- Produces: `_validate_dashboard_contracts` 在返回前拒绝内部矛盾的 hash-consistent artifact bundle。

- [ ] **Step 1: 新增 ID 唯一性与集合 helper**

建议纯函数：

```python
def _validate_transformer_identity_contracts(
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    predictions: pd.DataFrame,
) -> None:
    ...
```

要求三表 `transformer_id` 无 null、无重复、集合精确一致。错误消息必须指明文件和差异 ID 数量，不输出整张表。

- [ ] **Step 2: 新增 predictions 与 metrics 绑定 helper**

建议：

```python
def _validate_prediction_metric_consistency(
    predictions: pd.DataFrame,
    metrics: dict[str, object],
) -> None:
    ...
```

使用 `math.isclose(..., rel_tol=0.0, abs_tol=1e-12)` 比较派生比例。不要用 `round` 后比较，也不要自动覆盖 metrics 中的坏值。

- [ ] **Step 3: 新增 truth/ledger/confusion/metrics 绑定 helper**

建议：

```python
def _validate_evaluation_consistency(
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    confusion_matrix: pd.DataFrame,
    metrics: dict[str, object],
) -> None:
    ...
```

矩阵转为 float 后先确认非负且每个值 `value == floor(value)`，再安全转 int。矩阵方向沿用 `evaluation.py`：

```text
[[TN, FP],
 [FN, TP]]
```

派生：

```python
precision = tp / (tp + fp) if tp + fp else 0.0
recall = tp / (tp + fn) if tp + fn else 0.0
f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
```

- [ ] **Step 4: 保持验证顺序**

强制顺序：

```text
manifest regular file
-> manifest JSON/schema/status/declarations
-> verify_manifest_hashes
-> parse artifacts
-> column/nonempty/basic metrics checks
-> cross-artifact semantic checks
-> return RunArtifacts
```

- [ ] **Step 5: 运行受影响测试与全量测试**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_app_data_access.py tests/integration/test_streamlit_smoke.py tests/integration/test_pages.py -q
.venv\Scripts\python.exe -m pytest -q
```

- [ ] **Step 6: 提交实现**

```text
fix: bind dashboard metrics to parsed artifacts
```

---

## 7. Task 5：发布默认合成证据包

**Files:**

- Create: `reports/evidence/README.md`
- Create: `reports/evidence/default_run/manifest.json`
- Create: `reports/evidence/default_run/config.snapshot.yaml`
- Create: `reports/evidence/default_run/truth_topology.csv`
- Create: `reports/evidence/default_run/reported_ledger.csv`
- Create: `reports/evidence/default_run/transformer_measurements.parquet`
- Create: `reports/evidence/default_run/feeder_measurements.parquet`
- Create: `reports/evidence/default_run/observed_measurements.parquet`
- Create: `reports/evidence/default_run/candidate_features.parquet`
- Create: `reports/evidence/default_run/predictions.parquet`
- Create: `reports/evidence/default_run/metrics.json`
- Create: `reports/evidence/default_run/confusion_matrix.csv`
- Create: `reports/evidence/default_run/network_nodes.csv`
- Create: `reports/evidence/default_run/network_edges.csv`
- Create: `reports/evidence/default_run/simulation_validation.csv`
- Create: `tests/unit/test_public_evidence.py`

**Interfaces:**

- Consumes: 已验证本机源目录 `runs/run-20260816T121851-b42381de-ca6652/`。
- Produces: Git 跟踪的、约 4.58 MiB、可由 `verify_manifest_hashes` 验证并可逐字节复现两份规范报告的合成证据包。

- [ ] **Step 1: 先验证源目录，不重新生成**

读取源 `manifest.json`，确认：

```text
status=completed
artifact_schema_version=2
run_id=20260816T121851Z-fb16e1
git_commit=533b64a09570b80533e26724430089bc61c755da
verify_manifest_hashes(...) succeeds
```

确认目录只含 `manifest.json` 加 manifest 声明的 13 个文件。若任何哈希失败，停止并输出 `PUBLIC_READY=NO`，不得从其他相似 run 猜测替代。

- [ ] **Step 2: 逐字节复制到公开证据目录**

只复制上述 14 个文件到：

```text
reports/evidence/default_run/
```

不得复制整个 `runs/`，不得加入临时文件、缓存、Notebook run 或其他实验目录。复制后再次运行 `verify_manifest_hashes`。

- [ ] **Step 3: 编写证据说明**

`reports/evidence/README.md` 必须说明：

- 数据全部为项目生成的合成仿真数据，不含真实电网数据；
- 包大小、run ID、源 commit、Python 与关键包版本；
- `manifest.json` 是 SHA-256 完整性清单，不是数字签名；
- 为什么包被纳入 Git：让全新 clone 能独立验证并复现规范 summary/manifest；
- 默认 30 天重新运行会产生新的 run ID/时间戳，不保证与历史报告逐字节相同。

- [ ] **Step 4: 添加永久公开证据测试**

`tests/unit/test_public_evidence.py` 至少包含：

```python
from pathlib import Path

from ltverify.io import read_json
from ltverify.manifest import verify_manifest_hashes
from ltverify.report import generate_default_summary

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "reports" / "evidence" / "default_run"


def test_public_default_evidence_reproduces_canonical_reports(tmp_path: Path) -> None:
    manifest = read_json(BUNDLE / "manifest.json")
    verify_manifest_hashes(manifest, BUNDLE)
    summary = tmp_path / "default_summary.json"
    manifest_copy = tmp_path / "default_manifest.json"
    generate_default_summary(BUNDLE, summary, manifest_output=manifest_copy)
    assert summary.read_bytes() == (
        ROOT / "reports" / "metrics" / "default_summary.json"
    ).read_bytes()
    assert manifest_copy.read_bytes() == (
        ROOT / "reports" / "metrics" / "default_manifest.json"
    ).read_bytes()
```

再加一个测试确认 bundle 的实际文件集合精确等于 `{"manifest.json", *output_paths}`，无遗漏和无额外文件。

- [ ] **Step 5: 确认所有证据文件被 Git 跟踪**

```powershell
git ls-files -- reports/evidence/default_run
```

预期 14 个文件。不要对这些约 2 MiB 的 Parquet 文件启用 Git LFS；当前规模无需引入额外下载门槛。

- [ ] **Step 6: 运行证据测试**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_public_evidence.py -q
```

- [ ] **Step 7: 提交证据包与测试**

```text
data: publish reproducible synthetic default evidence
```

---

## 8. Task 6：移除主页绝对路径泄露

**Files:**

- Modify: `app/streamlit_app.py`
- Modify: `tests/integration/test_streamlit_smoke.py`

**Interfaces:**

- Consumes: `RunArtifacts.run_dir`。
- Produces: 公开 UI 只显示安全的 run 标识，不显示服务器绝对路径。

- [ ] **Step 1: 添加失败测试**

运行一个有效 fixture，渲染首页，断言页面文本：

```text
包含 run_dir.name
不包含 str(run_dir.resolve())
不包含临时目录父路径
```

- [ ] **Step 2: 修改 caption**

使用安全标识：

```python
run_label = artifacts.run_dir.name
st.caption(f"运行标识: {run_label}；清单 SHA-256 哈希一致性已校验（非数字签名）")
```

不要只对 `D:\` 写特例；Windows、Linux、macOS 都不能显示完整服务器路径。

- [ ] **Step 3: 运行页面测试并提交**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_streamlit_smoke.py -q
```

```text
fix: hide server paths from public dashboard
```

---

## 9. Task 7：修正 README 与公开审计说明

**Files:**

- Modify: `README.md`
- Modify: `docs/audit-summary.md`
- Modify: `docs/design.md`（仅在证据设计需要同步时）
- Modify: `tests/unit/test_documentation.py`

**Interfaces:**

- Consumes: `reports/evidence/default_run/` 与现有 CI。
- Produces: 全新 clone 可复制执行的 Windows/Linux/macOS 命令和可点击文档导航。

- [ ] **Step 1: 使用明确解释器**

Windows 命令统一使用：

```text
.venv/Scripts/python.exe -m ltverify ...
.venv/Scripts/python.exe -m streamlit ...
```

Linux/macOS 命令统一使用：

```text
.venv/bin/python -m ltverify ...
.venv/bin/python -m streamlit ...
```

或分别提供激活命令，但不得在未说明激活的情况下从 `.venv` 安装后直接使用裸 `python`。

- [ ] **Step 2: 增加公开证据包复现命令**

Windows 示例写入系统临时目录，不能覆盖仓库权威文件：

```powershell
$auditOut = Join-Path $env:TEMP "ltverify-public-evidence"
New-Item -ItemType Directory -Path $auditOut -Force | Out-Null
.venv/Scripts/python.exe -m ltverify report `
  --run-dir reports/evidence/default_run `
  --output (Join-Path $auditOut "default_summary.json") `
  --manifest-output (Join-Path $auditOut "default_manifest.json")
```

然后说明与 `reports/metrics/default_summary.json`、`reports/metrics/default_manifest.json` 比较应逐字节一致。Linux/macOS 给出等价的临时目录命令。

- [ ] **Step 3: 区分两种复现语义**

README 明确写：

```text
公开证据复现：验证历史权威 run 并逐字节生成规范报告。
重新运行仿真：从 configs/default.yaml 生成新的 run，用于验证算法流程；run_id、时间戳与 manifest commit 会不同。
```

- [ ] **Step 4: 改成真实 Markdown 链接**

至少使用：

```markdown
[AI 使用说明](AI_USAGE.md)
[公开审计摘要](docs/audit-summary.md)
[设计说明](docs/design.md)
[方法论](docs/methodology.md)
[面试指南](docs/interview-guide.md)
[数据字典](data/README.md)
```

- [ ] **Step 5: 更新审计摘要**

增加“跨产物语义绑定”和“公开默认证据包”两项信任边界，并说明：

- loader 不只校验 hash/字段，还校验 displayed metrics 与 parsed artifacts 的一致性；
- 默认证据包是合成数据；
- checksum 仍不是签名；
- 测试数量不要硬编码，覆盖率只写最终 fresh 值或写 `≥90%`。

- [ ] **Step 6: 扩展文档测试**

`tests/unit/test_documentation.py` 检查：

```text
README 含 reports/evidence/default_run
README 的 report 命令含 --manifest-output
README 含上述 Markdown 链接目标
链接目标存在
公开 Markdown/Notebook 不含 D:\电力 或 C:\Users\
```

- [ ] **Step 7: 提交文档**

```text
docs: make public reproduction self-contained
```

---

## 10. Task 8：删除本交接文档并保持公开树干净

**Files:**

- Delete: `docs/handoff/2026-08-17-deepseek-public-release-final-audit-remediation-prompt.md`

**Interfaces:**

- Consumes: 已完成的代码、证据与公开文档提交。
- Produces: 当前公开工作树不含内部 Agent handoff；本文仍可从 Git 历史恢复。

- [ ] **Step 1: 完成全部修改后再删除本文**

确认本文已被完整执行并且最终验证记录已另行保存在终端回报中，再通过普通 Git 删除本文。不要清理历史对象。

- [ ] **Step 2: 验证历史可恢复**

```powershell
git log --all --oneline -- docs/handoff/2026-08-17-deepseek-public-release-final-audit-remediation-prompt.md
```

- [ ] **Step 3: 提交公开树清理**

```text
docs: remove final internal release handoff
```

---

## 11. 分阶段提交纪律

每个任务必须遵循：

```text
写失败测试
-> 运行并记录真实失败
-> 最小实现
-> 运行目标测试
-> 运行受影响集成测试
-> git diff --check
-> 只暂存当前任务文件
-> git diff --cached --name-status
-> git diff --cached --stat
-> 提交
```

推荐提交序列：

```text
test: reproduce displayed metric contract gaps
fix: validate every displayed dashboard metric
test: reproduce cross-artifact dashboard inconsistencies
fix: bind dashboard metrics to parsed artifacts
data: publish reproducible synthetic default evidence
fix: hide server paths from public dashboard
docs: make public reproduction self-contained
docs: remove final internal release handoff
```

不要再把测试、二进制证据、逻辑修复、README 和 handoff 删除混入同一提交。

---

## 12. 最终本地发布门禁

### 12.1 代码质量

```powershell
.venv\Scripts\python.exe -m ruff format --check src app tests scripts
.venv\Scripts\python.exe -m ruff check src app tests scripts
.venv\Scripts\python.exe -m pytest --cov=ltverify --cov-report=term-missing --cov-fail-under=90 -q
git diff --check
```

### 12.2 原始反例与新反例

必须逐项报告结果：

```text
output_paths=[[]] -> loader ArtifactLoadError，discovery 跳过
duplicate output path -> discovery 选择旧的合法 run
f1=999 -> rejected
precision=999 -> rejected
recall=-1 -> rejected
top2_correction_rate=999 -> rejected
scored_coverage=999 -> rejected
insufficient_data_rate=-1 -> rejected
n_total=999 与 predictions 行数不符 -> rejected
n_predicted=0 但 automatic_coverage=1 -> rejected
metrics f1=1 但 confusion matrix F1=0 -> rejected
页面无 traceback，不显示上述非法数字
```

### 12.3 公开证据包

```text
reports/evidence/default_run 含 14 个 tracked 文件
verify_manifest_hashes -> success
由公开 bundle 生成的 summary 与 canonical summary 逐字节一致
由公开 bundle 生成的 manifest copy 与 canonical manifest 逐字节一致
bundle 总大小约 4.58 MiB，无额外 run/cache 文件
```

### 12.4 原有实验证据

```text
verify_experiment_manifest(... require_source_configs=True) -> strict
load_robustness_artifacts(...) -> strict_verified
robustness summary rows -> 130
git cat-file -t 533b64a09570b80533e26724430089bc61c755da -> commit
git cat-file -t 59a623e09b4ea470a149a93d9e8efa51d2008fe7 -> commit
```

### 12.5 Notebook 与 wheel

三个 Notebook 必须执行到临时目录，均成功、无 error output、无本机绝对路径。wheel 输出到系统临时目录；如在仓库生成 ignored `build/`，确认绝对路径后删除，不得残留。

### 12.6 CI 与公开树

```text
.github/workflows/ci.yml 存在
本地等价命令全部通过
README 本地链接全部存在
README 使用明确 venv 解释器
README 证据命令含 --manifest-output
主页不显示 artifacts.run_dir.resolve()
当前树无 docs/handoff
当前树无 docs/superpowers/plans 或 specs
无 tracked .env、私钥、build、dist、runs、.venv
git status --short 无输出
remote 仍未配置
未 push
```

---

## 13. 最终回报格式

DeepSeek 最终必须按以下结构回报，不得只说“已完成”：

### A. 审查基线

- 起止 commit；
- 本轮新增提交 hash/subject；
- 明确未重写历史、未配置 remote、未 push。

### B. 指标契约修复

- 完整验证字段列表；
- applicability 与 null 规则；
- ID、predictions、coverage、confusion matrix、precision/recall/F1 的绑定关系；
- 11 个指定反例的实际输出。

### C. 公开证据

- bundle 文件数、字节数、最大文件；
- 源 run ID/commit；
- manifest 验证结果；
- 两个 byte-match 结果；
- 明确没有重跑 30 天或 130 案例。

### D. 公开展示

- 主页路径隐藏测试；
- README venv 命令、证据命令与 Markdown 链接；
- AI_USAGE/audit/design 更新；
- 截图是否生成；无真实截图能力时明确留给用户，不伪造。

### E. 最终门禁

- Ruff format/check；
- pytest 通过数、失败数、coverage；
- wheel；
- 三个 Notebook；
- strict / strict_verified / 130；
- secret/path scan；
- 最终 `git status --short`。

### F. 用户仍需亲自完成

- 配置 verified Git 身份；
- 决定 LICENSE 署名；
- 创建 GitHub repository 和 remote；
- 首次 push；
- 确认 Python 3.11/3.12 GitHub Actions 真实通过；
- CI 成功后添加真实 badge；
- 可选真实 Streamlit 截图；
- 决定是否创建 `v0.1.0` tag/release。

### G. 发布判定

只有所有本地强制门禁通过、当前树无内部 handoff、剩余事项仅为用户身份/远端/首次 CI/可选截图时，输出：

```text
PUBLIC_READY=YES
```

否则输出：

```text
PUBLIC_READY=NO
```

并列出仍阻塞的具体文件、命令、异常和复现数据。

---

## 14. 完成定义

只有以下全部满足，才可声明本轮完成：

- 所有模型评估页展示指标均有 current-schema 类型、范围、null/applicability 契约；
- truth、ledger、predictions、metrics、confusion matrix 在 loader 返回前完成语义绑定；
- 五个非法展示比例和三个跨产物矛盾反例全部被拒绝；
- 公开 clone 自带约 4.58 MiB 默认合成证据包，可验证 manifest 并逐字节复现两份规范报告；
- README 明确区分历史证据复现与新仿真运行，命令使用正确 venv 解释器和 `--manifest-output`；
- 主页不显示服务器绝对路径；
- Ruff、全测、coverage、wheel、三个 Notebook 全部 fresh 通过；
- 默认 report byte match、experiment strict、robustness strict_verified、130 行保持不变；
- 默认失败边界和研究限制未被篡改；
- 当前树不含本文或其他内部 handoff；
- Git 历史未改写，两个 evidence commit 仍存在；
- Agent 未猜测用户身份、配置远端或 push；
- 最终报告给出有证据支持的 `PUBLIC_READY=YES/NO`。
