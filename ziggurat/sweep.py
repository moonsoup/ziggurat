"""Tier 3: the report across many projects, and what changed between two runs.

A checker change is proven against real trees, not against the fixture it was
written for. Every false positive this tool has shipped passed its own tests,
and the false negatives were worse: a report that went quiet was read as a
project that had been fixed. So a change to a check is run here twice -- once
before, once after -- and `compare` names every finding that appeared or
vanished, and every project the checker now sees more or less of.

Records are written one file per project, so a sweep that dies half way still
leaves everything it finished, and two sweeps diff with ordinary tools too.
"""

from __future__ import annotations

import json
from pathlib import Path

from ziggurat import report as reporting


def projects(root) -> list:
    """Every directory directly under `root`, as a project. Hidden ones are
    tooling, not projects."""
    root = Path(root)
    return sorted(p for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


def run(root, out, only=None) -> list:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for where in projects(root):
        record = reporting.analyse(where, only=only).as_dict()
        target = out / f"{where.name}.json"
        target.write_text(json.dumps(record, indent=2, sort_keys=True))
        written.append(target)
    return written


def _load(directory: Path) -> dict:
    return {p.stem: json.loads(p.read_text())
            for p in sorted(Path(directory).glob("*.json"))}


def _said(record: dict) -> set:
    return {f"{f['check']}: {f['summary']}" for f in record.get("findings", [])}


def compare(before, after) -> list:
    """What a change to the checker changed about what it says.

    Silent about a project where nothing moved -- the lines that remain are
    the ones somebody has to adjudicate, one by one, against the code.
    """
    old, new = _load(before), _load(after)
    lines = []
    for name in sorted(old.keys() | new.keys()):
        if name not in new:
            lines.append(f"{name}: only in before")
            continue
        if name not in old:
            lines.append(f"{name}: only in after")
            continue
        was, now = old[name], new[name]
        body = []
        if was.get("scanned") != now.get("scanned"):
            body.append(f"  scanned {was.get('scanned')} -> {now.get('scanned')}")
        body.extend(f"  - {s}" for s in sorted(_said(was) - _said(now)))
        body.extend(f"  + {s}" for s in sorted(_said(now) - _said(was)))
        if body:
            lines.append(name)
            lines.extend(body)
    return lines
