import pandas as pd
import streamlit as st
from sklearn.metrics import precision_recall_curve

from ltverify.i18n import localize_frame, normalize_locale, translate
from ltverify.plotting import confusion_matrix_figure, pr_curve_figure

locale = normalize_locale(st.session_state.get("locale"))
st.title(translate(locale, "evaluation.title"))

artifacts = st.session_state.get("artifacts")
if artifacts is None:
    st.info(translate(locale, "common.load_home_first"))
    st.stop()

from ltverify.manifest import classify_artifact_schema_version

schema_state, schema_version = classify_artifact_schema_version(
    artifacts.manifest.get("artifact_schema_version")
)
if "artifact_schema_version" not in artifacts.manifest:
    schema_state = "legacy"

if schema_state == "legacy":
    st.warning(translate(locale, "evaluation.legacy_warning"))
elif schema_state == "newer":
    st.warning(translate(locale, "evaluation.newer_warning", version=schema_version))
elif schema_state == "invalid":
    st.error(
        translate(
            locale,
            "evaluation.invalid_schema",
            version=repr(artifacts.manifest.get("artifact_schema_version")),
        )
    )
    st.stop()

st.plotly_chart(
    confusion_matrix_figure(artifacts.confusion_matrix.to_numpy(), locale=locale),
    width="stretch",
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
if schema_state == "legacy":
    key_metrics.pop("pr_auc", None)
    key_metrics.pop("pr_auc_scored", None)
st.dataframe(localize_frame(pd.DataFrame([key_metrics]), locale), width="stretch")
st.caption(translate(locale, "evaluation.caption"))

if st.session_state.get("demo_mode"):
    pr_supported = (
        schema_state == "current"
        and {"transformer_id", "anomaly_score"} <= set(artifacts.predictions.columns)
        and {"transformer_id", "reported_feeder_id"} <= set(artifacts.ledger.columns)
        and {"transformer_id", "physical_feeder_id"} <= set(artifacts.truth.columns)
    )
    if not pr_supported:
        st.info(translate(locale, "evaluation.pr_unsupported"))
    else:
        labels = artifacts.ledger[["transformer_id", "reported_feeder_id"]].merge(
            artifacts.truth[["transformer_id", "physical_feeder_id"]],
            on="transformer_id",
            how="inner",
            validate="one_to_one",
        )
        merged = labels.merge(
            artifacts.predictions[["transformer_id", "anomaly_score"]],
            on="transformer_id",
            how="inner",
            validate="one_to_one",
        )
        y_true = (merged["reported_feeder_id"] != merged["physical_feeder_id"]).astype(int)
        scores = merged["anomaly_score"].fillna(0.0).to_numpy(dtype=float)
        precision, recall, _ = precision_recall_curve(y_true, scores)
        st.plotly_chart(
            pr_curve_figure(precision.tolist(), recall.tolist(), locale=locale),
            width="stretch",
        )
else:
    st.info(translate(locale, "evaluation.pr_requires_truth"))
