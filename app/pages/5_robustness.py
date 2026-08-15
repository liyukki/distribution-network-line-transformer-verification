from pathlib import Path

import pandas as pd
import streamlit as st

from ltverify.plotting import robustness_line_figure

st.title("鲁棒性实验")


def _default_summary() -> str:
    candidates = sorted(
        Path("runs").glob("experiments-*/experiment_summary.csv"), reverse=True
    )
    return str(candidates[0]) if candidates else ""


summary_path = st.text_input("实验汇总 CSV 路径", value=_default_summary())
if not summary_path:
    st.info(
        "未找到实验汇总，请先运行 "
        "python -m ltverify experiments --config configs/robustness.yaml"
    )
    st.stop()

path = Path(summary_path)
if not path.exists():
    st.error(f"文件不存在: {path.resolve()}")
    st.stop()

summary = pd.read_csv(path)
family = st.selectbox("实验族", sorted(summary["family"].unique().tolist()))
metric = st.selectbox(
    "指标",
    [
        "precision",
        "recall",
        "f1",
        "top1_correction_rate",
        "top3_correction_rate",
        "automatic_coverage",
    ],
)
st.plotly_chart(
    robustness_line_figure(summary, family, metric),
    use_container_width=True,
)
with st.expander("原始汇总"):
    st.dataframe(summary, use_container_width=True)
