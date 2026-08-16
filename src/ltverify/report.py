"""Automatic evidence summary generation.

Regenerates reports/metrics/default_summary.json from one run directory.
Every number is read from or computed from the run artifacts: the run ID,
manifest, metrics and the baseline comparison are never hand-copied. The
summary is portable: it contains hashes instead of machine-local absolute
paths, and it verifies the source manifest hashes before generating.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ltverify.config import load_config
from ltverify.contracts import DataContractError
from ltverify.data_access import load_run_artifacts
from ltverify.evaluation import evaluate_predictions
from ltverify.io import write_json_atomic
from ltverify.manifest import file_sha256, verify_manifest_hashes
from ltverify.scoring import ScoreWeights, diagnose, score_candidates

_BASELINE_WEIGHTS = ScoreWeights(
    raw_corr=1.0,
    residual_corr=0.0,
    diff_corr=0.0,
    rolling_corr_median=0.0,
    rolling_corr_q10=0.0,
    event_match=0.0,
    active_power_corr=0.0,
)


def _residual_correlation_means(run_dir: Path) -> dict[str, float]:
    observed = pd.read_parquet(run_dir / "observed_measurements.parquet")
    truth = pd.read_csv(run_dir / "truth_topology.csv")
    duplicated = observed.duplicated(
        subset=["timestamp", "transformer_id"], keep=False
    )
    if duplicated.any():
        examples = observed.loc[
            duplicated, ["timestamp", "transformer_id"]
        ].head(3).to_dict("records")
        raise DataContractError(
            f"duplicate timestamp-transformer pairs: {examples}"
        )
    wide = observed.pivot(
        index="timestamp", columns="transformer_id", values="voltage_pu"
    )
    residual = wide.sub(wide.median(axis=1), axis=0)
    physical = dict(zip(truth["transformer_id"], truth["physical_feeder_id"]))
    transformer_ids = list(truth["transformer_id"])
    same: list[float] = []
    cross: list[float] = []
    for left in range(len(transformer_ids)):
        for right in range(left + 1, len(transformer_ids)):
            correlation = float(
                residual[transformer_ids[left]].corr(
                    residual[transformer_ids[right]]
                )
            )
            if physical[transformer_ids[left]] == physical[transformer_ids[right]]:
                same.append(correlation)
            else:
                cross.append(correlation)
    return {
        "same_feeder_residual_corr_mean": float(np.nanmean(same)),
        "cross_feeder_residual_corr_mean": float(np.nanmean(cross)),
        "same_feeder_pair_count": len(same),
        "cross_feeder_pair_count": len(cross),
    }


def _time_series_validation_summary(run_dir: Path) -> dict[str, object]:
    frame = pd.read_csv(run_dir / "simulation_validation.csv")
    type_counts: dict[str, int] = {}
    for violation_type in (
        "non_convergence",
        "power_balance",
        "voltage_out_of_bounds",
        "transformer_overload",
    ):
        type_counts[violation_type] = int(
            frame["violation_type"]
            .fillna("")
            .str.contains(violation_type, regex=False)
            .sum()
        )
    return {
        "timestamp_count": len(frame),
        "convergence_rate": float(frame["converged"].mean()),
        "voltage_min_pu": float(frame["voltage_min_pu"].min()),
        "voltage_max_pu": float(frame["voltage_max_pu"].max()),
        "maximum_transformer_loading_percent": float(
            frame["maximum_transformer_loading_percent"].max()
        ),
        "maximum_power_balance_error_mw": float(
            frame["absolute_power_balance_error_mw"].max()
        ),
        "severity_counts": frame["severity"].value_counts().to_dict(),
        "violation_type_counts": type_counts,
    }


def generate_default_summary(
    run_dir: Path,
    output_path: Path,
    manifest_output: Path | None = None,
) -> Path:
    """Regenerate the default-summary evidence file from run artifacts.

    The portable source-manifest copy is written to manifest_output when
    given, otherwise to <output_stem>.manifest.json next to the report.
    """
    run_dir = Path(run_dir)
    artifacts = load_run_artifacts(run_dir)
    config = load_config(run_dir / "config.snapshot.yaml")
    if artifacts.manifest.get("artifact_schema_version") != 2:
        raise ValueError(
            "旧版运行目录（schema != 2）无法生成可信证据，请重新运行流水线"
        )
    verify_manifest_hashes(artifacts.manifest, run_dir)

    baseline_scored = score_candidates(
        artifacts.candidate_features, _BASELINE_WEIGHTS
    )
    baseline_predictions = diagnose(
        baseline_scored, artifacts.ledger, config.scoring
    )
    baseline_result = evaluate_predictions(
        baseline_predictions,
        artifacts.truth,
        artifacts.ledger,
        baseline_scored,
        evidence_weight_threshold=config.scoring.evidence_weight_threshold,
    )

    manifest_path = run_dir / "manifest.json"
    summary = {
        "run_id": artifacts.manifest["run_id"],
        "source_run_id": artifacts.manifest["run_id"],
        "source_manifest_sha256": file_sha256(manifest_path),
        "artifact_schema_version": artifacts.manifest["artifact_schema_version"],
        "source_git_commit": artifacts.manifest.get("git_commit"),
        "config_sha256": artifacts.manifest["config_sha256"],
        "status": artifacts.manifest["status"],
        "python_version": artifacts.manifest["python_version"],
        "package_versions": artifacts.manifest["package_versions"],
        "seed": artifacts.manifest["random_seed"],
        "metrics": artifacts.metrics,
        "baseline_comparison": {
            key: baseline_result.metrics[key]
            for key in (
                "precision",
                "recall",
                "f1",
                "pr_auc",
                "top1_correction_rate",
                "top2_correction_rate",
            )
        },
        "failure_boundary": _residual_correlation_means(run_dir),
        "time_series_validation": _time_series_validation_summary(run_dir),
        "artifact_sha256": {
            name: file_sha256(run_dir / name)
            for name in (
                "predictions.parquet",
                "metrics.json",
                "simulation_validation.csv",
            )
        },
        "generated_by": (
            "python -m ltverify report --run-dir <run_dir> --output "
            "<output_path>"
        ),
    }
    write_json_atomic(summary, output_path)
    if manifest_output is None:
        manifest_target = output_path.with_name(
            f"{output_path.stem}.manifest.json"
        )
    else:
        manifest_target = Path(manifest_output)
    write_json_atomic(artifacts.manifest, manifest_target)
    return output_path
