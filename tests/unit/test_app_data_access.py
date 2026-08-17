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


def _fixture_run(
    tmp_path: Path,
    *,
    ledger_error_rate: float = 0.20,
) -> Path:
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
  ledger_error_rate: {ledger_error_rate}
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


def test_load_run_artifacts_accepts_valid_zero_error_run(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path, ledger_error_rate=0.0)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["n_actual_errors"] == 0
    assert metrics["topk_applicable"]["top1"] is True
    assert metrics["top1_correction_rate"] is None
    assert metrics["top1_evaluation_coverage"] is None
    assert metrics["top1_evaluated_count"] == 0

    artifacts = load_run_artifacts(run_dir)
    assert artifacts.metrics["n_actual_errors"] == 0


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


@pytest.mark.parametrize(
    "bad_output_paths",
    [
        [[]],
        [{}],
        [1],
        [None],
        ["metrics.json", ["predictions.parquet"]],
    ],
)
def test_load_run_artifacts_rejects_non_string_output_path_elements(
    tmp_path: Path, bad_output_paths: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_paths"] = bad_output_paths
    manifest["output_sha256"] = {}
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(ArtifactLoadError, match="output_paths"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "bad_output_paths",
    [
        [[]],
        [{}],
        [1],
        [None],
        ["metrics.json", ["predictions.parquet"]],
    ],
)
def test_discover_completed_run_dir_skips_non_string_output_path_elements(
    tmp_path: Path, bad_output_paths: object
) -> None:
    source = _fixture_run(tmp_path)
    runs_root = tmp_path / "runs"
    runs_root.mkdir(exist_ok=True)
    old = runs_root / "run-20260816T000000-complete"
    shutil.copytree(source, old)
    bad = runs_root / "run-20260816T999999-bad"
    bad.mkdir()
    (bad / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_schema_version": 2,
                "status": "completed",
                "output_paths": bad_output_paths,
                "output_sha256": {},
            }
        ),
        encoding="utf-8",
    )
    assert Path(discover_completed_run_dir(runs_root)).resolve() == old.resolve()


def test_discover_completed_run_dir_skips_duplicate_output_paths(
    tmp_path: Path,
) -> None:
    source = _fixture_run(tmp_path)
    runs_root = tmp_path / "runs"
    runs_root.mkdir(exist_ok=True)
    old = runs_root / "run-20260816T000000-complete"
    shutil.copytree(source, old)
    bad = runs_root / "run-20260816T999999-duplicate"
    shutil.copytree(source, bad)
    manifest_path = bad / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_paths"].append("config.snapshot.yaml")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert Path(discover_completed_run_dir(runs_root)).resolve() == old.resolve()


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


DISPLAYED_REQUIRED_RATIOS = (
    "precision",
    "recall",
    "f1",
    "automatic_coverage",
    "insufficient_data_rate",
    "scored_coverage",
)

DISPLAYED_NULLABLE_RATIOS = (
    "pr_auc",
    "pr_auc_scored",
    "top1_correction_rate",
    "top2_correction_rate",
    "top3_correction_rate",
    "top1_evaluation_coverage",
    "top2_evaluation_coverage",
    "top3_evaluation_coverage",
)

INVALID_RATIOS = (-0.01, 1.01, "0.8")


@pytest.mark.parametrize("field", DISPLAYED_REQUIRED_RATIOS)
@pytest.mark.parametrize("value", INVALID_RATIOS)
def test_load_run_artifacts_rejects_invalid_displayed_required_ratio(
    tmp_path: Path, field: str, value: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics[field] = value
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match=field):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize("field", DISPLAYED_NULLABLE_RATIOS)
@pytest.mark.parametrize("value", INVALID_RATIOS)
def test_load_run_artifacts_rejects_invalid_displayed_nullable_ratio(
    tmp_path: Path, field: str, value: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics[field] = value
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match=field):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_missing_displayed_required_ratio(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics.pop("precision")
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="precision"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda m: m.update({"pr_auc_applicable": "yes"}),
        lambda m: m.update({"pr_auc_applicable": True, "pr_auc": None}),
        lambda m: m.update({"pr_auc_applicable": False, "pr_auc": 0.5}),
        lambda m: m.update({"pr_auc_scored_applicable": 1}),
        lambda m: m.update({"pr_auc_scored_applicable": True, "pr_auc_scored": None}),
        lambda m: m.update({"pr_auc_scored_applicable": False, "pr_auc_scored": 0.5}),
        lambda m: m.update({"topk_applicable": []}),
        lambda m: m.update({"topk_applicable": {"top1": True}}),
        lambda m: m.update({"topk_applicable": {"top1": 1, "top2": True, "top3": False}}),
    ],
)
def test_load_run_artifacts_rejects_invalid_applicability_metadata(
    tmp_path: Path, mutator: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    mutator(metrics)
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="pr_auc|topk|applicable"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda m: m.update({"top1_evaluated_count": m["n_actual_errors"] + 1}),
        lambda m: m.update({"top1_evaluation_coverage": 1.0}),
        lambda m: m.update(
            {
                "candidate_feeder_count": 1,
                "topk_applicable": {"top1": True, "top2": False, "top3": False},
                "top2_evaluated_count": 0,
                "top2_evaluation_coverage": None,
                "top2_correction_rate": None,
                "top3_evaluated_count": 0,
                "top3_evaluation_coverage": None,
                "top3_correction_rate": None,
            }
        ),
        lambda m: m.update(
            {"top1_evaluated_count": 0, "top1_correction_rate": 0.5}
        ),
    ],
)
def test_loader_rejects_inconsistent_topk_metadata(
    tmp_path: Path,
    mutator: object,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics_path = run_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    mutator(metrics)
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="top1|Top-1|applicable|coverage"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda m: m.update({"n_actual_correct": True}),
        lambda m: m.update({"n_actual_correct": -1}),
        lambda m: m.update({"n_actual_correct": 1.5}),
        lambda m: m.update({"n_actual_correct": 1, "n_actual_errors": 1, "n_total": 5}),
        lambda m: m.update({"top1_evaluated_count": -1}),
        lambda m: m.update({"top2_evaluated_count": True}),
        lambda m: m.update({"excluded_candidate_count": -1}),
        lambda m: m.update({"candidate_feeder_count": 0}),
        lambda m: m.update({"candidate_feeder_count": True}),
        lambda m: m.update({"scored_coverage": 0.9, "insufficient_data_rate": 0.0}),
    ],
)
def test_load_run_artifacts_rejects_invalid_count_and_derived_relations(
    tmp_path: Path, mutator: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    mutator(metrics)
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(
        ArtifactLoadError,
        match="n_actual_correct|evaluated|excluded|candidate|scored_coverage|insufficient",
    ):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "value",
    [-0.01, 1.01, 999.0, "0.8", True, float("nan"), float("inf")],
)
def test_load_run_artifacts_rejects_invalid_f1(tmp_path: Path, value: object) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["f1"] = value
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="f1"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "value",
    [-0.01, 1.01, 999.0, "0.8", True, float("nan"), float("inf")],
)
def test_load_run_artifacts_rejects_invalid_top1_correction_rate(
    tmp_path: Path, value: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["top1_correction_rate"] = value
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="top1_correction_rate"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "value",
    [-0.01, 1.01, 999.0, "0.8", True, float("nan"), float("inf")],
)
def test_load_run_artifacts_rejects_invalid_automatic_coverage(
    tmp_path: Path, value: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["automatic_coverage"] = value
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="automatic_coverage"):
        load_run_artifacts(run_dir)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda m: m.update({"n_predicted": True}),
        lambda m: m.update({"n_predicted": -1}),
        lambda m: m.update({"n_predicted": 1.5}),
        lambda m: m.update({"n_predicted": "3"}),
        lambda m: m.update({"n_total": 0}),
        lambda m: m.update({"n_total": True}),
        lambda m: m.update({"n_predicted": 10, "n_total": 5}),
        lambda m: m.update({"n_actual_errors": -1}),
        lambda m: m.update({"n_actual_errors": 999, "n_total": 5}),
    ],
)
def test_load_run_artifacts_rejects_invalid_count_relations(
    tmp_path: Path, mutator: object
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    mutator(metrics)
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="n_predicted|n_total|n_actual_errors"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_n_total_mismatch_with_predictions(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["n_total"] = 999
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="n_total"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_coverage_mismatch_with_predicted_count(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["n_predicted"] = 0
    metrics["automatic_coverage"] = 1.0
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="automatic_coverage|n_predicted"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_f1_mismatch_with_confusion_matrix(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["f1"] = 1.0
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="f1|confusion"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_transformer_id_set_mismatch(
    tmp_path: Path,
) -> None:
    import pandas as pd

    run_dir = _fixture_run(tmp_path)
    predictions = pd.read_parquet(run_dir / "predictions.parquet")
    predictions = predictions[
        predictions["transformer_id"] != predictions["transformer_id"].iloc[0]
    ]
    predictions.to_parquet(run_dir / "predictions.parquet")
    _update_manifest_hash(run_dir, "predictions.parquet")
    with pytest.raises(ArtifactLoadError, match="transformer_id"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_invalid_prediction_boolean_consistency(
    tmp_path: Path,
) -> None:
    import pandas as pd

    run_dir = _fixture_run(tmp_path)
    predictions = pd.read_parquet(run_dir / "predictions.parquet")
    predictions["predicted_is_mislinked"] = 1
    predictions.to_parquet(run_dir / "predictions.parquet")
    _update_manifest_hash(run_dir, "predictions.parquet")
    with pytest.raises(ArtifactLoadError, match="predicted_is_mislinked"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_semantically_invalid_metrics(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics["f1"] = "not-a-number"
    metrics["n_predicted"] = []
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    _update_manifest_hash(run_dir, "metrics.json")
    with pytest.raises(ArtifactLoadError, match="n_predicted|f1"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_rejects_missing_prediction_columns(
    tmp_path: Path,
) -> None:
    import pandas as pd

    run_dir = _fixture_run(tmp_path)
    predictions = pd.read_parquet(run_dir / "predictions.parquet")
    predictions.drop(columns=["decision"]).to_parquet(run_dir / "predictions.parquet")
    _update_manifest_hash(run_dir, "predictions.parquet")
    with pytest.raises(ArtifactLoadError, match="predictions.parquet|decision"):
        load_run_artifacts(run_dir)


def test_load_run_artifacts_wraps_verifier_permission_error(tmp_path: Path, monkeypatch) -> None:
    run_dir = _fixture_run(tmp_path)

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("ltverify.data_access.verify_manifest_hashes", denied)
    with pytest.raises(ArtifactLoadError) as excinfo:
        load_run_artifacts(run_dir)
    assert isinstance(excinfo.value.__cause__, PermissionError)


def test_load_run_artifacts_preserves_parser_assertion_error(tmp_path: Path, monkeypatch) -> None:
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
    (tampered / "metrics.json").write_text(json.dumps({"f1": 0.999999}), encoding="utf-8")
    assert Path(discover_completed_run_dir(runs_root)).resolve() == tampered.resolve()


def test_discover_completed_run_dir_returns_empty_when_none(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    (runs_root / "run-1").mkdir()
    assert discover_completed_run_dir(runs_root) == ""
