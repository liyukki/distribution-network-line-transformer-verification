"""Run manifests: environment capture and reproduction metadata."""

import hashlib
import platform
import re
import subprocess
import uuid
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ltverify.config import load_config

_PACKAGES = ("pandapower", "pandas", "numpy", "pydantic", "scikit-learn", "pyarrow")


class RunManifest(BaseModel):
    run_id: str
    artifact_schema_version: int = 2
    started_at_utc: datetime
    finished_at_utc: datetime | None = None
    status: Literal["running", "completed", "failed"] = "running"
    config_sha256: str
    git_commit: str | None = None
    python_version: str
    package_versions: dict[str, str]
    random_seed: int
    input_paths: list[str]
    output_paths: list[str]
    output_sha256: dict[str, str] = {}
    failure_summary: dict[str, str] | None = None


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def package_versions() -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name in _PACKAGES:
        try:
            resolved[name] = version(name)
        except PackageNotFoundError:
            resolved[name] = "unknown"
    return resolved


def file_sha256(path: Path) -> str:
    """SHA-256 of one file, used for artifact integrity checks."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


SchemaState = Literal["legacy", "current", "newer", "invalid"]


def classify_artifact_schema_version(
    raw: object,
) -> tuple[SchemaState, int | None]:
    """Strict schema version classification.

    Only plain integers are accepted (bool is rejected); floats, inf,
    NaN, strings, lists and None are invalid. < 2 is legacy, == 2 is
    current, > 2 is newer/unsupported.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        return ("invalid", None)
    if raw < 2:
        return ("legacy", raw)
    if raw == 2:
        return ("current", raw)
    return ("newer", raw)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def verify_manifest_hashes(manifest: dict[str, object], run_dir: Path) -> None:
    """Verify a schema-v2 manifest against the run directory.

    Enforces: no duplicate output paths; output_paths and output_sha256
    keys match exactly; every path is a safe relative name; every hash is
    a 64-hex SHA-256; every file exists and matches; and the config
    snapshot hash chain (config.snapshot.yaml == config_sha256) holds.
    """
    paths = manifest.get("output_paths")
    hashes = manifest.get("output_sha256")
    if not isinstance(paths, list) or not isinstance(hashes, dict):
        raise TypeError("清单缺少 output_paths 或 output_sha256 字段")
    if len(paths) != len(set(paths)):
        raise ValueError(f"output_paths 存在重复条目: {paths}")
    if set(paths) != set(hashes.keys()):
        difference = sorted(set(paths) ^ set(hashes.keys()))
        raise ValueError(
            f"output_paths 与 output_sha256 必须一一对应，差异条目: {difference}"
        )
    for name in paths:
        text = str(name)
        if Path(text).is_absolute() or re.match(r"^[A-Za-z]:", text):
            raise ValueError(f"output_paths 不允许绝对路径: {text}")
        if ".." in Path(text).parts:
            raise ValueError(f"output_paths 不允许路径穿越: {text}")
        expected = str(hashes[name])
        if not _SHA256_PATTERN.match(expected):
            raise ValueError(
                f"output_sha256 必须是 64 位十六进制: {text} -> {expected}"
            )
        path = Path(run_dir) / text
        if not path.exists():
            raise ValueError(f"缺少清单产物: {text}")
        actual = file_sha256(path)
        if actual != expected:
            raise ValueError(
                f"产物校验失败: {text}（期望 {expected}，实际 {actual}）"
            )
    if "config.snapshot.yaml" not in hashes:
        raise ValueError(
            "schema-v2 清单必须包含 config.snapshot.yaml 哈希（旧清单请重新运行流水线）"
        )
    config_sha = str(manifest.get("config_sha256", ""))
    if not _SHA256_PATTERN.match(config_sha):
        raise ValueError("manifest.config_sha256 不是 64 位十六进制哈希")
    if hashes["config.snapshot.yaml"] != config_sha:
        raise ValueError(
            "config.snapshot.yaml 哈希与 manifest.config_sha256 不一致"
        )


def build_manifest(config_path: Path, run_dir: Path) -> RunManifest:
    """Capture the environment and inputs of a run."""
    config = load_config(config_path)
    now = datetime.now(UTC)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    return RunManifest(
        run_id=run_id,
        artifact_schema_version=2,
        started_at_utc=now,
        config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        git_commit=git_commit(),
        python_version=platform.python_version(),
        package_versions=package_versions(),
        random_seed=config.random_seed,
        input_paths=[str(config_path)],
        output_paths=[],
        output_sha256={},
    )
