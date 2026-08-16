"""Dashboard artifact loading with actionable error messages."""

import json
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ltverify.contracts import (
    FEEDER_MEASUREMENT_COLUMNS,
    LEDGER_COLUMNS,
    TRANSFORMER_MEASUREMENT_COLUMNS,
    TRUTH_COLUMNS,
    DataContractError,
    validate_columns,
)
from ltverify.features import FEATURE_COLUMNS
from ltverify.io import read_json
from ltverify.manifest import (
    classify_artifact_schema_version,
    validate_output_declarations,
    verify_manifest_hashes,
)
from ltverify.scoring import PREDICTION_COLUMNS


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
    metrics: dict[str, object]
    confusion_matrix: pd.DataFrame
    network_nodes: pd.DataFrame
    network_edges: pd.DataFrame


DASHBOARD_ARTIFACT_FILES = {
    "truth": "truth_topology.csv",
    "ledger": "reported_ledger.csv",
    "observed_measurements": "observed_measurements.parquet",
    "feeder_measurements": "feeder_measurements.parquet",
    "candidate_features": "candidate_features.parquet",
    "predictions": "predictions.parquet",
    "metrics": "metrics.json",
    "confusion_matrix": "confusion_matrix.csv",
    "network_nodes": "network_nodes.csv",
    "network_edges": "network_edges.csv",
}

REQUIRED_DASHBOARD_ARTIFACTS = frozenset(DASHBOARD_ARTIFACT_FILES.values())

NETWORK_NODE_COLUMNS = frozenset({"node_id", "voltage_kv"})
NETWORK_EDGE_COLUMNS = frozenset({"from_node", "to_node", "feeder_id"})

_REPAIR_HINT = "请运行 python -m ltverify run-all --config configs/default.yaml"


def _require_regular_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ArtifactLoadError(f"{label}不是普通文件: {path.resolve()}；{_REPAIR_HINT}")


def _read_frame(run_dir: Path, name: str) -> pd.DataFrame:
    path = run_dir / name
    _require_regular_file(path, "产物文件")
    try:
        if name.endswith(".csv"):
            frame = pd.read_csv(path)
            if "index" in frame.columns:
                frame = frame.set_index("index")
            return frame
        return pd.read_parquet(path)
    except (
        OSError,
        UnicodeError,
        ValueError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as exc:
        raise ArtifactLoadError(f"无法解析产物 {name}: {exc}") from exc
    except Exception as exc:
        if type(exc).__name__ in {
            "ArrowException",
            "ArrowInvalid",
            "ArrowIOError",
            "ParquetError",
        }:
            raise ArtifactLoadError(f"无法解析产物 {name}: {exc}") from exc
        raise


def _read_metrics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "metrics.json"
    _require_regular_file(path, "产物文件")
    try:
        metrics = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactLoadError(f"无法解析 metrics.json: {exc}") from exc
    if not isinstance(metrics, dict):
        raise ArtifactLoadError("metrics.json 顶层必须是 JSON object")
    return metrics


def _require_ratio_metric(
    metrics: dict[str, object],
    key: str,
    *,
    allow_none: bool,
) -> float | None:
    value = metrics.get(key)
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ArtifactLoadError(f"metrics.{key} 必须是 [0,1] 内有限数值")
    numeric = float(value)
    if not np.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ArtifactLoadError(f"metrics.{key} 必须是 [0,1] 内有限数值")
    return numeric


def _require_count_metric(
    metrics: dict[str, object],
    key: str,
    *,
    positive: bool,
) -> int:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ArtifactLoadError(f"metrics.{key} 必须是整数")
    numeric = int(value)
    if positive and numeric <= 0:
        raise ArtifactLoadError(f"metrics.{key} 必须是正整数")
    if not positive and numeric < 0:
        raise ArtifactLoadError(f"metrics.{key} 必须是非负整数")
    return numeric


def _validate_metrics(metrics: dict[str, object]) -> None:
    n_total = _require_count_metric(metrics, "n_total", positive=True)
    n_predicted = _require_count_metric(metrics, "n_predicted", positive=False)
    if n_predicted > n_total:
        raise ArtifactLoadError("metrics.n_predicted 不能大于 n_total")
    _require_ratio_metric(metrics, "f1", allow_none=False)
    _require_ratio_metric(metrics, "automatic_coverage", allow_none=False)
    _require_ratio_metric(metrics, "top1_correction_rate", allow_none=True)
    if "n_actual_errors" in metrics:
        n_errors = _require_count_metric(metrics, "n_actual_errors", positive=False)
        if n_errors > n_total:
            raise ArtifactLoadError("metrics.n_actual_errors 不能大于 n_total")


def _validate_dashboard_contracts(
    *,
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    observed_measurements: pd.DataFrame,
    feeder_measurements: pd.DataFrame,
    candidate_features: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: dict[str, object],
    confusion_matrix: pd.DataFrame,
    network_nodes: pd.DataFrame,
    network_edges: pd.DataFrame,
) -> None:
    try:
        validate_columns(truth, TRUTH_COLUMNS, "truth_topology.csv")
        validate_columns(ledger, LEDGER_COLUMNS, "reported_ledger.csv")
        validate_columns(
            observed_measurements,
            TRANSFORMER_MEASUREMENT_COLUMNS,
            "observed_measurements.parquet",
        )
        validate_columns(
            feeder_measurements,
            FEEDER_MEASUREMENT_COLUMNS,
            "feeder_measurements.parquet",
        )
        validate_columns(
            candidate_features,
            FEATURE_COLUMNS,
            "candidate_features.parquet",
        )
        validate_columns(predictions, PREDICTION_COLUMNS, "predictions.parquet")
        validate_columns(network_nodes, NETWORK_NODE_COLUMNS, "network_nodes.csv")
        validate_columns(network_edges, NETWORK_EDGE_COLUMNS, "network_edges.csv")
    except DataContractError as exc:
        raise ArtifactLoadError(str(exc)) from exc

    if predictions.empty:
        raise ArtifactLoadError("predictions.parquet 不能为空表")
    if observed_measurements.empty:
        raise ArtifactLoadError("observed_measurements.parquet 不能为空表")

    _validate_metrics(metrics)

    try:
        matrix = confusion_matrix.to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ArtifactLoadError("confusion_matrix.csv 必须是 2×2 数值矩阵") from exc
    if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
        raise ArtifactLoadError("confusion_matrix.csv 必须是 2×2 数值矩阵")


def discover_completed_run_dir(runs_root: Path = Path("runs")) -> str:
    """Return the newest structurally valid completed run directory.

    This is a lightweight discovery helper for the dashboard default. It
    skips non-directories, missing/malformed manifests, non-object
    manifests, unsupported schemas, non-completed statuses, and runs that
    do not declare the complete dashboard artifact set with regular files.
    Full hash verification is left to :func:`load_run_artifacts`.
    """
    runs_root = Path(runs_root)
    for candidate in sorted(runs_root.glob("run-*"), reverse=True):
        if not candidate.is_dir():
            continue
        manifest_path = candidate / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = read_json(manifest_path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        state, _ = classify_artifact_schema_version(manifest.get("artifact_schema_version"))
        if state != "current":
            continue
        if manifest.get("status") != "completed":
            continue
        try:
            output_paths, _ = validate_output_declarations(manifest)
        except (ValueError, TypeError):
            continue
        if not REQUIRED_DASHBOARD_ARTIFACTS.issubset(set(output_paths)):
            continue
        if "config.snapshot.yaml" not in output_paths:
            continue
        if not all((candidate / name).is_file() for name in REQUIRED_DASHBOARD_ARTIFACTS):
            continue
        if not (candidate / "config.snapshot.yaml").is_file():
            continue
        return str(candidate)
    return ""


def load_run_artifacts(run_dir: Path) -> RunArtifacts:
    """Load every artifact of one completed, hash-verified run.

    This is the single trusted dashboard entry point. The mandatory order
    is:

    manifest file is a regular file -> JSON object -> supported schema ->
    status is completed -> required dashboard artifacts are declared ->
    verify_manifest_hashes -> parse business artifacts -> validate display
    contracts. Any parse/verification error is converted to
    :class:`ArtifactLoadError`; no artifact is read before the manifest
    hash chain passes.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    _require_regular_file(manifest_path, "运行清单")
    try:
        manifest = read_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactLoadError(f"无法解析运行清单 manifest.json: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ArtifactLoadError("运行清单 manifest.json 顶层必须是 JSON object")

    state, _ = classify_artifact_schema_version(manifest.get("artifact_schema_version"))
    if state != "current":
        raise ArtifactLoadError("运行清单 schema 不受支持，仅接受当前 schema-v2 运行")
    if manifest.get("status") != "completed":
        raise ArtifactLoadError(f"运行状态不是 completed: {manifest.get('status')!r}")

    try:
        output_paths, _ = validate_output_declarations(manifest)
    except (ValueError, TypeError) as exc:
        raise ArtifactLoadError(f"运行清单 output_paths/output_sha256 非法: {exc}") from exc
    declared = set(output_paths)
    missing_declared = sorted(REQUIRED_DASHBOARD_ARTIFACTS - declared)
    if missing_declared:
        raise ArtifactLoadError("运行清单未声明首页必需产物: " + ", ".join(missing_declared))

    try:
        verify_manifest_hashes(manifest, run_dir)
    except (ValueError, TypeError, OSError, UnicodeError) as exc:
        raise ArtifactLoadError(f"运行清单哈希一致性校验失败: {exc}；{_REPAIR_HINT}") from exc

    def read(name: str) -> pd.DataFrame:
        return _read_frame(run_dir, name)

    truth = read(DASHBOARD_ARTIFACT_FILES["truth"])
    ledger = read(DASHBOARD_ARTIFACT_FILES["ledger"])
    observed_measurements = read(DASHBOARD_ARTIFACT_FILES["observed_measurements"])
    feeder_measurements = read(DASHBOARD_ARTIFACT_FILES["feeder_measurements"])
    candidate_features = read(DASHBOARD_ARTIFACT_FILES["candidate_features"])
    predictions = read(DASHBOARD_ARTIFACT_FILES["predictions"])
    metrics = _read_metrics(run_dir)
    confusion_matrix = read(DASHBOARD_ARTIFACT_FILES["confusion_matrix"])
    network_nodes = read(DASHBOARD_ARTIFACT_FILES["network_nodes"])
    network_edges = read(DASHBOARD_ARTIFACT_FILES["network_edges"])

    _validate_dashboard_contracts(
        truth=truth,
        ledger=ledger,
        observed_measurements=observed_measurements,
        feeder_measurements=feeder_measurements,
        candidate_features=candidate_features,
        predictions=predictions,
        metrics=metrics,
        confusion_matrix=confusion_matrix,
        network_nodes=network_nodes,
        network_edges=network_edges,
    )

    return RunArtifacts(
        run_dir=run_dir,
        manifest=manifest,
        truth=truth,
        ledger=ledger,
        observed_measurements=observed_measurements,
        feeder_measurements=feeder_measurements,
        candidate_features=candidate_features,
        predictions=predictions,
        metrics=metrics,
        confusion_matrix=confusion_matrix,
        network_nodes=network_nodes,
        network_edges=network_edges,
    )
