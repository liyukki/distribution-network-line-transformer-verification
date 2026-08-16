import json
from pathlib import Path

import pandas as pd
import pytest

from ltverify.manifest import verify_manifest_hashes
from ltverify.pipeline import run_pipeline
from ltverify.simulation import SimulationResult

EXPECTED_ARTIFACTS = [
    "config.snapshot.yaml",
    "manifest.json",
    "truth_topology.csv",
    "reported_ledger.csv",
    "transformer_measurements.parquet",
    "feeder_measurements.parquet",
    "observed_measurements.parquet",
    "candidate_features.parquet",
    "predictions.parquet",
    "metrics.json",
    "confusion_matrix.csv",
    "network_nodes.csv",
    "network_edges.csv",
    "simulation_validation.csv",
]


def test_small_pipeline_writes_all_artifacts() -> None:
    config = Path("tests/fixtures/small_config.yaml")
    run_dir = run_pipeline(config)
    assert run_dir.exists()
    for name in EXPECTED_ARTIFACTS:
        assert (run_dir / name).exists(), f"missing artifact: {name}"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["artifact_schema_version"] == 2
    assert set(manifest["output_sha256"]) == set(EXPECTED_ARTIFACTS) - {"manifest.json"}
    verify_manifest_hashes(manifest, run_dir)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "precision" in metrics
    assert "recall" in metrics
    assert "top1_correction_rate" in metrics


def test_pipeline_stops_on_critical_violation(monkeypatch) -> None:
    from ltverify import pipeline as pipeline_module

    def violating_simulate(*args: object, **kwargs: object) -> SimulationResult:
        return SimulationResult(
            transformer_measurements=pd.DataFrame(),
            feeder_measurements=pd.DataFrame(),
            failures=pd.DataFrame(),
            validation=pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-01-01 00:00"),
                        "converged": True,
                        "voltage_min_pu": 0.85,
                        "voltage_max_pu": 1.0,
                        "maximum_transformer_loading_percent": 150.0,
                        "absolute_power_balance_error_mw": 1e-9,
                        "violation_type": "transformer_overload",
                        "message": "transformer overload: trafo 1 at 150.0%",
                        "severity": "critical",
                    }
                ]
            ),
        )

    monkeypatch.setattr(
        pipeline_module, "simulate_time_series", violating_simulate
    )
    with pytest.raises(RuntimeError, match="critical physical violations"):
        run_pipeline(Path("tests/fixtures/small_config.yaml"))


def test_base_case_warning_violations_do_not_stop_pipeline(monkeypatch) -> None:
    from ltverify import pipeline as pipeline_module
    from ltverify.validation import PowerFlowValidation

    def warning_static(*args: object, **kwargs: object) -> PowerFlowValidation:
        return PowerFlowValidation(
            converged=True,
            voltage_min_pu=0.90,
            voltage_max_pu=1.05,
            absolute_power_balance_error_mw=1e-9,
            violations=("transformer overload: trafo 1 at 110.0%",),
            severity="warning",
            violation_types=("transformer_overload",),
        )

    monkeypatch.setattr(pipeline_module, "run_static_validation", warning_static)
    run_dir = run_pipeline(Path("tests/fixtures/small_config.yaml"))
    assert run_dir.exists()
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["base_case_violation_count"] == 1
    assert metrics["base_case_violation_types"] == ["transformer_overload"]
    assert metrics["base_case_violations"] == [
        "transformer overload: trafo 1 at 110.0%"
    ]
    assert metrics["base_case_severity"] == "warning"


def test_critical_base_case_with_terminate_off_is_recorded(
    tmp_path: Path, monkeypatch
) -> None:
    from ltverify import pipeline as pipeline_module
    from ltverify.validation import PowerFlowValidation

    def critical_static(*args: object, **kwargs: object) -> PowerFlowValidation:
        return PowerFlowValidation(
            converged=True,
            voltage_min_pu=0.90,
            voltage_max_pu=1.05,
            absolute_power_balance_error_mw=1e-9,
            violations=("transformer overload: trafo 1 at 150.0%",),
            severity="critical",
            violation_types=("transformer_overload",),
        )

    config = tmp_path / "relaxed.yaml"
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
  terminate_on_critical: false
  critical_violation_types: [power_balance, voltage_out_of_bounds, transformer_overload]
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
output_root: {tmp_path.as_posix()}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline_module, "run_static_validation", critical_static)
    run_dir = run_pipeline(config)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["base_case_severity"] == "critical"
    assert metrics["base_case_violation_count"] == 1
    assert metrics["base_case_violations"] == [
        "transformer overload: trafo 1 at 150.0%"
    ]
