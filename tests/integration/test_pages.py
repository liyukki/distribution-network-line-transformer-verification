from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ltverify.data_access import load_run_artifacts
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


def test_robustness_page_renders_with_real_aggregates() -> None:
    aggregates = sorted((ROOT / "runs").glob("experiments-*/experiment_aggregates.csv"))
    if not aggregates:
        pytest.skip("无实验聚合产物，跳过鲁棒性页面渲染测试")
    app_test = AppTest.from_file(
        ROOT / "app" / "pages" / "5_robustness.py", default_timeout=120
    )
    app_test.run()
    raised = [element.value for element in app_test.exception]
    assert len(app_test.exception) == 0, raised
    assert len(app_test.get("plotly_chart")) >= 1
