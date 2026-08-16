"""Atomic artifact readers and writers.

Every writer goes through a sibling temporary file and replaces the target
atomically, so interrupted runs never leave half-written artifacts.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _temporary_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".tmp")


def write_table_atomic(frame: pd.DataFrame, path: Path) -> Path:
    """Write a DataFrame as parquet or csv, chosen by file suffix."""
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix == ".parquet":
        writer = lambda tmp: frame.to_parquet(tmp)
    elif suffix == ".csv":
        writer = lambda tmp: frame.to_csv(tmp, index=False, encoding="utf-8")
    else:
        raise ValueError("unsupported table format")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temporary_path(target)
    writer(tmp)
    tmp.replace(target)
    return target


def read_table(path: Path) -> pd.DataFrame:
    """Read a table artifact by file suffix."""
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(target)
    if suffix == ".csv":
        return pd.read_csv(target)
    raise ValueError("unsupported table format")


def write_json_atomic(payload: Any, path: Path) -> Path:
    """Write a JSON-serializable object atomically as UTF-8."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temporary_path(target)
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    tmp.replace(target)
    return target


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
