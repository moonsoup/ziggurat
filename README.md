# Ziggurat

Architecture decided in planning, verified afterwards.

A ziggurat is a stepped structure: every level rests on the one below and never
the reverse. That is what a layered architecture is, and it is what this tool
checks — including on itself.

## Why it is not a linter or a hook

Architecture is a property of the **graph**. Import contracts need the whole
import graph; change coupling needs the whole history. In the vocabulary of
*Building Evolutionary Architectures* these are **holistic** fitness functions,
and forcing one into a per-file hook produces a heuristic that generates noise —
and noise is what gets a checker switched off.

So Ziggurat never blocks a keystroke. It runs when asked.

## What it measures, and why each one

| check | kind | why this one |
|---|---|---|
| entry-point sprawl | structural | 24 scripts in one `bin/`. Entry points do not import each other, so no import analysis can see it — it shows up only as a count. |
| dynamic loading | structural | code loaded by file path is a real dependency that every import analyser is blind to. |
| scattered constants | structural | one address written into ten files means one idea costs ten edits. That number is the measurement. |
| change coupling | empirical | files that keep changing together are coupled whether or not either imports the other. Reads the git history. |

**Structural findings are facts.** An import exists or it does not; a string is
in ten files or it is not. There is no threshold to argue about and nothing to
game.

**Empirical findings report and never gate.** Co-committal is a proxy for
coupling: files can share a commit for reasons that have nothing to do with each
other. Every such finding carries that caveat, because a measure that becomes a
target stops being a measure.

## Noise is the failure mode

The first real run drowned in `.apk`/`.dex`/`.idsig` triples changing together
100% of the time — true, trivially, and architecturally silent. The second was
dominated by modules paired with their own tests, which *should* change together.
Both are filtered. A checker that cries wolf is worse than no checker, because
it teaches everyone to reach for the disable switch.

## Usage

```bash
python3 bin/ziggurat.py report <path>
python3 bin/ziggurat.py report <path> --only structure
```

One entry point with subcommands, not a script per capability — which is the
first thing this tool complains about.

## Its own contract

`.importlinter` declares Ziggurat's tiers and is enforced on Ziggurat:

```
report                          tier 2, composes analysers
structure | history             tier 1, independent of each other
findings                        tier 0, depends on nothing
```

```bash
lint-imports
```

The contract describes what exists **today**. A contract written for the
codebase you *want* fails on day one against the code it was pointed at, and a
check that is red from the start teaches everyone to ignore it.

## Reading

- Ford, Parsons, Kua & Sadalage, *Building Evolutionary Architectures* — fitness
  function taxonomy (atomic/holistic, triggered/continual, static/dynamic)
- [Import Linter](https://import-linter.readthedocs.io/) — the contract format;
  not reinvented here
- [CodeScene on change coupling](https://docs.enterprise.codescene.io/versions/4.5.0/guides/technical/change-coupling.html)
  and Tornhill, *Your Code as a Crime Scene*

## Hooking it in without it costing too much

Running a full report on every action is too expensive to live with. Running it
never is how a project drifts. The way out is that the two questions have very
different prices:

    ziggurat drift <path>     is it even possible that the architecture moved?
    ziggurat report <path>    what does it say?

`drift` is silent and cheap until the SHAPE moves, and only then does it pay
for the report.

**Shape is three things, and deliberately not the code:**

1. which modules exist
2. which of them are entry points
3. what top-level names each one defines -- functions, classes, constants

That list is not arbitrary. It is exactly what every finding this tool produces
depends on. Entry-point sprawl is (2). Constants scattered across modules is
(3). Dynamic loading and module coupling are (1). If none of them moved, no new
finding can exist, and the expensive report would say what it said last time.

Function bodies are never read. An edit inside a function cannot create an
entry point, scatter a constant or add a module -- however wrong that edit is,
it is not ARCHITECTURALLY wrong, and that distinction is the whole saving.

Measured on a 153-module project: 0.14s for the gate against 0.57s for the
report, and the gap widens on a large repository because the history analyser
walks git log while the gate only parses top-level syntax.

**Where to hook it.** Wherever edits land -- a pre-commit hook, an agent's
post-edit step, a save hook. It exits 0 and says one line when nothing moved.

**What it cannot see.** Change coupling is history, not shape: two files can
begin changing together without either being touched structurally. A shape gate
will never catch that. So this is not a substitute for the full report -- it
catches the structural half immediately and leaves the historical half to a
slower rhythm, which is the part that belongs in planning rather than in a
hook.

### What the literature actually says about cadence

Ford, Parsons and Kua classify every architectural check on two axes BEFORE
deciding when to run it -- atomic (one context) against holistic (dimensions
interacting), and triggered (an event) against continual (constant
verification):

|            | triggered                                   | continual                          |
|------------|---------------------------------------------|------------------------------------|
| atomic     | circular dependencies, complexity, coverage | endpoint conformance, conformity monkey |
| holistic   | integration tests -- security against scalability | performance monitoring, chaos monkey |

The point is that **cadence is DERIVED from the classification, not chosen
separately**. The question is not "how often should this run" but "what kind of
check is this", and the answer decides. That makes the classification a
planning artefact rather than an operational tuning knob -- which is the whole
premise of this tool.

Against that taxonomy:

- `drift` is **atomic/triggered**. It examines one thing -- the shape -- and
  runs on an event. That is the box that belongs in a per-edit hook.
- the **change-coupling** finding is neither. It is mined from version-control
  history, and nothing about a single commit makes it true or false. Tornhill's
  work treats coupling and hotspots as a way of PRIORITISING refactoring
  targets, not as a gate, which is why this tool prints it and never fails on
  it. That is the orthodox treatment, not a hedge.

The honest order, then, is the opposite of how `drift` came to exist here: it
was built first and classified afterwards. In planning, decide which fitness
functions a project needs and what category each falls into -- and the hooks
follow mechanically.

Sources: Ford, Parsons & Kua, *Building Evolutionary Architectures* (2nd ed.),
ch. 2; Adam Tornhill, *Software Design X-Rays* / CodeScene.

