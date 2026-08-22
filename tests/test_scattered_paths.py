"""Paths written into many files -- the commonest scattered constant there is."""


from ziggurat import structure


def project(tmp_path, files):
    for name, source in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source)
    return tmp_path


def findings(root, check="scattered-path"):
    return [f for f in structure.analyse(root).findings if f.check == check]


# --- one IDEA with many namers ---------------------------------------------

def test_a_directory_named_in_many_files_is_found(tmp_path) -> None:
    """The finding that prompted this check: a data directory written into
    seventeen modules, so it could not be relocated at all."""
    root = project(tmp_path, {
        f"m{i}.py": f'p = "records/thing{i}.jsonl"\n' for i in range(6)})
    found = findings(root)
    assert any("records/" in f.summary for f in found), found
    assert any("6 files" in f.summary for f in found)


def test_it_says_one_idea_many_namers(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'p = "records/a{i}.jsonl"\n' for i in range(5)})
    assert "One IDEA with many namers" in findings(root)[0].evidence


def test_a_directory_in_few_files_is_a_coincidence(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'p = "records/a{i}.jsonl"\n' for i in range(3)})
    assert findings(root) == []


# --- one FILE with many namers ---------------------------------------------

def test_the_same_file_named_in_many_modules_is_found(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'p = "data/eye.jsonl"\n' for i in range(5)})
    found = findings(root)
    assert any("data/eye.jsonl" in f.summary for f in found), found


def test_a_directory_finding_does_not_also_report_each_file(tmp_path) -> None:
    """Reporting both would say the same thing twice, and the directory one is
    the more useful of the two."""
    files = {}
    for i in range(5):
        files[f"m{i}.py"] = 'a = "records/eye.jsonl"\nb = "records/ear.jsonl"\n'
    found = findings(project(tmp_path, files))
    assert len(found) == 1
    assert "records/" in found[0].summary


# --- what is not a path ----------------------------------------------------

def test_a_media_type_is_not_a_scattered_path(tmp_path) -> None:
    """The first version of this check accused four files of scattering
    `application/` -- which was "application/json", correctly written in all
    four. The guard was on the directory branch only, and the literal branch
    let it straight through."""
    root = project(tmp_path, {
        f"m{i}.py": 'h = {"Content-Type": "application/json"}\n' for i in range(5)})
    assert findings(root) == []


def test_every_media_type_is_excluded(tmp_path) -> None:
    for kind in ("text/html", "audio/wav", "image/png", "video/mp4",
                 "multipart/form-data"):
        root = project(tmp_path / kind.replace("/", "-"),
                       {f"m{i}.py": f'c = "{kind}"\n' for i in range(5)})
        assert findings(root) == [], kind


def test_a_url_is_an_address_not_a_path(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'u = "http://example.com/api"\n' for i in range(5)})
    assert findings(root) == []


def test_is_path_rejects_at_collection_not_at_reporting() -> None:
    """A rule applied on one path out of two is not applied."""
    assert structure._is_path("records/eye.jsonl") is True
    assert structure._is_path("application/json") is False
    assert structure._is_path("http://x/y") is False


# --- the exemptions the sibling check already earned -----------------------

def test_a_path_in_a_docstring_is_documentation(tmp_path) -> None:
    """It can go stale, which is a different and much smaller problem than a
    coupling -- and reporting it as one is the noise that gets a checker
    switched off."""
    root = project(tmp_path, {
        f"m{i}.py": '"""Writes to records/thing.jsonl."""\nx = 1\n'
        for i in range(6)})
    assert findings(root) == []


def test_the_config_module_is_where_a_path_belongs(tmp_path) -> None:
    """A value there is the value being where it belongs, and counting it would
    tell you to remove it from the one correct place."""
    files = {f"m{i}.py": 'p = "records/a.jsonl"\n' for i in range(3)}
    files["config.py"] = 'RECORDS = "records/a.jsonl"\n'
    files["settings.py"] = 'RECORDS = "records/a.jsonl"\n'
    assert findings(project(tmp_path, files)) == []


def test_tests_do_not_count(tmp_path) -> None:
    files = {f"test_m{i}.py": 'p = "records/a.jsonl"\n' for i in range(6)}
    assert findings(project(tmp_path, files)) == []


# --- the check it extends still works --------------------------------------

def test_the_address_check_is_untouched(tmp_path) -> None:
    """This adds a case; it does not replace one."""
    root = project(tmp_path, {
        f"m{i}.py": 'host = "10.1.2.3"\n' for i in range(5)})
    assert findings(root, check="scattered-constant"), "IPs must still be found"
