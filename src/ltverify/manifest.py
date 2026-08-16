"""Run manifests: environment capture and reproduction metadata."""

import hashlib
import platform
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


def verify_manifest_hashes(manifest: dict[str, object], run_dir: Path) -> None:
    """Raise on any artifact whose bytes no longer match the manifest."""
    for name, expected in manifest.get("output_sha256", {}).items():
        path = Path(run_dir) / str(name)
        if not path.exists():
            raise ValueError(f"缺少清单产物: {path}")
        actual = file_sha256(path)
        if actual != expected:
            raise ValueError(
                f"产物校验失败: {name}（期望 {expected}，实际 {actual}）"
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
