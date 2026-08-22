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
