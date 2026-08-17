"""Dashboard artifact loading with actionable error messages."""

import json
import math
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import ValidationError
from yaml import YAMLError

from ltverify.config import load_config
from ltverify.contracts import (
    FEEDER_MEASUREMENT_COLUMNS,
    LEDGER_COLUMNS,
    TRANSFORMER_MEASUREMENT_COLUMNS,
    TRUTH_COLUMNS,
    DataContractError,
    validate_columns,
)
from ltverify.evaluation import evaluate_predictions
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
DASHBOARD_FEATURE_COLUMNS = frozenset(FEATURE_COLUMNS) | {
    "enhanced_score",
    "available_feature_weight",
}
EVALUATION_METRIC_KEYS = (
    "precision",
    "recall",
    "f1",
    "pr_auc",
    "pr_auc_applicable",
    "pr_auc_unavailable_reason",
    "pr_auc_scored",
    "pr_auc_scored_applicable",
    "pr_auc_scored_unavailable_reason",
    "top1_correction_rate",
    "top1_evaluated_count",
    "top1_evaluation_coverage",
    "top2_correction_rate",
    "top2_evaluated_count",
    "top2_evaluation_coverage",
    "top3_correction_rate",
    "top3_evaluated_count",
    "top3_evaluation_coverage",
    "topk_applicable",
    "excluded_candidate_count",
    "candidate_feeder_count",
    "n_total",
    "n_actual_errors",
    "n_actual_correct",
    "n_predicted",
    "automatic_coverage",
    "insufficient_data_rate",
    "scored_coverage",
)

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


def _require_present(metrics: dict[str, object], key: str) -> None:
    if key not in metrics:
        raise ArtifactLoadError(f"metrics 缺少必填字段: {key}")


def _require_ratio_metric(metrics: dict[str, object], key: str) -> float:
    _require_present(metrics, key)
    value = metrics[key]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ArtifactLoadError(f"metrics.{key} 必须是 [0,1] 内有限数值")
    numeric = float(value)
    if not np.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ArtifactLoadError(f"metrics.{key} 必须是 [0,1] 内有限数值")
    return numeric


def _require_nullable_ratio_metric(metrics: dict[str, object], key: str) -> float | None:
    _require_present(metrics, key)
    value = metrics[key]
    if value is None:
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
    _require_present(metrics, key)
    value = metrics[key]
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ArtifactLoadError(f"metrics.{key} 必须是整数")
    numeric = int(value)
    if positive and numeric <= 0:
        raise ArtifactLoadError(f"metrics.{key} 必须是正整数")
    if not positive and numeric < 0:
        raise ArtifactLoadError(f"metrics.{key} 必须是非负整数")
    return numeric


def _validate_applicability_triple(
    metrics: dict[str, object],
    value_key: str,
    applicable_key: str,
    reason_key: str,
) -> None:
    applicable = metrics.get(applicable_key)
    if not isinstance(applicable, bool):
        raise ArtifactLoadError(f"{applicable_key} 必须是 bool")
    value = metrics.get(value_key)
    reason = metrics.get(reason_key)
    if applicable:
        if value is None:
            raise ArtifactLoadError(f"{value_key} 在 applicable=True 时不能为 null")
        _require_nullable_ratio_metric(metrics, value_key)
        if reason is not None:
            raise ArtifactLoadError(f"{reason_key} 在 applicable=True 时必须为 null")
    else:
        if value is not None:
            raise ArtifactLoadError(f"{value_key} 在 applicable=False 时必须为 null")
        if not isinstance(reason, str) or not reason:
            raise ArtifactLoadError(f"{reason_key} 在 applicable=False 时必须为非空字符串")


def _validate_metrics(metrics: dict[str, object]) -> None:
    for key in (
        "precision",
        "recall",
        "f1",
        "automatic_coverage",
        "insufficient_data_rate",
        "scored_coverage",
    ):
        _require_ratio_metric(metrics, key)
    for key in (
        "pr_auc",
        "pr_auc_scored",
        "top1_correction_rate",
        "top2_correction_rate",
        "top3_correction_rate",
        "top1_evaluation_coverage",
        "top2_evaluation_coverage",
        "top3_evaluation_coverage",
    ):
        _require_nullable_ratio_metric(metrics, key)

    _validate_applicability_triple(
        metrics, "pr_auc", "pr_auc_applicable", "pr_auc_unavailable_reason"
    )
    _validate_applicability_triple(
        metrics,
        "pr_auc_scored",
        "pr_auc_scored_applicable",
        "pr_auc_scored_unavailable_reason",
    )

    topk = metrics.get("topk_applicable")
    if not isinstance(topk, dict) or set(topk) != {"top1", "top2", "top3"}:
        raise ArtifactLoadError("topk_applicable 必须是包含 top1/top2/top3 的字典")
    for key in ("top1", "top2", "top3"):
        if not isinstance(topk[key], bool):
            raise ArtifactLoadError(f"topk_applicable.{key} 必须是 bool")

    n_total = _require_count_metric(metrics, "n_total", positive=True)
    n_predicted = _require_count_metric(metrics, "n_predicted", positive=False)
    n_actual_errors = _require_count_metric(metrics, "n_actual_errors", positive=False)
    n_actual_correct = _require_count_metric(metrics, "n_actual_correct", positive=False)
    candidate_feeder_count = _require_count_metric(
        metrics,
        "candidate_feeder_count",
        positive=True,
    )
    if n_predicted > n_total:
        raise ArtifactLoadError("metrics.n_predicted 不能大于 n_total")
    if n_actual_errors > n_total or n_actual_correct > n_total:
        raise ArtifactLoadError("metrics 计数不能大于 n_total")
    if n_actual_errors + n_actual_correct != n_total:
        raise ArtifactLoadError("metrics.n_actual_errors + n_actual_correct 必须等于 n_total")

    _require_count_metric(metrics, "excluded_candidate_count", positive=False)

    for key in ("top1", "top2", "top3"):
        rate_key = f"{key}_correction_rate"
        coverage_key = f"{key}_evaluation_coverage"
        count_key = f"{key}_evaluated_count"
        rate = _require_nullable_ratio_metric(metrics, rate_key)
        coverage = _require_nullable_ratio_metric(metrics, coverage_key)
        count = _require_count_metric(metrics, count_key, positive=False)

        expected_applicable = candidate_feeder_count > int(key[-1])
        if topk[key] != expected_applicable:
            raise ArtifactLoadError(
                f"{key} 适用性不一致: topk_applicable.{key}={topk[key]}，"
                f"candidate_feeder_count={candidate_feeder_count} 要求 "
                f"applicable={expected_applicable}"
            )

        if not topk[key]:
            if rate is not None or coverage is not None or count != 0:
                raise ArtifactLoadError(
                    f"{key} 不适用时 rate/coverage 必须为 null 且 evaluated_count 为 0"
                )
            continue

        if n_actual_errors == 0:
            if count != 0 or rate is not None or coverage is not None:
                raise ArtifactLoadError(
                    f"{key} 适用且无实际错误时 evaluated_count 必须为 0，rate/coverage 必须为 null"
                )
            continue

        if count > n_actual_errors:
            raise ArtifactLoadError(f"metrics.{count_key} 不能大于 metrics.n_actual_errors")
        expected_coverage = count / n_actual_errors
        if coverage is None or not math.isclose(
            coverage,
            expected_coverage,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ArtifactLoadError(
                f"metrics.{coverage_key} 必须等于 {count_key}/n_actual_errors = {expected_coverage}"
            )
        if count == 0:
            if rate is not None:
                raise ArtifactLoadError(
                    f"{key} 适用且 evaluated_count=0 时 correction_rate 必须为 null"
                )
        elif rate is None:
            raise ArtifactLoadError(
                f"{key} 适用且 evaluated_count>0 时 correction_rate 不能为 null"
            )

    scored_coverage = _require_ratio_metric(metrics, "scored_coverage")
    insufficient_data_rate = _require_ratio_metric(metrics, "insufficient_data_rate")
    if not math.isclose(
        scored_coverage + insufficient_data_rate,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ArtifactLoadError("metrics.scored_coverage + insufficient_data_rate 必须等于 1")


def _require_nonempty_string_series(
    frame: pd.DataFrame,
    column: str,
    label: str,
) -> pd.Series:
    """Tighten one object column to a non-empty-string contract.

    Must run before any hash, set, unique, sort or merge operation on the
    column: list/dict/array/null/numeric/bool/bytes/empty-string values
    are rejected with a domain error instead of leaking a raw TypeError.
    """
    values = frame[column]
    valid = values.map(lambda value: isinstance(value, str) and bool(value))
    if not bool(valid.all()):
        raise ArtifactLoadError(f"{label}.{column} 必须全部为非空字符串")
    return values


def _validate_transformer_identity_contracts(
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    predictions: pd.DataFrame,
) -> None:
    for name, frame in (
        ("truth_topology.csv", truth),
        ("reported_ledger.csv", ledger),
        ("predictions.parquet", predictions),
    ):
        _require_nonempty_string_series(frame, "transformer_id", name)
        if frame["transformer_id"].duplicated().any():
            raise ArtifactLoadError(f"{name} 的 transformer_id 存在重复")
    _require_nonempty_string_series(truth, "physical_feeder_id", "truth_topology.csv")
    _require_nonempty_string_series(ledger, "reported_feeder_id", "reported_ledger.csv")
    _require_nonempty_string_series(
        predictions,
        "reported_feeder_id",
        "predictions.parquet",
    )
    ids = [set(frame["transformer_id"]) for frame in (truth, ledger, predictions)]
    if not all(item == ids[0] for item in ids[1:]):
        raise ArtifactLoadError("truth/ledger/predictions 的 transformer_id 集合不一致")
    ledger_reported = ledger.set_index("transformer_id")["reported_feeder_id"].sort_index()
    prediction_reported = predictions.set_index("transformer_id")["reported_feeder_id"].sort_index()
    if not prediction_reported.equals(ledger_reported):
        raise ArtifactLoadError("predictions.reported_feeder_id 与 reported_ledger.csv 台账不一致")


def _validate_candidate_identity_contracts(
    candidate_features: pd.DataFrame,
    predictions: pd.DataFrame,
) -> None:
    for column in ("transformer_id", "reported_feeder_id", "candidate_feeder_id"):
        _require_nonempty_string_series(
            candidate_features,
            column,
            "candidate_features.parquet",
        )
    candidate_ids = set(candidate_features["transformer_id"])
    prediction_ids = set(predictions["transformer_id"])
    if candidate_ids != prediction_ids:
        raise ArtifactLoadError("candidate_features/predictions 的 transformer_id 集合不一致")
    duplicate_key = candidate_features.duplicated(subset=["transformer_id", "candidate_feeder_id"])
    if duplicate_key.any():
        raise ArtifactLoadError(
            "candidate_features 的 transformer_id/candidate_feeder_id 组合存在重复"
        )
    candidate_reported = candidate_features[["transformer_id", "reported_feeder_id"]].merge(
        predictions[["transformer_id", "reported_feeder_id"]],
        on="transformer_id",
        how="left",
        suffixes=("_candidate", "_prediction"),
        validate="many_to_one",
    )
    if not candidate_reported["reported_feeder_id_candidate"].equals(
        candidate_reported["reported_feeder_id_prediction"]
    ):
        raise ArtifactLoadError("candidate_features.reported_feeder_id 与 predictions 不一致")


def _validate_prediction_metric_consistency(
    predictions: pd.DataFrame,
    metrics: dict[str, object],
) -> None:
    if len(predictions) != int(metrics["n_total"]):
        raise ArtifactLoadError("predictions 行数与 metrics.n_total 不一致")
    predicted = predictions["predicted_is_mislinked"]
    if not pd.api.types.is_bool_dtype(predicted):
        raise ArtifactLoadError("predictions.predicted_is_mislinked 必须是严格 bool")
    n_predicted = int(predicted.sum())
    if n_predicted != int(metrics["n_predicted"]):
        raise ArtifactLoadError("predictions 的预测数不等于 metrics.n_predicted")
    allowed_decisions = {
        "no_change",
        "insufficient_data",
        "automatic_recommendation",
    }
    decision_values = _require_nonempty_string_series(
        predictions, "decision", "predictions.parquet"
    )
    decisions = set(decision_values)
    if not decisions.issubset(allowed_decisions):
        raise ArtifactLoadError(
            f"predictions.decision 含未知值: {sorted(decisions - allowed_decisions)}"
        )
    auto = predictions["decision"] == "automatic_recommendation"
    if not predictions.loc[auto, "predicted_is_mislinked"].all():
        raise ArtifactLoadError("automatic_recommendation 必须对应 predicted_is_mislinked=True")
    if predictions.loc[~auto, "predicted_is_mislinked"].any():
        raise ArtifactLoadError("非 automatic_recommendation 必须对应 predicted_is_mislinked=False")
    n_total = int(metrics["n_total"])
    auto_rate = float(auto.sum()) / n_total
    if not math.isclose(
        auto_rate,
        float(metrics["automatic_coverage"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ArtifactLoadError("automatic_coverage 与 predictions 不一致")
    insufficient = predictions["decision"] == "insufficient_data"
    scored = ~insufficient
    insufficient_rate = float(insufficient.sum()) / n_total
    scored_rate = float(scored.sum()) / n_total
    if not math.isclose(
        insufficient_rate,
        float(metrics["insufficient_data_rate"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ArtifactLoadError("insufficient_data_rate 与 predictions 不一致")
    if not math.isclose(
        scored_rate,
        float(metrics["scored_coverage"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ArtifactLoadError("scored_coverage 与 predictions 不一致")


def _validate_evaluation_consistency(
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    confusion_matrix: pd.DataFrame,
    metrics: dict[str, object],
) -> None:
    merged = ledger.merge(
        truth[["transformer_id", "physical_feeder_id"]],
        on="transformer_id",
        how="left",
        validate="one_to_one",
    )
    actual_errors = int((merged["reported_feeder_id"] != merged["physical_feeder_id"]).sum())
    if actual_errors != int(metrics["n_actual_errors"]):
        raise ArtifactLoadError("truth/ledger 计算的错误数不等于 metrics.n_actual_errors")
    try:
        matrix = confusion_matrix.to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ArtifactLoadError("confusion_matrix.csv 必须是 2×2 数值矩阵") from exc
    if matrix.shape != (2, 2):
        raise ArtifactLoadError("confusion_matrix.csv 必须是 2×2 数值矩阵")
    if not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ArtifactLoadError("confusion_matrix.csv 必须是非负有限数值")
    if not np.all(matrix == np.floor(matrix)):
        raise ArtifactLoadError("confusion_matrix.csv 必须是整数值")
    matrix_int = matrix.astype(int)
    if int(matrix_int.sum()) != int(metrics["n_total"]):
        raise ArtifactLoadError("confusion matrix 总和与 metrics.n_total 不一致")
    _tn, fp, fn, tp = matrix_int.ravel()
    if fn + tp != int(metrics["n_actual_errors"]):
        raise ArtifactLoadError("confusion matrix 实际正例数与 metrics.n_actual_errors 不一致")
    if fp + tp != int(metrics["n_predicted"]):
        raise ArtifactLoadError("confusion matrix 预测正例数与 metrics.n_predicted 不一致")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    for derived, key in (
        (precision, "precision"),
        (recall, "recall"),
        (f1, "f1"),
    ):
        if not math.isclose(
            derived,
            float(metrics[key]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ArtifactLoadError(f"confusion matrix 派生的 {key} 与 metrics 不一致")


def _metric_values_equal(actual: object, expected: object) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is bool and type(expected) is bool and actual == expected
    if isinstance(actual, dict) or isinstance(expected, dict):
        if not isinstance(actual, dict) or not isinstance(expected, dict):
            return False
        if set(actual) != set(expected):
            return False
        return all(_metric_values_equal(actual[key], expected[key]) for key in expected)
    if isinstance(actual, Real) or isinstance(expected, Real):
        if not isinstance(actual, Real) or not isinstance(expected, Real):
            return False
        return math.isclose(
            float(actual),
            float(expected),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    return type(actual) is type(expected) and actual == expected


def _validate_recomputed_evaluation(
    *,
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    predictions: pd.DataFrame,
    candidate_features: pd.DataFrame,
    metrics: dict[str, object],
    evidence_weight_threshold: float,
) -> None:
    try:
        recomputed = evaluate_predictions(
            predictions=predictions,
            truth=truth,
            ledger=ledger,
            candidate_scores=candidate_features,
            evidence_weight_threshold=evidence_weight_threshold,
        ).metrics
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise ArtifactLoadError(f"无法从权威产物重算评价指标: {exc}") from exc
    for key in EVALUATION_METRIC_KEYS:
        if key not in metrics:
            raise ArtifactLoadError(f"metrics 缺少必填字段: {key}")
        if not _metric_values_equal(metrics[key], recomputed[key]):
            raise ArtifactLoadError(
                f"metrics.{key} 与 truth/ledger/predictions/candidate_features 重算结果不一致"
            )


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
    evidence_weight_threshold: float,
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
            DASHBOARD_FEATURE_COLUMNS,
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

    _validate_transformer_identity_contracts(truth, ledger, predictions)
    _validate_candidate_identity_contracts(candidate_features, predictions)
    _validate_prediction_metric_consistency(predictions, metrics)
    _validate_evaluation_consistency(truth, ledger, confusion_matrix, metrics)
    _validate_recomputed_evaluation(
        truth=truth,
        ledger=ledger,
        predictions=predictions,
        candidate_features=candidate_features,
        metrics=metrics,
        evidence_weight_threshold=evidence_weight_threshold,
    )


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

    try:
        config = load_config(run_dir / "config.snapshot.yaml")
    except (OSError, UnicodeError, YAMLError, ValidationError, ValueError, TypeError) as exc:
        raise ArtifactLoadError(f"无法解析 config.snapshot.yaml: {exc}") from exc

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
        evidence_weight_threshold=config.scoring.evidence_weight_threshold,
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
