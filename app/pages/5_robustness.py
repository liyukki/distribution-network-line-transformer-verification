import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from ltverify.experiments import (
    CURRENT_AGGREGATES_NAME,
    CURRENT_MANIFEST_NAME,
    CURRENT_SUMMARY_NAME,
    LEGACY_AGGREGATES_NAME,
    LEGACY_SUMMARY_NAME,
)
from ltverify.i18n import (
    family_label,
    localize_frame,
    metric_label,
    normalize_locale,
    translate,
)
from ltverify.plotting import robustness_line_figure
from ltverify.robustness_loader import RobustnessLoadError, load_robustness_artifacts

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_EXPERIMENT_CONFIG = _REPO_ROOT / "configs/robustness.yaml"
_DEFAULT_BASE_CONFIG = _REPO_ROOT / "configs/default.yaml"
LOGGER = logging.getLogger(__name__)
locale = normalize_locale(st.session_state.get("locale"))

st.title(translate(locale, "robustness.title"))


def _default_experiment_paths() -> tuple[str, str]:
    """Pick a structurally complete experiment directory.

    New ``robustness_*`` naming is preferred globally. A current candidate
    must have aggregates, summary, and manifest all present as regular
    files; legacy candidates need the exact legacy aggregate name and, if a
    summary exists, the exact legacy summary name. Content hashes are not
    checked here; the loader performs verification.
    """
    directories = sorted(Path("runs").glob("experiments-*"), reverse=True)
    for directory in directories:
        aggregates = directory / CURRENT_AGGREGATES_NAME
        summary = directory / CURRENT_SUMMARY_NAME
        manifest = directory / CURRENT_MANIFEST_NAME
        if aggregates.is_file() and summary.is_file() and manifest.is_file():
            return str(aggregates), str(summary)
    for directory in directories:
        aggregates = directory / LEGACY_AGGREGATES_NAME
        if not aggregates.is_file():
            continue
        summary = directory / LEGACY_SUMMARY_NAME
        if summary.exists() and not summary.is_file():
            continue
        return str(aggregates), (str(summary) if summary.is_file() else "")
    return "", ""


def _source_config_paths() -> tuple[Path | None, Path | None]:
    experiment_config = _DEFAULT_EXPERIMENT_CONFIG if _DEFAULT_EXPERIMENT_CONFIG.is_file() else None
    base_config = _DEFAULT_BASE_CONFIG if _DEFAULT_BASE_CONFIG.is_file() else None
    return experiment_config, base_config


default_aggregates_path, default_summary_path = _default_experiment_paths()
aggregates_path = st.text_input(
    translate(locale, "robustness.aggregates_path"),
    value=default_aggregates_path,
)
summary_path = st.text_input(
    translate(locale, "robustness.summary_path"),
    value=default_summary_path,
)
if not aggregates_path:
    st.info(translate(locale, "robustness.missing_products"))
    st.stop()

aggregates_file = Path(aggregates_path)
summary_file = Path(summary_path) if summary_path else None

experiment_config_path, base_config_path = _source_config_paths()
try:
    artifacts = load_robustness_artifacts(
        aggregates_file,
        summary_file,
        experiment_config_path=experiment_config_path,
        base_config_path=base_config_path,
    )
except RobustnessLoadError as exc:
    LOGGER.warning("Robustness artifact loading failed: %s", exc)
    if locale == "zh-CN":
        st.error(translate(locale, "robustness.load_failed", detail=str(exc)))
    else:
        st.error(translate(locale, "robustness.load_failed_generic"))
    st.stop()

aggregates = artifacts.aggregates
verification_message = (
    artifacts.message
    if locale == "zh-CN"
    else translate(locale, f"robustness.verification.{artifacts.verification_state}")
)
if artifacts.verification_state == "strict_verified":
    st.success(verification_message)
elif artifacts.verification_state == "artifact_hashes_verified":
    st.warning(verification_message)
else:
    st.warning(verification_message)

family = st.selectbox(
    translate(locale, "robustness.family"),
    sorted(aggregates["family"].unique().tolist()),
    format_func=lambda value: family_label(locale, value),
)
metric = st.selectbox(
    translate(locale, "robustness.metric"),
    [
        "precision",
        "recall",
        "f1",
        "pr_auc",
        "pr_auc_scored",
        "top1_correction_rate",
        "top2_correction_rate",
        "automatic_coverage",
        "scored_coverage",
        "insufficient_data_rate",
        "convergence_rate",
    ],
    format_func=lambda value: metric_label(locale, value),
)
st.caption(translate(locale, "robustness.caption"))
mean_column = f"mean_{metric}"
if mean_column not in aggregates.columns:
    st.info(
        translate(
            locale,
            "robustness.missing_metric",
            metric=metric_label(locale, metric),
            column=mean_column,
        )
    )
    st.stop()
numeric = pd.to_numeric(aggregates[mean_column], errors="coerce")
if not numeric.notna().any():
    if aggregates[mean_column].notna().any():
        st.error(
            translate(
                locale,
                "robustness.nonnumeric_metric",
                metric=metric_label(locale, metric),
                column=mean_column,
            )
        )
    else:
        st.info(
            translate(
                locale,
                "robustness.empty_metric",
                metric=metric_label(locale, metric),
                column=mean_column,
            )
        )
    st.stop()
aggregates = aggregates.copy()
aggregates[mean_column] = numeric
try:
    figure = robustness_line_figure(aggregates, family, metric, locale=locale)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
st.plotly_chart(figure, width="stretch")
with st.expander(translate(locale, "robustness.aggregates")):
    st.dataframe(localize_frame(aggregates, locale), width="stretch")

if artifacts.summary is not None:
    with st.expander(translate(locale, "robustness.case_details")):
        st.dataframe(localize_frame(artifacts.summary, locale), width="stretch")
        failed = artifacts.summary[artifacts.summary["status"] != "completed"]
        if len(failed):
            st.warning(translate(locale, "robustness.failed_cases", count=len(failed)))
