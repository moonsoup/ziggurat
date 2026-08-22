"""Tier 1: which files move together, read from the git history.

The empirical half. "One idea should be one edit" is a claim about change, and
change is what a version control history records -- so files that keep changing
in the same commit are coupled whether or not either one imports the other.
This is an established technique and it finds dependencies that exist in
nobody's diagram.

IT REPORTS, IT NEVER GATES, and the reason is in the literature rather than in
taste: co-committal is a PROXY for coupling. Files can appear in the same
commit for reasons that have nothing to do with each other -- a release bump, a
reformat, one person tidying as they pass. Every finding carries that caveat,
because a number that becomes a target stops measuring anything.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path

from ziggurat.findings import Confidence, Finding, Report

#: A commit touching more than this many files is a sweep -- a rename, a
#: licence header, a formatter -- and couples everything to everything. It
#: carries no information about which parts belong together, so it is dropped.
SWEEP_AT = 12

#: Below this many shared commits, two files changing together is a commit
#: rather than a pattern.
MIN_SHARED = 4

#: Share of one file's commits that must also touch the other.
MIN_RATIO = 0.6

MAX_COMMITS = 2000

#: Directories whose contents are produced, not written. The first real run of
#: this analyser drowned in .apk/.dex/.idsig triples changing together 100% of
#: the time -- true, trivially, and architecturally silent. Coupling between
#: two outputs of one build step is a fact about the build step.
GENERATED_DIRS = {"build", "dist", "target", "out", "node_modules", ".venv",
                  "venv", "__pycache__", "vendor", "coverage", ".tox"}

#: Extensions that are never authored by hand.
#: Files that every release touches by process rather than by design. In a real
#: project pyproject.toml and __init__.py co-changed 100% of the time -- because
#: each release bumps the version in both. That is process coupling, and
#: reporting it as architecture is the documented false-positive mode.
MANIFESTS = {"pyproject.toml", "setup.py", "setup.cfg", "package.json",
             "package-lock.json", "VERSION", "Cargo.toml", "CHANGELOG.md",
             "__init__.py", "version.py", "_version.py"}

GENERATED_SUFFIXES = {".apk", ".dex", ".idsig", ".jar", ".class", ".pyc", ".so",
                      ".dylib", ".o", ".a", ".zip", ".tar", ".gz", ".lock",
                      ".png", ".jpg", ".jpeg", ".mp4", ".m4a", ".wav", ".pdf",
                      ".db", ".sqlite", ".jsonl"}


def _pairs_as_test(left: str, right: str) -> bool:
    """Is one of these the other's test?

    A module and its test SHOULD change together -- that is the discipline
    working, not a coupling fault. Reporting it is noise of a subtler kind than
    build artifacts, because it is perfectly true and still not a problem.
    """
    def stem(path: str) -> str:
        name = path.split("/")[-1]
        for suffix in (".py", ".js", ".ts", ".rb", ".go"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        for prefix in ("test_",):
            if name.startswith(prefix):
                name = name[len(prefix):]
        for tail in ("_test", ".test", ".spec", "_spec"):
            if name.endswith(tail):
                name = name[: -len(tail)]
        return name

    if stem(left) != stem(right):
        return False
    return any("test" in p.lower() or "spec" in p.lower() for p in (left, right))


def _is_manifest(path: str) -> bool:
    return path.split("/")[-1] in MANIFESTS


def _is_generated(path: str) -> bool:
    parts = path.split("/")
    if set(parts) & GENERATED_DIRS:
        return True
    name = parts[-1]
    return any(name.endswith(suffix) for suffix in GENERATED_SUFFIXES)


def _log(root: Path) -> list:
    """Commits as lists of paths, newest first. [] if this is not a repo."""
    result = subprocess.run(
        ["git", "log", f"-{MAX_COMMITS}", "--name-only", "--pretty=format:%H",
         "--no-merges"],
        cwd=root, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    commits, current = [], []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            if current:
                commits.append(current)
            current = []
        else:
            current.append(line)
    if current:
        commits.append(current)
    return commits


def analyse(root) -> Report:
    root = Path(root).resolve()
    report = Report(project=root.name)
    if not (root / ".git").exists():
        return report.skip("change-coupling", f"{root} is not a git repository")

    commits = _log(root)
    if len(commits) < MIN_SHARED * 2:
        return report.skip(
            "change-coupling",
            f"only {len(commits)} commit(s); history is too short to say "
            "anything about what changes together")

    touched = Counter()
    together = Counter()
    for files in commits:
        # Sweeps couple everything to everything and mean nothing.
        if len(files) > SWEEP_AT:
            continue

        unique = sorted({f for f in set(files)
                         if not _is_generated(f) and not _is_manifest(f)})
        if len(unique) < 2:
            continue
        touched.update(unique)
        for pair in combinations(unique, 2):
            together[pair] += 1

    for (left, right), shared in together.most_common(40):
        if shared < MIN_SHARED:
            continue
        if _pairs_as_test(left, right):
            continue
        ratio = shared / min(touched[left], touched[right])
        if ratio < MIN_RATIO:
            continue
        report.add(Finding(
            check="change-coupling",
            summary=f"{left} and {right} change together {ratio:.0%} of the time",
            evidence=(f"{shared} commits touched both; {left} has "
                      f"{touched[left]} commits and {right} has "
                      f"{touched[right]}. They may share a real dependency, or "
                      "the co-change may be coincidental -- co-committal is a "
                      "proxy, not proof, which is why this reports and never "
                      "blocks."),
            confidence=Confidence.EMPIRICAL,
            paths=(left, right),
            suggestion=("if there is no import between them, look for a shared "
                        "constant, a duplicated shape, or a boundary that runs "
                        "in the wrong place."),
        ))
    return report
