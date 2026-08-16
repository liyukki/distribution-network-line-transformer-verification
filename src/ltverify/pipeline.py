"""End-to-end pipeline: config to evaluated artifacts in one run."""

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ltverify.config import load_config
from ltverify.corruption import build_truth, corrupt_ledger, disturb_measurements
from ltverify.evaluation import evaluate_predictions
from ltverify.features import build_candidate_features
from ltverify.io import write_json_atomic, write_table_atomic
from ltverify.manifest import RunManifest, build_manifest, file_sha256
from ltverify.network import build_network, topology_frames
from ltverify.preprocessing import prepare_measurements
from ltverify.profiles import generate_profiles
from ltverify.scoring import ScoreWeights, diagnose, score_candidates
from ltverify.simulation import simulate_time_series
from ltverify.validation import run_static_validation


def _run_directory(config_sha256: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return Path(
        f"run-{stamp}-{config_sha256[:8]}-{uuid.uuid4().hex[:6]}"
    )


def _write_manifest(
    manifest: RunManifest, run_dir: Path, output_paths: list[Path]
) -> None:
    manifest.output_paths = [path.name for path in output_paths]
    manifest.output_sha256 = {
        path.name: file_sha256(path) for path in output_paths if path.exists()
    }
    write_json_atomic(
        manifest.model_dump(mode="json"), run_dir / "manifest.json"
    )


def run_pipeline(config_path: Path) -> Path:
    """Run all stages and return the run directory.

    The run directory lives under the configured output root, which
    resolves relative to the current working directory.
    """
    config_path = Path(config_path)
    config = load_config(config_path)
    config_sha256 = build_manifest(config_path, Path(".")).config_sha256
    run_dir = config.output_root / _run_directory(config_sha256)
    run_dir.mkdir(parents=True, exist_ok=False)

    manifest = build_manifest(config_path, run_dir)

    failure_context: dict[str, object] = {}
    try:
        shutil.copyfile(config_path, run_dir / "config.snapshot.yaml")
        _write_manifest(manifest, run_dir, [])
        artifacts = build_network(config.network)

        base_case = run_static_validation(artifacts, config.validation)
        if not base_case.converged:
            failure_context = {
                "stage": "base_case_validation",
                "severity": base_case.severity,
                "violation_count": len(base_case.violations),
                "violation_types": list(base_case.violation_types),
                "violations": list(base_case.violations),
            }
            raise RuntimeError("base-case power flow did not converge")
        if (
            base_case.severity == "critical"
            and config.validation.terminate_on_critical
        ):
            failure_context = {
                "stage": "base_case_validation",
                "severity": base_case.severity,
                "violation_count": len(base_case.violations),
                "violation_types": list(base_case.violation_types),
                "violations": list(base_case.violations),
            }
            raise RuntimeError(
                f"critical base-case violations: {base_case.violations}"
            )

        profiles = generate_profiles(
            artifacts, config.profiles, seed=config.random_seed
        )
        simulation = simulate_time_series(
            artifacts, profiles, config.validation
        )
        if not simulation.failures.empty:
            failure = simulation.failures.iloc[0]
            raise RuntimeError(
                f"simulation failed at {failure['timestamp']}: "
                f"{failure['error_type']} - {failure['message']}"
            )
        if config.validation.terminate_on_critical and len(simulation.validation):
            critical = simulation.validation[
                simulation.validation["severity"] == "critical"
            ]
            if len(critical):
                stamps = critical["timestamp"].head(3).tolist()
                raise RuntimeError(
                    f"critical physical violations at timestamps: {stamps}"
                )

        truth = build_truth(artifacts)
        ledger = corrupt_ledger(
            truth, config.corruption.ledger_error_rate, seed=config.random_seed
        )
        observed = disturb_measurements(
            simulation.transformer_measurements,
            config.corruption,
            seed=config.random_seed,
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
        scored = score_candidates(features, ScoreWeights())
        predictions = diagnose(scored, ledger, config.scoring)
        result = evaluate_predictions(
            predictions,
            truth,
            ledger,
            scored,
            evidence_weight_threshold=config.scoring.evidence_weight_threshold,
        )

        nodes, edges = topology_frames(artifacts)
        metrics = dict(result.metrics)
        metrics["base_case_converged"] = base_case.converged
        metrics["base_case_voltage_min_pu"] = base_case.voltage_min_pu
        metrics["base_case_voltage_max_pu"] = base_case.voltage_max_pu
        metrics["base_case_balance_error_mw"] = (
            base_case.absolute_power_balance_error_mw
        )
        metrics["base_case_severity"] = base_case.severity
        metrics["base_case_violation_count"] = len(base_case.violations)
        metrics["base_case_violation_types"] = list(base_case.violation_types)
        metrics["base_case_violations"] = list(base_case.violations)

        outputs: list[Path] = [
            run_dir / "config.snapshot.yaml",
            run_dir / "truth_topology.csv",
            run_dir / "reported_ledger.csv",
            run_dir / "transformer_measurements.parquet",
            run_dir / "feeder_measurements.parquet",
            run_dir / "observed_measurements.parquet",
            run_dir / "candidate_features.parquet",
            run_dir / "predictions.parquet",
            run_dir / "metrics.json",
            run_dir / "confusion_matrix.csv",
            run_dir / "network_nodes.csv",
            run_dir / "network_edges.csv",
            run_dir / "simulation_validation.csv",
        ]
        write_table_atomic(truth, outputs[1])
        write_table_atomic(ledger, outputs[2])
        write_table_atomic(simulation.transformer_measurements, outputs[3])
        write_table_atomic(simulation.feeder_measurements, outputs[4])
        write_table_atomic(observed, outputs[5])
        write_table_atomic(scored, outputs[6])
        write_table_atomic(predictions, outputs[7])
        write_json_atomic(metrics, outputs[8])
        write_table_atomic(result.confusion_matrix.reset_index(), outputs[9])
        write_table_atomic(nodes, outputs[10])
        write_table_atomic(edges, outputs[11])
        write_table_atomic(simulation.validation, outputs[12])

        manifest.status = "completed"
        manifest.finished_at_utc = datetime.now(UTC)
        _write_manifest(manifest, run_dir, outputs)
        return run_dir
    except Exception as exc:
        manifest.status = "failed"
        manifest.finished_at_utc = datetime.now(UTC)
        failure_summary: dict[str, object] = {
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        failure_summary.update(failure_context)
        manifest.failure_summary = failure_summary
        snapshot = run_dir / "config.snapshot.yaml"
        if snapshot.exists():
            _write_manifest(manifest, run_dir, [snapshot])
        else:
            manifest_path = run_dir / "manifest.json"
            if manifest_path.exists():
                manifest_path.unlink()
        raise
