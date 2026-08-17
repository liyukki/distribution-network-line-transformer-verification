import streamlit as st

from ltverify.i18n import normalize_locale, translate, translate_value
from ltverify.plotting import candidate_score_bars_figure, voltage_curves_figure

locale = normalize_locale(st.session_state.get("locale"))
st.title(translate(locale, "diagnosis.title"))

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info(translate(locale, "common.load_home_first"))
    st.stop()

transformer_id = st.selectbox(
    translate(locale, "diagnosis.select_transformer"),
    artifacts.predictions["transformer_id"].tolist(),
)
prediction = artifacts.predictions[artifacts.predictions["transformer_id"] == transformer_id].iloc[
    0
]
st.markdown(
    f"**{translate(locale, 'diagnosis.decision')}**: "
    f"{translate_value(locale, 'decision', prediction['decision'])}　|　"
    f"**{translate(locale, 'diagnosis.reported_feeder')}**: "
    f"{prediction['reported_feeder_id']}　|　"
    f"**{translate(locale, 'diagnosis.recommended_feeder')}**: "
    f"{prediction['recommended_feeder_id']}　|　"
    f"**{translate(locale, 'diagnosis.confidence')}**: {prediction['confidence']:.3f}　|　"
    f"**{translate(locale, 'diagnosis.coverage')}**: {prediction['coverage']:.3f}"
)

observed = artifacts.observed_measurements
device = observed[observed["transformer_id"] == transformer_id]
voltage_wide = device.pivot(index="timestamp", columns="transformer_id", values="voltage_pu")
st.plotly_chart(
    voltage_curves_figure(voltage_wide, [transformer_id], locale=locale),
    width="stretch",
)

scores = artifacts.candidate_features[
    artifacts.candidate_features["transformer_id"] == transformer_id
]
st.plotly_chart(
    candidate_score_bars_figure(scores, transformer_id, locale=locale),
    width="stretch",
)

quality = device["data_quality_flag"].value_counts().to_dict()
localized_quality = {
    str(translate_value(locale, "data_quality", key)): value for key, value in quality.items()
}
st.warning(translate(locale, "diagnosis.data_quality", quality=localized_quality))
