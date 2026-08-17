import streamlit as st

from ltverify.i18n import normalize_locale, translate
from ltverify.plotting import similarity_heatmap_figure

locale = normalize_locale(st.session_state.get("locale"))
st.title(translate(locale, "similarity.title"))

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info(translate(locale, "common.load_home_first"))
    st.stop()

mode = st.selectbox(
    translate(locale, "similarity.matrix_type"),
    ["raw", "residual", "difference"],
    format_func=lambda value: translate(locale, f"similarity.mode.{value}"),
)
observed = artifacts.observed_measurements
voltage = observed.pivot(index="timestamp", columns="transformer_id", values="voltage_pu")
if mode == "raw":
    matrix = voltage
elif mode == "residual":
    matrix = voltage.sub(voltage.median(axis=1), axis=0)
else:
    matrix = voltage.diff()
correlation = matrix.corr()
st.plotly_chart(similarity_heatmap_figure(correlation, locale=locale), width="stretch")
st.caption(translate(locale, "similarity.caption"))
