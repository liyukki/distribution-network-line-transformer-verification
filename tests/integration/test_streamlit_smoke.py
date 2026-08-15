from pathlib import Path

from streamlit.testing.v1 import AppTest

from ltverify.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[2]


def test_streamlit_app_loads_run_without_errors(monkeypatch) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(
        ROOT / "app" / "streamlit_app.py", default_timeout=120
    )
    app_test.run()
    assert len(app_test.exception) == 0
    titles = "".join(element.value for element in app_test.title)
    assert "线变关系智能校验" in titles
