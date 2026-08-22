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
        f"m{i}.py": f'p = Path("records/thing{i}.jsonl")\n' for i in range(6)})
    found = findings(root)
    assert any("records/" in f.summary for f in found), found
    assert any("6 files" in f.summary for f in found)


def test_it_says_one_idea_many_namers(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(5)})
    assert "One IDEA with many namers" in findings(root)[0].evidence


def test_a_directory_in_few_files_is_a_coincidence(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(3)})
    assert findings(root) == []


# --- one FILE with many namers ---------------------------------------------

def test_the_same_file_named_in_many_modules_is_found(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'p = Path("data/eye.jsonl")\n' for i in range(5)})
    found = findings(root)
    assert any("data/eye.jsonl" in f.summary for f in found), found


def test_a_directory_finding_does_not_also_report_each_file(tmp_path) -> None:
    """Reporting both would say the same thing twice, and the directory one is
    the more useful of the two."""
    files = {}
    for i in range(5):
        files[f"m{i}.py"] = ('a = Path("records/eye.jsonl")\n'
                             'b = Path("records/ear.jsonl")\n')
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
        f"m{i}.py": 'h = open("application/json")\n' for i in range(5)})
    assert findings(root) == []


def test_every_media_type_is_excluded(tmp_path) -> None:
    for kind in ("text/html", "audio/wav", "image/png", "video/mp4",
                 "multipart/form-data"):
        root = project(tmp_path / kind.replace("/", "-"),
                       {f"m{i}.py": f'c = open("{kind}")\n' for i in range(5)})
        assert findings(root) == [], kind


def test_a_url_is_an_address_not_a_path(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": 'u = open("http://example.com/api")\n' for i in range(5)})
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
    files = {f"m{i}.py": 'p = Path("records/a.jsonl")\n' for i in range(3)}
    files["config.py"] = 'RECORDS = Path("records/a.jsonl")\n'
    files["settings.py"] = 'RECORDS = Path("records/a.jsonl")\n'
    assert findings(project(tmp_path, files)) == []


def test_tests_do_not_count(tmp_path) -> None:
    files = {f"test_m{i}.py": 'p = Path("records/a.jsonl")\n' for i in range(6)}
    assert findings(project(tmp_path, files)) == []


# --- the check it extends still works --------------------------------------

def test_the_address_check_is_untouched(tmp_path) -> None:
    """This adds a case; it does not replace one."""
    root = project(tmp_path, {
        f"m{i}.py": 'host = "10.1.2.3"\n' for i in range(5)})
    assert findings(root, check="scattered-constant"), "IPs must still be found"


# --- the forms a regex could not see (moonsoup/ziggurat#3) -----------------

def test_an_argparse_default_is_a_namer(tmp_path) -> None:
    """The one nobody finds when relocating, because it reads as
    configuration rather than as a path."""
    root = project(tmp_path, {
        f"m{i}.py": f'p.add_argument("--out", default="records/a{i}.txt")\n'
        for i in range(5)})
    assert findings(root), "an argparse default names the directory too"


def test_a_pathlib_join_is_a_namer(tmp_path) -> None:
    """`root / "records" / name` has no slash in any literal, so a search for
    one walks straight past it."""
    root = project(tmp_path, {
        f"m{i}.py": f'p = root / "records" / "a{i}.jsonl"\n' for i in range(5)})
    assert findings(root)


def test_an_f_string_is_a_namer(tmp_path) -> None:
    """Braces fall outside a character class, which is why
    `f"records/{serial}-restore.sh"` survived the first version."""
    root = project(tmp_path, {
        f"m{i}.py": f'p = Path(f"records/{{name}}-{i}.sh")\n' for i in range(5)})
    assert findings(root)


def test_a_string_the_project_has_proved_is_a_path_counts_anywhere(tmp_path) -> None:
    """`capture.shoot(bod, cam, "records")` passes a directory positionally to
    a function whose name means nothing to a checker. Once the project has
    proved `records` IS a directory elsewhere, a bare mention is the same
    directory named again."""
    files = {f"m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(4)}
    for i in range(3):
        files[f"n{i}.py"] = 'shoot(body, cam, "records")\n'
    found = findings(project(tmp_path, files))
    assert found
    assert found[0].summary.count("files")  # counts the bare ones too
    assert len(found[0].paths) >= 6


# --- the noise that made it useless on other languages (#2) ----------------

def test_go_import_specifiers_are_not_paths(tmp_path) -> None:
    """`os/exec` and `encoding/json` are namespaces. Reporting them made the
    check unusable on every Go project it was pointed at."""
    root = project(tmp_path, {
        f"m{i}.go": 'import (\n\t"os/exec"\n\t"encoding/json"\n)\n'
        for i in range(6)})
    assert findings(root) == []


def test_typescript_relative_imports_are_not_paths(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.ts": 'import { a } from "./client";\n'
                    'import { b } from "../types";\n' for i in range(6)})
    assert findings(root) == []


def test_a_model_id_is_not_a_directory(tmp_path) -> None:
    """`Qwen/ is written into 32 files` -- with the advice that relocating it
    should be a setting, which is nonsense for a HuggingFace model."""
    root = project(tmp_path, {
        f"m{i}.sh": 'MODEL="Qwen/Qwen2.5-Coder-7B-Instruct"\n' for i in range(6)})
    assert findings(root) == []


def test_an_http_route_is_not_a_directory(tmp_path) -> None:
    root = project(tmp_path, {
        f"m{i}.py": f'@app.get("/genes/{i}")\ndef f(): pass\n' for i in range(6)})
    assert findings(root) == []


def test_a_profile_name_is_not_a_directory(tmp_path) -> None:
    """`--profile` contains the substring "file", and substring matching duly
    reported the profile name "balanced" as a scattered directory."""
    root = project(tmp_path, {
        f"m{i}.py": 'p.add_argument("--profile", default="balanced")\n'
        for i in range(6)})
    assert findings(root) == []


def test_a_file_mode_is_not_a_directory(tmp_path) -> None:
    """`target.open("a")` passes a MODE. Taking every argument of every
    path-ish call reported the letter "a" as a scattered directory."""
    root = project(tmp_path, {
        f"m{i}.py": 'with target.open("a") as fh:\n    pass\n' for i in range(6)})
    assert findings(root) == []


def test_navigation_is_not_a_name(tmp_path) -> None:
    """Every Python project joins on `..`, and a directory called `.` is
    nobody's directory."""
    root = project(tmp_path, {
        f"m{i}.py": 'sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))\n'
        for i in range(6)})
    assert findings(root) == []


def test_a_dict_key_is_not_a_directory(tmp_path) -> None:
    """The confirmation pass promotes bare strings once a head is proved a
    directory -- and over-reached, turning the key "genes" into a scattered
    path in fourteen files. A head must be seen WITH a slash, or in enough
    files to stand on its own."""
    files = {f"m{i}.py": 'x = {"genes": [], "id": 1}\n' for i in range(6)}
    files["one.py"] = 'p = Path("genes")\n'
    assert findings(project(tmp_path, files)) == []
