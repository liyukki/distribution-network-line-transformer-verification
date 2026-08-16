import json
from pathlib import Path

from ltverify.pipeline import run_pipeline
from ltverify.report import generate_default_summary


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
  power_balance_tolerance_mw: 0.000001
  transformer_loading_limit_percent: 100.0
  terminate_on_critical: true
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
  minimum_pairs: 16
  rolling_window: 24
  event_quantile: 0.90
  interpolation_limit: 2
  evidence_weight_threshold: 0.5
output_root: {tmp_path.as_posix()}
""",
        encoding="utf-8",
    )
    return run_pipeline(config)


def test_generate_default_summary_from_artifacts(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    output = tmp_path / "summary.json"
    generate_default_summary(run_dir, output)
    summary = json.loads(output.read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == manifest["run_id"]
    assert summary["status"] == "completed"
    assert summary["metrics"]["f1"] == metrics["f1"]
    assert "f1" in summary["baseline_comparison"]
    assert summary["failure_boundary"]["same_feeder_pair_count"] > 0
    assert summary["failure_boundary"]["cross_feeder_pair_count"] > 0
