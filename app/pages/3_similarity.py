import streamlit as st

from ltverify.plotting import similarity_heatmap_figure

st.title("相似度矩阵")

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info("请先在主页加载运行目录。")
    st.stop()

mode = st.selectbox("矩阵类型", ["原始电压", "去公共趋势残差", "一阶差分"])
observed = artifacts.observed_measurements
voltage = observed.pivot(index="timestamp", columns="transformer_id", values="voltage_pu")
if mode == "原始电压":
    matrix = voltage
elif mode == "去公共趋势残差":
    matrix = voltage.sub(voltage.median(axis=1), axis=0)
else:
    matrix = voltage.diff()
correlation = matrix.corr()
st.plotly_chart(similarity_heatmap_figure(correlation), width="stretch")
st.caption("矩阵按所选模式在共同有效时间点上计算 Pearson 相关系数。")
