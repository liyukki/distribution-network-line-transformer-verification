import json
from pathlib import Path

from ltverify.pipeline import run_pipeline

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
]


def test_small_pipeline_writes_all_artifacts() -> None:
    config = Path("tests/fixtures/small_config.yaml")
    run_dir = run_pipeline(config)
    assert run_dir.exists()
    for name in EXPECTED_ARTIFACTS:
        assert (run_dir / name).exists(), f"missing artifact: {name}"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "precision" in metrics
    assert "recall" in metrics
    assert "top1_correction_rate" in metrics
