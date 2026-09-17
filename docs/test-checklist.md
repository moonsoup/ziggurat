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
| Module-qualified path calls (`os.makedirs`, `os.path.*`, `shutil.*`, `pathlib.Path`, aliases) | [broken] | #15 | 5 files each → `[]`; bare `Path("outputs")` control → found |
| One slash-bearing path does not promote bare mentions everywhere | [broken] | #16 | `Path("cache/x.db")` + 3× `print("cache")` → `cache/ is written into 4 files` |
| `./` and `../` paths are grouped; `//host/` URLs are not directories | [broken] | #17 | `./data/fN.json` ×5 → `[]`; `//cdn.example.com/lib/` reported in 4 files |
| drift re-runs when a body edit or a non-Python file could change the report | [broken] | #18 | body edit → `shape unchanged` while report gains `records/`; new `scripts/deploy.sh` → `shape unchanged` |
| change-coupling ratio counts every commit touching a file | [broken] | #19 | 10+10 commits, 4 shared → `100%` (true 40%); evidence `a.py has 4 commits` (has 5) |
| change-coupling judges every pair, not the top 40 | [broken] | #20 | 45 fully coupled pairs → 40 findings |
| sibling-from-global: `str.join` is not a path; `os.path.join(GLOBAL, path.name)` is | [broken] | #21 | `SEP.join([path.stem])` reported; `os.path.join(DATA_DIR, path.name)` missed |
| singleton-bottleneck readers must be able to see the config | [broken] | #22 | parameter `name` in 4 modules → "read by" 4 |
| dynamic-loading sees `import_module`, `run_path`, `exec(open())`, `load_source` | [broken] | #23 | each → `[]` |
| Docs name every check; every module is under the import contract | [broken] | #24 | README and structure docstring omit 2 checks; `.importlinter` omits `shape` |
| `method.open("a")` / `name.replace("a", "b")` still not paths | [working] | — | control test passes at 992db24 |
| drift silent when nothing, or only a comment, changed | [working] | — | control tests pass at 992db24 |
| gitignored and vendored trees stay skipped, with or without git | [working] | — | control tests pass at 992db24 |
| scattered-constant on version strings (suspected by the verifier) | [working] | — | not filed: across 45 projects the only findings were one real VPS address |
