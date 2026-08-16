from pathlib import Path

import pandas as pd
import streamlit as st

from ltverify.plotting import robustness_line_figure

st.title("鲁棒性实验")


def _default_path(pattern: str) -> str:
    candidates = sorted(Path("runs").glob(pattern), reverse=True)
    return str(candidates[0]) if candidates else ""


aggregates_path = st.text_input(
    "实验聚合 CSV 路径（experiment_aggregates.csv）",
    value=_default_path("experiments-*/experiment_aggregates.csv"),
)
if not aggregates_path:
    st.info(
        "未找到实验聚合产物，请先运行 "
        "python -m ltverify experiments --config configs/robustness.yaml"
    )
    st.stop()

aggregates_file = Path(aggregates_path)
if not aggregates_file.exists():
    st.error(f"文件不存在: {aggregates_file.resolve()}")
    st.stop()

aggregates = pd.read_csv(aggregates_file)
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
if aggregates[mean_column].isna().all():
    st.info(f"{metric} 不适用：所有聚合样本为空值")
    st.stop()
try:
    figure = robustness_line_figure(aggregates, family, metric)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
st.plotly_chart(figure, width='stretch')
with st.expander("聚合汇总"):
    st.dataframe(aggregates, width='stretch')

summary_path = st.text_input(
    "案例明细 CSV 路径（experiment_summary.csv，仅用于明细与失败原因）",
    value=_default_path("experiments-*/experiment_summary.csv"),
)
if summary_path and Path(summary_path).exists():
    summary = pd.read_csv(summary_path)
    with st.expander("案例明细与失败原因"):
        st.dataframe(summary, width='stretch')
        failed = summary[summary["status"] != "completed"]
        if len(failed):
            st.warning(f"存在 {len(failed)} 个失败案例，详见明细表。")
