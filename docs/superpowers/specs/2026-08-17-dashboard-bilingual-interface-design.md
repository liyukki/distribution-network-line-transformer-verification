# Dashboard Bilingual Interface Design

## Objective

Add a sidebar language selector with `简体中文` and `English`, defaulting to Simplified Chinese. Every user-facing dashboard label, message, table heading, categorical value, chart title, legend, and axis title must follow the selected locale while all stored artifacts and model-facing values remain unchanged.

## Scope

The implementation covers:

- The main Streamlit shell, sidebar, navigation titles, summary metrics, status text, and captions.
- Network, diagnosis, similarity, evaluation, and robustness pages.
- Dataframe column headings and known categorical values displayed from predictions, truth, candidate features, robustness aggregates, and robustness summaries.
- Plotly chart titles, legends, colorbars, hover labels, and axis titles.
- Known domain values such as decisions, run states, verification states, data-quality flags, experiment families, and evaluation metrics.

The following remain unchanged in both languages because they are identifiers, units, filenames, commands, or standard technical abbreviations:

- Transformer and feeder identifiers such as `T001` and `F01`.
- `kV`, `p.u.`, `CSV`, `SHA-256`, `PR-AUC`, `F1`, file paths, and command lines.
- Numeric values, timestamps, hashes, run identifiers, schema versions, and artifact filenames.

## Architecture

Create `src/ltverify/i18n.py` as the single localization boundary. It will expose:

- `Locale = Literal["zh-CN", "en-US"]`
- `DEFAULT_LOCALE: Locale = "zh-CN"`
- `SUPPORTED_LOCALES: tuple[Locale, ...] = ("zh-CN", "en-US")`
- `translate(locale: Locale, key: str, **values: object) -> str`
- `translate_value(locale: Locale, domain: str, value: object) -> object`
- `metric_label(locale: Locale, metric: str) -> str`
- `column_label(locale: Locale, column: str) -> str`
- `localize_frame(frame: pd.DataFrame, locale: Locale) -> pd.DataFrame`

`translate` reads immutable dictionaries whose key sets must be identical across locales. Missing translation keys are programming errors and raise `KeyError`; they must not silently expose an internal key. Format parameters use `str.format` after the translated template is selected.

`translate_value` maps only known categorical domains. Unknown identifiers and free-form details fall back to their original value so the display never corrupts operational evidence. `localize_frame` returns a copy, translates known categorical cells, and renames visible columns; it never mutates a `RunArtifacts` dataframe.

## Locale State and Navigation

The main app owns locale selection:

1. Read `st.session_state["locale"]`, defaulting to `zh-CN`.
2. Render a sidebar selectbox with canonical options `zh-CN` and `en-US` and localized display labels.
3. Store the selected canonical locale back into session state before building navigation.
4. Pass locale implicitly through `st.session_state` to every page.
5. Build `st.navigation` titles from translation keys on every rerun.

The selector label follows the currently selected locale. Option labels remain `简体中文` and `English` in both modes so users can recover from either language without understanding the active language.

## Display-Layer Translation

Canonical values remain the only values used for filtering, comparisons, evaluator calls, artifact validation, and hashes. Translation occurs immediately before rendering:

- Selectboxes use canonical options with `format_func` for localized labels.
- Metrics are selected by canonical key and displayed using `metric_label`.
- Dataframes pass through `localize_frame` only in the `st.dataframe` call.
- Decisions such as `automatic_recommendation`, `insufficient_data`, and `no_change` are translated only in rendered Markdown or dataframe copies.
- States such as `completed`, `failed`, `strict_verified`, and data-quality flags are translated by their domain map.
- Dynamic robustness columns use structured labels: `mean_<metric>` becomes the localized metric plus localized “mean”, and `std_<metric>` becomes the localized metric plus localized “sample standard deviation”.
- Null display text is `不适用` in Chinese and `N/A` in English.

This boundary ensures changing the language cannot alter metrics, filtering, PR labels, Top-k results, evidence hashes, or the selected transformer.

## Plot Localization

Every public plotting function gains a backward-compatible keyword-only locale argument defaulting to `zh-CN`. Chart construction uses translation helpers for titles, legends, colorbars, axis titles, and fixed hover labels.

The representative signature is `confusion_matrix_figure(matrix: np.ndarray, *, locale: Locale = DEFAULT_LOCALE) -> go.Figure`.

The same pattern applies to voltage curves, candidate scores, similarity heatmap, topology, PR curve, and robustness line figures. Series names and identifiers remain canonical when they identify equipment; user-facing metric and experiment-family names are localized.

## Page Requirements

### Main Shell

- Default language is Simplified Chinese.
- Language switching updates the app title, sidebar, navigation, summary cards, run status, missing-run guidance, and hash caption immediately.
- `completed` displays as `已完成` in Chinese and `Completed` in English.

### Network Page

- Translate title, empty-state message, captions, expander labels, subheading, visible prediction/truth columns, and categorical values.
- Preserve node, transformer, and feeder identifiers.

### Diagnosis Page

- Translate title, selector label, decision value, field labels, chart labels, and data-quality flags.
- The selected transformer remains the canonical transformer ID.

### Similarity Page

- Translate the page title, matrix-mode selector label and options, chart text, empty-state message, and caption.
- Internal branch selection continues to use stable canonical mode values rather than comparing translated text.

### Evaluation Page

- Translate schema warnings, metric-table headings, explanatory caption, empty-state messages, and chart labels.
- Continue deriving PR labels from ledger plus truth; locale must not affect that data path.
- Chinese metric headings must not expose raw keys such as `pr_auc_scored`, `scored_coverage`, or `n_actual_errors`.

### Robustness Page

- Translate path-field labels, state messages, experiment-family and metric selectors, figure text, expanders, table headings, status values, and failure-count messages.
- Selectors retain canonical family and metric values and localize with `format_func`.
- Filenames and paths remain unchanged.

## Error Handling

- Invalid locale values from stale session state normalize to `zh-CN`.
- Missing translation keys raise during tests and development rather than silently leaking keys.
- Unknown domain values remain visible as their original value because hiding operational data is worse than showing an unfamiliar code.
- Existing `ArtifactLoadError` and `RobustnessLoadError` messages are already Chinese. Chinese mode displays the detailed message. English mode logs the original diagnostic server-side and renders a translated generic failure plus the canonical repair command, so Chinese exception text does not leak into the English interface.
- Localization failures must not alter artifact loading or hash-verification order.

## Testing Strategy

### Unit Tests

- Assert both locale dictionaries have exactly the same non-empty key set.
- Assert invalid locales normalize to `zh-CN`.
- Assert known decisions, states, quality flags, metrics, families, direct columns, and dynamic mean/std columns translate in both directions.
- Assert unknown identifiers are preserved.
- Assert `localize_frame` does not mutate its input.
- Assert every Plotly function produces localized titles and axes for both locales while retaining equipment identifiers.

### Streamlit Integration Tests

- Verify the initial selector value is `zh-CN` and the navigation is Chinese.
- Switch to `en-US` and verify navigation, page title, summary cards, and page text rerender in English.
- Render all five pages under both locales without exceptions.
- In Chinese evaluation and robustness tables, assert known internal keys and categorical values are absent from visible headings/cells.
- Verify switching locale does not change loaded metrics, selected transformer IDs, or PR-curve label inputs.

### Release Gates

- Full pytest suite with at least 90% coverage.
- Ruff format and lint checks.
- Existing four semantic-forgery attacks remain rejected.
- Public evidence report and manifest remain byte-identical.
- Strict robustness verification remains `strict` and `strict_verified` with 130 cases.
- Three notebooks execute and one wheel builds.
- Worktree, generated-path, secret-pattern, local-link, and public-handoff scans remain clean.

## Acceptance Criteria

The feature is complete when:

1. A user can switch between `简体中文` and `English` from the sidebar.
2. Simplified Chinese is the default on a fresh session.
3. Every known user-facing string and known categorical value follows the selected locale.
4. Chinese mode exposes no known raw decision, status, quality, metric, or robustness-family keys.
5. Technical identifiers and canonical artifacts remain unchanged.
6. Language switching does not change evaluation results or trust-boundary behavior.
7. All release gates pass and the dashboard remains suitable for public GitHub publication.
