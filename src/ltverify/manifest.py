"""Run manifests: environment capture and reproduction metadata."""

import hashlib
import platform
import re
import subprocess
import uuid
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
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
    failure_summary: dict[str, object] | None = None


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

_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)
_FORBIDDEN_FILENAME_CHARS = set('<>:"|?*')


def validate_portable_relative_path(value: object, *, field: str) -> str:
    """Validate a portable, OS-independent relative artifact path.

    The same contract is used for run manifests and experiment manifests:
    no backslashes, drive letters, UNC/absolute paths, empty segments,
    path traversal, Windows reserved device names, forbidden filename
    characters, or trailing dots/spaces. This is intentionally based on
    POSIX path semantics so Windows-style separators cannot bypass the
    check on a POSIX host.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} 路径必须是非空字符串")
    text = value
    if re.match(r"^[A-Za-z]:", text):
        raise ValueError(
            f"{field} 路径禁止盘符前缀/绝对路径: {text!r}"
        )
    if "\\" in text:
        raise ValueError(f"{field} 路径禁止反斜杠/绝对路径: {text!r}")
    if PurePosixPath(text).is_absolute():
        raise ValueError(f"{field} 路径禁止绝对路径: {text!r}")
    for part in text.split("/"):
        if part in ("", ".", ".."):
            raise ValueError(
                f"{field} 路径禁止空段、点段或路径穿越: {text!r}"
            )
        if any(ord(char) < 32 or char in _FORBIDDEN_FILENAME_CHARS for char in part):
            raise ValueError(
                f"{field} 路径包含非法字符: {text!r}"
            )
        if part != part.rstrip(" ."):
            raise ValueError(
                f"{field} 路径禁止尾随点或空格: {text!r}"
            )
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise ValueError(
                f"{field} 路径包含 Windows 保留设备名: {text!r}"
            )
    return text


def verify_manifest_hashes(manifest: dict[str, object], run_dir: Path) -> None:
    """Verify a schema-v2 manifest against the run directory.

    Enforces: input_paths exists and is a non-empty list of portable
    relative names; no duplicate output paths; output_paths and
    output_sha256 keys match exactly; every path is a safe relative name;
    every hash is a 64-hex SHA-256; every file exists and matches; and the
    config snapshot hash chain (config.snapshot.yaml == config_sha256)
    holds.
    """
    input_paths = manifest.get("input_paths")
    if input_paths is None:
        raise ValueError("input_paths 字段缺失")
    if not isinstance(input_paths, list):
        raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
            "input_paths 必须是 list[str]"
        )
    if not input_paths:
        raise ValueError("input_paths 不能为空列表")
    for index, name in enumerate(input_paths):
        if not isinstance(name, str):
            raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
                f"input_paths[{index}] 必须是字符串"
            )
        validate_portable_relative_path(name, field="input_paths")
    if len(input_paths) != len(set(input_paths)):
        raise ValueError("input_paths 存在重复项")

    paths = manifest.get("output_paths")
    hashes = manifest.get("output_sha256")
    if not isinstance(paths, list):
        raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
            "output_paths 必须是 list[str]"
        )
    if not isinstance(hashes, dict):
        raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
            "output_sha256 必须是 dict[str, str]"
        )
    for index, name in enumerate(paths):
        if not isinstance(name, str):
            raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
                f"output_paths[{index}] 必须是字符串"
            )
        validate_portable_relative_path(name, field="output_paths")
    if len(paths) != len(set(paths)):
        raise ValueError(f"output_paths 存在重复条目: {paths}")
    for key, value in hashes.items():
        if not isinstance(key, str):
            raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
                "output_sha256 的键必须是字符串"
            )
        if not isinstance(value, str):
            raise ValueError(  # noqa: TRY004 - manifest contract errors use ValueError
                f"output_sha256['{key}'] 必须是字符串"
            )
    if set(paths) != set(hashes.keys()):
        difference = sorted(set(paths) ^ set(hashes.keys()))
        raise ValueError(
            f"output_paths 与 output_sha256 必须一一对应，差异条目: {difference}"
        )
    for name in paths:
        text = validate_portable_relative_path(name, field="output_paths")
        expected = hashes[name]
        if not _SHA256_PATTERN.match(expected):
            raise ValueError(
                f"output_sha256['{text}'] 必须是 64 位十六进制字符串"
            )
        path = Path(run_dir) / text
        if not path.is_file():
            raise ValueError(f"清单产物不是普通文件: {text}")
        try:
            actual = file_sha256(path)
        except OSError as exc:
            raise ValueError(
                f"读取清单产物哈希失败: {text}"
            ) from exc
        if actual != expected:
            raise ValueError(
                f"产物校验失败: {text}（期望 {expected}，实际 {actual}）"
            )
    if "config.snapshot.yaml" not in hashes:
        raise ValueError(
            "schema-v2 清单必须包含 config.snapshot.yaml 哈希（旧清单请重新运行流水线）"
        )
    config_sha_value = manifest.get("config_sha256")
    if not isinstance(config_sha_value, str) or not _SHA256_PATTERN.match(
        config_sha_value
    ):
        raise ValueError("manifest.config_sha256 不是 64 位十六进制哈希")
    if hashes["config.snapshot.yaml"] != config_sha_value:
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
        input_paths=[config_path.name],
        output_paths=[],
        output_sha256={},
    )
