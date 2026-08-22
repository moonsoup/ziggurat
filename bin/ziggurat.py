#!/usr/bin/env python3
"""Ziggurat -- architecture decided in planning, verified afterwards.

    ziggurat report <path>            what the structure and the history say
    ziggurat report <path> --only structure
    ziggurat drift <path>             report ONLY if the shape has moved

`drift` exists because running a full report on every action is too expensive
to live with, and running it never is how a project drifts. Deciding WHETHER
the architecture could have changed is nearly free; only the answer "yes" is
worth paying for. Hook `drift` wherever edits land -- it is silent and cheap
until a module appears, a script becomes a second way in, or a constant escapes
into a new file.

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
from ziggurat import shape as shaping  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ziggurat",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    r = sub.add_parser("report", help="analyse a project as it is")
    r.add_argument("path")
    r.add_argument("--only", nargs="*", default=None,
                   help="run only these analysers (structure, history)")

    d = sub.add_parser("drift", help="report only if the shape has moved")
    d.add_argument("path")
    d.add_argument("--state", default="",
                   help="where the fingerprint lives (default: "
                        "<path>/.ziggurat-shape.json)")
    d.add_argument("--quiet", action="store_true",
                   help="say nothing at all when the shape is unchanged")

    args = ap.parse_args(argv)
    if args.command == "report":
        result = reporting.analyse(args.path, only=args.only)
        print(result.render())
        # Findings are not failures. This tool reports; a project decides what
        # to do about it, which is the difference between a report and a gate.
        return 0

    if args.command == "drift":
        root = Path(args.path)
        state = Path(args.state) if args.state else root / ".ziggurat-shape.json"
        before = shaping.load(state)
        after = shaping.shape(root)
        moved = shaping.differences(before, after)
        if not before:
            shaping.save(state, after)
            print(f"ziggurat: recorded the shape of {root.name} "
                  f"({len(after['modules'])} modules). Nothing to compare "
                  "against yet.")
            return 0
        if not moved:
            if not args.quiet:
                print("ziggurat: shape unchanged "
                      f"({shaping.digest(after)}); not re-running the report.")
            return 0
        print("ziggurat: the shape moved --")
        for line in moved:
            print(f"  {line}")
        print()
        print(reporting.analyse(str(root)).render())
        shaping.save(state, after)
        # Still not a gate. This reports; the project decides.
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
