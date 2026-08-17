import streamlit as st

from ltverify.i18n import localize_frame, normalize_locale, translate
from ltverify.plotting import topology_figure

locale = normalize_locale(st.session_state.get("locale"))
st.title(translate(locale, "network.title"))

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info(translate(locale, "common.load_home_first"))
    st.stop()

demo_mode = bool(st.session_state.get("demo_mode"))
st.plotly_chart(
    topology_figure(
        artifacts.network_nodes,
        artifacts.network_edges,
        color_edges_by_feeder=demo_mode,
        locale=locale,
    ),
    width="stretch",
)
if demo_mode:
    st.caption(translate(locale, "network.demo_caption"))
else:
    st.caption(translate(locale, "network.normal_caption"))
with st.expander(translate(locale, "network.ledger_comparison")):
    st.dataframe(localize_frame(artifacts.predictions, locale), width="stretch")
    if st.session_state.get("demo_mode"):
        st.subheader(translate(locale, "network.physical_truth"))
        st.dataframe(localize_frame(artifacts.truth, locale), width="stretch")
