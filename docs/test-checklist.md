# Ziggurat test checklist

The living record of what has been verified against the real tool, and how.
`[working]` / `[broken]` / `[fixed]` / `[untested]`, each with dated evidence.
It grows while testing; it is not a scope decided up front.

**How a check is verified here.** A fixture built to *break* the check, run
through the real code, is the minimum. Then `ziggurat sweep ~/Software --out A`
before a change and `--out B` after, and `ziggurat compare A B`. Every finding
that appears or vanishes is read against the code and adjudicated. A change
that only passes its own fixture is not verified.

## 2026-09-17: second independent verification

Baseline sweep: 992db24, 45 projects under `~/Software`.

| item | state | issue | evidence |
|---|---|---|---|
| Folder-name rules (skip / test / entry-point / shape) match the path inside the project, not the absolute path | [fixed] | #12 | was: under `build/` → `[]`, under `tests/` → `[]`, library under `tools/` → `8 separate entry points`. 2026-09-17: oligolia cloned under `build/` scanned 0 (c54fea6) → 122 (fix), same as its real checkout; 45-project sweep unchanged apart from ziggurat's own history |
| A report says how many source files it read | [fixed] | #13 | was: render over 3 files and over 0 both said only `nothing found`. 2026-09-17: `ziggurat: oligolia (122 source files read)`; `ziggurat: dns_confirm (0 source files read)` (a CLAUDE.md-only dir); `--only history` shows no count rather than 0; sweep: no finding moved |
| Tracked source under a build-output-named directory is scanned | [fixed] | #14 | was: `scanned` 0 of 5 tracked `build/hooks/*.py`. 2026-09-17: sweep shows oligolia `scanned 122 -> 126`, the 4 = exactly `git ls-files build` source files; no finding moved in any of 45 projects. Untracked `build/lib/` copy under git still skipped (new test) |
| Module-qualified path calls (`os.makedirs`, `os.path.*`, `shutil.*`, `pathlib.Path`, aliases) | [fixed] | #15 | was: 5 files each → `[]`. 2026-09-17: sweep gained exactly 2 findings, both true positives read against the code — Drivers `~/Software` and `~/work` each in 5 scripts as `default=os.path.expanduser("~/Software")`; nothing vanished; `target.open("a")` control still quiet |
| One slash-bearing path does not promote bare mentions everywhere | [fixed] | #16 | was: `Path("cache/x.db")` + 3× `print("cache")` → 4 files. 2026-09-17: bare words handed to message calls no longer count. Three approaches swept: amplify-only broke a pinned real case; list/tuple-as-label lost 2 real namers (Populous3D `("data", "constant.txt", parse)`, bio_battle pathspec); message-only changed exactly one count across 45 projects, correctly (`_deprecated` f-string label `'data'`). Findings now carry `named_bare_only` |
| `./` and `../` paths are grouped; `//host/` URLs are not directories | [fixed] | #17 | was: `./data/fN.json` ×5 → `[]`; `//cdn.example.com/lib/` reported in 4 files. 2026-09-17: all reproductions + `_path_head` unit cases pass; 45-project sweep: no finding moved |
| drift re-runs when a body edit or a non-Python file could change the report | [broken] | #18 | body edit → `shape unchanged` while report gains `records/`; new `scripts/deploy.sh` → `shape unchanged` |
| change-coupling ratio counts every commit touching a file | [fixed] | #19 | was: 10+10 commits, 4 shared → `100%`. 2026-09-17: fixture 40% → not reported; oligolia now `README.md has 7 commits and docs/index.html has 8`, 6 shared → 86% (was 100%), and 7 matches the first verifier's independent `git log` count. Sweep: every coupled pair's ratio fell, none appeared, pairs truly under 60% dropped (agent-mash 1, bio_battle 4, incarnation 2, playtest 1, projectMan 5, sentience 3, Populous3D 1) |
| change-coupling judges every pair, not the top 40 | [fixed] | #20 | was: 45 fully coupled pairs → 40 findings. 2026-09-17: 45 → 45. Sweep: 77 pairs that were silently dropped now surface (Populous3D 72, projectMan 5), spot-checked as real co-change (e.g. every port edits registry.c + addresses.h + shims.c together); nothing vanished. Readable report lists 40 per check then `... and 63 more change-coupling findings not listed (--full lists every one)`; JSON carries all 103 |
| sibling-from-global: `str.join` is not a path; `os.path.join(GLOBAL, path.name)` is | [fixed] | #21 | was: `SEP.join([path.stem])` reported; `os.path.join(DATA_DIR, path.name)` missed. 2026-09-17: both reproductions pass (join with ≥2 args takes its base from the first argument; str.join has one); sweep: no project changed |
| singleton-bottleneck readers must be able to see the config | [broken] | #22 | parameter `name` in 4 modules → "read by" 4 |
| dynamic-loading sees `import_module`, `run_path`, `exec(open())`, `load_source` | [broken] | #23 | each → `[]` |
| Docs name every check; every module is under the import contract | [broken] | #24 | README and structure docstring omit 2 checks; `.importlinter` omits `shape` |
| compare shows a finding whose sites changed under the same summary | [fixed] | #25 | found by Codex review (agent_comms msg_003): same summary, different files → `[]`. 2026-09-17: prints `~ ... (sites changed)` with `-`/`+` files under `--sites` |
| #15 qualification respects a rebound name (`from os import path` + local `path`) | [fixed] | #26 | found evaluating Codex msg_003: `path.write_text("draft")` ×5 → `draft appears in 5 files`. 2026-09-17: scope-aware; nothing-shadows control still found; sweep: no project changed (latent, not live) |
| #14 holds for all of build/dist/target/coverage; #15 holds for every alias form | [working] | #14 #15 | Codex msg_003 test gaps; parametrised tests added 2026-09-17 pass without code change |
| `method.open("a")` / `name.replace("a", "b")` still not paths | [working] | — | control test passes at 992db24 |
| drift silent when nothing, or only a comment, changed | [working] | — | control tests pass at 992db24 |
| gitignored and vendored trees stay skipped, with or without git | [working] | — | control tests pass at 992db24 |
| scattered-constant on version strings (suspected by the verifier) | [working] | — | not filed: across 45 projects the only findings were one real VPS address |

## 2026-09-17: Ziggurat as a SPIndlebox plugin (phase 1)

Verified through the platform, not asserted. Evidence: `docs/equivalence/` (manifest + verdict),
produced by `rockin-robin/scripts/rr_equivalence_run.ts`, which dispatches from a ledger so a
subject that silently did not run cannot be counted as equal.

| item | state | evidence |
|---|---|---|
| `ziggurat:change-coupling` through `spindlebox report` equals `bin/ziggurat.py report --only history --json` | [working] | 13/13 subjects equal, 13 compared, reconciliation clean. Full execution record committed at `docs/equivalence/run-change-coupling/` (ledger with nonces, per-subject commit + dirty count, exit codes, sha256 of each side's output) — re-running reproduces the digests. Subjects: ziggurat (4 findings), spindlebox (2), oligolia (3), and spindlebox's 10 `miniproj_*` fixtures (1 `skipped` each) — so both findings and `skipped` are covered |
| the harness can fail | [working] | negative control (A asked for structure, B for history): `NOT VERIFIED 0/3`, each difference named (`findings.length: 0 !== 4`), exit 1 |
| `bin/ziggurat.py` still runs with nothing installed | [working] | the body moved to `ziggurat.cli`; import-linter contract "Only the plugin module knows spindlebox exists" KEPT (3 contracts kept) |
| the four subcommands and their flags are unchanged | [working] | `--help` lists report/drift/sweep/compare; suite 200 passed, 12 xfailed (the paused #18/#22/#23/#24) |
| SPIndlebox's built-in commands unchanged by the contract | [working] | 443 → 487 tests pass, ruff clean, `report --list` and typing-health/dup-candidates byte-identical in md and json |

Subject trees were dirty when measured (ziggurat 12 files, spindlebox 4, oligolia 1); the verdict
records each commit and count, because uncommitted files are part of what Ziggurat reads.

### Codex's review of the plugin move (msg_007)

| item | state | evidence |
|---|---|---|
| a class-body assignment does not unbind a path module at module level | [fixed] | #29, a regression the #26 fix introduced: `import os` + `class C: os = object()` + `os.makedirs("outputs")` ×5 reported nothing. Latent on the pinned corpus — pre-fix vs post-fix structure reports are identical for all 3 subjects, which is why the sweep missed it and a hand-built fixture found it |

| the committed evidence is the execution record, not a summary | [fixed] | rockin-robin#20, found by Codex: only the verdict had been committed. `docs/equivalence/run-change-coupling/` now holds ledger + runs + verdict (28K, output digested not embedded) |
| a claim over zero subjects cannot verify | [fixed] | rockin-robin#20: an empty subject list reported `verified: true`; now a finding and exit 1 |
| the custody ledger verifies under its key | [fixed] | was unverifiable: `ledger verify --path` recursed until the interpreter gave up (mEllergrace/stop-guessing#94, fixed test-first in 92208b2 and patched into the vendored 0.6.1 copy). 2026-09-17: `PASS: 492 records, chain intact and verified under its key`; oligolia's 1033 records also PASS. LOG-10 still answers No, for write-protection and access, not for verifiability |

### Codex's toolchain + repo review (msg_011)

| item | state | evidence |
|---|---|---|
| agent/tool state is not a project file | [fixed] | #30: this repo's own report named `.stop-guessing/state/*.json` for a week (tracked, so git-ignore did not remove it; `.jsonl` was filtered and `.json` was not) and the author filtered those lines by hand in every sweep rather than fixing the cause. Now filtered in history and skipped in the walk; the report shows a genuine pair instead |
| nothing nobody authored changes a finding | [fixed] | new `tests/test_not_the_project.py` asserts the CLASS: tool state, an index, caches, a worktree, a vendored tree, committed `dist/` chunks and a minified bundle added to a project leave its findings identical. Two of its first fixtures passed VACUOUSLY (6 commits, below history's 8-commit minimum) and were corrected to fail first |
| a committed bundle is not the project | [fixed] | #14 briefly deferred `dist`/`target`/`coverage` to git alongside `build/`; the class fixture showed five committed webpack chunks becoming a finding. Only `build/` defers now (hand-written build scripts live there) |
| a minified bundle is skipped by content, not by name | [fixed] | no directory-name list catches oligolia's `structure_viewer/assets/3Dmol-min.js` (moonsoup/spindlebox#33); a `.js`/`.ts`/`.css` file with a line over 2000 chars is generated |
