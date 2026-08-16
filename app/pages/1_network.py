import streamlit as st

from ltverify.plotting import topology_figure

st.title("网络拓扑")

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info("请先在主页加载运行目录。")
    st.stop()

demo_mode = bool(st.session_state.get("demo_mode"))
st.plotly_chart(
    topology_figure(
        artifacts.network_nodes,
        artifacts.network_edges,
        color_edges_by_feeder=demo_mode,
    ),
    use_container_width=True,
)
if demo_mode:
    st.caption("演示评价模式：线条颜色按物理馈线着色；标记颜色为电压等级。")
else:
    st.caption("普通模式：线路为中性色，不展示物理馈线归属；标记颜色为电压等级。")
with st.expander("台账与推荐对照"):
    st.dataframe(artifacts.predictions, use_container_width=True)
    if st.session_state.get("demo_mode"):
        st.subheader("物理真值（仅演示评价模式）")
        st.dataframe(artifacts.truth, use_container_width=True)
