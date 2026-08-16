import json
import sys
from pathlib import Path

import pytest

from ltverify.manifest import (
    build_manifest,
    validate_portable_relative_path,
    verify_manifest_hashes,
)

ROOT = Path(__file__).resolve().parents[2]


def test_manifest_contains_reproduction_fields(tmp_path: Path) -> None:
    manifest = build_manifest(Path("configs/default.yaml"), tmp_path)
    assert manifest.random_seed == 42
    assert len(manifest.config_sha256) == 64
    expected_prefix = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert manifest.python_version.startswith(expected_prefix)
    assert "pandapower" in manifest.package_versions


def _fake_manifest(paths: list[str], sha: dict[str, str]) -> dict[str, object]:
    return {"output_paths": paths, "output_sha256": sha}


def test_output_paths_and_sha_keys_must_match_exactly(tmp_path: Path) -> None:
    extra_hash = _fake_manifest(["a.csv"], {"a.csv": "0" * 64, "b.csv": "0" * 64})
    with pytest.raises(ValueError, match="一一对应"):
        verify_manifest_hashes(extra_hash, tmp_path)
    missing_hash = _fake_manifest(["a.csv", "b.csv"], {"a.csv": "0" * 64})
    with pytest.raises(ValueError, match="一一对应"):
        verify_manifest_hashes(missing_hash, tmp_path)
    empty_hash = _fake_manifest(["a.csv"], {})
    with pytest.raises(ValueError, match="一一对应"):
        verify_manifest_hashes(empty_hash, tmp_path)


def test_manifest_rejects_unsafe_paths_and_bad_hashes(tmp_path: Path) -> None:
    absolute = _fake_manifest([str(tmp_path / "a.csv")], {str(tmp_path / "a.csv"): "0" * 64})
    with pytest.raises(ValueError, match="绝对路径"):
        verify_manifest_hashes(absolute, tmp_path)
    traversal = _fake_manifest([".." + "/evil.csv"], {".." + "/evil.csv": "0" * 64})
    with pytest.raises(ValueError, match="路径穿越"):
        verify_manifest_hashes(traversal, tmp_path)
    duplicated = _fake_manifest(["a.csv", "a.csv"], {"a.csv": "0" * 64})
    with pytest.raises(ValueError, match="重复"):
        verify_manifest_hashes(duplicated, tmp_path)
    (tmp_path / "a.csv").write_text("x", encoding="utf-8")
    bad_hash = _fake_manifest(["a.csv"], {"a.csv": "not-a-sha256"})
    with pytest.raises(ValueError, match="64 位十六进制"):
        verify_manifest_hashes(bad_hash, tmp_path)


def test_build_manifest_input_paths_are_portable(tmp_path: Path) -> None:
    relative_manifest = build_manifest(Path("configs/default.yaml"), tmp_path)
    assert relative_manifest.input_paths == ["default.yaml"]

    absolute_manifest = build_manifest(ROOT / "configs/default.yaml", tmp_path)
    assert absolute_manifest.input_paths == ["default.yaml"]
    for value in absolute_manifest.input_paths:
        assert "\\" not in value
        assert not Path(value).is_absolute()


def test_delivered_default_manifest_paths_are_portable() -> None:
    manifest_path = ROOT / "reports/metrics/default_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for value in manifest["input_paths"] + manifest["output_paths"]:
        assert "\\" not in value
        assert not Path(value).is_absolute()
        validate_portable_relative_path(value, field="delivered_manifest")


@pytest.mark.parametrize(
    "unsafe",
    [
        "../evil.csv",
        "..\\evil.csv",
        "C:\\evil.csv",
        "/absolute/evil.csv",
        "\\\\server\\share\\evil.csv",
        "a/../../b.csv",
        "a//b.csv",
        "a/./b.csv",
    ],
)
def test_validate_portable_relative_path_rejects_cross_platform_unsafe(
    unsafe: str,
) -> None:
    with pytest.raises(ValueError):
        validate_portable_relative_path(unsafe, field="test")
