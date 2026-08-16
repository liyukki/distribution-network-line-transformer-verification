from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from ltverify.data_access import RunArtifacts, load_run_artifacts
from ltverify.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[2]

DATA_PAGES = [
    "1_network.py",
    "2_diagnosis.py",
    "3_similarity.py",
    "4_evaluation.py",
]


@pytest.fixture(scope="module")
def run_dir() -> Path:
    return run_pipeline(Path("tests/fixtures/small_config.yaml"))


def test_data_pages_render_without_exceptions(run_dir: Path) -> None:
    artifacts = load_run_artifacts(run_dir)
    for page in DATA_PAGES:
        app_test = AppTest.from_file(
            ROOT / "app" / "pages" / page, default_timeout=120
        )
        app_test.session_state["artifacts"] = artifacts
        app_test.session_state["demo_mode"] = True
        app_test.run()
        raised = [element.value for element in app_test.exception]
        assert len(app_test.exception) == 0, f"{page} raised: {raised}"


def test_robustness_page_renders_with_tmp_aggregates(tmp_path: Path) -> None:
    metrics = [
        "precision",
        "recall",
        "f1",
        "top1_correction_rate",
        "top2_correction_rate",
        "automatic_coverage",
        "convergence_rate",
    ]
    aggregates = pd.DataFrame(
        {
            "family": ["missing_rate", "missing_rate"],
            "value": ["0.0", "0.1"],
            **{f"mean_{metric}": [0.9, 0.8] for metric in metrics},
            **{f"std_{metric}": [0.05, 0.06] for metric in metrics},
        }
    )
    csv_path = tmp_path / "experiment_aggregates.csv"
    aggregates.to_csv(csv_path, index=False)
    app_test = AppTest.from_file(
        ROOT / "app" / "pages" / "5_robustness.py", default_timeout=120
    )
    app_test.run()
    app_test.text_input[0].set_value(str(csv_path))
    app_test.run()
    raised = [element.value for element in app_test.exception]
    assert len(app_test.exception) == 0, raised
    assert len(app_test.get("plotly_chart")) >= 1


def test_legacy_run_page_4_shows_warning_without_crash(
    run_dir: Path, monkeypatch
) -> None:
    artifacts = load_run_artifacts(run_dir)
    legacy_predictions = artifacts.predictions.drop(
        columns=["anomaly_score"], errors="ignore"
    )
    legacy_manifest = dict(artifacts.manifest)
    legacy_manifest["artifact_schema_version"] = 1
    legacy = RunArtifacts(
        run_dir=artifacts.run_dir,
        manifest=legacy_manifest,
        truth=artifacts.truth,
        ledger=artifacts.ledger,
        observed_measurements=artifacts.observed_measurements,
        feeder_measurements=artifacts.feeder_measurements,
        candidate_features=artifacts.candidate_features,
        predictions=legacy_predictions,
        metrics=dict(artifacts.metrics),
        confusion_matrix=artifacts.confusion_matrix,
        network_nodes=artifacts.network_nodes,
        network_edges=artifacts.network_edges,
    )
    app_test = AppTest.from_file(
        ROOT / "app" / "pages" / "4_evaluation.py", default_timeout=120
    )
    app_test.session_state["artifacts"] = legacy
    app_test.session_state["demo_mode"] = True
    app_test.run()
    raised = [element.value for element in app_test.exception]
    assert len(app_test.exception) == 0, raised
    warnings = [element.value for element in app_test.warning]
    assert any("不兼容" in text for text in warnings)
    # 旧版运行不绘制 PR 曲线：只有混淆矩阵一个图表
    assert len(app_test.get("plotly_chart")) == 1
