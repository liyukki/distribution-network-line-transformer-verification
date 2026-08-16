"""Automatic evidence summary generation.

Regenerates reports/metrics/default_summary.json from one run directory.
Every number is read from or computed from the run artifacts: the run ID,
manifest, metrics and the baseline comparison are never hand-copied.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ltverify.config import load_config
from ltverify.data_access import load_run_artifacts
from ltverify.evaluation import evaluate_predictions
from ltverify.io import write_json_atomic
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


def generate_default_summary(run_dir: Path, output_path: Path) -> Path:
    """Regenerate the default-summary evidence file from run artifacts."""
    run_dir = Path(run_dir)
    artifacts = load_run_artifacts(run_dir)
    config = load_config(run_dir / "config.snapshot.yaml")

    baseline_scored = score_candidates(
        artifacts.candidate_features, _BASELINE_WEIGHTS
    )
    baseline_predictions = diagnose(
        baseline_scored, artifacts.ledger, config.scoring
    )
    baseline_result = evaluate_predictions(
        baseline_predictions, artifacts.truth, artifacts.ledger, baseline_scored
    )

    summary = {
        "run_id": artifacts.manifest["run_id"],
        "manifest_path": str((run_dir / "manifest.json").resolve()),
        "config_sha256": artifacts.manifest["config_sha256"],
        "git_commit": artifacts.manifest.get("git_commit"),
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
        "generated_by": (
            "python -m ltverify report --run-dir <run_dir> --output "
            "<output_path>"
        ),
    }
    write_json_atomic(summary, output_path)
    return output_path
