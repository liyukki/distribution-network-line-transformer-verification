# Dashboard Bilingual Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete Simplified Chinese and English display layer to the Streamlit dashboard, default to Chinese, and keep all canonical artifacts and evaluation behavior unchanged.

**Architecture:** Introduce one pure localization module under `ltverify`, then make Streamlit pages and Plotly builders translate only at render time. Canonical dataframe columns, categorical values, selector values, metrics, hashes, and model inputs remain unchanged. Locale is owned by the main Streamlit shell and shared through session state.

**Tech Stack:** Python 3.11/3.12, pandas, Plotly, Streamlit 1.51+, pytest, Ruff.

## Global Constraints

- Implement the approved specification at `docs/superpowers/specs/2026-08-17-dashboard-bilingual-interface-design.md` from baseline commit `7302d86`.
- Work directly on the current `main` branch as authorized by the repository owner; do not push to a remote.
- Use strict TDD for every production behavior: add a focused test, observe the intended failure, implement the smallest behavior, and observe it pass.
- Default locale is `zh-CN`; supported locale values are exactly `zh-CN` and `en-US`.
- Never mutate `RunArtifacts` frames or canonical metric dictionaries during localization.
- Never translate transformer IDs, feeder IDs, timestamps, paths, filenames, hashes, commands, numeric values, `kV`, `p.u.`, `CSV`, `SHA-256`, `PR-AUC`, or `F1`.
- Selectors use canonical values and localized `format_func`; translated values must never control business branches.
- All plotting locale parameters are keyword-only and default to `zh-CN`, preserving existing callers.
- Missing translation keys raise `KeyError`; invalid stale locale values normalize to `zh-CN`.
- English artifact-load failures show an English summary and repair command without rendering the original Chinese exception text; the original exception is logged.
- Do not regenerate or edit canonical files under `reports/evidence/default_run/` or `reports/metrics/`.
- The current public tree must not retain this implementation plan or the temporary design specification after completion.

## File Structure

- Create `src/ltverify/i18n.py`: locale normalization, static UI translations, metric/family/column labels, categorical value maps, and dataframe-copy localization.
- Create `tests/unit/test_i18n.py`: translation completeness, normalization, value mapping, dynamic columns, and input immutability.
- Modify `src/ltverify/plotting.py`: keyword-only locale support for every public figure builder.
- Modify `tests/unit/test_plotting.py`: Chinese and English chart assertions.
- Modify `app/streamlit_app.py`: language selector, localized shell/navigation/cards, locale state, and localized load errors.
- Modify `app/pages/1_network.py` through `app/pages/5_robustness.py`: localize all visible normal-flow strings and displayed dataframes.
- Modify `tests/integration/test_streamlit_smoke.py`: default locale, switching, navigation, summary cards, and localized error behavior.
- Modify `tests/integration/test_pages.py`: render all pages under both locales and assert canonical data behavior remains unchanged.
- Modify `docs/design.md` and `README.md`: document the bilingual selector without overstating translation of technical identifiers.
- Delete the temporary specification and this plan in the final documentation commit.

---

### Task 1: Build the Pure Localization Core

**Files:**
- Create: `src/ltverify/i18n.py`
- Create: `tests/unit/test_i18n.py`

**Interfaces:**
- Produces: `Locale`, `DEFAULT_LOCALE`, `SUPPORTED_LOCALES`, `TRANSLATIONS`, `normalize_locale`, `translate`, `translate_value`, `metric_label`, `family_label`, `column_label`, and `localize_frame`.
- Consumes: pandas only; this module must not import Streamlit or artifact loaders.

- [ ] **Step 1: Write failing catalog and normalization tests**

Create `tests/unit/test_i18n.py` with these behaviors:

```python
import pandas as pd
import pytest

from ltverify.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    TRANSLATIONS,
    column_label,
    family_label,
    localize_frame,
    metric_label,
    normalize_locale,
    translate,
    translate_value,
)


def test_catalogs_have_identical_nonempty_keys() -> None:
    assert DEFAULT_LOCALE == "zh-CN"
    assert SUPPORTED_LOCALES == ("zh-CN", "en-US")
    assert set(TRANSLATIONS["zh-CN"]) == set(TRANSLATIONS["en-US"])
    assert all(TRANSLATIONS[locale] for locale in SUPPORTED_LOCALES)
    assert all(
        isinstance(value, str) and value
        for locale in SUPPORTED_LOCALES
        for value in TRANSLATIONS[locale].values()
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("zh-CN", "zh-CN"), ("en-US", "en-US"), (None, "zh-CN"), ("fr-FR", "zh-CN")],
)
def test_normalize_locale(raw: object, expected: str) -> None:
    assert normalize_locale(raw) == expected


def test_translate_formats_selected_catalog() -> None:
    assert translate("zh-CN", "failed_case_count", count=2) == "存在 2 个失败案例"
    assert translate("en-US", "failed_case_count", count=2) == "2 failed cases found"
    with pytest.raises(KeyError):
        translate("zh-CN", "missing.translation.key")
```

- [ ] **Step 2: Run the tests and confirm import failure**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_i18n.py -q
```

Expected: collection fails because `ltverify.i18n` does not exist. This is the intended red state.

- [ ] **Step 3: Implement locale types, normalization, and paired catalogs**

Create `src/ltverify/i18n.py`. Use `MappingProxyType` for the two catalog dictionaries. Include translation keys for every literal rendered by the shell and five pages, grouped with stable prefixes:

- `app.*`: app title, language selector, run directory, demo mode, five navigation titles, cards, status, run identifier, hash caption, missing-run guidance, and load-failure summaries.
- `network.*`, `diagnosis.*`, `similarity.*`, `evaluation.*`, `robustness.*`: every title, selector, option, caption, expander, warning, info, and failure template in the corresponding page.
- `plot.*`: every chart title, axis title, legend, colorbar, hover label, mean, and sample-standard-deviation phrase.
- Shared templates: `not_applicable`, `failed_case_count`, `original_diagnostic_logged`, and language option labels.

Implement `normalize_locale` by returning the input only when it is a member of `SUPPORTED_LOCALES`; otherwise return `DEFAULT_LOCALE`. Implement `translate` with direct dictionary indexing and `str.format`.

- [ ] **Step 4: Run catalog tests to green**

Run the Task 1 test command. Expected: catalog and normalization tests pass.

- [ ] **Step 5: Add failing value, label, and dataframe tests**

Add literal assertions covering both locales:

```python
@pytest.mark.parametrize(
    ("locale", "expected"),
    [("zh-CN", "自动推荐"), ("en-US", "Automatic recommendation")],
)
def test_translate_known_decision(locale: str, expected: str) -> None:
    assert translate_value(locale, "decision", "automatic_recommendation") == expected


def test_labels_cover_metrics_families_and_dynamic_columns() -> None:
    assert metric_label("zh-CN", "pr_auc_scored") == "可评分子集 PR-AUC"
    assert metric_label("en-US", "top1_correction_rate") == "Top-1 correction rate"
    assert family_label("zh-CN", "missing_rate") == "数据缺失率"
    assert family_label("en-US", "missing_rate") == "Missing-data rate"
    assert column_label("zh-CN", "transformer_id") == "配变编号"
    assert column_label("en-US", "mean_f1") == "F1 mean"
    assert column_label("zh-CN", "std_pr_auc") == "PR-AUC 样本标准差"


def test_unknown_identifier_is_preserved() -> None:
    assert translate_value("zh-CN", "decision", "future_value") == "future_value"
    assert column_label("zh-CN", "future_column") == "future_column"


def test_localize_frame_translates_copy_without_mutating_input() -> None:
    source = pd.DataFrame(
        {
            "transformer_id": ["T001"],
            "decision": ["automatic_recommendation"],
            "status": ["completed"],
            "pr_auc": [0.5],
        }
    )
    original = source.copy(deep=True)
    localized = localize_frame(source, "zh-CN")
    pd.testing.assert_frame_equal(source, original)
    assert localized.columns.tolist() == ["配变编号", "判定", "状态", "PR-AUC"]
    assert localized.iloc[0].tolist() == ["T001", "自动推荐", "已完成", 0.5]
```

- [ ] **Step 6: Implement complete domain and column maps**

Provide maps for:

- Decisions: `automatic_recommendation`, `insufficient_data`, `no_change`.
- Run and case states: `completed`, `failed`, `running`.
- Verification states: `strict_verified`, `artifact_hashes_verified`, `legacy_unverified`.
- Data-quality flags emitted by the pipeline, including `ok`, `missing`, `interpolated`, `spike`, and `time_shifted`.
- Experiment families present in `configs/robustness.yaml` and the 130-row public summary.
- Every metric option currently listed on evaluation and robustness pages.
- Every column in the dataframes rendered by the five pages; handle `mean_` and `std_` prefixes through `metric_label` rather than duplicating every aggregate column.

`localize_frame` must deep-copy the frame, translate categorical columns by original canonical column name, then rename columns last.

- [ ] **Step 7: Run all i18n tests and commit the core**

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_i18n.py -q
.venv/Scripts/python.exe -m ruff format src/ltverify/i18n.py tests/unit/test_i18n.py
.venv/Scripts/python.exe -m ruff check src/ltverify/i18n.py tests/unit/test_i18n.py
git add src/ltverify/i18n.py tests/unit/test_i18n.py
git diff --cached --check
git commit -m "feat: add dashboard localization core"
```

---

### Task 2: Localize Every Plotly Figure

**Files:**
- Modify: `src/ltverify/plotting.py`
- Modify: `tests/unit/test_plotting.py`

**Interfaces:**
- Consumes: `Locale`, `DEFAULT_LOCALE`, `translate`, `metric_label`, and `family_label`.
- Produces: existing plotting APIs with a keyword-only `locale` parameter.

- [ ] **Step 1: Add failing English assertions**

Keep existing Chinese tests and add English cases for all seven builders. Required literal assertions include:

```python
def test_confusion_matrix_figure_has_english_axes() -> None:
    figure = confusion_matrix_figure(np.array([[8, 1], [2, 5]]), locale="en-US")
    assert figure.layout.title.text == "Confusion matrix"
    assert figure.layout.xaxis.title.text == "Predicted label"
    assert figure.layout.yaxis.title.text == "Actual label"


def test_pr_curve_figure_has_english_axes() -> None:
    figure = pr_curve_figure([1.0, 0.8], [0.2, 1.0], locale="en-US")
    assert figure.layout.title.text == "Precision-recall curve"
    assert figure.layout.xaxis.title.text == "Recall"
    assert figure.layout.yaxis.title.text == "Precision"


def test_robustness_figure_localizes_family_and_metric() -> None:
    summary = pd.DataFrame(
        {
            "family": ["missing_rate", "missing_rate"],
            "value": ["0.0", "0.1"],
            "mean_f1": [0.9, 0.8],
            "std_f1": [0.05, 0.06],
        }
    )
    figure = robustness_line_figure(summary, "missing_rate", "f1", locale="zh-CN")
    assert "数据缺失率" in figure.layout.title.text
    assert figure.layout.yaxis.title.text == "F1"
```

Also assert English titles for voltage curves, candidate scores, similarity matrix, and topology; verify `T001` and `F01` remain unchanged.

- [ ] **Step 2: Run plotting tests and confirm locale argument failures**

Run `pytest tests/unit/test_plotting.py -q`. Expected: new tests fail because builders do not accept `locale`.

- [ ] **Step 3: Add keyword-only locale parameters and translation calls**

Update every public builder without changing data computation. `robustness_line_figure` continues filtering with canonical `family` and selecting canonical `mean_<metric>` columns; use localized labels only in the trace and layout. Error messages use Chinese under the default locale and English under `en-US`.

- [ ] **Step 4: Run plotting tests to green and commit**

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_plotting.py -q
.venv/Scripts/python.exe -m ruff format src/ltverify/plotting.py tests/unit/test_plotting.py
.venv/Scripts/python.exe -m ruff check src/ltverify/plotting.py tests/unit/test_plotting.py
git add src/ltverify/plotting.py tests/unit/test_plotting.py
git diff --cached --check
git commit -m "feat: localize dashboard figures"
```

---

### Task 3: Localize the Main Shell and Language Switching

**Files:**
- Modify: `app/streamlit_app.py`
- Modify: `tests/integration/test_streamlit_smoke.py`

**Interfaces:**
- Consumes: localization core and existing trusted `load_run_artifacts` entry point.
- Produces: session key `locale` available before page navigation.

- [ ] **Step 1: Add failing default and switch tests**

Add a module-scoped real run fixture to avoid regenerating a run for each new language assertion. Test fresh app state:

- First selectbox value is `zh-CN` and options are canonical locale values.
- Title includes `线变关系智能校验看板`.
- Metric cards include `预测告警数`, `运行状态`, and localized value `已完成`.
- Navigation page titles are Chinese.

Then set the language selectbox to `en-US`, rerun, and assert title `Line-transformer relationship verification`, cards `Predicted alerts` and `Run status`, value `Completed`, and English navigation titles.

- [ ] **Step 2: Run the two tests and confirm missing-selector failures**

Run the two new node IDs. Expected: the default test fails because the first selectbox is not a locale selector, and switching cannot be performed.

- [ ] **Step 3: Implement locale state before all visible shell text**

In the sidebar, render language selection before run directory and demo mode. Use canonical values with option labels fixed as `简体中文` and `English`. Normalize stale state before widget creation. Build title, navigation, metric labels, status value, captions, empty guidance, and load-failure UI from translations.

For English load failures, log with `logging.getLogger(__name__).exception` and display `Artifact loading failed. Run python -m ltverify run-all --config configs/default.yaml and try again.` Do not render `str(exc)` in English mode. Preserve detailed `str(exc)` in Chinese mode.

- [ ] **Step 4: Run all Streamlit smoke tests**

Run `pytest tests/integration/test_streamlit_smoke.py -q`. Existing path-hiding, tamper, malformed-data, and rerun tests must remain green in the default Chinese locale.

- [ ] **Step 5: Format, lint, and commit shell localization**

```powershell
.venv/Scripts/python.exe -m ruff format app/streamlit_app.py tests/integration/test_streamlit_smoke.py
.venv/Scripts/python.exe -m ruff check app/streamlit_app.py tests/integration/test_streamlit_smoke.py
git add app/streamlit_app.py tests/integration/test_streamlit_smoke.py
git diff --cached --check
git commit -m "feat: add dashboard language selector"
```

---

### Task 4: Localize All Five Pages and Visible Tables

**Files:**
- Modify: `app/pages/1_network.py`
- Modify: `app/pages/2_diagnosis.py`
- Modify: `app/pages/3_similarity.py`
- Modify: `app/pages/4_evaluation.py`
- Modify: `app/pages/5_robustness.py`
- Modify: `tests/integration/test_pages.py`

**Interfaces:**
- Consumes: `st.session_state["locale"]`, localization helpers, and locale-aware plotting functions.
- Produces: fully localized normal-flow pages while retaining canonical selection and evaluation paths.

- [ ] **Step 1: Parameterize the page render test over both locales**

Change `test_data_pages_render_without_exceptions` to run every page with both `zh-CN` and `en-US`. Set locale in session state before `app_test.run()`. Keep `demo_mode=True` so truth-only captions and PR charts are covered.

- [ ] **Step 2: Add failing Chinese leak and English presence tests**

Add focused page assertions:

- Diagnosis Chinese Markdown contains `自动推荐`, `数据质量标记`, or the localized canonical decision for the selected row, and does not contain `automatic_recommendation`, `insufficient_data`, or `no_change`.
- Evaluation Chinese visible table headings contain `精确率`, `召回率`, `可评分子集 PR-AUC`, and `实际错误数`, and do not expose `precision`, `recall`, `pr_auc_scored`, `scored_coverage`, or `n_actual_errors`.
- Robustness selector display labels are localized while selected canonical values remain valid inputs to `robustness_line_figure`.
- English page titles are `Network topology`, `Transformer diagnosis`, `Similarity matrix`, `Model evaluation`, and `Robustness experiments`.
- The existing PR label-capture test produces identical `y_true` under both locales.

- [ ] **Step 3: Run new tests and observe string failures**

Run the new page node IDs. Expected: English title assertions and Chinese canonical-value leak assertions fail on current pages.

- [ ] **Step 4: Localize network, diagnosis, and similarity pages**

At the top of each page normalize session locale. Translate all static text, pass locale to figures, and call `localize_frame` only inside dataframe display. Diagnosis translates the decision and quality-count dictionary but filters by canonical transformer ID. Similarity selector options are stable internal codes `raw`, `residual`, and `difference`; display localized option labels with `format_func` and branch on those codes.

- [ ] **Step 5: Localize evaluation page without changing PR semantics**

Build the displayed one-row metrics dataframe with localized column labels. Keep canonical keys for retrieval. Pass locale to confusion and PR figures. Preserve the existing ledger-plus-truth label merge byte-for-byte except for surrounding translated UI. Schema state comparisons remain canonical.

- [ ] **Step 6: Localize robustness page without changing filtering**

Keep canonical family and metric selectbox options, provide `format_func` using `family_label` and `metric_label`, and pass canonical selections plus locale to the plot. Localize aggregate/summary display copies, status values, verification messages, captions, missing-column messages, expander titles, and failure count. Filenames and paths remain canonical.

- [ ] **Step 7: Run all page and plotting integration tests**

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_pages.py tests/integration/test_streamlit_smoke.py tests/unit/test_plotting.py -q
```

Expected: every page renders under both locales, existing trust-boundary tests pass, and no known Chinese-mode canonical UI values leak.

- [ ] **Step 8: Format, lint, and commit page localization**

```powershell
.venv/Scripts/python.exe -m ruff format app src/ltverify/i18n.py src/ltverify/plotting.py tests/integration tests/unit/test_i18n.py tests/unit/test_plotting.py
.venv/Scripts/python.exe -m ruff check app src/ltverify/i18n.py src/ltverify/plotting.py tests/integration tests/unit/test_i18n.py tests/unit/test_plotting.py
git add app tests/integration/test_pages.py src/ltverify/i18n.py
git diff --cached --check
git commit -m "feat: localize dashboard pages"
```

---

### Task 5: Public Documentation, Cleanup, and Release Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/design.md`
- Delete: `docs/superpowers/specs/2026-08-17-dashboard-bilingual-interface-design.md`
- Delete: `docs/superpowers/plans/2026-08-17-dashboard-bilingual-interface.md`

**Interfaces:**
- Consumes: completed bilingual UI and green tests.
- Produces: GitHub-ready public tree and final `PUBLIC_READY` judgment.

- [ ] **Step 1: Document the selector accurately**

Add one README sentence under dashboard usage: the sidebar defaults to Simplified Chinese and can switch to English; identifiers, filenames, units, commands, and artifact values remain canonical. Add the localization boundary to `docs/design.md` with the same limits.

- [ ] **Step 2: Run full formatting, lint, tests, and coverage**

```powershell
.venv/Scripts/python.exe -m ruff format src app tests scripts
.venv/Scripts/python.exe -m ruff format --check src app tests scripts
.venv/Scripts/python.exe -m ruff check src app tests scripts
.venv/Scripts/python.exe -m pytest --cov=ltverify --cov-report=term-missing --cov-fail-under=90 -q
git diff --check
```

- [ ] **Step 3: Repeat semantic and evidence gates**

Run the four synchronized-hash forgery probes for reported feeder, PR-AUC, Top-1, and candidate count. Require all four to return `REJECTED` while the canonical default run returns `ACCEPTED`. Reproduce `default_summary.json` and `default_manifest.json` into a system temporary directory and require SHA-256 equality with both canonical report files. Require experiment manifest `strict`, robustness loader `strict_verified`, and 130 summary rows.

- [ ] **Step 4: Execute notebooks and build wheel**

Execute all three notebooks with `jupyter nbconvert --execute` into a system temporary directory. Build exactly one wheel with `pip wheel . --no-deps` into another temporary directory. Remove only verified temporary outputs and the exact repository `build/` directory created by pip; leave no `build/` or `dist/` directory.

- [ ] **Step 5: Verify the running dashboard in both languages**

Restart Streamlit bound only to `127.0.0.1:8501` with `LTVERIFY_RUN_DIR=reports/evidence/default_run`. Require HTTP 200. Use Streamlit integration tests as the authoritative UI assertions and manually confirm the in-app browser can switch between `简体中文` and `English` without a page exception.

- [ ] **Step 6: Update public docs and remove internal handoffs**

Use `apply_patch` to update README/design and delete the temporary spec and plan. Run documentation tests, local Markdown-link scan, public handoff scan, tracked secret-pattern scan, and generated-path scan.

- [ ] **Step 7: Commit documentation and cleanup**

```powershell
git add README.md docs/design.md docs/superpowers/specs/2026-08-17-dashboard-bilingual-interface-design.md docs/superpowers/plans/2026-08-17-dashboard-bilingual-interface.md
git diff --cached --check
git commit -m "docs: publish bilingual dashboard guidance"
```

- [ ] **Step 8: Final decision**

Set `PUBLIC_READY=YES` only when the worktree is clean, all tests and release gates pass, canonical evidence has zero diff, both locales render, the server listens only on `127.0.0.1`, and no internal plan remains in the current public tree. Do not push because no remote is configured.
