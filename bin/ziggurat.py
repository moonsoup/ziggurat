#!/usr/bin/env python3
"""Ziggurat -- architecture decided in planning, verified afterwards.

    ziggurat report <path>            what the structure and the history say
    ziggurat report <path> --only structure

ONE entry point with subcommands, not a script per capability. That is the
first thing this tool complains about, so it would be a poor advertisement to
be built the other way.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ziggurat import report as reporting  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ziggurat",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    r = sub.add_parser("report", help="analyse a project as it is")
    r.add_argument("path")
    r.add_argument("--only", nargs="*", default=None,
                   help="run only these analysers (structure, history)")

    args = ap.parse_args(argv)
    if args.command == "report":
        result = reporting.analyse(args.path, only=args.only)
        print(result.render())
        # Findings are not failures. This tool reports; a project decides what
        # to do about it, which is the difference between a report and a gate.
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
