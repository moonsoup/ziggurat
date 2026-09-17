"""The SPIndlebox plugin: Ziggurat's checks, asked through the platform.

THE ONLY MODULE HERE THAT IMPORTS SPINDLEBOX, and an import-linter contract
proves it. Everything else stays standard-library-only, so a checkout and a
Python remain the whole requirement for `bin/ziggurat.py` -- the platform adds
reach, it is not a dependency of the checks.

What it contributes:

    ziggurat.analyse    a project's report as a findings document
    stacks/*.stack.json reports, listed as `ziggurat:<report>`
    cli(argv)           the four subcommands, as `spindlebox ziggurat ...`

`ziggurat.analyse` deliberately calls the same `report.analyse` the standalone
CLI calls, and returns `as_dict()` untouched. A second path that computed the
answer slightly differently would be the whole risk of this move: the point is
to rehouse the checks, not to restate them.
"""

from __future__ import annotations

from pathlib import Path

from spindlebox import plugins as _platform

from ziggurat import cli as _cli
from ziggurat import report as reporting

#: The entry-point name. Must match `pyproject.toml`.
name = "ziggurat"

#: The platform contract this speaks; a mismatch is refused by spindlebox
#: rather than half-loaded.
api = _platform.PLUGIN_API

#: Reports, as data. `<plugin>:<report>` once the platform lists them.
stack_dir = Path(__file__).resolve().parent / "stacks"


def analyse(ctx: dict) -> dict:
    """Every selected project's findings, keyed by project name.

    `only` narrows which analysers run, exactly as `--only` does on the CLI.
    A project whose analyser falls over is carried as a `skipped` entry by
    `report.analyse` itself, so it is reported rather than missing.
    """
    results = {}
    for project in ctx.get("projects", []):
        report = reporting.analyse(project["root"], only=ctx.get("only"))
        results[project["name"]] = report.as_dict()
    ctx["results"] = results
    return ctx


def register_ops(register) -> None:
    register("ziggurat.analyse", analyse,
             requires={"projects"}, provides={"results"})


def cli(argv) -> int:
    """`spindlebox ziggurat <subcommand>` is `ziggurat <subcommand>`."""
    return _cli.main(list(argv))
