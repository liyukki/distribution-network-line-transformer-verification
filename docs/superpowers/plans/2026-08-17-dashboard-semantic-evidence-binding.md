# Dashboard Semantic Evidence Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every public dashboard evaluation value derive from the hash-verified truth, ledger, predictions, candidate scores, and configuration snapshot, so synchronized edits to a metric and its SHA-256 entry cannot create a false but accepted display.

**Architecture:** Keep `load_run_artifacts` as the single trusted disk entry point and preserve its hash-before-parse order. After the hash chain passes, validate identity fields, parse the verified configuration snapshot, independently recompute evaluation results with the existing `evaluate_predictions` function, and compare every public evaluation field to `metrics.json` with strict null/type semantics and `1e-12` numeric tolerance. The evaluation page must derive labels from ledger plus truth rather than treating a duplicated field in predictions as authoritative.

**Tech Stack:** Python 3.11/3.12, pandas, NumPy, scikit-learn, Pydantic, PyYAML, pytest, Streamlit, Ruff, GitHub Actions.

## Global Constraints

- Implementation baseline is commit `f181ae2`; first verify it is an ancestor with `git merge-base --is-ancestor f181ae2 HEAD`.
- Do not regenerate or edit files under `reports/evidence/default_run/` or `reports/metrics/`; the current canonical bytes must remain unchanged.
- Preserve the trust order: regular manifest file, JSON object, current schema, completed status, required declarations, SHA-256 verification, then parsing and semantic validation.
- Any malformed user-controlled artifact must raise `ArtifactLoadError`; the Streamlit entry point must not leak raw `TypeError`, `KeyError`, `IndexError`, YAML, Pydantic, pandas, or scikit-learn exceptions.
- Keep zero-error semantics: when `n_actual_errors == 0`, an applicable Top-k field has count `0`, rate `null`, and coverage `null`.
- Keep Top-k applicability semantics: Top-k is applicable only when the verified candidate-feeder count is strictly greater than `k`.
- Numeric equality for derived metrics uses `math.isclose(rel_tol=0.0, abs_tol=1e-12)` after the existing field-specific type checks; booleans, strings, dictionaries, and `null` use exact type-aware equality.
- Do not add a new metric implementation. Reuse `ltverify.evaluation.evaluate_predictions` so generation and verification share one definition.
- Do not weaken, delete, or mark existing tests as skipped. The finished suite must pass on a clean worktree with at least 90% coverage.
- Keep commits narrow and do not commit `.venv`, caches, notebook execution outputs, `build/`, `dist/`, or temporary audit files.

---

## Audit Verdict at `f181ae2`

`PUBLIC_READY=NO`

The conventional release gates pass, but four synchronized-artifact attacks are accepted after the modified file's SHA-256 value is correctly updated in `manifest.json`:

1. `predictions.parquet.reported_feeder_id` can disagree with `reported_ledger.csv`; the loader accepts it, the diagnosis page displays it, and the evaluation page uses it to create PR-curve labels.
2. `metrics.pr_auc` and `metrics.pr_auc_scored` can both be replaced by `1.0`; the loader accepts and displays them although the canonical value is `0.3778787878787879`.
3. `metrics.top1_correction_rate` can be changed from `0.2` to the plausible but false value `0.4` while count and coverage stay unchanged; the loader accepts it and the homepage displays it.
4. `metrics.candidate_feeder_count` can be changed from `3` to `4` and the Top-3 metadata made internally consistent; the loader accepts it although `candidate_features.parquet` still contains exactly three unique feeders.

These are semantic-binding failures, not checksum failures. The repository correctly states that SHA-256 is not a digital signature, but the loader and audit summary also claim cross-artifact semantic validation. Public display must therefore reject values that disagree with the already verified artifacts.

Current passing evidence, to be repeated after implementation:

- `397 passed in 344.21s`; total coverage `91.33%`.
- Ruff format and lint checks pass for 58 files.
- The three teaching notebooks execute successfully.
- One wheel builds successfully.
- `default_summary.json` and `default_manifest.json` reproduce byte-for-byte.
- Experiment manifest returns `strict`; robustness loader returns `strict_verified`; robustness summary has 130 rows.
- Local Markdown links and tracked secret-pattern scans pass.

## File Structure

- Modify `src/ltverify/data_access.py`: validate duplicated identity fields, parse the verified config snapshot, recompute evaluation fields, and compare them to metrics.
- Modify `app/pages/4_evaluation.py`: calculate PR-curve labels from ledger plus truth and join only the anomaly score from predictions.
- Modify `tests/unit/test_app_data_access.py`: add synchronized-hash adversarial tests and valid-run regression tests.
- Modify `tests/integration/test_pages.py`: prove the evaluation page uses ledger/truth labels and converts loader failures to a visible Streamlit error.
- Modify `docs/audit-summary.md`: state the exact evaluation fields covered by cross-artifact recomputation after the code passes.
- Delete `docs/superpowers/plans/2026-08-17-dashboard-semantic-evidence-binding.md` in the final cleanup commit so the public tree contains product documentation rather than an agent handoff.

---

### Task 1: Add Red Tests for the Four Accepted Forgeries

**Files:**
- Modify: `tests/unit/test_app_data_access.py`

**Interfaces:**
- Consumes: existing `_fixture_run(tmp_path)` and `_update_manifest_hash(run_dir, name)` helpers.
- Produces: four tests that fail at `f181ae2` because `load_run_artifacts` currently accepts each forged artifact.

- [ ] **Step 1: Add pandas and a metrics rewrite helper**

Add `import pandas as pd` with the third-party imports. Add this helper immediately after `_update_manifest_hash`:

```python
def _write_metrics_and_rehash(run_dir: Path, metrics: dict[str, object]) -> None:
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _update_manifest_hash(run_dir, "metrics.json")
```

- [ ] **Step 2: Add the prediction-versus-ledger identity test**

```python
def test_loader_rejects_prediction_reported_feeder_drift(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    predictions_path = run_dir / "predictions.parquet"
    predictions = pd.read_parquet(predictions_path)
    ledger = pd.read_csv(run_dir / "reported_ledger.csv").set_index("transformer_id")
    transformer_id = str(predictions.iloc[0]["transformer_id"])
    reported = str(ledger.loc[transformer_id, "reported_feeder_id"])
    replacement = "F99" if reported != "F99" else "F98"
    predictions.loc[
        predictions["transformer_id"] == transformer_id,
        "reported_feeder_id",
    ] = replacement
    predictions.to_parquet(predictions_path, index=False)
    _update_manifest_hash(run_dir, "predictions.parquet")

    with pytest.raises(ArtifactLoadError, match="reported_feeder_id|ledger|台账"):
        load_run_artifacts(run_dir)
```

- [ ] **Step 3: Add forged PR-AUC tests**

```python
@pytest.mark.parametrize("field", ["pr_auc", "pr_auc_scored"])
def test_loader_rejects_forged_pr_auc_with_valid_hash(
    tmp_path: Path,
    field: str,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics[f"{field}_applicable"] is True
    original = float(metrics[field])
    metrics[field] = 0.0 if original != 0.0 else 1.0
    _write_metrics_and_rehash(run_dir, metrics)

    with pytest.raises(ArtifactLoadError, match=field):
        load_run_artifacts(run_dir)
```

- [ ] **Step 4: Add the plausible forged Top-1 test**

```python
def test_loader_rejects_plausible_forged_top1_rate(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["top1_evaluated_count"] > 0
    original = float(metrics["top1_correction_rate"])
    metrics["top1_correction_rate"] = 0.0 if original != 0.0 else 1.0
    _write_metrics_and_rehash(run_dir, metrics)

    with pytest.raises(ArtifactLoadError, match="top1_correction_rate|top1"):
        load_run_artifacts(run_dir)
```

- [ ] **Step 5: Add the forged candidate-count test**

```python
def test_loader_rejects_candidate_count_not_bound_to_features(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["candidate_feeder_count"] == 3
    metrics["candidate_feeder_count"] = 4
    metrics["topk_applicable"] = {"top1": True, "top2": True, "top3": True}
    metrics["top3_evaluated_count"] = 0
    metrics["top3_evaluation_coverage"] = 0.0
    metrics["top3_correction_rate"] = None
    _write_metrics_and_rehash(run_dir, metrics)

    with pytest.raises(ArtifactLoadError, match="candidate_feeder_count|candidate"):
        load_run_artifacts(run_dir)
```

- [ ] **Step 6: Run the four tests and verify the intended failures**

Run:

```powershell
.venv/Scripts/python.exe -m pytest `
  tests/unit/test_app_data_access.py::test_loader_rejects_prediction_reported_feeder_drift `
  tests/unit/test_app_data_access.py::test_loader_rejects_forged_pr_auc_with_valid_hash `
  tests/unit/test_app_data_access.py::test_loader_rejects_plausible_forged_top1_rate `
  tests/unit/test_app_data_access.py::test_loader_rejects_candidate_count_not_bound_to_features -q
```

Expected: five failed parameterized cases because no `ArtifactLoadError` is raised. A parse failure, hash failure, or raw exception is not the expected red state.

- [ ] **Step 7: Commit only the red tests**

```powershell
git add tests/unit/test_app_data_access.py
git diff --cached --check
git commit -m "test: expose dashboard semantic metric forgeries"
```

---

### Task 2: Bind Duplicated Identity Fields Before Evaluation

**Files:**
- Modify: `src/ltverify/data_access.py`
- Test: `tests/unit/test_app_data_access.py`

**Interfaces:**
- Consumes: `_require_nonempty_string_series(frame, column, label)`.
- Produces: `_validate_candidate_identity_contracts(candidate_features, predictions)` and stricter `_validate_transformer_identity_contracts(truth, ledger, predictions)`.

- [ ] **Step 1: Extend transformer identity validation**

After the existing transformer-ID set check, align ledger and predictions by `transformer_id` and compare `reported_feeder_id` exactly:

```python
ledger_reported = ledger.set_index("transformer_id")["reported_feeder_id"].sort_index()
prediction_reported = (
    predictions.set_index("transformer_id")["reported_feeder_id"].sort_index()
)
if not prediction_reported.equals(ledger_reported):
    raise ArtifactLoadError(
        "predictions.reported_feeder_id 与 reported_ledger.csv 台账不一致"
    )
```

Validate `predictions.reported_feeder_id` with `_require_nonempty_string_series` before the comparison.

- [ ] **Step 2: Add candidate identity contracts**

Add a helper with this exact behavior:

```python
def _validate_candidate_identity_contracts(
    candidate_features: pd.DataFrame,
    predictions: pd.DataFrame,
) -> None:
    for column in ("transformer_id", "reported_feeder_id", "candidate_feeder_id"):
        _require_nonempty_string_series(
            candidate_features,
            column,
            "candidate_features.parquet",
        )
    candidate_ids = set(candidate_features["transformer_id"])
    prediction_ids = set(predictions["transformer_id"])
    if candidate_ids != prediction_ids:
        raise ArtifactLoadError(
            "candidate_features/predictions 的 transformer_id 集合不一致"
        )
    duplicate_key = candidate_features.duplicated(
        subset=["transformer_id", "candidate_feeder_id"]
    )
    if duplicate_key.any():
        raise ArtifactLoadError(
            "candidate_features 的 transformer_id/candidate_feeder_id 组合存在重复"
        )
```

Also compare `candidate_features.reported_feeder_id` to the matching `predictions.reported_feeder_id` for every row:

```python
candidate_reported = candidate_features[
    ["transformer_id", "reported_feeder_id"]
].merge(
    predictions[["transformer_id", "reported_feeder_id"]],
    on="transformer_id",
    how="left",
    suffixes=("_candidate", "_prediction"),
    validate="many_to_one",
)
if not candidate_reported["reported_feeder_id_candidate"].equals(
    candidate_reported["reported_feeder_id_prediction"]
):
    raise ArtifactLoadError(
        "candidate_features.reported_feeder_id 与 predictions 不一致"
    )
```

- [ ] **Step 3: Require columns consumed by the dashboard and evaluator**

Define:

```python
DASHBOARD_FEATURE_COLUMNS = frozenset(FEATURE_COLUMNS) | {
    "enhanced_score",
    "available_feature_weight",
}
```

Use `DASHBOARD_FEATURE_COLUMNS` instead of `FEATURE_COLUMNS` in `_validate_dashboard_contracts`. This prevents a later raw `KeyError` and documents the true read contract.

- [ ] **Step 4: Call the candidate helper before any set, unique, sort, merge, or evaluator operation**

The order inside `_validate_dashboard_contracts` must be:

```python
_validate_transformer_identity_contracts(truth, ledger, predictions)
_validate_candidate_identity_contracts(candidate_features, predictions)
_validate_prediction_metric_consistency(predictions, metrics)
```

- [ ] **Step 5: Add one domain-error regression for a list-valued candidate feeder**

```python
def test_loader_wraps_list_candidate_feeder_as_domain_error(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    path = run_dir / "candidate_features.parquet"
    frame = pd.read_parquet(path)
    frame["candidate_feeder_id"] = [
        [str(value)] for value in frame["candidate_feeder_id"]
    ]
    frame.to_parquet(path, index=False)
    _update_manifest_hash(run_dir, "candidate_features.parquet")

    with pytest.raises(ArtifactLoadError, match="candidate_feeder_id"):
        load_run_artifacts(run_dir)
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_app_data_access.py -q
```

Expected: the identity-drift and list-valued candidate tests pass. The three metric-forgery tests remain red until Task 3.

- [ ] **Step 7: Commit identity binding**

```powershell
git add src/ltverify/data_access.py tests/unit/test_app_data_access.py
git diff --cached --check
git commit -m "fix: bind dashboard identity fields across artifacts"
```

---

### Task 3: Recompute and Compare Every Public Evaluation Metric

**Files:**
- Modify: `src/ltverify/data_access.py`
- Test: `tests/unit/test_app_data_access.py`

**Interfaces:**
- Consumes: `load_config(path: Path) -> AppConfig` and `evaluate_predictions(predictions, truth, ledger, candidate_scores, evidence_weight_threshold) -> EvaluationResult`.
- Produces: `_validate_recomputed_evaluation` returning `None`, called after all structural and identity contracts pass.

- [ ] **Step 1: Add imports and the complete comparison key set**

Import `ValidationError` from `pydantic`, `YAMLError` from `yaml`, `load_config` from `ltverify.config`, and `evaluate_predictions` from `ltverify.evaluation`.

Add this exact key set near the dashboard constants:

```python
EVALUATION_METRIC_KEYS = (
    "precision",
    "recall",
    "f1",
    "pr_auc",
    "pr_auc_applicable",
    "pr_auc_unavailable_reason",
    "pr_auc_scored",
    "pr_auc_scored_applicable",
    "pr_auc_scored_unavailable_reason",
    "top1_correction_rate",
    "top1_evaluated_count",
    "top1_evaluation_coverage",
    "top2_correction_rate",
    "top2_evaluated_count",
    "top2_evaluation_coverage",
    "top3_correction_rate",
    "top3_evaluated_count",
    "top3_evaluation_coverage",
    "topk_applicable",
    "excluded_candidate_count",
    "candidate_feeder_count",
    "n_total",
    "n_actual_errors",
    "n_actual_correct",
    "n_predicted",
    "automatic_coverage",
    "insufficient_data_rate",
    "scored_coverage",
)
```

- [ ] **Step 2: Load the verified configuration snapshot after hash verification**

Immediately after `verify_manifest_hashes` succeeds, parse `config.snapshot.yaml`:

```python
try:
    config = load_config(run_dir / "config.snapshot.yaml")
except (OSError, UnicodeError, YAMLError, ValidationError, ValueError, TypeError) as exc:
    raise ArtifactLoadError(f"无法解析 config.snapshot.yaml: {exc}") from exc
```

Do not move this read before `verify_manifest_hashes`. Pass `config.scoring.evidence_weight_threshold` into `_validate_dashboard_contracts` as a keyword-only float.

- [ ] **Step 3: Add a strict recursive metric comparator**

Implement type-aware comparison so `True` never equals `1`, `null` never equals `0`, dictionaries require identical keys, and floating values use the global tolerance:

```python
def _metric_values_equal(actual: object, expected: object) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is bool and type(expected) is bool and actual == expected
    if isinstance(actual, dict) or isinstance(expected, dict):
        if not isinstance(actual, dict) or not isinstance(expected, dict):
            return False
        if set(actual) != set(expected):
            return False
        return all(
            _metric_values_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(actual, Real) or isinstance(expected, Real):
        if not isinstance(actual, Real) or not isinstance(expected, Real):
            return False
        return math.isclose(
            float(actual),
            float(expected),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    return type(actual) is type(expected) and actual == expected
```

- [ ] **Step 4: Recompute evaluation and reject every disagreement**

Add:

```python
def _validate_recomputed_evaluation(
    *,
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    predictions: pd.DataFrame,
    candidate_features: pd.DataFrame,
    metrics: dict[str, object],
    evidence_weight_threshold: float,
) -> None:
    try:
        recomputed = evaluate_predictions(
            predictions=predictions,
            truth=truth,
            ledger=ledger,
            candidate_scores=candidate_features,
            evidence_weight_threshold=evidence_weight_threshold,
        ).metrics
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise ArtifactLoadError(f"无法从权威产物重算评价指标: {exc}") from exc
    for key in EVALUATION_METRIC_KEYS:
        if key not in metrics:
            raise ArtifactLoadError(f"metrics 缺少必填字段: {key}")
        if not _metric_values_equal(metrics[key], recomputed[key]):
            raise ArtifactLoadError(
                f"metrics.{key} 与 truth/ledger/predictions/candidate_features 重算结果不一致"
            )
```

Call this helper after identity contracts and the existing shape/type checks. Keep the existing confusion-matrix and metric checks as early, targeted error messages; the recomputation is the final semantic gate.

- [ ] **Step 5: Add valid edge-case regressions**

Extend the existing zero-error test with the single-class applicability assertions:

```python
assert metrics["pr_auc"] is None
assert metrics["pr_auc_applicable"] is False
assert metrics["pr_auc_unavailable_reason"] == "single_class_all_negative"
assert metrics["pr_auc_scored"] is None
assert metrics["pr_auc_scored_applicable"] is False
assert isinstance(metrics["pr_auc_scored_unavailable_reason"], str)
```

Add a hash-order regression that does not update either manifest hash:

```python
def test_loader_rejects_tampered_config_snapshot_before_parse(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    config_path = run_dir / "config.snapshot.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "\nrandom_seed: 99\n",
        encoding="utf-8",
    )

    with pytest.raises(ArtifactLoadError, match="哈希一致性校验失败"):
        load_run_artifacts(run_dir)
```

- [ ] **Step 6: Run all data-access and evaluation tests**

Run:

```powershell
.venv/Scripts/python.exe -m pytest `
  tests/unit/test_app_data_access.py `
  tests/unit/test_evaluation.py -q
```

Expected: all tests pass, including all five parameterized forgery cases from Task 1.

- [ ] **Step 7: Commit full semantic recomputation**

```powershell
git add src/ltverify/data_access.py tests/unit/test_app_data_access.py
git diff --cached --check
git commit -m "fix: recompute dashboard evaluation evidence"
```

---

### Task 4: Make the PR Curve Use the Authoritative Ledger

**Files:**
- Modify: `app/pages/4_evaluation.py`
- Modify: `tests/integration/test_pages.py`

**Interfaces:**
- Consumes: `artifacts.ledger`, `artifacts.truth`, and `artifacts.predictions` after trusted loading.
- Produces: PR labels based on `reported_ledger.csv` plus `truth_topology.csv`, with anomaly scores joined by transformer ID.

- [ ] **Step 1: Add an integration test with deliberately divergent in-memory prediction labels**

Add this test. It changes only the in-memory predictions after trusted loading, which models a stale session or direct-page invocation:

```python
def test_evaluation_page_uses_ledger_truth_labels(
    run_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = load_run_artifacts(run_dir)
    predictions = artifacts.predictions.copy()
    predictions["reported_feeder_id"] = "F99"
    target = RunArtifacts(
        run_dir=artifacts.run_dir,
        manifest=dict(artifacts.manifest),
        truth=artifacts.truth,
        ledger=artifacts.ledger,
        observed_measurements=artifacts.observed_measurements,
        feeder_measurements=artifacts.feeder_measurements,
        candidate_features=artifacts.candidate_features,
        predictions=predictions,
        metrics=dict(artifacts.metrics),
        confusion_matrix=artifacts.confusion_matrix,
        network_nodes=artifacts.network_nodes,
        network_edges=artifacts.network_edges,
    )
    expected = artifacts.ledger[["transformer_id", "reported_feeder_id"]].merge(
        artifacts.truth[["transformer_id", "physical_feeder_id"]],
        on="transformer_id",
        how="inner",
        validate="one_to_one",
    )
    expected_labels = (
        expected["reported_feeder_id"] != expected["physical_feeder_id"]
    ).astype(int).tolist()
    captured: dict[str, object] = {}

    def capture_curve(
        y_true: object,
        scores: object,
    ) -> tuple[list[float], list[float], list[float]]:
        captured["y_true"] = list(y_true)
        captured["scores"] = list(scores)
        return [1.0, 0.5], [0.0, 1.0], [0.5]

    monkeypatch.setattr(
        "sklearn.metrics.precision_recall_curve",
        capture_curve,
    )
    app_test = AppTest.from_file(
        ROOT / "app" / "pages" / "4_evaluation.py",
        default_timeout=120,
    )
    app_test.session_state["artifacts"] = target
    app_test.session_state["demo_mode"] = True
    app_test.run()

    assert len(app_test.exception) == 0
    assert captured["y_true"] == expected_labels
```

- [ ] **Step 2: Replace the prediction-owned label calculation**

Replace the current prediction-to-truth join block with:

```python
labels = artifacts.ledger[["transformer_id", "reported_feeder_id"]].merge(
    artifacts.truth[["transformer_id", "physical_feeder_id"]],
    on="transformer_id",
    how="inner",
    validate="one_to_one",
)
merged = labels.merge(
    artifacts.predictions[["transformer_id", "anomaly_score"]],
    on="transformer_id",
    how="inner",
    validate="one_to_one",
)
y_true = (merged["reported_feeder_id"] != merged["physical_feeder_id"]).astype(int)
scores = merged["anomaly_score"].fillna(0.0).to_numpy(dtype=float)
```

Replace the old combined-column predicate with ownership-aware checks:

```python
pr_supported = (
    schema_state == "current"
    and {"transformer_id", "anomaly_score"} <= set(artifacts.predictions.columns)
    and {"transformer_id", "reported_feeder_id"} <= set(artifacts.ledger.columns)
    and {"transformer_id", "physical_feeder_id"} <= set(artifacts.truth.columns)
)
```

- [ ] **Step 3: Run page tests**

Run:

```powershell
.venv/Scripts/python.exe -m pytest `
  tests/integration/test_pages.py `
  tests/integration/test_streamlit_smoke.py -q
```

Expected: all tests pass and the captured labels come from ledger plus truth.

- [ ] **Step 4: Commit the page defense**

```powershell
git add app/pages/4_evaluation.py tests/integration/test_pages.py
git diff --cached --check
git commit -m "fix: derive evaluation labels from authoritative ledger"
```

---

### Task 5: Align Public Claims and Run the Complete Release Gate

**Files:**
- Modify: `docs/audit-summary.md`
- Delete at final step: `docs/superpowers/plans/2026-08-17-dashboard-semantic-evidence-binding.md`

**Interfaces:**
- Consumes: the completed semantic loader and page tests.
- Produces: accurate public documentation, clean current tree, and an evidence-backed `PUBLIC_READY` result.

- [ ] **Step 1: Tighten the audit-summary claim**

Replace the current cross-artifact bullet with wording that names the new coverage:

```markdown
- **Cross-artifact semantic binding**：loader 在返回前校验 truth/ledger/predictions/candidate_features/metrics/confusion matrix 的 ID 与重复台账字段，并使用哈希闭环内的 config.snapshot.yaml 重算 PR-AUC、Top-k、coverage、计数及 Precision/Recall/F1；展示指标与重算结果不一致时拒绝加载。
```

Do not claim digital-signature protection or real-grid external validity.

- [ ] **Step 2: Run formatting and static checks**

```powershell
.venv/Scripts/python.exe -m ruff format src app tests scripts
.venv/Scripts/python.exe -m ruff format --check src app tests scripts
.venv/Scripts/python.exe -m ruff check src app tests scripts
git diff --check
```

Expected: 58 or more files already formatted, all checks pass, and `git diff --check` prints nothing.

- [ ] **Step 3: Run the full test and coverage gate**

```powershell
.venv/Scripts/python.exe -m pytest `
  --cov=ltverify `
  --cov-report=term-missing `
  --cov-fail-under=90 -q
```

Expected: every collected test passes and total coverage is at least 90%. Record the exact pass count and coverage percentage in the handoff response.

- [ ] **Step 4: Reproduce the public evidence without touching canonical files**

```powershell
$auditOut = Join-Path $env:TEMP ("ltverify-public-evidence-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $auditOut | Out-Null
.venv/Scripts/python.exe -m ltverify report `
  --run-dir reports/evidence/default_run `
  --output (Join-Path $auditOut "default_summary.json") `
  --manifest-output (Join-Path $auditOut "default_manifest.json")
if ((Get-FileHash (Join-Path $auditOut "default_summary.json")).Hash -ne `
    (Get-FileHash reports/metrics/default_summary.json).Hash) { throw "summary bytes differ" }
if ((Get-FileHash (Join-Path $auditOut "default_manifest.json")).Hash -ne `
    (Get-FileHash reports/metrics/default_manifest.json).Hash) { throw "manifest bytes differ" }
$resolvedAuditOut = [IO.Path]::GetFullPath($auditOut)
$resolvedTemp = [IO.Path]::GetFullPath($env:TEMP)
if (-not $resolvedAuditOut.StartsWith($resolvedTemp, [StringComparison]::OrdinalIgnoreCase)) {
    throw "audit output escaped the system temporary directory"
}
[IO.Directory]::Delete($resolvedAuditOut, $true)
```

Expected: both hashes match and only the resolved `$auditOut` directory is removed.

- [ ] **Step 5: Recheck strict robustness evidence**

Run:

```powershell
@'
import json
from pathlib import Path

import pandas as pd

from ltverify.experiments import verify_experiment_manifest
from ltverify.robustness_loader import load_robustness_artifacts

root = Path(".").resolve()
artifact_dir = root / "reports" / "metrics"
manifest = json.loads(
    (artifact_dir / "robustness_experiment_manifest.json").read_text(
        encoding="utf-8"
    )
)
manifest_state = verify_experiment_manifest(
    manifest,
    artifact_dir,
    experiment_config_path=root / "configs" / "robustness.yaml",
    base_config_path=root / "configs" / "default.yaml",
    require_source_configs=True,
)
loaded = load_robustness_artifacts(
    artifact_dir / "robustness_aggregates.csv",
    artifact_dir / "robustness_summary.csv",
    experiment_config_path=root / "configs" / "robustness.yaml",
    base_config_path=root / "configs" / "default.yaml",
)
rows = len(pd.read_csv(artifact_dir / "robustness_summary.csv"))
print(f"EXPERIMENT_MANIFEST={manifest_state}")
print(f"ROBUSTNESS_LOADER={loaded.verification_state}")
print(f"ROBUSTNESS_ROWS={rows}")
'@ | .venv/Scripts/python.exe -
```

Required output:

```text
EXPERIMENT_MANIFEST=strict
ROBUSTNESS_LOADER=strict_verified
ROBUSTNESS_ROWS=130
```

- [ ] **Step 6: Execute all notebooks and build one wheel into temporary directories**

Run:

```powershell
$notebookOut = Join-Path $env:TEMP ("ltverify-notebooks-" + [guid]::NewGuid().ToString("N"))
$wheelOut = Join-Path $env:TEMP ("ltverify-wheel-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $notebookOut, $wheelOut | Out-Null
Get-ChildItem notebooks -Filter "*.ipynb" | Sort-Object Name | ForEach-Object {
    .venv/Scripts/python.exe -m jupyter nbconvert `
      --to notebook `
      --execute $_.FullName `
      --output $_.Name `
      --output-dir $notebookOut `
      --ExecutePreprocessor.timeout=600
    if ($LASTEXITCODE -ne 0) { throw "notebook failed: $($_.Name)" }
}
.venv/Scripts/python.exe -m pip wheel . --no-deps --wheel-dir $wheelOut
if ($LASTEXITCODE -ne 0) { throw "wheel build failed" }
if ((Get-ChildItem -File $wheelOut -Filter "*.whl").Count -ne 1) {
    throw "wheel count is not one"
}
$resolvedTemp = [IO.Path]::GetFullPath($env:TEMP)
foreach ($temporaryOutput in @($notebookOut, $wheelOut)) {
    $resolvedOutput = [IO.Path]::GetFullPath($temporaryOutput)
    if (-not $resolvedOutput.StartsWith(
        $resolvedTemp,
        [StringComparison]::OrdinalIgnoreCase
    )) { throw "temporary output escaped the system temporary directory" }
    [IO.Directory]::Delete($resolvedOutput, $true)
}
$repositoryRoot = [IO.Path]::GetFullPath((Get-Location).Path)
$buildTarget = [IO.Path]::GetFullPath((Join-Path $repositoryRoot "build"))
if ([IO.Directory]::Exists($buildTarget)) {
    if ($buildTarget -ne [IO.Path]::GetFullPath((Join-Path $repositoryRoot "build"))) {
        throw "resolved build target is not repository build directory"
    }
    [IO.Directory]::Delete($buildTarget, $true)
}
if ([IO.Directory]::Exists((Join-Path $repositoryRoot "dist"))) {
    throw "unexpected dist directory remains"
}
```

Required result: all three notebooks exit `0`, exactly one `.whl` exists, and no `build/` or `dist/` directory remains in the repository.

- [ ] **Step 7: Run documentation, link, secret, and tracked-path audits**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_documentation.py -q
@'
import re
from pathlib import Path

root = Path(".").resolve()
broken = []
checked = 0
for markdown in root.rglob("*.md"):
    if any(
        part in {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__"}
        for part in markdown.parts
    ):
        continue
    text = markdown.read_text(encoding="utf-8")
    for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", text):
        target = target.strip().strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path_part = target.split("#", 1)[0].replace("%20", " ")
        checked += 1
        if path_part and not (markdown.parent / path_part).resolve().exists():
            broken.append((str(markdown.relative_to(root)), target))
print(f"LOCAL_MARKDOWN_LINKS_CHECKED={checked}")
if broken:
    raise SystemExit(f"broken local Markdown links: {broken}")
print("LOCAL_MARKDOWN_LINKS=PASS")
'@ | .venv/Scripts/python.exe -
git grep -n -I -E -- 'AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AIza[0-9A-Za-z_-]{30,}'
if ($LASTEXITCODE -eq 0) { throw "tracked secret-like value found" }
git ls-files | Select-String -Pattern '(^|/)(\.venv|\.pytest_cache|\.ruff_cache|__pycache__|build|dist)(/|$)|\.pyc$'
if ($LASTEXITCODE -eq 0) { throw "forbidden generated path is tracked" }
```

Expected: documentation tests pass, all local Markdown targets exist, no tracked secret-like value is found, and no forbidden generated path is tracked.

- [ ] **Step 8: Commit public documentation**

```powershell
git add docs/audit-summary.md
git diff --cached --check
git commit -m "docs: document recomputed dashboard evidence"
```

- [ ] **Step 9: Remove this handoff from the current public tree**

```powershell
git rm docs/superpowers/plans/2026-08-17-dashboard-semantic-evidence-binding.md
git diff --cached --check
git commit -m "docs: remove completed semantic binding handoff"
```

- [ ] **Step 10: Apply the final publication decision**

Run:

```powershell
git status --short
git diff --check
git ls-files | Select-String -Pattern '(^|/)(\.venv|\.pytest_cache|\.ruff_cache|__pycache__|build|dist)(/|$)|\.pyc$'
```

Set `PUBLIC_READY=YES` only if all conditions below are true:

- The four original attacks now raise `ArtifactLoadError` with a domain-specific message.
- The valid default, zero-error, and single-class runs load successfully.
- Full tests, coverage, Ruff, notebooks, wheel, evidence byte comparison, strict robustness verification, link scan, and secret scan pass.
- Canonical evidence files have no byte changes.
- The worktree is clean and no forbidden generated path is tracked.
- The current public tree contains no implementation handoff or release-blocker prompt.

Otherwise return `PUBLIC_READY=NO`, list the exact failed command or still-accepted attack, and do not push or publish.

## Required DeepSeek Agent Harness Final Response

Return these fields in this order:

```text
BASELINE_ANCESTOR=<True|False>
FORGERY_REPORTED_FEEDER=<REJECTED|ACCEPTED>
FORGERY_PR_AUC=<REJECTED|ACCEPTED>
FORGERY_TOP1=<REJECTED|ACCEPTED>
FORGERY_CANDIDATE_COUNT=<REJECTED|ACCEPTED>
TESTS=<passed count and elapsed time>
COVERAGE=<percentage>
RUFF=<PASS|FAIL>
NOTEBOOKS=<PASS|FAIL>
WHEEL=<PASS|FAIL>
PUBLIC_EVIDENCE_BYTES=<PASS|FAIL>
EXPERIMENT_MANIFEST=<strict or returned state>
ROBUSTNESS_LOADER=<strict_verified or returned state>
ROBUSTNESS_ROWS=<integer>
CANONICAL_EVIDENCE_CHANGED=<True|False>
WORKTREE_CLEAN=<True|False>
FINAL_COMMITS=<short hashes and subjects>
PUBLIC_READY=<YES|NO>
```

Do not push to GitHub. Stop after the clean local release judgment so the repository owner can perform one final review.
