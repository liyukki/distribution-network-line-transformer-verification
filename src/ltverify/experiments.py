"""Robustness experiment matrix and ablation runs.

One factor at a time around the default base case; ablations disable one
feature group at a time by zeroing its score weight. Clean simulation
artifacts are cached by (seed, pv_scale) so all cases sharing physical
data reuse the same power-flow results.
"""

import time
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import yaml

from ltverify.config import load_config
from ltverify.corruption import build_truth, corrupt_ledger, disturb_measurements
from ltverify.evaluation import evaluate_predictions
from ltverify.features import build_candidate_features
from ltverify.network import build_network
from ltverify.pipeline import EVENT_QUANTILE, INTERPOLATION_LIMIT, ROLLING_WINDOW
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
    "top1_correction_rate",
    "top3_correction_rate",
    "automatic_coverage",
    "runtime_seconds",
)

SUMMARY_COLUMNS = [
    "case_id",
    "family",
    "value",
    "seed",
    *_METRIC_COLUMNS,
    "status",
    "error_type",
    "error_message",
]


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
) -> dict[str, float | int]:
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
        INTERPOLATION_LIMIT,
        config.scoring.minimum_coverage,
    )
    features = build_candidate_features(
        prepared,
        ledger,
        simulation.feeder_measurements,
        ROLLING_WINDOW,
        EVENT_QUANTILE,
    )
    scored = score_candidates(features, _weights_for(case.enabled_features))
    predictions = diagnose(scored, ledger, config.scoring)
    result = evaluate_predictions(predictions, truth, ledger, scored)
    return result.metrics


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
        for metric in _METRIC_COLUMNS:
            if len(succeeded):
                row[f"mean_{metric}"] = float(succeeded[metric].mean())
                row[f"std_{metric}"] = float(succeeded[metric].std(ddof=1))
            else:
                row[f"mean_{metric}"] = float("nan")
                row[f"std_{metric}"] = float("nan")
        aggregates.append(row)
    return pd.DataFrame(aggregates)


def run_experiments(path: Path, output_dir: Path) -> Path:
    """Run every case, write raw and aggregated summaries, return the dir."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    base_config = load_config(Path(raw["base_config"]))
    cases = expand_experiment_grid(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache: dict[tuple[int, float], tuple[object, object, object]] = {}
    rows: list[dict[str, object]] = []
    for case in cases:
        started = time.perf_counter()
        try:
            metrics = _run_case(case, base_config, cache)
            rows.append(
                {
                    "case_id": case.case_id,
                    "family": case.family,
                    "value": case.value,
                    "seed": case.seed,
                    **{metric: metrics.get(metric, float("nan")) for metric in _METRIC_COLUMNS},
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
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
        rows[-1]["runtime_seconds"] = time.perf_counter() - started
    summary = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    summary.to_csv(output_dir / "experiment_summary.csv", index=False)
    aggregates = _aggregate(summary)
    aggregates.to_csv(output_dir / "experiment_aggregates.csv", index=False)
    return output_dir
