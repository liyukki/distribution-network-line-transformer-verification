import pandas as pd
import pytest

from ltverify.io import read_json, read_table, write_json_atomic, write_table_atomic


def test_atomic_parquet_roundtrip_creates_parent_and_leaves_no_tmp(tmp_path) -> None:
    target = tmp_path / "nested" / "data.parquet"
    frame = pd.DataFrame({"timestamp": [1, 2], "value": [0.5, 0.6]})
    write_table_atomic(frame, target)
    assert target.exists()
    roundtrip = read_table(target)
    pd.testing.assert_frame_equal(roundtrip, frame)
    assert list(tmp_path.rglob("*.tmp")) == []


def test_unsupported_suffix_raises(tmp_path) -> None:
    with pytest.raises(ValueError, match="unsupported table format"):
        write_table_atomic(pd.DataFrame({"a": [1]}), tmp_path / "x.txt")


def test_csv_and_json_roundtrip(tmp_path) -> None:
    frame = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    write_table_atomic(frame, tmp_path / "t.csv")
    pd.testing.assert_frame_equal(read_table(tmp_path / "t.csv"), frame)
    payload = {"key": "中文值"}
    write_json_atomic(payload, tmp_path / "m.json")
    assert read_json(tmp_path / "m.json") == payload


def test_json_writer_uses_platform_independent_lf_newlines(tmp_path) -> None:
    target = tmp_path / "portable.json"
    write_json_atomic({"first": 1, "second": 2}, target)
    raw = target.read_bytes()
    assert b"\n" in raw
    assert b"\r\n" not in raw
