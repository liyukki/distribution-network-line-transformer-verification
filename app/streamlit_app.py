import os
from pathlib import Path

import streamlit as st

from ltverify.data_access import ArtifactLoadError, RunArtifacts, load_run_artifacts

st.set_page_config(page_title="线变关系智能校验", layout="wide")
st.title("线变关系智能校验看板")


def _default_run_dir() -> str:
    env = os.environ.get("LTVERIFY_RUN_DIR")
    if env:
        return env
    candidates = sorted(Path("runs").glob("run-*"), reverse=True)
    return str(candidates[0]) if candidates else ""


with st.sidebar:
    run_dir = st.text_input("运行目录", value=_default_run_dir())
    demo_mode = st.toggle("演示评价模式", value=False)
    st.caption("演示评价模式下才显示物理真值与真实标签。")

if not run_dir:
    st.info(
        "请先运行 python -m ltverify run-all --config configs/default.yaml，"
        "然后在左侧填写运行目录。"
    )
    st.stop()


@st.cache_data(show_spinner=False)
def _load_run(directory: str) -> RunArtifacts:
    return load_run_artifacts(Path(directory))


try:
    artifacts = _load_run(run_dir)
except ArtifactLoadError as exc:
    st.error(str(exc))
    st.stop()

st.session_state["artifacts"] = artifacts
st.session_state["demo_mode"] = demo_mode

metrics = artifacts.metrics
columns = st.columns(5)
columns[0].metric("预测告警数", int(metrics.get("n_predicted", 0)))
columns[1].metric("F1", f"{float(metrics.get('f1', 0)):.3f}")
columns[2].metric(
    "Top-1 修正率", f"{float(metrics.get('top1_correction_rate', 0)):.3f}"
)
columns[3].metric(
    "自动推荐覆盖率", f"{float(metrics.get('automatic_coverage', 0)):.3f}"
)
columns[4].metric("运行状态", str(artifacts.manifest.get("status", "unknown")))
st.caption(f"运行目录: {artifacts.run_dir.resolve()}")

pages = st.navigation(
    [
        st.Page("pages/1_network.py", title="网络拓扑"),
        st.Page("pages/2_diagnosis.py", title="配变诊断"),
        st.Page("pages/3_similarity.py", title="相似度矩阵"),
        st.Page("pages/4_evaluation.py", title="模型评估"),
        st.Page("pages/5_robustness.py", title="鲁棒性实验"),
    ]
)
pages.run()
