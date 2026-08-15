import pandas as pd
import streamlit as st
from sklearn.metrics import precision_recall_curve

from ltverify.plotting import confusion_matrix_figure, pr_curve_figure

st.title("模型评估")

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info("请先在主页加载运行目录。")
    st.stop()

st.plotly_chart(
    confusion_matrix_figure(artifacts.confusion_matrix.to_numpy()),
    use_container_width=True,
)

key_metrics = {
    key: artifacts.metrics.get(key, float("nan"))
    for key in (
        "precision",
        "recall",
        "f1",
        "pr_auc",
        "top1_correction_rate",
        "top3_correction_rate",
        "automatic_coverage",
        "insufficient_data_rate",
        "n_total",
        "n_actual_errors",
    )
}
st.dataframe(pd.DataFrame([key_metrics]), use_container_width=True)
st.caption("主指标为 Precision/Recall/F1/PR-AUC 与 Top-1/Top-3；不使用 Accuracy 作为主结论。")

if st.session_state.get("demo_mode"):
    truth = artifacts.truth.set_index("transformer_id")
    merged = artifacts.predictions.join(truth, on="transformer_id")
    y_true = (
        merged["reported_feeder_id"] != merged["physical_feeder_id"]
    ).astype(int)
    scores = merged["confidence"].fillna(0.0).to_numpy(dtype=float)
    precision, recall, _ = precision_recall_curve(y_true, scores)
    st.plotly_chart(
        pr_curve_figure(precision.tolist(), recall.tolist()),
        use_container_width=True,
    )
else:
    st.info("PR 曲线需要真实标签，请开启左侧的演示评价模式。")
