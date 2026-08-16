import json
from pathlib import Path

import pandas as pd
import pytest

from ltverify.manifest import file_sha256
from ltverify.robustness_loader import (
    RobustnessLoadError,
    load_robustness_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]


def _write_current_trio(tmp_path: Path) -> Path:
    artifact_dir = tmp_path / "current"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(
        {
            "case_id": ["a", "b"],
            "family": ["missing_rate", "missing_rate"],
            "value": ["0.0", "0.1"],
            "status": ["completed", "completed"],
        }
    )
    summary_path = artifact_dir / "robustness_summary.csv"
    summary.to_csv(summary_path, index=False)
    aggregates = pd.DataFrame(
        {
            "family": ["missing_rate", "missing_rate"],
            "value": ["0.0", "0.1"],
            "mean_precision": [0.9, 0.8],
            "std_precision": [0.05, 0.06],
        }
    )
    aggregates_path = artifact_dir / "robustness_aggregates.csv"
    aggregates.to_csv(aggregates_path, index=False)
    manifest = {
        "artifact_schema_version": 2,
        "experiment_config_name": "robustness.yaml",
        "experiment_config_sha256": "0" * 64,
        "experiment_config_snapshot": {},
        "base_config_name": "default.yaml",
        "base_config_sha256": "0" * 64,
        "base_config_snapshot": {},
        "case_counts": {"total": 2, "completed": 2, "failed": 0},
        "output_files": {
            "robustness_summary.csv": file_sha256(summary_path),
            "robustness_aggregates.csv": file_sha256(aggregates_path),
        },
    }
    (artifact_dir / "robustness_experiment_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return artifact_dir


def _write_legacy_pair(tmp_path: Path) -> tuple[Path, Path]:
    artifact_dir = tmp_path / "legacy"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    aggregates = pd.DataFrame(
        {
            "family": ["missing_rate"],
            "value": ["0.1"],
            "mean_precision": [0.8],
            "std_precision": [0.06],
        }
    )
    summary = pd.DataFrame(
        {
            "case_id": ["a"],
            "family": ["missing_rate"],
            "value": ["0.1"],
            "status": ["completed"],
        }
    )
    aggregates_path = artifact_dir / "experiment_aggregates.csv"
    summary_path = artifact_dir / "experiment_summary.csv"
    aggregates.to_csv(aggregates_path, index=False)
    summary.to_csv(summary_path, index=False)
    return aggregates_path, summary_path


def test_load_rejects_forged_aggregates_not_in_manifest(tmp_path: Path) -> None:
    artifact_dir = _write_current_trio(tmp_path)
    forged = artifact_dir / "robustness_forged.csv"
    pd.DataFrame(
        {
            "family": ["FORGED"],
            "value": ["999"],
            "mean_precision": [0.999],
            "std_precision": [0.0],
        }
    ).to_csv(forged, index=False)
    with pytest.raises(RobustnessLoadError, match="aggregates|robustness_aggregates"):
        load_robustness_artifacts(
            forged,
            artifact_dir / "robustness_summary.csv",
            experiment_config_path=ROOT / "configs/robustness.yaml",
            base_config_path=ROOT / "configs/default.yaml",
        )


def test_load_rejects_forged_summary_not_in_manifest(tmp_path: Path) -> None:
    artifact_dir = _write_current_trio(tmp_path)
    forged = artifact_dir / "robustness_forged_summary.csv"
    pd.DataFrame(
        {
            "case_id": ["FORGED"],
            "status": ["completed"],
        }
    ).to_csv(forged, index=False)
    with pytest.raises(RobustnessLoadError, match="summary|robustness_summary"):
        load_robustness_artifacts(
            artifact_dir / "robustness_aggregates.csv",
            forged,
            experiment_config_path=ROOT / "configs/robustness.yaml",
            base_config_path=ROOT / "configs/default.yaml",
        )


@pytest.mark.parametrize(
    ("aggregate_name", "summary_name", "should_pass", "state"),
    [
        ("robustness_aggregates.csv", "robustness_summary.csv", True, "artifact_hashes_verified"),
        ("robustness_forged.csv", "robustness_summary.csv", False, None),
        ("robustness_aggregates.csv", "robustness_forged_summary.csv", False, None),
        ("robustness_aggregates.csv", "experiment_summary.csv", False, None),
        ("experiment_aggregates.csv", "experiment_summary.csv", True, "legacy_unverified"),
        ("experiment_aggregates.csv", "robustness_summary.csv", False, None),
        ("experiment_fake.csv", "", False, None),
    ],
)
def test_load_enforces_exact_file_roles(
    tmp_path: Path,
    aggregate_name: str,
    summary_name: str,
    should_pass: bool,
    state: str | None,
) -> None:
    current_dir = _write_current_trio(tmp_path)
    legacy_agg, legacy_summary = _write_legacy_pair(tmp_path)

    if aggregate_name.startswith("experiment_"):
        aggregate_path = legacy_agg.parent / aggregate_name
        if aggregate_name != "experiment_aggregates.csv":
            aggregate_path.write_text("family,value\nx,1\n", encoding="utf-8")
    else:
        aggregate_path = current_dir / aggregate_name
        if aggregate_name not in ("robustness_aggregates.csv", "robustness_forged.csv"):
            aggregate_path = current_dir / aggregate_name
        if aggregate_name == "robustness_forged.csv":
            pd.DataFrame(
                {
                    "family": ["FORGED"],
                    "value": ["999"],
                    "mean_precision": [0.999],
                    "std_precision": [0.0],
                }
            ).to_csv(aggregate_path, index=False)

    if summary_name:
        if summary_name.startswith("experiment_"):
            summary_path = legacy_summary.parent / summary_name
            if summary_name != "experiment_summary.csv":
                summary_path.write_text(
                    "case_id,status\nx,completed\n", encoding="utf-8"
                )
        else:
            summary_path = current_dir / summary_name
            if summary_name == "robustness_forged_summary.csv":
                pd.DataFrame(
                    {"case_id": ["FORGED"], "status": ["completed"]}
                ).to_csv(summary_path, index=False)
    else:
        summary_path = None

    if should_pass:
        result = load_robustness_artifacts(aggregate_path, summary_path)
        assert result.verification_state == state
    else:
        with pytest.raises(RobustnessLoadError):
            load_robustness_artifacts(aggregate_path, summary_path)


@pytest.mark.parametrize("raw", ["[]", "null", '"manifest"', "42", "true"])
def test_load_rejects_non_object_manifest(tmp_path: Path, raw: str) -> None:
    artifact_dir = _write_current_trio(tmp_path)
    (artifact_dir / "robustness_experiment_manifest.json").write_text(
        raw, encoding="utf-8"
    )
    with pytest.raises(RobustnessLoadError, match="object|字典|manifest|清单"):
        load_robustness_artifacts(
            artifact_dir / "robustness_aggregates.csv",
            artifact_dir / "robustness_summary.csv",
        )


@pytest.mark.parametrize(
    ("family", "value"),
    [
        (["missing_rate", None], ["0.1", "0.2"]),
        (["missing_rate", "   "], ["0.1", "0.2"]),
        ([None, None], ["0.1", "0.2"]),
        (["missing_rate", "missing_rate"], ["0.1", None]),
    ],
)
def test_load_rejects_missing_or_blank_family_value(
    tmp_path: Path, family: list[object], value: list[object]
) -> None:
    aggregate_path = tmp_path / "experiment_aggregates.csv"
    pd.DataFrame(
        {
            "family": family,
            "value": value,
            "mean_precision": [0.9, 0.8],
            "std_precision": [0.05, 0.06],
        }
    ).to_csv(aggregate_path, index=False)
    with pytest.raises(RobustnessLoadError, match="family|value"):
        load_robustness_artifacts(aggregate_path)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("mean_precision", float("inf")),
        ("mean_precision", float("-inf")),
        ("std_precision", float("inf")),
        ("std_precision", float("-inf")),
        ("std_precision", -1.0),
        ("std_precision", "abc"),
    ],
)
def test_load_rejects_invalid_metric_values(
    tmp_path: Path, column: str, value: object
) -> None:
    aggregate_path = tmp_path / "experiment_aggregates.csv"
    frame = pd.DataFrame(
        {
            "family": ["missing_rate"],
            "value": ["0.1"],
            "mean_precision": [0.8],
            "std_precision": [0.06],
        }
    )
    frame[column] = [value]
    frame.to_csv(aggregate_path, index=False)
    with pytest.raises(RobustnessLoadError, match="非有限|非数值|标准差|std"):
        load_robustness_artifacts(aggregate_path)
