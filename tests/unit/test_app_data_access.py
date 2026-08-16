import json
import shutil
from pathlib import Path

import pytest

from ltverify.data_access import (
    DASHBOARD_ARTIFACT_FILES,
    ArtifactLoadError,
    discover_completed_run_dir,
    load_run_artifacts,
)
from ltverify.manifest import file_sha256
from ltverify.pipeline import run_pipeline


def _fixture_run(tmp_path: Path) -> Path:
    config = tmp_path / "small.yaml"
    config.write_text(
        f"""random_seed: 42
network:
  feeder_count: 3
  transformers_per_feeder: 3
  hv_kv: 110.0
  mv_kv: 10.0
  lv_kv: 0.4
profiles:
  start: "2026-01-01"
  days: 1
  interval_minutes: 360
  power_factor: 0.95
  pv_scale: 1.0
validation:
  voltage_min_pu: 0.90
  voltage_max_pu: 1.10
corruption:
  ledger_error_rate: 0.20
  voltage_noise_std_pu: 0.0005
  missing_rate: 0.01
  spike_rate: 0.001
  time_shift_steps: 0
  time_shift_device_rate: 0.10
scoring:
  current_score_threshold: 0.70
  margin_threshold: 0.08
  minimum_coverage: 0.80
output_root: {tmp_path.as_posix()}
""",
        encoding="utf-8",
    )
    return run_pipeline(config)


def _update_manifest_hash(run_dir: Path, name: str) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_sha256"][name] = file_sha256(run_dir / name)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_load_run_artifacts_reads_all_artifacts(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    artifacts = load_run_artifacts(run_dir)
    assert artifacts.manifest["status"] == "completed"
    assert len(artifacts.truth) == 9
    assert len(artifacts.ledger) == 9
    assert "precision" in artifacts.metrics
    assert set(artifacts.predictions.columns) >= {"transformer_id", "decision"}


def test_missing_predictions_raises_with_path_and_command(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "predictions.parquet").unlink()
    with pytest.raises(ArtifactLoadError) as excinfo:
        load_run_artifacts(run_dir)
    message = str(excinfo.value)
    assert "predictions.parquet" in message
    assert "哈希一致性校验失败" in message
    assert "python -m ltverify run-all --config configs/default.yaml" in message


def test_load_run_artifacts_rejects_tampered_metrics_before_parse(
    tmp_path: Path, monkeypatch
) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "metrics.json").write_text(
        json.dumps({"f1": 0.999999, "n_predicted": 999999}),
        encoding="utf-8",
    )
    def fail_if_parsed(*args: object, **kwargs: object) -> object:
        raise AssertionError("解析器不得在哈希校验前执行")

    monkeypatch.setattr("ltverify.data_access._read_frame", fail_if_parsed)
    with pytest.raises(ArtifactLoadError, match="哈希一致性校验失败"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_tampered_predictions_before_parse(
    tmp_path: Path, monkeypatch
) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "predictions.parquet").write_bytes(b"tampered")
    def fail_if_parsed(*args: object, **kwargs: object) -> object:
        raise AssertionError("解析器不得在哈希校验前执行")

    monkeypatch.setattr("ltverify.data_access._read_frame", fail_if_parsed)
    with pytest.raises(ArtifactLoadError, match="哈希一致性校验失败"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_non_object_manifest(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "manifest.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ArtifactLoadError, match="object"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_malformed_manifest(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "manifest.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ArtifactLoadError, match="manifest.json"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_manifest_directory(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest_path.unlink()
    manifest_path.mkdir()
    with pytest.raises(ArtifactLoadError, match="不是普通文件"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_malformed_metrics_after_hash_update(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "metrics.json").write_text("{bad", encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="metrics.json"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_malformed_csv_after_hash_update(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "truth_topology.csv").write_text("", encoding="utf-8")
    _update_manifest_hash(run_dir, "truth_topology.csv")
    with pytest.raises(ArtifactLoadError, match="truth_topology.csv"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_non_completed_status(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "running"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactLoadError, match="completed"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize("omitted_name", list(DASHBOARD_ARTIFACT_FILES.values()))
def test_load_run_artifacts_rejects_omitted_dashboard_declaration(
    tmp_path: Path, monkeypatch, omitted_name: str
) -> None:
    run_dir = _fixture_run(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_paths"].remove(omitted_name)
    manifest["output_sha256"].pop(omitted_name, None)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / omitted_name).write_bytes(b"forged")

    def fail_if_parsed(*args: object, **kwargs: object) -> object:
        raise AssertionError("解析器不得在声明校验前执行")

    monkeypatch.setattr("ltverify.data_access._read_frame", fail_if_parsed)
    with pytest.raises(ArtifactLoadError, match="未声明首页必需产物"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_allows_extra_declared_artifacts(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    extra = run_dir / "extra.txt"
    extra.write_text("extra", encoding="utf-8")
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_paths"].append("extra.txt")
    manifest["output_sha256"]["extra.txt"] = file_sha256(extra)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifacts = load_run_artifacts(run_dir)
    assert artifacts.manifest["output_paths"][-1] == "extra.txt"


def test_load_run_artifacts_rejects_semantically_invalid_metrics(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "metrics.json").write_text(
        json.dumps({"f1": "not-a-number", "n_predicted": []}),
        encoding="utf-8",
    )
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="n_predicted|f1"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_missing_prediction_columns(
    tmp_path: Path,
) -> None:
    import pandas as pd

    run_dir = _fixture_run(tmp_path)
    predictions = pd.read_parquet(run_dir / "predictions.parquet")
    predictions.drop(columns=["decision"]).to_parquet(
        run_dir / "predictions.parquet"
    )
    _update_manifest_hash(run_dir, "predictions.parquet")
    with pytest.raises(ArtifactLoadError, match="predictions.parquet|decision"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_wraps_verifier_permission_error(
    tmp_path: Path, monkeypatch
) -> None:
    run_dir = _fixture_run(tmp_path)

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("ltverify.data_access.verify_manifest_hashes", denied)
    with pytest.raises(ArtifactLoadError) as excinfo:
        load_run_artifacts(run_dir)
    assert isinstance(excinfo.value.__cause__, PermissionError)


def test_load_run_artifacts_preserves_parser_assertion_error(
    tmp_path: Path, monkeypatch
) -> None:
    run_dir = _fixture_run(tmp_path)

    def bad_parser(*args: object, **kwargs: object) -> object:
        raise AssertionError("programmer bug")

    monkeypatch.setattr("ltverify.data_access.pd.read_csv", bad_parser)
    with pytest.raises(AssertionError, match="programmer bug"):
        load_run_artifacts(run_dir)


def test_discover_completed_run_dir_skips_failed_and_incomplete(
    tmp_path: Path,
) -> None:
    source = _fixture_run(tmp_path)
    runs_root = tmp_path / "runs"
    runs_root.mkdir(exist_ok=True)
    old = runs_root / "run-20260816T000000-completed"
    shutil.copytree(source, old)
    new_failed = runs_root / "run-20260816T100000-failed"
    new_failed.mkdir()
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
    fake_file = runs_root / "run-20260816T200000-file"
    fake_file.write_text("not a dir", encoding="utf-8")
    assert Path(discover_completed_run_dir(runs_root)).resolve() == old.resolve()


def test_discover_completed_run_dir_skips_incomplete_new_completed(
    tmp_path: Path,
) -> None:
    source = _fixture_run(tmp_path)
    runs_root = tmp_path / "runs"
    runs_root.mkdir(exist_ok=True)
    old = runs_root / "run-20260816T000000-complete"
    shutil.copytree(source, old)
    incomplete = runs_root / "run-20260816T999999-incomplete"
    incomplete.mkdir()
    (incomplete / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_schema_version": 2,
                "status": "completed",
                "output_paths": ["metrics.json", "config.snapshot.yaml"],
                "output_sha256": {"metrics.json": "0" * 64, "config.snapshot.yaml": "0" * 64},
            }
        ),
        encoding="utf-8",
    )
    assert Path(discover_completed_run_dir(runs_root)).resolve() == old.resolve()


def test_discover_completed_run_dir_skips_missing_required_file(
    tmp_path: Path,
) -> None:
    source = _fixture_run(tmp_path)
    runs_root = tmp_path / "runs"
    runs_root.mkdir(exist_ok=True)
    old = runs_root / "run-20260816T000000-complete"
    shutil.copytree(source, old)
    broken = runs_root / "run-20260816T999999-broken"
    shutil.copytree(source, broken)
    (broken / "predictions.parquet").unlink()
    manifest_path = broken / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Keep the declaration, but the file is missing; discovery must skip.
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert Path(discover_completed_run_dir(runs_root)).resolve() == old.resolve()


def test_discover_completed_run_dir_selects_structurally_complete_but_tampered(
    tmp_path: Path,
) -> None:
    source = _fixture_run(tmp_path)
    runs_root = tmp_path / "runs"
    runs_root.mkdir(exist_ok=True)
    tampered = runs_root / "run-20260816T999999-tampered"
    shutil.copytree(source, tampered)
    (tampered / "metrics.json").write_text(
        json.dumps({"f1": 0.999999}), encoding="utf-8"
    )
    assert Path(discover_completed_run_dir(runs_root)).resolve() == tampered.resolve()


def test_discover_completed_run_dir_returns_empty_when_none(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    (runs_root / "run-1").mkdir()
    assert discover_completed_run_dir(runs_root) == ""
