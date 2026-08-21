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
