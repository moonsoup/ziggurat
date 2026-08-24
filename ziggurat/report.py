"""Tier 2: composing the analysers into one report.

Knows the analysers; they do not know it, and they do not know each other. That
is what lets a new analyser be added without touching any existing one, and
what makes a failure attributable: if `structure` is quiet and `history` is
loud, that is a fact about the project, not about the wiring.
"""

from __future__ import annotations

from pathlib import Path

from ziggurat import history, structure
from ziggurat.findings import Report

ANALYSERS = (("structure", structure.analyse), ("history", history.analyse))


def analyse(root, only=None) -> Report:
    root = Path(root).resolve()
    combined = Report(project=root.name)
    for name, run in ANALYSERS:
        if only and name not in only:
            continue
        try:
            part = run(root)
        except Exception as exc:  # noqa: BLE001
            # An analyser that fell over must say so. A check that silently did
            # not run looks exactly like a check that passed.
            combined.skip(name, f"{type(exc).__name__}: {exc}")
            continue
        combined.findings.extend(part.findings)
        combined.skipped.extend(part.skipped)
        # Carried, not dropped. An analyser's inconclusive observations are
        # still observations, and losing them here would make the composed
        # report quieter than the analyser that produced it.
        combined.quiet.extend(part.quiet)
    return combined
