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


def _said(record: dict) -> dict:
    """Each finding, as a line, with the files behind it."""
    return {f"{f['check']}: {f['summary']}": list(f.get("paths", []))
            for f in record.get("findings", [])}


def compare(before, after, sites: bool = False) -> list:
    """What a change to the checker changed about what it says.

    Silent about a project where nothing moved -- the lines that remain are
    the ones somebody has to adjudicate, one by one, against the code.

    `sites` lists the files behind every finding that moved, because
    adjudicating means reading them. Extracting them from the records by
    hand read the neighbouring finding's files -- keys are sorted, so
    `paths` precedes `summary` -- and a verdict was written about the wrong
    five files.
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
        said_was, said_now = _said(was), _said(now)
        for mark, gone, kept in (("-", said_was, said_now),
                                 ("+", said_now, said_was)):
            for line in sorted(set(gone) - set(kept)):
                body.append(f"  {mark} {line}")
                if sites:
                    body.extend(f"      {where}" for where in gone[line])
        if body:
            lines.append(name)
            lines.extend(body)
    return lines
