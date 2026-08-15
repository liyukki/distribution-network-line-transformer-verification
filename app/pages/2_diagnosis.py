import streamlit as st

from ltverify.plotting import candidate_score_bars_figure, voltage_curves_figure

st.title("配变诊断")

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info("请先在主页加载运行目录。")
    st.stop()

transformer_id = st.selectbox(
    "选择配变", artifacts.predictions["transformer_id"].tolist()
)
prediction = artifacts.predictions[
    artifacts.predictions["transformer_id"] == transformer_id
].iloc[0]
st.markdown(
    f"**判定**: {prediction['decision']}　|　"
    f"**台账馈线**: {prediction['reported_feeder_id']}　|　"
    f"**推荐馈线**: {prediction['recommended_feeder_id']}　|　"
    f"**置信度**: {prediction['confidence']:.3f}　|　"
    f"**覆盖率**: {prediction['coverage']:.3f}"
)

observed = artifacts.observed_measurements
device = observed[observed["transformer_id"] == transformer_id]
voltage_wide = device.pivot(
    index="timestamp", columns="transformer_id", values="voltage_pu"
)
st.plotly_chart(
    voltage_curves_figure(voltage_wide, [transformer_id]),
    use_container_width=True,
)

scores = artifacts.candidate_features[
    artifacts.candidate_features["transformer_id"] == transformer_id
]
st.plotly_chart(
    candidate_score_bars_figure(scores, transformer_id),
    use_container_width=True,
)

quality = device["data_quality_flag"].value_counts().to_dict()
if quality:
    st.warning(f"数据质量标记: {quality}")
else:
    st.info("该配变量测未发现质量标记。")
