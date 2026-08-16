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
