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
    #: The same observation, structured, for a reader that is not a person.
    #: The default report is one line per finding because a wall of text is
    #: not read; an agent planning a change needs every reader and every
    #: site, and should not have to parse prose to get them.
    detail: dict = field(default_factory=dict)

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
    #: Observations that are real but not decisive -- kept OUT of the findings
    #: so they cannot crowd a decision, and kept rather than dropped because
    #: "we looked and found nothing conclusive" is itself worth reading.
    quiet: list = field(default_factory=list)

    def add(self, finding: Finding) -> "Report":
        self.findings.append(finding)
        return self

    def skip(self, check: str, why: str) -> "Report":
        self.skipped.append((check, why))
        return self

    def by_confidence(self, confidence: Confidence) -> list:
        return [f for f in self.findings if f.confidence is confidence]

    def render(self, full: bool = False) -> str:
        """The report a person reads.

        `full` adds every site behind each finding. The default stays one
        line and its evidence, because a wall of text is not read -- and a
        report nobody reads is the same as no report. What the extra detail
        is FOR is a reader that is not a person; see `as_dict`.
        """
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
                if full and finding.paths:
                    out.append(f"        every site ({len(finding.paths)}):")
                    for where in finding.paths:
                        out.append(f"          {where}")
                if full and finding.detail:
                    for key, value in sorted(finding.detail.items()):
                        if isinstance(value, list):
                            value = ", ".join(str(v) for v in value)
                        out.append(f"        {key}: {value}")
            out.append("")

        # KEPT OUT OF THE DECISION PATH, and kept. Real observations that are
        # not conclusive crowd out the ones that are, and dropping them
        # silently is how "we looked and found nothing" becomes indis-
        # tinguishable from "we did not look".
        if self.quiet:
            out.append(f"  --- also seen, not conclusive ({len(self.quiet)}) ---")
            if full:
                for item in self.quiet:
                    name = item.get("name", "?")
                    readers = item.get("read_by", [])
                    out.append(f"  {name}: read by {len(readers)}, "
                               f"no collection of the same idea")
                    for where in readers:
                        out.append(f"          {where}")
            else:
                names = ", ".join(str(i.get("name", "?")) for i in self.quiet[:8])
                out.append(f"  {names}"
                           f"{'...' if len(self.quiet) > 8 else ''}")
                out.append("  (--full to see why each was set aside)")
            out.append("")

        for check, why in self.skipped:
            out.append(f"  [skip] {check}: {why}")
        return "\n".join(out)

    def as_dict(self) -> dict:
        """The same report, structured, for a reader that is not a person.

        An agent planning a change needs every reader and every site and
        should not have to parse prose to get them -- and prose is what it
        would have to parse, because the human tiers deliberately summarise.
        """
        return {
            "project": self.project,
            "findings": [
                {
                    "check": f.check,
                    "summary": f.summary,
                    "evidence": f.evidence,
                    "confidence": f.confidence.value,
                    "paths": list(f.paths),
                    "suggestion": f.suggestion,
                    "detail": f.detail,
                }
                for f in self.findings
            ],
            "quiet": list(self.quiet),
            "skipped": [{"check": c, "why": w} for c, w in self.skipped],
        }
