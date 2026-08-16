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
        "top1_correction_rate",
        "top2_correction_rate",
        "automatic_coverage",
        "convergence_rate",
    ],
)
try:
    figure = robustness_line_figure(aggregates, family, metric)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
st.plotly_chart(figure, use_container_width=True)
with st.expander("聚合汇总"):
    st.dataframe(aggregates, use_container_width=True)

summary_path = st.text_input(
    "案例明细 CSV 路径（experiment_summary.csv，仅用于明细与失败原因）",
    value=_default_path("experiments-*/experiment_summary.csv"),
)
if summary_path and Path(summary_path).exists():
    summary = pd.read_csv(summary_path)
    with st.expander("案例明细与失败原因"):
        st.dataframe(summary, use_container_width=True)
        failed = summary[summary["status"] != "completed"]
        if len(failed):
            st.warning(f"存在 {len(failed)} 个失败案例，详见明细表。")
