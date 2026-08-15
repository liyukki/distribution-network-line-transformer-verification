"""Dashboard artifact loading with actionable error messages."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ltverify.io import read_json


class ArtifactLoadError(RuntimeError):
    """Raised when a required run artifact is missing or unreadable."""


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    manifest: dict[str, object]
    truth: pd.DataFrame
    ledger: pd.DataFrame
    observed_measurements: pd.DataFrame
    feeder_measurements: pd.DataFrame
    candidate_features: pd.DataFrame
    predictions: pd.DataFrame
    metrics: dict[str, float | int]
    confusion_matrix: pd.DataFrame
    network_nodes: pd.DataFrame
    network_edges: pd.DataFrame


_REPAIR_HINT = "请运行 python -m ltverify run-all --config configs/default.yaml"


def _read_frame(run_dir: Path, name: str) -> pd.DataFrame:
    path = run_dir / name
    if not path.exists():
        raise ArtifactLoadError(
            f"缺少产物文件: {path.resolve()}；{_REPAIR_HINT}"
        )
    if name.endswith(".csv"):
        frame = pd.read_csv(path)
        if "index" in frame.columns:
            frame = frame.set_index("index")
        return frame
    return pd.read_parquet(path)


def _read_metrics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "metrics.json"
    if not path.exists():
        raise ArtifactLoadError(f"缺少产物文件: {path.resolve()}；{_REPAIR_HINT}")
    return read_json(path)


def load_run_artifacts(run_dir: Path) -> RunArtifacts:
    """Load every artifact of one completed run."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ArtifactLoadError(
            f"缺少产物文件: {manifest_path.resolve()}；{_REPAIR_HINT}"
        )
    manifest = read_json(manifest_path)
    return RunArtifacts(
        run_dir=run_dir,
        manifest=manifest,
        truth=_read_frame(run_dir, "truth_topology.csv"),
        ledger=_read_frame(run_dir, "reported_ledger.csv"),
        observed_measurements=_read_frame(
            run_dir, "observed_measurements.parquet"
        ),
        feeder_measurements=_read_frame(
            run_dir, "feeder_measurements.parquet"
        ),
        candidate_features=_read_frame(run_dir, "candidate_features.parquet"),
        predictions=_read_frame(run_dir, "predictions.parquet"),
        metrics=_read_metrics(run_dir),
        confusion_matrix=_read_frame(run_dir, "confusion_matrix.csv"),
        network_nodes=_read_frame(run_dir, "network_nodes.csv"),
        network_edges=_read_frame(run_dir, "network_edges.csv"),
    )
