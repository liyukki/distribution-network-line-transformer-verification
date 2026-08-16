"""Safe loading and verification for robustness experiment dashboard inputs.

The Streamlit robustness page treats user-supplied paths and CSVs as
external input. This module centralizes the safe-loading contract:

- paths must exist and be regular files;
- current ``robustness_*`` artifacts are verified against their sibling
  ``robustness_experiment_manifest.json`` before any table is parsed;
- legacy ``experiment_*`` artifacts are accepted for compatibility but are
  clearly reported as unverified;
- parse and schema errors are converted to user-facing domain errors.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from ltverify.experiments import verify_experiment_manifest
from ltverify.io import read_json

VerificationState = Literal[
    "strict_verified",
    "artifact_hashes_verified",
    "legacy_unverified",
]


class RobustnessLoadError(RuntimeError):
    """Raised when robustness dashboard inputs cannot be safely loaded."""


@dataclass(frozen=True)
class RobustnessArtifacts:
    aggregates: pd.DataFrame
    summary: pd.DataFrame | None
    verification_state: VerificationState
    message: str


def _ensure_regular_file(path: Path) -> None:
    if not path.exists():
        raise RobustnessLoadError(f"文件不存在: {path}")
    if not path.is_file():
        raise RobustnessLoadError(f"路径不是普通文件: {path}")


def _read_csv_safely(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (
        OSError,
        UnicodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as exc:
        raise RobustnessLoadError(
            f"无法解析 CSV: {path.name}: {exc}"
        ) from exc


def _validate_aggregates(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise RobustnessLoadError("聚合 CSV 为空")
    missing = sorted({"family", "value"} - set(frame.columns))
    if missing:
        raise RobustnessLoadError(
            f"聚合 CSV 缺少必要列: {missing}"
        )
    if frame["family"].dropna().astype(str).str.strip().eq("").all():
        raise RobustnessLoadError("聚合 CSV 的 family 列没有可用取值")


def _validate_summary(frame: pd.DataFrame) -> None:
    if "status" not in frame.columns:
        raise RobustnessLoadError("案例明细 CSV 缺少 status 列")
    unknown = sorted(
        set(frame["status"].dropna().astype(str).unique())
        - {"completed", "failed"}
    )
    if unknown:
        raise RobustnessLoadError(
            f"案例明细 CSV 含未知状态: {unknown}"
        )


def load_robustness_artifacts(
    aggregates_path: Path,
    summary_path: Path | None = None,
    *,
    experiment_config_path: Path | None = None,
    base_config_path: Path | None = None,
) -> RobustnessArtifacts:
    """Load and verify robustness experiment tables for display.

    Current-naming artifacts are verified against the sibling manifest
    before parsing. When both source config paths are supplied and match,
    the returned state is ``strict_verified``; otherwise it is
    ``artifact_hashes_verified``. Legacy ``experiment_*`` inputs are
    returned as ``legacy_unverified``.
    """
    aggregates_path = Path(aggregates_path)
    _ensure_regular_file(aggregates_path)

    resolved_summary: Path | None = None
    if summary_path:
        resolved_summary = Path(summary_path)
        _ensure_regular_file(resolved_summary)
        if resolved_summary.parent.resolve() != aggregates_path.parent.resolve():
            raise RobustnessLoadError(
                "aggregates 与 summary 必须来自同一实验目录"
            )

    if aggregates_path.name.startswith("robustness_"):
        artifact_dir = aggregates_path.parent
        manifest_path = artifact_dir / "robustness_experiment_manifest.json"
        if not manifest_path.is_file():
            raise RobustnessLoadError(
                "当前命名产物缺少 robustness_experiment_manifest.json，"
                "无法验签；请使用旧命名或重新生成实验"
            )
        try:
            manifest = read_json(manifest_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RobustnessLoadError(
                f"实验清单解析失败: {exc}"
            ) from exc

        if resolved_summary is not None and (
            resolved_summary.parent.resolve() != artifact_dir.resolve()
        ):
            raise RobustnessLoadError(
                "当前命名产物要求 aggregates 与 summary 位于同一目录"
            )
        effective_summary = (
            resolved_summary
            if resolved_summary is not None
            else artifact_dir / "robustness_summary.csv"
        )
        try:
            verify_experiment_manifest(
                manifest,
                artifact_dir,
                require_source_configs=False,
            )
        except (ValueError, TypeError) as exc:
            raise RobustnessLoadError(
                f"实验产物验签失败: {exc}"
            ) from exc

        aggregates = _read_csv_safely(aggregates_path)
        _validate_aggregates(aggregates)

        summary: pd.DataFrame | None = None
        if effective_summary.exists():
            summary = _read_csv_safely(effective_summary)
            _validate_summary(summary)

        strict_message = ""
        if experiment_config_path is not None and base_config_path is not None:
            try:
                verify_experiment_manifest(
                    manifest,
                    artifact_dir,
                    experiment_config_path=experiment_config_path,
                    base_config_path=base_config_path,
                    require_source_configs=True,
                )
                return RobustnessArtifacts(
                    aggregates,
                    summary,
                    "strict_verified",
                    "已完成严格源配置核验（name/hash/snapshot 全部一致）",
                )
            except (ValueError, TypeError) as exc:
                strict_message = str(exc)

        if strict_message:
            return RobustnessArtifacts(
                aggregates,
                summary,
                "artifact_hashes_verified",
                f"产物哈希已验证，但源配置未交叉核验：{strict_message}",
            )
        return RobustnessArtifacts(
            aggregates,
            summary,
            "artifact_hashes_verified",
            "产物哈希已验证（离线模式）",
        )

    if aggregates_path.name.startswith("experiment_"):
        aggregates = _read_csv_safely(aggregates_path)
        _validate_aggregates(aggregates)
        summary = None
        if resolved_summary is not None:
            summary = _read_csv_safely(resolved_summary)
            _validate_summary(summary)
        return RobustnessArtifacts(
            aggregates,
            summary,
            "legacy_unverified",
            "旧命名实验产物未经验签，仅供兼容展示",
        )

    raise RobustnessLoadError(
        "无法识别实验产物命名，请使用 robustness_* 或 experiment_* 前缀"
    )
