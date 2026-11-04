"""Command line: segyqc check FILE [--config qc.yaml] [--out report/]."""
import argparse
import os
import sys

import yaml

from .config import ConfigError
from .runner import run_qc

EXIT_OK = 0
EXIT_FAIL = 1   # minimal satu check melaporkan FAIL
EXIT_ERROR = 2  # QC tidak bisa dijalankan (file atau config bermasalah)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="segyqc",
        description="Automated quality control for post-stack 3D SEG-Y files.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="run all QC checks on a SEG-Y file")
    check.add_argument("file", help="path to the SEG-Y file")
    check.add_argument("--config", default=None, help="path to qc.yaml (optional)")
    check.add_argument("--out", default="report",
                       help="output folder for report.json (default: report)")
    return parser


def _describe(exc):
    if isinstance(exc, FileNotFoundError):
        name = exc.filename or (exc.args[0] if exc.args else "")
        return f"file not found: {name}"
    if isinstance(exc, ConfigError):
        return f"invalid config: {exc}"
    return f"config is not valid YAML: {exc}"


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        report = run_qc(args.file, config=args.config)
    except (FileNotFoundError, ConfigError, yaml.YAMLError) as exc:
        print(f"error: {_describe(exc)}", file=sys.stderr)
        return EXIT_ERROR

    print(f"segyqc: {report.path}")
    for f in report.findings:
        print(f"  [{f.severity.value:<4}] {f.check_id}  {f.message}")
    s = report.summary()
    print(f"Summary: {s['INFO']} INFO, {s['WARN']} WARN, {s['FAIL']} FAIL")

    out_path = os.path.join(args.out, "report.json")
    try:
        report.to_json(out_path)
    except OSError as exc:
        print(f"error: cannot write report to {out_path}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Report written to {out_path}")
    return EXIT_FAIL if report.has_fail else EXIT_OK