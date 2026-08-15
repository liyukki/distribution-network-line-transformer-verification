"""Command-line entry points for the verification project."""

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ltverify.experiments import expand_experiment_grid, run_experiments
from ltverify.pipeline import run_pipeline

_SUBCOMMANDS = (
    "simulate",
    "corrupt",
    "diagnose",
    "evaluate",
    "run-all",
    "experiments",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ltverify",
        description="配电网线变关系智能校验命令行工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in _SUBCOMMANDS:
        sub = subparsers.add_parser(name)
        sub.add_argument("--config", required=True, help="YAML 配置文件路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
    if not config_path.exists():
        print(f"missing prerequisite artifact: {config_path.resolve()}")
        return 1
    print(f"{args.command} prerequisites satisfied: {config_path.resolve()}")
    return 0
