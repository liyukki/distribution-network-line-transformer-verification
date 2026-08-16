import json
from pathlib import Path

import pytest

from ltverify.pipeline import run_pipeline
from ltverify.report import generate_default_summary


def _fixture_run(tmp_path: Path) -> Path:
    config = tmp_path / "small.yaml"
    config.write_text(
        f"""random_seed: 42
network:
  feeder_count: 3
  transformers_per_feeder: 3
  hv_kv: 110.0
  mv_kv: 10.0
  lv_kv: 0.4
profiles:
  start: "2026-01-01"
  days: 1
  interval_minutes: 360
  power_factor: 0.95
  pv_scale: 1.0
validation:
  voltage_min_pu: 0.90
  voltage_max_pu: 1.10
  power_balance_tolerance_mw: 0.000001
  transformer_loading_limit_percent: 100.0
  terminate_on_critical: true
corruption:
  ledger_error_rate: 0.20
  voltage_noise_std_pu: 0.0005
  missing_rate: 0.01
  spike_rate: 0.001
  time_shift_steps: 0
  time_shift_device_rate: 0.10
scoring:
  current_score_threshold: 0.70
  margin_threshold: 0.08
  minimum_coverage: 0.80
  minimum_pairs: 16
  rolling_window: 24
  event_quantile: 0.90
  interpolation_limit: 2
  evidence_weight_threshold: 0.5
output_root: {tmp_path.as_posix()}
""",
        encoding="utf-8",
    )
    return run_pipeline(config)


def test_generate_default_summary_from_artifacts(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    output = tmp_path / "summary.json"
    generate_default_summary(run_dir, output)
    summary = json.loads(output.read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == manifest["run_id"]
    assert summary["status"] == "completed"
    assert summary["metrics"]["f1"] == metrics["f1"]
    assert "f1" in summary["baseline_comparison"]
    assert summary["failure_boundary"]["same_feeder_pair_count"] > 0
    assert summary["failure_boundary"]["cross_feeder_pair_count"] > 0


def test_summary_is_portable_and_carries_hashes(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    output = tmp_path / "summary.json"
    generate_default_summary(run_dir, output)
    summary = json.loads(output.read_text(encoding="utf-8"))
    # 不得包含本机绝对工作区路径
    assert "manifest_path" not in summary

    def walk_strings(value: object) -> list[str]:
        found: list[str] = []
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                found.extend(walk_strings(item))
        elif isinstance(value, list):
            for item in value:
                found.extend(walk_strings(item))
        return found

    for text in walk_strings(summary):
        assert "D:\\" not in text.replace("\\", "\\")
    assert summary["artifact_schema_version"] == 2
    assert len(summary["source_manifest_sha256"]) == 64
    validation = summary["time_series_validation"]
    for key in (
        "timestamp_count",
        "convergence_rate",
        "voltage_min_pu",
        "voltage_max_pu",
        "maximum_transformer_loading_percent",
        "maximum_power_balance_error_mw",
        "severity_counts",
        "violation_type_counts",
    ):
        assert key in validation


def test_report_refuses_tampered_config_snapshot(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    snapshot = run_dir / "config.snapshot.yaml"
    snapshot.write_text(
        snapshot.read_text(encoding="utf-8") + "\n# tampered\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="config"):
        generate_default_summary(run_dir, tmp_path / "summary.json")


def test_report_manifest_output_contract(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    custom_output = tmp_path / "custom_summary.json"
    custom_manifest = tmp_path / "custom.manifest.json"
    generate_default_summary(
        run_dir, custom_output, manifest_output=custom_manifest
    )
    assert custom_manifest.exists()
    assert not (tmp_path / "default_manifest.json").exists()
    # 未指定时使用 <stem>.manifest.json
    another = tmp_path / "another_summary.json"
    generate_default_summary(run_dir, another)
    assert (tmp_path / "another_summary.manifest.json").exists()


def test_report_verifies_before_parsing(monkeypatch, tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "predictions.parquet").write_bytes(b"tampered")
    calls: list[str] = []

    def forbidden_loader(*args: object, **kwargs: object) -> object:
        calls.append("load_run_artifacts")
        raise AssertionError("解析器不得在验签前执行")

    def forbidden_config(*args: object, **kwargs: object) -> object:
        calls.append("load_config")
        raise AssertionError("配置解析不得在验签前执行")

    monkeypatch.setattr("ltverify.report.load_run_artifacts", forbidden_loader)
    monkeypatch.setattr("ltverify.report.load_config", forbidden_config)
    with pytest.raises(ValueError, match="产物校验失败"):
        generate_default_summary(run_dir, tmp_path / "summary.json")
    assert calls == []


def test_tampered_snapshot_yields_integrity_error_not_parse_error(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run(tmp_path)
    (run_dir / "config.snapshot.yaml").write_text(
        "key: [unclosed", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="产物校验失败"):
        generate_default_summary(run_dir, tmp_path / "summary.json")


def test_report_rejects_output_collisions(tmp_path: Path) -> None:
    run_dir = _fixture_run(tmp_path)
    same = tmp_path / "same.json"
    with pytest.raises(ValueError, match="相同"):
        generate_default_summary(run_dir, same, manifest_output=same)
    assert not same.exists()
    # resolve 后相同的两条路径
    output = tmp_path / "out.json"
    manifest_alias = tmp_path / "sub" / ".." / "out.json"
    with pytest.raises(ValueError, match="相同"):
        generate_default_summary(run_dir, output, manifest_output=manifest_alias)
    assert not output.exists()
    # 覆盖源清单声明产物
    with pytest.raises(ValueError, match="源产物"):
        generate_default_summary(run_dir, run_dir / "manifest.json")
    with pytest.raises(ValueError, match="源产物"):
        generate_default_summary(run_dir, run_dir / "predictions.parquet")
