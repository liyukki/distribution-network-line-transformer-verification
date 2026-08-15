from pathlib import Path

import pytest

from ltverify.data_access import ArtifactLoadError, load_run_artifacts
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
    assert str((run_dir / "predictions.parquet").resolve()) in message
    assert "python -m ltverify run-all --config configs/default.yaml" in message
