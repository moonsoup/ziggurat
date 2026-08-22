"""The cases an independent verifier found by attacking the check.

Each of these is a measured false positive or false negative from a fixture
built to break `scattered-path`, not a case imagined while writing it. Issues
moonsoup/ziggurat#3 and #5 through #9.
"""

from test_scattered_paths import findings, project


# --- #5: amplification through the second pass -----------------------------

def test_a_dict_lookup_does_not_name_a_directory(tmp_path, monkeypatch) -> None:
    """The worst of the false positives. `Path("genes")` in four files is a
    real scattered path; `cell["genes"]` in ten more is a dict lookup naming
    nothing. The regex second pass could not tell them apart and reported
    fourteen files, which is also why the regression test for the earlier
    `genes` bug did not survive contact with a real tree."""
    files = {f"real{i}.py": 'p = Path("genes")\n' for i in range(4)}
    files.update({f"lookup{i}.py": 'n = cell["genes"]\n' for i in range(10)})
    root = project(tmp_path, files)
    for f in findings(root):
        assert "14 files" not in f.summary, f.summary
        assert "genes" not in f.summary or "4 files" in f.summary, f.summary


def test_an_ordinary_word_is_not_promoted_by_count_alone(tmp_path) -> None:
    """Four `--dest-state` defaults of "pending" plus ten modules comparing
    against it reported `pending appears in 14 files`."""
    files = {f"opt{i}.py": (
        'ap.add_argument("--dest-state", default="pending")\n')
        for i in range(4)}
    files.update({f"cmp{i}.py": 'if job["state"] == "pending": pass\n'
                  for i in range(10)})
    root = project(tmp_path, files)
    assert not any("pending" in f.summary for f in findings(root)), \
        findings(root)


# --- #6: option NAME is not proof ------------------------------------------

def test_a_log_level_default_is_not_a_directory(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'ap.add_argument("--log-level", default="INFO")\n'
        for i in range(5)})
    assert not any("INFO" in f.summary for f in findings(root))


def test_an_output_format_default_is_not_a_directory(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'ap.add_argument("--output-format", default="json")\n'
        for i in range(5)})
    assert not any("json" in f.summary.split("/")[0] for f in findings(root))


def test_an_email_default_is_not_a_directory(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'ap.add_argument("--to", default="a@b.com")\n'
        for i in range(5)})
    assert findings(root) == []


def test_a_strong_option_word_still_carries_a_bare_default(tmp_path) -> None:
    """The capability this must not lose. `--outdir` is about paths and
    essentially nothing else, so a bare word default is still a path."""
    root = project(tmp_path, {
        f"m{i}.py": f'ap.add_argument("--outdir", default="records/x{i}.json")\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


# --- #7: subscripts, dict keys, comparisons --------------------------------

def test_a_json_field_unpack_does_not_name_a_directory(tmp_path) -> None:
    files = {"real.py": 'p = Path("data/raw.csv")\n'}
    files.update({f"api{i}.py": 'rows = response["data"]\n' for i in range(5)})
    root = project(tmp_path, files)
    assert not any("6 files" in f.summary and "data" in f.summary
                   for f in findings(root)), findings(root)


def test_a_dict_key_does_not_name_a_directory(tmp_path) -> None:
    files = {"real.py": 'p = Path("user/avatar.png")\n'}
    files.update({f"m{i}.py": 'msg = {"role": "user"}\n' for i in range(5)})
    root = project(tmp_path, files)
    assert not any("user" in f.summary and "6 files" in f.summary
                   for f in findings(root)), findings(root)


def test_the_positional_case_the_second_pass_exists_for_still_works(
        tmp_path) -> None:
    """`shoot(bod, cam, "records")` hands a directory to a function whose
    name means nothing to a checker. Losing this would be trading one fault
    for another."""
    files = {f"real{i}.py": f'p = Path("records/a{i}.jsonl")\n'
             for i in range(4)}
    files.update({f"pos{i}.py": 'shoot(bod, cam, "records")\n'
                  for i in range(2)})
    root = project(tmp_path, files)
    assert any("6 files" in f.summary for f in findings(root)), findings(root)


# --- #9: joinpath ----------------------------------------------------------

def test_joinpath_names_a_directory(tmp_path) -> None:
    """`joinpath` was in JOINING and not in PATH_CALLS, and the guard needs
    both -- so it was collected by nothing, while the comment above JOINING
    offered it as an example of what was handled."""
    root = project(tmp_path, {
        f"m{i}.py": f'p = base.joinpath("records").joinpath("a{i}.jsonl")\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


def test_pure_posix_path_names_a_directory(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'p = PurePosixPath("records/a{i}.jsonl")\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


# --- #3: absolute paths, which #3 named and its fix missed -----------------

def test_an_absolute_directory_is_found(tmp_path) -> None:
    """`_path_head` split on `/` and took `[0]`, which is "" for anything
    absolute -- so no absolute directory was ever grouped, however many files
    named it."""
    root = project(tmp_path, {
        f"m{i}.py": f'p = Path("/var/lib/records/x{i}.json")\n'
        for i in range(5)})
    assert any("/var/lib/records" in f.summary for f in findings(root)), \
        findings(root)


def test_a_url_is_still_not_an_absolute_path(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'u = fetch("//cdn.example.com/lib{i}.js")\n'
        for i in range(5)})
    assert findings(root) == []


# --- #8: what belongs to the project ---------------------------------------

def test_a_git_worktree_is_not_a_second_set_of_modules(tmp_path) -> None:
    """A worktree is a full second copy of the repo. Counting it doubled
    every file, which put six of one project's seven findings over the
    threshold on two real files apiece."""
    files = {f"m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(2)}
    files.update({f".claude/worktrees/branch/m{i}.py":
                  f'p = Path("records/a{i}.jsonl")\n' for i in range(2)})
    files.update({f".claude/worktrees/other/m{i}.py":
                  f'p = Path("records/a{i}.jsonl")\n' for i in range(2)})
    root = project(tmp_path, files)
    assert findings(root) == [], (
        "two real files became six by counting copies of themselves")


def test_framework_build_output_is_not_source(tmp_path) -> None:
    """projectMan's `/robots.txt` across twelve files was entirely inside
    `packages/web/.next/`, in bundled files literally named
    `node_modules_*.js`."""
    root = project(tmp_path, {
        f"packages/web/.next/static/chunk{i}.js":
        f'a = "/public/robots{i}.txt"\n' for i in range(8)})
    assert findings(root) == []


# --- F1: the regression the git filter introduced ---------------------------

def test_uncommitted_source_is_still_scanned(tmp_path) -> None:
    """The worst regression of the lot, and it had no test at all.

    Scanning only `git ls-files` made uncommitted source invisible. Measured
    across 42 projects: 130 files vanished, 88 of them ordinary source
    somebody had written and not yet committed -- and one project's hardcoded
    VPS address, named in four files, was reported as two. Newly written code
    is also the code most worth checking.
    """
    import subprocess

    files = {f"m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(5)}
    files["committed.py"] = "x = 1\n"
    root = project(tmp_path, files)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "committed.py"], cwd=root, check=True)

    found = findings(root)
    assert any("5 files" in f.summary for f in found), (
        f"uncommitted source went unscanned: {found}")


def test_gitignored_output_is_still_skipped(tmp_path) -> None:
    """The capability the git filter was added FOR must survive the fix."""
    import subprocess

    files = {".gitignore": ".next/\n"}
    files.update({f".next/chunk{i}.js": f'a = "/public/robots{i}.txt"\n'
                  for i in range(8)})
    root = project(tmp_path, files)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    assert findings(root) == []


def test_a_project_inside_another_repo_is_not_judged_by_the_parent(
        tmp_path) -> None:
    """A directory with no .git of its own resolves to the enclosing
    repository, whose index describes a tree this is only part of. It would
    get partial visibility with nothing to signal it."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    inner = tmp_path / "sub"
    files = {f"sub/m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(5)}
    project(tmp_path, files)
    assert any("5 files" in f.summary for f in findings(inner)), (
        "judged by the parent repo's index, which does not describe it")


# --- F2: what the AST pass dropped ------------------------------------------

def test_a_path_in_a_list_still_names_a_directory(tmp_path) -> None:
    """Cost a real finding on a real tree: `docs/` named in four modules,
    every one inside CONTEXT = ["CLAUDE.md", "docs/product-brief.md"]."""
    files = {"real.py": 'p = Path("docs/a.md")\n'}
    files.update({f"m{i}.py": f'CONTEXT = ["README.md", "docs/brief{i}.md"]\n'
                  for i in range(5)})
    root = project(tmp_path, files)
    assert any("docs" in f.summary for f in findings(root)), findings(root)


def test_a_returned_path_still_names_a_directory(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'def where():\n    return "records/a{i}.jsonl"\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


def test_a_default_parameter_still_names_a_directory(tmp_path) -> None:
    files = {"real.py": 'p = Path("records/x.jsonl")\n'}
    files.update({f"m{i}.py": f'def load(root="records", n={i}):\n    pass\n'
                  for i in range(5)})
    root = project(tmp_path, files)
    assert any("records" in f.summary for f in findings(root)), findings(root)


def test_a_dict_value_that_is_a_path_still_counts(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'STREAMS = {{"eye": "records/eye{i}.jsonl"}}\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


def test_an_fstring_inside_a_larger_expression_still_counts(tmp_path) -> None:
    """`Path(args.restore or f"records/{serial}.sh")` -- real code, and the
    single file the AST pass lost on the tool's own reference tree."""
    root = project(tmp_path, {
        f"m{i}.py": f'p = Path(args.out or f"records/x{i}-{{n}}.sh")\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


# --- F5: the lookup wearing a method's clothes ------------------------------

def test_dict_get_is_a_lookup_not_a_path(tmp_path) -> None:
    """`d["data"]` was excluded and `d.get("data")` was not, so two projects'
    counts were inflated by a file each while the subscript beside them was
    correctly ignored."""
    files = {"real.py": 'p = Path("data/raw.csv")\n'}
    files.update({f"api{i}.py": 'rows = response.get("data")\n' for i in range(5)})
    root = project(tmp_path, files)
    assert not any("6 files" in f.summary and "data" in f.summary
                   for f in findings(root)), findings(root)


def test_a_package_called_worktrees_is_not_silenced(tmp_path) -> None:
    """A bare `worktrees` in SKIP_DIRS matches a single path component
    wherever it appears, so it would silence a project that ships a package
    by that name. The pattern actually meant is `.claude/worktrees`."""
    root = project(tmp_path, {
        f"worktrees/m{i}.py": f'p = Path("records/a{i}.jsonl")\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


def test_a_glob_is_not_a_directory(tmp_path) -> None:
    """Collecting unambiguous file literals wherever they sit picked up
    `*/CLAUDE.md` and reported `*/ is written into 8 files` -- modules that
    share a search pattern, not a directory anyone could relocate."""
    root = project(tmp_path, {
        f"m{i}.py": f'hits = glob("*/brief{i}.md")\n' for i in range(6)})
    assert not any(f.summary.startswith("*/") for f in findings(root)), \
        findings(root)


def test_home_relative_reports_the_real_directory_not_a_tilde(tmp_path) -> None:
    """`~/` as a head is every home-relative path in a project lumped
    together and no directory at all."""
    root = project(tmp_path, {
        f"m{i}.py": f'p = Path("~/.claude/settings{i}.json")\n' for i in range(5)})
    found = findings(root)
    assert not any(f.summary.startswith("~/ ") for f in found), found
    assert any("~/.claude" in f.summary for f in found), found


# --- F4: what the widened word lists let through ---------------------------

def test_a_compound_option_is_judged_by_its_last_word(tmp_path) -> None:
    """`--filename-case` names a case, not a filename, and its default
    `lower` was reported as a directory across five files. The trailing noun
    is what the value is OF."""
    root = project(tmp_path, {
        f"m{i}.py": 'ap.add_argument("--filename-case", default="lower")\n'
        for i in range(5)})
    assert not any("lower" in f.summary for f in findings(root)), findings(root)


def test_outdir_still_carries_its_bare_default(tmp_path) -> None:
    """The capability the last-word rule must not cost."""
    root = project(tmp_path, {
        f"m{i}.py": f'ap.add_argument("--out-dir", default="records/x{i}.json")\n'
        for i in range(5)})
    assert any("records" in f.summary for f in findings(root)), findings(root)


def test_a_date_is_not_a_directory(tmp_path) -> None:
    """A slash is not enough. `--from`/`--to` defaults of 2026/08/22 reported
    a directory across five files, at both previous commits."""
    root = project(tmp_path, {
        f"m{i}.py": 'ap.add_argument("--from", default="2026/08/22")\n'
        for i in range(5)})
    assert findings(root) == [], findings(root)


def test_a_regex_default_is_not_a_directory(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'ap.add_argument("--source", default=r"^\\d+/\\d+$")\n'
        for i in range(5)})
    assert findings(root) == [], findings(root)


def test_the_value_test_rejects_the_shapes_it_used_to_accept() -> None:
    """Checked directly, because these reached it through several callers."""
    from ziggurat.structure import _value_looks_like_a_path as looks

    for not_a_path in ("2026/08/22", r"^\d+/\d+$", "*.py", "a|b/c", "1/2/3"):
        assert not looks(not_a_path), not_a_path
    for is_a_path in ("records/eye.jsonl", "~/.claude", "./out", "/var/lib/x"):
        assert looks(is_a_path), is_a_path
