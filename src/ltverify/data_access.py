"""Dashboard artifact loading with actionable error messages."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ltverify.io import read_json
from ltverify.manifest import (
    classify_artifact_schema_version,
    verify_manifest_hashes,
)


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


_REPAIR_HINT = "请运行 python -m ltverify run-all --config configs/default.yaml"


def _require_regular_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ArtifactLoadError(
            f"{label}不是普通文件: {path.resolve()}；{_REPAIR_HINT}"
        )


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
    except Exception as exc:
        raise ArtifactLoadError(
            f"无法解析产物 {name}: {exc}"
        ) from exc


def _read_metrics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "metrics.json"
    _require_regular_file(path, "产物文件")
    try:
        metrics = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactLoadError(
            f"无法解析 metrics.json: {exc}"
        ) from exc
    if not isinstance(metrics, dict):
        raise ArtifactLoadError("metrics.json 顶层必须是 JSON object")
    return metrics


def discover_completed_run_dir(runs_root: Path = Path("runs")) -> str:
    """Return the newest structurally valid completed run directory.

    This is a lightweight discovery helper for the dashboard default. It
    skips non-directories, missing/malformed manifests, non-object
    manifests, unsupported schemas, non-completed statuses, and runs with
    empty output declarations. Full hash verification is left to
    :func:`load_run_artifacts`.
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
        state, _ = classify_artifact_schema_version(
            manifest.get("artifact_schema_version")
        )
        if state != "current":
            continue
        if manifest.get("status") != "completed":
            continue
        if not isinstance(manifest.get("output_paths"), list) or not manifest[
            "output_paths"
        ]:
            continue
        if not isinstance(manifest.get("output_sha256"), dict):
            continue
        return str(candidate)
    return ""


def load_run_artifacts(run_dir: Path) -> RunArtifacts:
    """Load every artifact of one completed, hash-verified run.

    This is the single trusted dashboard entry point. The mandatory order
    is:

    manifest file is a regular file -> JSON object -> supported schema ->
    status is completed -> verify_manifest_hashes -> parse business
    artifacts. Any parse/verification error is converted to
    :class:`ArtifactLoadError`; no artifact is read before the manifest
    hash chain passes.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    _require_regular_file(manifest_path, "运行清单")
    try:
        manifest = read_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactLoadError(
            f"无法解析运行清单 manifest.json: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise ArtifactLoadError("运行清单 manifest.json 顶层必须是 JSON object")

    state, _ = classify_artifact_schema_version(
        manifest.get("artifact_schema_version")
    )
    if state != "current":
        raise ArtifactLoadError(
            "运行清单 schema 不受支持，仅接受当前 schema-v2 运行"
        )
    if manifest.get("status") != "completed":
        raise ArtifactLoadError(
            f"运行状态不是 completed: {manifest.get('status')!r}"
        )
    try:
        verify_manifest_hashes(manifest, run_dir)
    except (ValueError, TypeError) as exc:
        raise ArtifactLoadError(
            f"运行清单哈希一致性校验失败: {exc}；{_REPAIR_HINT}"
        ) from exc

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
