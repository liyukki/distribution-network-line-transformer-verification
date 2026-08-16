"""Robustness experiment matrix and ablation runs.

One factor at a time around the default base case; ablations disable one
feature group at a time by zeroing its score weight. Clean simulation
artifacts are cached by (seed, pv_scale) so all cases sharing physical
data reuse the same power-flow results. Cases with simulation failures or
critical physical violations are recorded as failed, never silently
counted as completed. Every run writes a robustness_experiment_manifest.json
with configuration, environment and output hashes.
"""

import hashlib
import platform
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yaml

from ltverify.config import load_config
from ltverify.corruption import build_truth, corrupt_ledger, disturb_measurements
from ltverify.evaluation import evaluate_predictions
from ltverify.features import build_candidate_features
from ltverify.io import write_json_atomic
from ltverify.manifest import (
    git_commit,
    package_versions,
    validate_portable_relative_path,
)
from ltverify.network import build_network
from ltverify.preprocessing import prepare_measurements
from ltverify.profiles import generate_profiles
from ltverify.scoring import ScoreWeights, diagnose, score_candidates
from ltverify.simulation import simulate_time_series

FAMILY_CONFIG_PATHS = {
    "ledger_error_rate": "corruption.ledger_error_rate",
    "voltage_noise_std_pu": "corruption.voltage_noise_std_pu",
    "missing_rate": "corruption.missing_rate",
    "time_shift_steps": "corruption.time_shift_steps",
    "pv_scale": "profiles.pv_scale",
}

_ALL_FEATURE_NAMES = tuple(asdict(ScoreWeights()).keys())

ABLATION_FEATURES = {
    "full": _ALL_FEATURE_NAMES,
    "without_residual": tuple(
        name for name in _ALL_FEATURE_NAMES if name != "residual_corr"
    ),
    "without_difference": tuple(
        name for name in _ALL_FEATURE_NAMES if name != "diff_corr"
    ),
    "without_rolling": tuple(
        name
        for name in _ALL_FEATURE_NAMES
        if name not in ("rolling_corr_median", "rolling_corr_q10")
    ),
    "without_events": tuple(
        name for name in _ALL_FEATURE_NAMES if name != "event_match"
    ),
    "without_power": tuple(
        name for name in _ALL_FEATURE_NAMES if name != "active_power_corr"
    ),
}

_METRIC_COLUMNS = (
    "precision",
    "recall",
    "f1",
    "pr_auc",
    "pr_auc_scored",
    "top1_correction_rate",
    "top2_correction_rate",
    "automatic_coverage",
    "scored_coverage",
    "insufficient_data_rate",
    "n_actual_errors",
    "runtime_seconds",
)

_PHYSICAL_COLUMNS = (
    "convergence_rate",
    "violation_count",
    "maximum_power_balance_error_mw",
    "non_convergence_count",
    "power_balance_count",
    "voltage_out_of_bounds_count",
    "transformer_overload_count",
    "voltage_min_pu",
    "voltage_max_pu",
    "maximum_transformer_loading_percent",
)

SUMMARY_COLUMNS = [
    "case_id",
    "family",
    "value",
    "seed",
    *_METRIC_COLUMNS,
    *_PHYSICAL_COLUMNS,
    "status",
    "error_type",
    "error_message",
]

CURRENT_AGGREGATES_NAME = "robustness_aggregates.csv"
CURRENT_SUMMARY_NAME = "robustness_summary.csv"
CURRENT_MANIFEST_NAME = "robustness_experiment_manifest.json"
LEGACY_AGGREGATES_NAME = "experiment_aggregates.csv"
LEGACY_SUMMARY_NAME = "experiment_summary.csv"

REQUIRED_EXPERIMENT_OUTPUTS = frozenset(
    {CURRENT_SUMMARY_NAME, CURRENT_AGGREGATES_NAME}
)


@dataclass(frozen=True)
class ExperimentCase:
    case_id: str
    family: str
    value: str
    seed: int
    config_overrides: dict[str, object]
    enabled_features: tuple[str, ...]


def expand_experiment_grid(path: Path) -> list[ExperimentCase]:
    """Expand the robustness YAML into one case per family/level/seed."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    seeds = raw.get("seeds", [])
    cases: list[ExperimentCase] = []
    for family, levels in raw.get("experiments", {}).items():
        config_path = FAMILY_CONFIG_PATHS[family]
        for level in levels:
            for seed in seeds:
                cases.append(
                    ExperimentCase(
                        case_id=f"{family}-{level}-seed{seed}",
                        family=family,
                        value=str(level),
                        seed=int(seed),
                        config_overrides={config_path: level},
                        enabled_features=ABLATION_FEATURES["full"],
                    )
                )
    for ablation in raw.get("ablation_features", []):
        for seed in seeds:
            cases.append(
                ExperimentCase(
                    case_id=f"ablation-{ablation}-seed{seed}",
                    family="ablation",
                    value=str(ablation),
                    seed=int(seed),
                    config_overrides={},
                    enabled_features=ABLATION_FEATURES[ablation],
                )
            )
    return cases


def _apply_overrides(config: object, overrides: dict[str, object]) -> None:
    for dotted_path, value in overrides.items():
        target = config
        parts = dotted_path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        setattr(target, parts[-1], value)


def _weights_for(enabled_features: tuple[str, ...]) -> ScoreWeights:
    defaults = asdict(ScoreWeights())
    return ScoreWeights(
        **{
            name: (defaults[name] if name in enabled_features else 0.0)
            for name in defaults
        }
    )


def _run_case(
    case: ExperimentCase,
    base_config: object,
    cache: dict[tuple[int, float], tuple[object, object, object]],
) -> tuple[dict[str, float | int], dict[str, float | int]]:
    config = base_config.model_copy(deep=True)
    _apply_overrides(config, case.config_overrides)
    seed = case.seed
    cache_key = (seed, float(config.profiles.pv_scale))
    if cache_key in cache:
        artifacts, profiles, simulation = cache[cache_key]
    else:
        artifacts = build_network(config.network)
        profiles = generate_profiles(artifacts, config.profiles, seed=seed)
        simulation = simulate_time_series(artifacts, profiles, config.validation)

    if not simulation.failures.empty:
        raise RuntimeError(
            "simulation failures: "
            f"{simulation.failures.head(3).to_dict('records')}"
        )
    if config.validation.terminate_on_critical and len(simulation.validation):
        critical = simulation.validation[
            simulation.validation["severity"] == "critical"
        ]
        if len(critical):
            raise RuntimeError(
                "critical physical violations in experiment case"
            )

    if cache_key not in cache:
        cache[cache_key] = (artifacts, profiles, simulation)

    truth = build_truth(artifacts)
    ledger = corrupt_ledger(
        truth, config.corruption.ledger_error_rate, seed=seed
    )
    observed = disturb_measurements(
        simulation.transformer_measurements, config.corruption, seed=seed
    )
    prepared = prepare_measurements(
        observed,
        config.profiles.interval_minutes,
        config.scoring.interpolation_limit,
        config.scoring.minimum_coverage,
    )
    features = build_candidate_features(
        prepared,
        ledger,
        simulation.feeder_measurements,
        config.scoring.rolling_window,
        config.scoring.event_quantile,
        config.scoring.minimum_pairs,
    )
    scored = score_candidates(features, _weights_for(case.enabled_features))
    predictions = diagnose(scored, ledger, config.scoring)
    result = evaluate_predictions(
        predictions,
        truth,
        ledger,
        scored,
        evidence_weight_threshold=config.scoring.evidence_weight_threshold,
    )

    validation = simulation.validation
    type_counts: dict[str, int] = {}
    if len(validation):
        for violation_type in (
            "non_convergence",
            "power_balance",
            "voltage_out_of_bounds",
            "transformer_overload",
        ):
            type_counts[violation_type] = int(
                validation["violation_type"]
                .fillna("")
                .str.contains(violation_type, regex=False)
                .sum()
            )
        physical = {
            "convergence_rate": float(validation["converged"].mean()),
            "violation_count": int((validation["severity"] != "ok").sum()),
            "maximum_power_balance_error_mw": float(
                validation["absolute_power_balance_error_mw"].max()
            ),
            "non_convergence_count": type_counts["non_convergence"],
            "power_balance_count": type_counts["power_balance"],
            "voltage_out_of_bounds_count": type_counts[
                "voltage_out_of_bounds"
            ],
            "transformer_overload_count": type_counts[
                "transformer_overload"
            ],
            "voltage_min_pu": float(validation["voltage_min_pu"].min()),
            "voltage_max_pu": float(validation["voltage_max_pu"].max()),
            "maximum_transformer_loading_percent": float(
                validation["maximum_transformer_loading_percent"].max()
            ),
        }
    else:
        physical = {
            "convergence_rate": float("nan"),
            "violation_count": 0,
            "maximum_power_balance_error_mw": float("nan"),
            "non_convergence_count": 0,
            "power_balance_count": 0,
            "voltage_out_of_bounds_count": 0,
            "transformer_overload_count": 0,
            "voltage_min_pu": float("nan"),
            "voltage_max_pu": float("nan"),
            "maximum_transformer_loading_percent": float("nan"),
        }
    return result.metrics, physical


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    aggregates: list[dict[str, object]] = []
    completed = summary[summary["status"] == "completed"]
    for (family, value), group in summary.groupby(["family", "value"]):
        succeeded = completed[
            (completed["family"] == family) & (completed["value"] == value)
        ]
        row: dict[str, object] = {
            "family": family,
            "value": value,
            "n_completed": len(succeeded),
            "failure_count": int((group["status"] == "failed").sum()),
        }
        for metric in _METRIC_COLUMNS + _PHYSICAL_COLUMNS:
            if len(succeeded):
                row[f"mean_{metric}"] = float(succeeded[metric].mean())
                row[f"std_{metric}"] = float(succeeded[metric].std(ddof=1))
            else:
                row[f"mean_{metric}"] = float("nan")
                row[f"std_{metric}"] = float("nan")
        aggregates.append(row)
    return pd.DataFrame(aggregates)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_base_config(experiment_path: Path, raw: dict) -> Path:
    """Resolve base_config relative to the experiment YAML directory."""
    base = Path(str(raw["base_config"]))
    if not base.is_absolute():
        base = (experiment_path.parent / base).resolve()
    return base


def _portable(value: object) -> object:
    """Normalize every string to POSIX separators for portable manifests."""
    if isinstance(value, dict):
        return {key: _portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_portable(item) for item in value]
    if isinstance(value, str):
        return value.replace("\\", "/")
    return value


def run_experiments(path: Path, output_dir: Path) -> Path:
    """Run every case, write summaries and a manifest, return the dir."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base_config_path = _resolve_base_config(path, raw)
    base_config = load_config(base_config_path)
    cases = expand_experiment_grid(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache: dict[tuple[int, float], tuple[object, object, object]] = {}
    rows: list[dict[str, object]] = []
    started_at_utc = datetime.now(UTC)
    for case in cases:
        started = time.perf_counter()
        try:
            metrics, physical = _run_case(case, base_config, cache)
            rows.append(
                {
                    "case_id": case.case_id,
                    "family": case.family,
                    "value": case.value,
                    "seed": case.seed,
                    **{metric: metrics.get(metric, float("nan")) for metric in _METRIC_COLUMNS},
                    **physical,
                    "status": "completed",
                    "error_type": "",
                    "error_message": "",
                }
            )
        except Exception as exc:  # noqa: BLE001 - failed cases are recorded, not fatal
            rows.append(
                {
                    "case_id": case.case_id,
                    "family": case.family,
                    "value": case.value,
                    "seed": case.seed,
                    **{metric: float("nan") for metric in _METRIC_COLUMNS},
                    **{column: float("nan") for column in _PHYSICAL_COLUMNS},
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
        rows[-1]["runtime_seconds"] = time.perf_counter() - started
    summary = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    summary.to_csv(output_dir / CURRENT_SUMMARY_NAME, index=False)
    aggregates = _aggregate(summary)
    aggregates.to_csv(output_dir / CURRENT_AGGREGATES_NAME, index=False)

    manifest = {
        "artifact_schema_version": 2,
        "experiment_config_name": path.name,
        "experiment_config_sha256": _file_sha256(path),
        "experiment_config_snapshot": _portable(raw),
        "base_config_name": base_config_path.name,
        "base_config_sha256": _file_sha256(base_config_path),
        "base_config_snapshot": _portable(
            base_config.model_dump(mode="json")
        ),
        "git_commit": git_commit(),
        "python_version": platform.python_version(),
        "package_versions": package_versions(),
        "started_at_utc": started_at_utc.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "case_counts": {
            "total": len(cases),
            "completed": int((summary["status"] == "completed").sum()),
            "failed": int((summary["status"] == "failed").sum()),
        },
        "output_files": {
            CURRENT_SUMMARY_NAME: _file_sha256(
                output_dir / CURRENT_SUMMARY_NAME
            ),
            CURRENT_AGGREGATES_NAME: _file_sha256(
                output_dir / CURRENT_AGGREGATES_NAME
            ),
        },
    }
    write_json_atomic(
        manifest, output_dir / CURRENT_MANIFEST_NAME
    )
    return output_dir


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def verify_experiment_manifest(
    manifest: dict[str, object],
    artifact_dir: Path,
    *,
    experiment_config_path: Path | None = None,
    base_config_path: Path | None = None,
    require_source_configs: bool = False,
) -> str:
    """Verify a robustness experiment manifest against its artifact dir.

    Returns ``"strict"`` when both original source config paths were
    provided and name/hash/snapshot all cross-check successfully; returns
    ``"offline"`` when only artifact/schema/count verification is
    performed. Offline mode cannot prove the embedded snapshots came from
    the original YAML/config files.

    Checks schema, safe relative output paths, 64-hex hashes, file
    existence and byte equality, config hashes against the embedded
    snapshots, and case-count consistency with the summary file. When the
    caller provides the original config paths, their file hashes must
    equal the recorded hashes.
    """
    if require_source_configs and (
        experiment_config_path is None or base_config_path is None
    ):
        raise ValueError(
            "严格验证需要同时提供 experiment_config_path 和 base_config_path"
        )
    if not isinstance(manifest, dict):
        raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
            "实验清单顶层必须是 JSON object"
        )
    artifact_dir = Path(artifact_dir)
    schema = manifest.get("artifact_schema_version")
    if not isinstance(schema, int) or isinstance(schema, bool) or schema != 2:
        raise ValueError(f"不支持的 experiment manifest schema: {schema!r}")
    output_files = manifest.get("output_files")
    if not isinstance(output_files, dict) or not output_files:
        raise ValueError("experiment manifest 的 output_files 为空或缺失")
    if set(output_files) != REQUIRED_EXPERIMENT_OUTPUTS:
        missing = sorted(REQUIRED_EXPERIMENT_OUTPUTS - set(output_files))
        extra = sorted(set(output_files) - REQUIRED_EXPERIMENT_OUTPUTS)
        raise ValueError(
            "output_files 必须精确包含 "
            f"{sorted(REQUIRED_EXPERIMENT_OUTPUTS)}；"
            f"缺失: {missing}，多余: {extra}"
        )
    for name, expected in output_files.items():
        text = validate_portable_relative_path(name, field="output_files")
        if not _SHA256_PATTERN.match(str(expected)):
            raise ValueError(f"output_files 哈希必须是 64 位十六进制: {text}")
        path = artifact_dir / text
        if not path.is_file():
            raise ValueError(
                f"experiment manifest 声明的文件不是普通文件: {text}"
            )
        actual = _file_sha256(path)
        if actual != expected:
            raise ValueError(
                f"实验产物校验失败: {text}（期望 {expected}，实际 {actual}）"
            )
    for key in ("experiment_config_sha256", "base_config_sha256"):
        value = manifest.get(key)
        if not isinstance(value, str) or not _SHA256_PATTERN.match(value):
            raise ValueError(f"{key} 不是 64 位十六进制哈希")
    for key in ("experiment_config_name", "base_config_name"):
        validate_portable_relative_path(manifest.get(key), field=key)
    for key in ("experiment_config_snapshot", "base_config_snapshot"):
        if not isinstance(manifest.get(key), dict):
            raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
                f"experiment manifest 缺少 {key} 字典"
            )
    strict_verified = False
    if experiment_config_path is not None and base_config_path is not None:
        strict_verified = True
    if experiment_config_path is not None:
        path = Path(experiment_config_path)
        if path.name != manifest["experiment_config_name"]:
            raise ValueError(
                "experiment 配置 name 不一致: "
                f"{path.name} != {manifest['experiment_config_name']}"
            )
        if _file_sha256(path) != manifest["experiment_config_sha256"]:
            raise ValueError(
                f"experiment 配置 hash 不一致: {experiment_config_path}"
            )
        actual_snapshot = _portable(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )
        if actual_snapshot != manifest["experiment_config_snapshot"]:
            raise ValueError("experiment 配置 snapshot 与原始 YAML 不一致")
    if base_config_path is not None:
        path = Path(base_config_path)
        if path.name != manifest["base_config_name"]:
            raise ValueError(
                "base 配置 name 不一致: "
                f"{path.name} != {manifest['base_config_name']}"
            )
        if _file_sha256(path) != manifest["base_config_sha256"]:
            raise ValueError(
                f"base 配置 hash 不一致: {base_config_path}"
            )
        actual_snapshot = _portable(
            load_config(path).model_dump(mode="json")
        )
        if actual_snapshot != manifest["base_config_snapshot"]:
            raise ValueError("base 配置 snapshot 与原始配置不一致")
    counts = manifest.get("case_counts")
    if not isinstance(counts, dict):
        raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
            "case_counts 必须是字典"
        )
    for key in ("total", "completed", "failed"):
        value = counts.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
                f"case_counts.{key} 必须是整数"
            )
        if value < 0:
            raise ValueError(f"case_counts.{key} 不能为负数")
    total = counts["total"]
    completed = counts["completed"]
    failed = counts["failed"]
    if total != completed + failed:
        raise ValueError(
            f"case_counts 不一致: total={total} != completed+failed="
            f"{completed + failed}"
        )
    summary_path = artifact_dir / CURRENT_SUMMARY_NAME
    if not summary_path.exists():
        raise ValueError(f"缺少 {CURRENT_SUMMARY_NAME}")
    summary = pd.read_csv(summary_path)
    if len(summary) != total:
        raise ValueError(
            f"summary 行数 {len(summary)} 与 case_counts.total {total} 不一致"
        )
    if "status" not in summary.columns:
        raise ValueError(f"{CURRENT_SUMMARY_NAME} 缺少 status 列")
    unknown_statuses = sorted(
        set(summary["status"].astype(str).unique()) - {"completed", "failed"}
    )
    if unknown_statuses:
        raise ValueError(f"summary status 存在未知值: {unknown_statuses}")
    actual_completed = int((summary["status"] == "completed").sum())
    actual_failed = int((summary["status"] == "failed").sum())
    if actual_completed != completed or actual_failed != failed:
        raise ValueError(
            "case_counts 与 summary 实际状态不一致: "
            f"completed {completed} != {actual_completed}，"
            f"failed {failed} != {actual_failed}"
        )
    return "strict" if strict_verified else "offline"
