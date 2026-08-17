import logging
import os
from pathlib import Path

import streamlit as st

from ltverify.data_access import (
    ArtifactLoadError,
    RunArtifacts,
    discover_completed_run_dir,
    load_run_artifacts,
)
from ltverify.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    normalize_locale,
    translate,
    translate_value,
)

LOGGER = logging.getLogger(__name__)
initial_locale = normalize_locale(st.session_state.get("locale", DEFAULT_LOCALE))
st.set_page_config(page_title=translate(initial_locale, "app.title"), layout="wide")


def _default_run_dir() -> str:
    env = os.environ.get("LTVERIFY_RUN_DIR")
    if env:
        return env
    return discover_completed_run_dir()


with st.sidebar:
    locale = st.selectbox(
        translate(initial_locale, "app.language"),
        options=SUPPORTED_LOCALES,
        index=SUPPORTED_LOCALES.index(initial_locale),
        format_func=lambda option: translate(option, f"language.{option}"),
        key="locale",
    )
    locale = normalize_locale(locale)
    run_dir = st.text_input(translate(locale, "app.run_directory"), value=_default_run_dir())
    demo_mode = st.toggle(translate(locale, "app.demo_mode"), value=False)
    st.caption(translate(locale, "app.demo_caption"))

st.title(translate(locale, "app.title"))

if not run_dir:
    st.info(translate(locale, "app.missing_run"))
    st.stop()


def _load_run(directory: str) -> RunArtifacts:
    return load_run_artifacts(Path(directory))


try:
    artifacts = _load_run(run_dir)
except ArtifactLoadError as exc:
    LOGGER.warning("Artifact loading failed: %s", exc)
    if locale == "zh-CN":
        st.error(translate(locale, "app.artifact_load_failed", detail=str(exc)))
    else:
        st.error(translate(locale, "app.artifact_load_failed_generic"))
    st.stop()

st.session_state["artifacts"] = artifacts
st.session_state["demo_mode"] = demo_mode

metrics = artifacts.metrics


def _metric_text(key: str) -> str:
    value = metrics.get(key)
    if value is None:
        return translate(locale, "not_applicable")
    return f"{float(value):.3f}"


columns = st.columns(5)
columns[0].metric(translate(locale, "app.predicted_alerts"), int(metrics.get("n_predicted", 0)))
columns[1].metric("F1", _metric_text("f1"))
columns[2].metric(translate(locale, "app.top1_rate"), _metric_text("top1_correction_rate"))
columns[3].metric(translate(locale, "app.automatic_coverage"), _metric_text("automatic_coverage"))
columns[4].metric(
    translate(locale, "app.run_status"),
    str(translate_value(locale, "status", artifacts.manifest.get("status", "unknown"))),
)
run_label = artifacts.run_dir.name
st.caption(
    f"{translate(locale, 'app.run_identifier', run_id=run_label)}；"
    f"{translate(locale, 'app.hash_verified')}"
)

pages = st.navigation(
    [
        st.Page("pages/1_network.py", title=translate(locale, "nav.network")),
        st.Page("pages/2_diagnosis.py", title=translate(locale, "nav.diagnosis")),
        st.Page("pages/3_similarity.py", title=translate(locale, "nav.similarity")),
        st.Page("pages/4_evaluation.py", title=translate(locale, "nav.evaluation")),
        st.Page("pages/5_robustness.py", title=translate(locale, "nav.robustness")),
    ]
)
pages.run()
