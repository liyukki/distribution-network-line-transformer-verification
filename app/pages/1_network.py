import streamlit as st

from ltverify.plotting import topology_figure

st.title("网络拓扑")

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info("请先在主页加载运行目录。")
    st.stop()

st.plotly_chart(
    topology_figure(artifacts.network_nodes, artifacts.network_edges),
    use_container_width=True,
)
st.caption("线条颜色按馈线着色（F01/F02/F03），主变连接为灰色；标记颜色为电压等级。")
with st.expander("台账与推荐对照"):
    st.dataframe(artifacts.predictions, use_container_width=True)
    if st.session_state.get("demo_mode"):
        st.subheader("物理真值（仅演示评价模式）")
        st.dataframe(artifacts.truth, use_container_width=True)
