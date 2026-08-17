import json
import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ltverify.manifest import file_sha256
from ltverify.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[2]


def _update_manifest_hash(run_dir: Path, name: str) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_sha256"][name] = file_sha256(run_dir / name)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _copy_run_to(tmp_path: Path, run_dir: Path, name: str) -> Path:
    target = tmp_path / "runs" / name
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir, target, dirs_exist_ok=True)
    return target


def test_streamlit_app_loads_run_without_errors(monkeypatch) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    titles = "".join(element.value for element in app_test.title)
    assert "线变关系智能校验" in titles


def test_streamlit_rejects_tampered_metrics(monkeypatch) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    (run_dir / "metrics.json").write_text(
        json.dumps({"f1": 0.999999, "n_predicted": 999999}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1
    page_text = " ".join(
        [element.value for element in app_test.markdown]
        + [element.value for element in app_test.metric]
    )
    assert "0.999999" not in page_text
    assert "999999" not in page_text


def test_streamlit_rejects_non_object_manifest(monkeypatch) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    (run_dir / "manifest.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1


def test_streamlit_rejects_semantically_invalid_metrics(
    monkeypatch,
) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    (run_dir / "metrics.json").write_text(
        json.dumps({"f1": "not-a-number", "n_predicted": []}),
        encoding="utf-8",
    )
    _update_manifest_hash(run_dir, "metrics.json")
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1


def test_streamlit_hides_absolute_run_path(monkeypatch) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    captions = [element.value for element in getattr(app_test, "caption", [])]
    text = " ".join([element.value for element in app_test.markdown] + captions)
    assert str(run_dir.resolve()) not in text
    assert run_dir.name in text


def test_streamlit_rejects_out_of_range_f1(monkeypatch) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["f1"] = 999.0
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1
    page_text = " ".join(
        [element.value for element in app_test.markdown]
        + [element.value for element in app_test.metric]
    )
    assert "999.000" not in page_text


def test_streamlit_rejects_missing_prediction_column(monkeypatch) -> None:
    import pandas as pd

    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    predictions = pd.read_parquet(run_dir / "predictions.parquet")
    predictions.drop(columns=["decision"]).to_parquet(run_dir / "predictions.parquet")
    _update_manifest_hash(run_dir, "predictions.parquet")
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1


def test_streamlit_shows_domain_error_for_list_valued_decision(
    monkeypatch,
) -> None:
    import pandas as pd

    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    predictions = pd.read_parquet(run_dir / "predictions.parquet")
    predictions["decision"] = [
        [str(value)] for value in predictions["decision"]
    ]
    predictions.to_parquet(run_dir / "predictions.parquet")
    _update_manifest_hash(run_dir, "predictions.parquet")
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1
    error_text = " ".join(element.value for element in app_test.error)
    assert "decision" in error_text


def test_streamlit_rejects_malformed_metrics_after_hash_update(
    monkeypatch,
) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    (run_dir / "metrics.json").write_text("{bad", encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1


def test_streamlit_auto_discovery_skips_failed_run(tmp_path: Path, monkeypatch) -> None:
    source_run = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    old_run = _copy_run_to(tmp_path, source_run, "run-20260816T000000-completed")
    new_failed = tmp_path / "runs" / "run-20260816T100000-failed"
    new_failed.mkdir(parents=True)
    (new_failed / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_schema_version": 2,
                "status": "failed",
                "output_paths": [],
                "output_sha256": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert Path(app_test.text_input[0].value).resolve() == old_run.resolve()


def test_streamlit_rerun_revalidates_after_artifact_change(
    monkeypatch,
) -> None:
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(run_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) == 0

    (run_dir / "metrics.json").write_text(
        json.dumps({"f1": 0.999999, "n_predicted": 999999}),
        encoding="utf-8",
    )
    app_test.run()
    assert len(app_test.exception) == 0
    assert len(app_test.error) >= 1
    page_text = " ".join(
        [element.value for element in app_test.markdown]
        + [element.value for element in app_test.metric]
    )
    assert "999999" not in page_text
    assert "0.999999" not in page_text


def test_streamlit_explicit_bad_dir_is_not_replaced(tmp_path: Path, monkeypatch) -> None:
    bad_dir = tmp_path / "bad-run"
    bad_dir.mkdir()
    monkeypatch.setenv("LTVERIFY_RUN_DIR", str(bad_dir.resolve()))
    app_test = AppTest.from_file(ROOT / "app" / "streamlit_app.py", default_timeout=120)
    app_test.run()
    assert len(app_test.exception) == 0
    errors = " ".join(element.value for element in app_test.error)
    assert str(bad_dir.resolve()) in errors
