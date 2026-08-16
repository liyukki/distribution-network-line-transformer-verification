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

import numpy as np
import pandas as pd

from ltverify.experiments import (
    CURRENT_AGGREGATES_NAME,
    CURRENT_MANIFEST_NAME,
    CURRENT_SUMMARY_NAME,
    LEGACY_AGGREGATES_NAME,
    LEGACY_SUMMARY_NAME,
    verify_experiment_manifest,
)
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


def _normalize_aggregates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise RobustnessLoadError("聚合 CSV 为空")
    missing = sorted({"family", "value"} - set(frame.columns))
    if missing:
        raise RobustnessLoadError(
            f"聚合 CSV 缺少必要列: {missing}"
        )
    if frame["family"].isna().any():
        raise RobustnessLoadError("聚合 CSV 的 family 列含缺失值")
    family = frame["family"].astype(str).str.strip()
    if family.eq("").any():
        raise RobustnessLoadError("聚合 CSV 的 family 列含空白值")
    if frame["value"].isna().any():
        raise RobustnessLoadError("聚合 CSV 的 value 列含缺失值")
    value = frame["value"].astype(str).str.strip()
    if value.eq("").any():
        raise RobustnessLoadError("聚合 CSV 的 value 列含空白值")

    normalized = frame.copy()
    normalized["family"] = family.to_numpy()
    normalized["value"] = value.to_numpy()

    for column in normalized.columns:
        if not column.startswith(("mean_", "std_")):
            continue
        converted = pd.to_numeric(normalized[column], errors="coerce")
        non_null_original = normalized[column].notna()
        if converted[non_null_original].isna().any():
            raise RobustnessLoadError(f"{column} 含非数值")
        if converted.notna().any():
            finite = np.isfinite(
                converted[converted.notna()].to_numpy(dtype=float)
            )
            if not finite.all():
                raise RobustnessLoadError(f"{column} 含非有限数值")
            if column.startswith("std_") and (converted < 0).any():
                raise RobustnessLoadError(f"{column} 含负标准差")
        normalized[column] = converted
    return normalized


def _normalize_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if "status" not in frame.columns:
        raise RobustnessLoadError("案例明细 CSV 缺少 status 列")
    if frame["status"].isna().any():
        raise RobustnessLoadError("案例明细 CSV 的 status 列含缺失值")
    status = frame["status"].astype(str).str.strip()
    if status.eq("").any():
        raise RobustnessLoadError("案例明细 CSV 的 status 列含空白值")
    unknown = sorted(set(status) - {"completed", "failed"})
    if unknown:
        raise RobustnessLoadError(
            f"案例明细 CSV 含未知状态: {unknown}"
        )
    normalized = frame.copy()
    normalized["status"] = status.to_numpy()
    return normalized


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

    if aggregates_path.name == CURRENT_AGGREGATES_NAME:
        return _load_current(
            aggregates_path,
            resolved_summary,
            experiment_config_path=experiment_config_path,
            base_config_path=base_config_path,
        )

    if aggregates_path.name == LEGACY_AGGREGATES_NAME:
        return _load_legacy(aggregates_path, resolved_summary)

    raise RobustnessLoadError(
        "无法识别实验产物文件名，必须精确使用 "
        f"{CURRENT_AGGREGATES_NAME} 或 {LEGACY_AGGREGATES_NAME}"
    )


def _load_current(
    aggregates_path: Path,
    resolved_summary: Path | None,
    *,
    experiment_config_path: Path | None,
    base_config_path: Path | None,
) -> RobustnessArtifacts:
    if resolved_summary is not None and (
        resolved_summary.name != CURRENT_SUMMARY_NAME
    ):
        raise RobustnessLoadError(
            f"当前命名 aggregate 必须搭配 {CURRENT_SUMMARY_NAME}"
        )
    artifact_dir = aggregates_path.parent
    manifest_path = artifact_dir / CURRENT_MANIFEST_NAME
    if not manifest_path.is_file():
        raise RobustnessLoadError(
            f"当前命名产物缺少 {CURRENT_MANIFEST_NAME}，"
            "无法进行哈希一致性校验；请使用旧命名或重新生成实验"
        )
    try:
        manifest = read_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RobustnessLoadError(
            f"实验清单解析失败: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise RobustnessLoadError("实验清单顶层必须是 JSON object")

    effective_summary = (
        resolved_summary
        if resolved_summary is not None
        else artifact_dir / CURRENT_SUMMARY_NAME
    )
    if effective_summary.name != CURRENT_SUMMARY_NAME:
        raise RobustnessLoadError(
            f"当前命名 summary 必须是 {CURRENT_SUMMARY_NAME}"
        )

    try:
        verify_experiment_manifest(
            manifest,
            artifact_dir,
            require_source_configs=False,
        )
    except (ValueError, TypeError) as exc:
        raise RobustnessLoadError(
            f"实验产物哈希一致性校验失败: {exc}"
        ) from exc

    aggregates = _normalize_aggregates(_read_csv_safely(aggregates_path))
    summary: pd.DataFrame | None = None
    if effective_summary.exists():
        summary = _normalize_summary(_read_csv_safely(effective_summary))

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


def _load_legacy(
    aggregates_path: Path,
    resolved_summary: Path | None,
) -> RobustnessArtifacts:
    if resolved_summary is not None and (
        resolved_summary.name != LEGACY_SUMMARY_NAME
    ):
        raise RobustnessLoadError(
            f"旧命名 aggregate 必须搭配 {LEGACY_SUMMARY_NAME}"
        )
    aggregates = _normalize_aggregates(_read_csv_safely(aggregates_path))
    summary: pd.DataFrame | None = None
    if resolved_summary is not None:
        summary = _normalize_summary(_read_csv_safely(resolved_summary))
    return RobustnessArtifacts(
        aggregates,
        summary,
        "legacy_unverified",
        "旧命名实验产物未经过哈希一致性校验，仅供兼容展示",
    )
