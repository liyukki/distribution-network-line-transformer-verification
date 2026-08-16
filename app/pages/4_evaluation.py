import pandas as pd
import streamlit as st
from sklearn.metrics import precision_recall_curve

from ltverify.plotting import confusion_matrix_figure, pr_curve_figure

st.title("模型评估")

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info("请先在主页加载运行目录。")
    st.stop()

legacy_run = (
    artifacts.manifest.get("artifact_schema_version") != 2
    or "anomaly_score" not in artifacts.predictions.columns
)
if legacy_run:
    st.warning(
        "该运行目录由旧版本生成（指标口径不兼容），"
        "旧版 PR-AUC 不作为当前口径展示，PR 曲线不可用；"
        "请重新运行 python -m ltverify run-all 后再查看。"
    )

st.plotly_chart(
    confusion_matrix_figure(artifacts.confusion_matrix.to_numpy()),
    width='stretch',
)

key_metrics = {
    key: artifacts.metrics.get(key, float("nan"))
    for key in (
        "precision",
        "recall",
        "f1",
        "pr_auc",
        "pr_auc_scored",
        "scored_coverage",
        "top1_correction_rate",
        "top2_correction_rate",
        "automatic_coverage",
        "insufficient_data_rate",
        "n_total",
        "n_actual_errors",
    )
}
if legacy_run:
    key_metrics.pop("pr_auc", None)
    key_metrics.pop("pr_auc_scored", None)
st.dataframe(pd.DataFrame([key_metrics]), width='stretch')
st.caption(
    "主指标为 Precision/Recall/F1/PR-AUC（连续 anomaly_score）与 Top-1/Top-2；"
    "pr_auc_scored 为 scored 子集上的诊断指标，须与 scored_coverage 同时解读；"
    "三馈线场景下 Top-3 不适用，不使用 Accuracy 作为主结论。"
)

if st.session_state.get("demo_mode"):
    if legacy_run:
        st.info("旧版运行目录不绘制 PR 曲线。")
    else:
        truth = artifacts.truth.set_index("transformer_id")
        merged = artifacts.predictions.join(truth, on="transformer_id")
        y_true = (
            merged["reported_feeder_id"] != merged["physical_feeder_id"]
        ).astype(int)
        scores = merged["anomaly_score"].fillna(0.0).to_numpy(dtype=float)
        precision, recall, _ = precision_recall_curve(y_true, scores)
        st.plotly_chart(
            pr_curve_figure(precision.tolist(), recall.tolist()),
            width='stretch',
        )
else:
    st.info("PR 曲线需要真实标签，请开启左侧的演示评价模式。")
