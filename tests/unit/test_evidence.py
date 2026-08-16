import json
from pathlib import Path

import pytest

from ltverify.experiments import verify_experiment_manifest
from ltverify.manifest import classify_artifact_schema_version

ROOT = Path(__file__).resolve().parents[2]


def test_delivered_robustness_manifest_is_self_verifying() -> None:
    manifest_path = ROOT / "reports/metrics/robustness_experiment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_experiment_manifest(
        manifest,
        manifest_path.parent,
        experiment_config_path=ROOT / "configs/robustness.yaml",
        base_config_path=ROOT / "configs/default.yaml",
    )


def test_classify_schema_states() -> None:
    assert classify_artifact_schema_version(None) == ("legacy", None)
    assert classify_artifact_schema_version(1) == ("legacy", 1)
    assert classify_artifact_schema_version(2) == ("current", 2)
    assert classify_artifact_schema_version(3) == ("newer", 3)
    assert classify_artifact_schema_version(2.5) == ("invalid", None)
    assert classify_artifact_schema_version(float("inf")) == ("invalid", None)
    assert classify_artifact_schema_version(True) == ("invalid", None)
    assert classify_artifact_schema_version("2") == ("invalid", None)
    assert classify_artifact_schema_version([]) == ("invalid", None)
