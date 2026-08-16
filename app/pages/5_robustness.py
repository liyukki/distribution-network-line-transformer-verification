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
from ltverify.plotting import robustness_line_figure
from ltverify.robustness_loader import RobustnessLoadError, load_robustness_artifacts

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_EXPERIMENT_CONFIG = _REPO_ROOT / "configs/robustness.yaml"
_DEFAULT_BASE_CONFIG = _REPO_ROOT / "configs/default.yaml"

st.title("鲁棒性实验")


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
        if (
            aggregates.is_file()
            and summary.is_file()
            and manifest.is_file()
        ):
            return str(aggregates), str(summary)
    for directory in directories:
        aggregates = directory / LEGACY_AGGREGATES_NAME
        if not aggregates.is_file():
            continue
        summary = directory / LEGACY_SUMMARY_NAME
        if summary.exists() and not summary.is_file():
            continue
        return str(aggregates), (
            str(summary) if summary.is_file() else ""
        )
    return "", ""


def _source_config_paths() -> tuple[Path | None, Path | None]:
    experiment_config = (
        _DEFAULT_EXPERIMENT_CONFIG
        if _DEFAULT_EXPERIMENT_CONFIG.is_file()
        else None
    )
    base_config = (
        _DEFAULT_BASE_CONFIG if _DEFAULT_BASE_CONFIG.is_file() else None
    )
    return experiment_config, base_config


default_aggregates_path, default_summary_path = _default_experiment_paths()
aggregates_path = st.text_input(
    "实验聚合 CSV 路径（robustness_aggregates.csv）",
    value=default_aggregates_path,
)
if not aggregates_path:
    st.info(
        "未找到实验聚合产物，请先运行 "
        "python -m ltverify experiments --config configs/robustness.yaml"
    )
    st.stop()

aggregates_file = Path(aggregates_path)
summary_path = st.text_input(
    "案例明细 CSV 路径（robustness_summary.csv，仅用于明细与失败原因）",
    value=default_summary_path,
)
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
    st.error(str(exc))
    st.stop()

aggregates = artifacts.aggregates
if artifacts.verification_state == "strict_verified":
    st.success(artifacts.message)
elif artifacts.verification_state == "artifact_hashes_verified":
    st.warning(artifacts.message)
else:
    st.warning(artifacts.message)

family = st.selectbox("实验族", sorted(aggregates["family"].unique().tolist()))
metric = st.selectbox(
    "指标",
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
)
st.caption(
    "pr_auc 为主样本口径；pr_auc_scored 为仅可评分子集的诊断口径，"
    "须与 scored_coverage 同时解读；空值显示为不适用。"
)
mean_column = f"mean_{metric}"
if mean_column not in aggregates.columns:
    st.info(f"{metric} 不适用：聚合产物缺少 {mean_column} 列")
    st.stop()
numeric = pd.to_numeric(aggregates[mean_column], errors="coerce")
if not numeric.notna().any():
    if aggregates[mean_column].notna().any():
        st.error(f"{metric} 不适用：{mean_column} 不是可用数值列")
    else:
        st.info(f"{metric} 不适用：{mean_column} 全为空值")
    st.stop()
aggregates = aggregates.copy()
aggregates[mean_column] = numeric
try:
    figure = robustness_line_figure(aggregates, family, metric)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
st.plotly_chart(figure, width='stretch')
with st.expander("聚合汇总"):
    st.dataframe(aggregates, width='stretch')

if artifacts.summary is not None:
    with st.expander("案例明细与失败原因"):
        st.dataframe(artifacts.summary, width='stretch')
        failed = artifacts.summary[artifacts.summary["status"] != "completed"]
        if len(failed):
            st.warning(f"存在 {len(failed)} 个失败案例，详见明细表。")
