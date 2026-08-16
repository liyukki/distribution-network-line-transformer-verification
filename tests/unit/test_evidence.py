import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from ltverify.experiments import verify_experiment_manifest
from ltverify.manifest import classify_artifact_schema_version, file_sha256

ROOT = Path(__file__).resolve().parents[2]


def test_delivered_robustness_manifest_passes_strict_source_verification() -> None:
    manifest_path = ROOT / "reports/metrics/robustness_experiment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_experiment_manifest(
        manifest,
        manifest_path.parent,
        experiment_config_path=ROOT / "configs/robustness.yaml",
        base_config_path=ROOT / "configs/default.yaml",
    )


def test_classify_schema_states() -> None:
    assert classify_artifact_schema_version(None) == ("invalid", None)
    assert classify_artifact_schema_version(1) == ("legacy", 1)
    assert classify_artifact_schema_version(2) == ("current", 2)
    assert classify_artifact_schema_version(3) == ("newer", 3)
    assert classify_artifact_schema_version(2.5) == ("invalid", None)
    assert classify_artifact_schema_version(float("inf")) == ("invalid", None)
    assert classify_artifact_schema_version(True) == ("invalid", None)
    assert classify_artifact_schema_version("2") == ("invalid", None)
    assert classify_artifact_schema_version([]) == ("invalid", None)


def _authoritative_experiment_manifest() -> tuple[dict[str, object], Path]:
    manifest_path = ROOT / "reports/metrics/robustness_experiment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest, manifest_path.parent


def _verify_tampered(manifest: dict[str, object], artifact_dir: Path) -> None:
    verify_experiment_manifest(
        manifest,
        artifact_dir,
        experiment_config_path=ROOT / "configs/robustness.yaml",
        base_config_path=ROOT / "configs/default.yaml",
    )


def _minimal_experiment_manifest(
    tmp_path: Path,
    summary: pd.DataFrame,
    case_counts: dict[str, object],
) -> dict[str, object]:
    summary_path = tmp_path / "robustness_summary.csv"
    summary.to_csv(summary_path, index=False)
    aggregates_path = tmp_path / "robustness_aggregates.csv"
    pd.DataFrame().to_csv(aggregates_path, index=False)
    return {
        "artifact_schema_version": 2,
        "experiment_config_name": "robustness.yaml",
        "experiment_config_sha256": "0" * 64,
        "experiment_config_snapshot": {},
        "base_config_name": "default.yaml",
        "base_config_sha256": "0" * 64,
        "base_config_snapshot": {},
        "case_counts": case_counts,
        "output_files": {
            "robustness_summary.csv": file_sha256(summary_path),
            "robustness_aggregates.csv": file_sha256(aggregates_path),
        },
    }


def test_experiment_manifest_rejects_tampered_experiment_snapshot() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["experiment_config_snapshot"]["base_config"] = "evil.yaml"
    with pytest.raises(ValueError, match="experiment.*snapshot|snapshot.*experiment|不一致"):
        _verify_tampered(tampered, artifact_dir)


def test_experiment_manifest_rejects_tampered_base_snapshot() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["base_config_snapshot"]["profiles"]["days"] = 1
    with pytest.raises(ValueError, match="base.*snapshot|snapshot.*base|不一致"):
        _verify_tampered(tampered, artifact_dir)


def test_experiment_manifest_rejects_case_counts_status_mismatch() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["case_counts"] = {"total": 130, "completed": 0, "failed": 130}
    with pytest.raises(ValueError, match="completed|failed|status"):
        _verify_tampered(tampered, artifact_dir)


def test_experiment_manifest_rejects_missing_core_output_hash() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    del tampered["output_files"]["robustness_aggregates.csv"]
    with pytest.raises(ValueError, match="output_files|robustness_aggregates"):
        _verify_tampered(tampered, artifact_dir)


def test_experiment_manifest_rejects_experiment_config_name_mismatch() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["experiment_config_name"] = "other.yaml"
    with pytest.raises(ValueError, match="experiment.*name|name.*experiment|不一致"):
        _verify_tampered(tampered, artifact_dir)


def test_experiment_manifest_rejects_base_config_name_mismatch() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["base_config_name"] = "other.yaml"
    with pytest.raises(ValueError, match="base.*name|name.*base|不一致"):
        _verify_tampered(tampered, artifact_dir)


@pytest.mark.parametrize(
    "bad_counts",
    [
        {"total": True, "completed": 130, "failed": 0},
        {"total": 130.0, "completed": 130, "failed": 0},
        {"total": "130", "completed": 130, "failed": 0},
        {"total": 130, "completed": -1, "failed": 131},
    ],
)
def test_experiment_manifest_rejects_invalid_case_counts(
    tmp_path: Path, bad_counts: dict[str, object]
) -> None:
    import pandas as pd

    summary = pd.DataFrame(
        {
            "case_id": ["a"],
            "status": ["completed"],
        }
    )
    manifest = _minimal_experiment_manifest(tmp_path, summary, bad_counts)
    with pytest.raises(ValueError, match="case_counts|completed|failed|total"):
        verify_experiment_manifest(manifest, tmp_path)


def test_experiment_manifest_rejects_unknown_status_in_summary(
    tmp_path: Path,
) -> None:
    import pandas as pd

    summary = pd.DataFrame(
        {
            "case_id": ["a", "b"],
            "status": ["completed", "mystery"],
        }
    )
    manifest = _minimal_experiment_manifest(
        tmp_path,
        summary,
        {"total": 2, "completed": 1, "failed": 1},
    )
    with pytest.raises(ValueError, match="status|未知"):
        verify_experiment_manifest(manifest, tmp_path)


@pytest.mark.parametrize(
    "unsafe",
    [
        "../evil.csv",
        "..\\evil.csv",
        "C:\\evil.csv",
        "/absolute/evil.csv",
        "\\\\server\\share\\evil.csv",
    ],
)
def test_experiment_manifest_rejects_unsafe_output_names(
    tmp_path: Path, unsafe: str
) -> None:
    import pandas as pd

    summary = pd.DataFrame({"case_id": ["a"], "status": ["completed"]})
    manifest = _minimal_experiment_manifest(
        tmp_path,
        summary,
        {"total": 1, "completed": 1, "failed": 0},
    )
    manifest["output_files"][unsafe] = "0" * 64
    with pytest.raises(ValueError):
        verify_experiment_manifest(manifest, tmp_path)


def test_experiment_manifest_offline_mode_reports_offline_verification() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["experiment_config_snapshot"] = {"forged": True}
    tampered["base_config_snapshot"] = {"forged": True}
    tampered["experiment_config_sha256"] = "0" * 64
    tampered["base_config_sha256"] = "1" * 64
    level = verify_experiment_manifest(tampered, artifact_dir)
    assert level == "offline"


def test_experiment_manifest_strict_mode_requires_source_configs() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    with pytest.raises(ValueError, match="source|config|严格"):
        verify_experiment_manifest(
            manifest,
            artifact_dir,
            require_source_configs=True,
        )


def test_experiment_manifest_strict_mode_rejects_forged_snapshot() -> None:
    manifest, artifact_dir = _authoritative_experiment_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["experiment_config_snapshot"] = {"forged": True}
    with pytest.raises(ValueError, match="snapshot|不一致"):
        verify_experiment_manifest(
            tampered,
            artifact_dir,
            experiment_config_path=ROOT / "configs/robustness.yaml",
            base_config_path=ROOT / "configs/default.yaml",
            require_source_configs=True,
        )
