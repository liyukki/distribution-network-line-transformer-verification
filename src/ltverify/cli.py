"""Command-line entry points for the verification project."""

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ltverify.experiments import expand_experiment_grid, run_experiments
from ltverify.pipeline import run_pipeline

_STAGE_SUBCOMMANDS = ("simulate", "corrupt", "diagnose", "evaluate")
_CONFIG_SUBCOMMANDS = ("run-all", "experiments")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ltverify",
        description="配电网线变关系智能校验命令行工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in _STAGE_SUBCOMMANDS:
        sub = subparsers.add_parser(
            name, help=f"{name}：暂未实现（请使用 run-all）"
        )
        sub.add_argument("--config", required=True, help="YAML 配置文件路径")
    for name in _CONFIG_SUBCOMMANDS:
        sub = subparsers.add_parser(name)
        sub.add_argument("--config", required=True, help="YAML 配置文件路径")
    report = subparsers.add_parser("report", help="从运行目录重新生成证据摘要")
    report.add_argument("--run-dir", required=True, help="已完成运行的目录")
    report.add_argument(
        "--output",
        default="reports/metrics/default_summary.json",
        help="输出 JSON 路径",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in _STAGE_SUBCOMMANDS:
        print(
            f"{args.command} 尚未实现：请使用 python -m ltverify run-all 运行完整流水线",
            file=sys.stderr,
        )
        return 1
    if args.command == "report":
        from ltverify.report import generate_default_summary

        try:
            output = generate_default_summary(
                Path(args.run_dir), Path(args.output)
            )
        except Exception as exc:  # noqa: BLE001 - CLI top-level boundary
            print(f"report failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(output.resolve())
        return 0
    config_path = Path(args.config)
    if args.command == "run-all":
        try:
            run_dir = run_pipeline(config_path)
        except Exception as exc:  # noqa: BLE001 - CLI top-level boundary
            print(f"run-all failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(run_dir.resolve())
        return 0
    if args.command == "experiments":
        try:
            expand_experiment_grid(config_path)
        except Exception as exc:  # noqa: BLE001 - CLI top-level boundary
            print(f"grid expansion failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        output_dir = Path("runs") / f"experiments-{stamp}-{uuid.uuid4().hex[:6]}"
        try:
            run_experiments(config_path, output_dir)
        except Exception as exc:  # noqa: BLE001 - CLI top-level boundary
            print(f"experiments failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        summary = pd.read_csv(output_dir / "experiment_summary.csv")
        if len(summary) and (summary["status"] != "completed").all():
            print("every experiment case failed", file=sys.stderr)
            return 1
        print(output_dir.resolve())
        return 0
    print(f"unknown command: {args.command}", file=sys.stderr)
    return 1
