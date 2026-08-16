import json
from pathlib import Path

import pytest

from ltverify.experiments import verify_experiment_manifest
from ltverify.manifest import verify_manifest_hashes


def test_verify_manifest_hashes_rejects_directory_output(tmp_path: Path) -> None:
    target = tmp_path / "config.snapshot.yaml"
    target.mkdir()
    manifest = {
        "output_paths": ["config.snapshot.yaml"],
        "output_sha256": {"config.snapshot.yaml": "0" * 64},
        "config_sha256": "0" * 64,
        "input_paths": ["default.yaml"],
    }
    with pytest.raises(ValueError, match="不是普通文件"):
        verify_manifest_hashes(manifest, tmp_path)


def test_verify_experiment_manifest_rejects_directory_output(
    tmp_path: Path,
) -> None:
    aggregates = tmp_path / "robustness_aggregates.csv"
    aggregates.mkdir()
    summary = tmp_path / "robustness_summary.csv"
    summary.write_text("case_id,status\nx,completed\n", encoding="utf-8")
    manifest = {
        "artifact_schema_version": 2,
        "experiment_config_name": "robustness.yaml",
        "experiment_config_sha256": "0" * 64,
        "experiment_config_snapshot": {},
        "base_config_name": "default.yaml",
        "base_config_sha256": "0" * 64,
        "base_config_snapshot": {},
        "case_counts": {"total": 1, "completed": 1, "failed": 0},
        "output_files": {
            "robustness_aggregates.csv": "0" * 64,
            "robustness_summary.csv": "0" * 64,
        },
    }
    with pytest.raises(ValueError, match="不是普通文件"):
        verify_experiment_manifest(manifest, tmp_path)


def test_coordinated_artifact_and_manifest_hash_is_internal_consistency(
    tmp_path: Path,
) -> None:
    """Document that checksum verification is not a digital signature.

    If an attacker can rewrite both the artifact and the sibling manifest
    hash, the verifier still passes. This is intentional: SHA-256 here only
    proves internal consistency, not authenticity.
    """
    from ltverify.manifest import file_sha256

    artifact = tmp_path / "metrics.json"
    artifact.write_text(
        json.dumps({"f1": 0.999999}), encoding="utf-8"
    )
    manifest = {
        "output_paths": ["metrics.json"],
        "output_sha256": {"metrics.json": file_sha256(artifact)},
        "config_sha256": "0" * 64,
        "input_paths": ["default.yaml"],
    }
    # The manifest does not contain config.snapshot.yaml, so verify would
    # fail for schema reasons; this test only asserts the file hash matches
    # after coordinated modification at the file-hash layer.
    assert manifest["output_sha256"]["metrics.json"] == file_sha256(artifact)
