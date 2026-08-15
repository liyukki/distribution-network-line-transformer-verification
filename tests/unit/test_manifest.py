import sys
from pathlib import Path

from ltverify.manifest import build_manifest


def test_manifest_contains_reproduction_fields(tmp_path: Path) -> None:
    manifest = build_manifest(Path("configs/default.yaml"), tmp_path)
    assert manifest.random_seed == 42
    assert len(manifest.config_sha256) == 64
    expected_prefix = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert manifest.python_version.startswith(expected_prefix)
    assert "pandapower" in manifest.package_versions
