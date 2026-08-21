"""The shared vocabulary: what an observation about a codebase looks like.

Tier 0. Depends on nothing, so every analyser can speak it without any of them
having to know about the others.

A Finding says what was observed, where, and -- the part that matters -- how it
was established. An architectural observation that cannot say how it was
arrived at is an opinion, and opinions are what this tool exists to replace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(Enum):
    """How much weight a finding can carry, which is not the same as how bad
    it is."""

    #: An import exists or it does not. A file is executable or it is not.
    #: Nothing to argue about and nothing to game.
    STRUCTURAL = "structural"

    #: Derived from history or heuristics. Real signal, documented failure
    #: modes. Co-changing files may be coupled, or may merely have been touched
    #: in the same commit for reasons that had nothing to do with each other.
    EMPIRICAL = "empirical"

    #: A judgement. Shown, never enforced.
    ADVISORY = "advisory"


@dataclass(frozen=True)
class Finding:
    check: str
    summary: str
    #: Why this was concluded. Required, and not decorative: a report that
    #: cannot be argued with cannot be corrected either.
    evidence: str
    confidence: Confidence = Confidence.ADVISORY
    paths: tuple = ()
    #: What to do about it, when there is a concrete answer. Empty when the
    #: honest position is "this is worth a look" rather than "do this".
    suggestion: str = ""

    def line(self) -> str:
        mark = {Confidence.STRUCTURAL: "FACT", Confidence.EMPIRICAL: "HIST",
                Confidence.ADVISORY: "note"}[self.confidence]
        return f"[{mark}] {self.check}: {self.summary}"


@dataclass
class Report:
    project: str = ""
    findings: list = field(default_factory=list)
    #: Checks that could not run, and why. A check that silently did not run
    #: looks exactly like a check that passed.
    skipped: list = field(default_factory=list)

    def add(self, finding: Finding) -> "Report":
        self.findings.append(finding)
        return self

    def skip(self, check: str, why: str) -> "Report":
        self.skipped.append((check, why))
        return self

    def by_confidence(self, confidence: Confidence) -> list:
        return [f for f in self.findings if f.confidence is confidence]

    def render(self) -> str:
        out = [f"ziggurat: {self.project}", ""]
        if not self.findings:
            out.append("  nothing found")
        for confidence in Confidence:
            group = self.by_confidence(confidence)
            if not group:
                continue
            out.append(f"  --- {confidence.value} ---")
            for finding in group:
                out.append(f"  {finding.line()}")
                out.append(f"        {finding.evidence}")
                if finding.suggestion:
                    out.append(f"        -> {finding.suggestion}")
            out.append("")
        for check, why in self.skipped:
            out.append(f"  [skip] {check}: {why}")
        return "\n".join(out)
