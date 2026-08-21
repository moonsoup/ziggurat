"""Tier 1: what the shape of the tree says, without running anything.

Every check here is a STRUCTURAL FACT -- a file exists, a string appears in N
files, a call is present. Nothing here is a threshold on a quality metric,
because a measure that becomes a target stops being a measure, and because a
gate you can argue with is a gate people learn to ignore.

The three checks are not a general theory of architecture. Each one is a
failure that actually happened in a real project, chosen because imports could
not see it:

    entry-point sprawl   24 scripts in bin/, none importing another
    dynamic loading      scripts loading scripts by file path
    scattered constants  one address written into a dozen files
"""

from __future__ import annotations

import re
from pathlib import Path

from ziggurat.findings import Confidence, Finding, Report

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", "target", "site-packages", ".mypy_cache", ".pytest_cache",
             ".tox", "vendor", ".idea", ".spi"}

SOURCE_SUFFIXES = {".py", ".sh", ".js", ".ts", ".rb", ".go", ".java", ".kt"}

ENTRY_DIRS = ("bin", "scripts", "cmd", "tools")

#: Below this, a set of entry points is a tool with commands rather than a pile
#: of one-offs. Saying otherwise would be the noise that gets checkers disabled.
SPRAWL_AT = 8

#: A literal in fewer files than this is a coincidence. A dozen is a decision
#: nobody made.
SCATTER_AT = 4

DYNAMIC_PATTERNS = (
    ("spec_from_file_location", "python: loads a module from a file path"),
    ("SourceFileLoader", "python: loads a module from a file path"),
    ("__import__(", "python: import by computed name"),
    ("require(path.", "node: require by computed path"),
    ("importlib.machinery", "python: import machinery by path"),
)

#: Routable addresses only. Loopback is a statement about this machine, not
#: about a deployment, and 0.0.0.0 means "every interface" rather than a host.
ADDRESS = re.compile(r"\b(?!127\.|0\.0\.0\.0)(?:\d{1,3}\.){3}\d{1,3}\b")


def _is_test(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & {"tests", "test", "spec"}:
        return True
    name = path.name
    return name.startswith("test_") or "_test." in name or ".test." in name


def _sources(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if set(path.parts) & SKIP_DIRS:
            continue
        yield path


def analyse(root) -> Report:
    root = Path(root)
    report = Report(project=root.name)
    if not root.is_dir():
        return report.skip("structure", f"{root} is not a directory")

    files = list(_sources(root))
    _entry_points(root, files, report)
    _dynamic_loading(files, root, report)
    _scattered_constants(files, root, report)
    return report


def _entry_points(root: Path, files: list, report: Report) -> None:
    entries = [f for f in files
               if any(part in ENTRY_DIRS for part in f.parts) and not _is_test(f)]
    if len(entries) < SPRAWL_AT:
        return
    report.add(Finding(
        check="entry-point-sprawl",
        summary=f"{len(entries)} separate entry points",
        evidence=(f"{len(entries)} executables across "
                  f"{sorted({p.parent.name for p in entries})}. Entry points do "
                  "not import each other, so no import analysis can see this; "
                  "it shows up only as a count."),
        confidence=Confidence.STRUCTURAL,
        paths=tuple(sorted(str(p.relative_to(root)) for p in entries)),
        suggestion=("check whether these are commands of one tool rather than "
                    "separate tools. Subcommands share config, argument "
                    "handling and discovery; parallel scripts share nothing "
                    "and each one re-decides everything."),
    ))


def _dynamic_loading(files: list, root: Path, report: Report) -> None:
    hits = []
    for path in files:
        if _is_test(path):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for needle, why in DYNAMIC_PATTERNS:
            if needle in text:
                hits.append((str(path.relative_to(root)), why))
                break
    if not hits:
        return
    report.add(Finding(
        check="dynamic-loading",
        summary=f"{len(hits)} file(s) load code by path rather than importing it",
        evidence=("; ".join(f"{p} ({why})" for p, why in hits[:6])
                  + ". This is a real dependency that every import analyser is "
                  "blind to, so the module graph understates the coupling."),
        confidence=Confidence.STRUCTURAL,
        paths=tuple(p for p, _ in hits),
        suggestion=("if the loaded file is worth importing, it belongs in the "
                    "package where it can be imported normally."),
    ))


def _scattered_constants(files: list, root: Path, report: Report) -> None:
    where: dict = {}
    for path in files:
        if _is_test(path):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for address in set(ADDRESS.findall(text)):
            # A dotted quad in a comment is still a dotted quad; version
            # numbers are not, because they do not have four parts.
            where.setdefault(address, set()).add(str(path.relative_to(root)))

    for address, paths in sorted(where.items()):
        if len(paths) < SCATTER_AT:
            continue
        report.add(Finding(
            check="scattered-constant",
            summary=f"{address} appears in {len(paths)} files",
            evidence=(f"{address} is written into {len(paths)} separate files: "
                      f"{', '.join(sorted(paths)[:5])}"
                      f"{'...' if len(paths) > 5 else ''}. One idea should be "
                      "one edit; changing this costs "
                      f"{len(paths)} edits and a search you might not finish."),
            confidence=Confidence.STRUCTURAL,
            paths=tuple(sorted(paths)),
            suggestion=("put it in a config module and read it from there, so "
                        "the next change is one edit."),
        ))
