from pathlib import Path

import pandas as pd

from ltverify.experiments import run_experiments

SUMMARY_COLUMNS = [
    "case_id",
    "family",
    "value",
    "seed",
    "precision",
    "recall",
    "f1",
    "top1_correction_rate",
    "top2_correction_rate",
    "automatic_coverage",
    "runtime_seconds",
    "convergence_rate",
    "violation_count",
    "voltage_min_pu",
    "voltage_max_pu",
    "maximum_transformer_loading_percent",
    "status",
]


def _small_base_yaml(tmp_path: Path) -> Path:
    base = tmp_path / "small_base.yaml"
    base.write_text(
        f"""
random_seed: 42
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
  ledger_error_rate: 0.10
  voltage_noise_std_pu: 0.0005
  missing_rate: 0.01
  spike_rate: 0.001
  time_shift_steps: 0
  time_shift_device_rate: 0.10
scoring:
  current_score_threshold: 0.70
  margin_threshold: 0.08
  minimum_coverage: 0.80
output_root: {tmp_path / "runs"}
""".replace("\\", "/"),
        encoding="utf-8",
    )
    return base


def test_two_case_smoke_runner(tmp_path: Path) -> None:
    base = _small_base_yaml(tmp_path)
    robustness = tmp_path / "robustness.yaml"
    robustness.write_text(
        f"""base_config: {base.as_posix()}
experiments:
  ledger_error_rate: [0.10]
ablation_features: []
seeds: [42, 43]
""",
        encoding="utf-8",
    )
    output_dir = tmp_path / "experiments"
    run_experiments(robustness, output_dir)
    summary = pd.read_csv(output_dir / "experiment_summary.csv")
    assert set(SUMMARY_COLUMNS) <= set(summary.columns)
    assert len(summary) == 2
    assert (summary["status"] == "completed").all()
    aggregates = pd.read_csv(output_dir / "experiment_aggregates.csv")
    assert "failure_count" in aggregates.columns
    assert len(aggregates) == 1
