"""Tier 1: the structure analyser must find the failures that actually happened.

These are not hypothetical. Every case here is something that occurred in
`incarnation` during the session that prompted this tool, and a miss is a
measurable false negative rather than a matter of taste.
"""

from ziggurat import structure
from ziggurat.findings import Confidence


def write(tmp_path, rel, content=""):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_entry_point_sprawl_is_found(tmp_path):
    """24 scripts in bin/ was the actual failure, and no import analyser can
    see it because entry points do not import each other."""
    for i in range(14):
        write(tmp_path, f"bin/thing{i}.py", "def main(): pass\n")
    report = structure.analyse(tmp_path)
    sprawl = [f for f in report.findings if f.check == "entry-point-sprawl"]
    assert sprawl, "14 entry points should be reported"
    assert "14" in sprawl[0].evidence
    assert sprawl[0].confidence is Confidence.STRUCTURAL


def test_a_few_entry_points_is_not_sprawl(tmp_path):
    """A tool with three commands is not a problem, and saying so would be the
    noise that gets a checker switched off."""
    for i in range(3):
        write(tmp_path, f"bin/thing{i}.py", "def main(): pass\n")
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "entry-point-sprawl"]


def test_loading_another_script_by_file_path_is_found(tmp_path):
    """This coupling hides from every import analyser, because it is not an
    import. It happened twice in incarnation."""
    write(tmp_path, "bin/a.py", "def main(): pass\n")
    write(tmp_path, "bin/b.py",
          "import importlib.util\n"
          "spec = importlib.util.spec_from_file_location('a', 'bin/a.py')\n")
    report = structure.analyse(tmp_path)
    dyn = [f for f in report.findings if f.check == "dynamic-loading"]
    assert dyn, "spec_from_file_location should be reported"
    assert "b.py" in " ".join(dyn[0].paths)
    assert dyn[0].confidence is Confidence.STRUCTURAL


def test_a_value_repeated_across_many_files_is_found(tmp_path):
    """One idea should be one edit. The body's address appeared in a dozen
    files, so moving the device cost a dozen edits and a search."""
    for i in range(6):
        write(tmp_path, f"src/mod{i}.py", 'HOST = "192.168.1.223"\n')
    report = structure.analyse(tmp_path)
    dup = [f for f in report.findings if f.check == "scattered-constant"]
    assert dup, "a repeated address should be reported"
    assert "192.168.1.223" in dup[0].evidence


def test_a_value_in_two_files_is_not_yet_a_problem(tmp_path):
    """Two is a coincidence; a dozen is a decision nobody made."""
    for i in range(2):
        write(tmp_path, f"src/mod{i}.py", 'HOST = "192.168.1.223"\n')
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "scattered-constant"]


def test_loopback_is_not_a_deployment_coupling(tmp_path):
    for i in range(8):
        write(tmp_path, f"src/mod{i}.py", 'URL = "http://127.0.0.1:8090"\n')
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "scattered-constant"]


def test_tests_are_not_counted(tmp_path):
    """Tests assert against literal values by their nature."""
    for i in range(8):
        write(tmp_path, f"tests/test_{i}.py", 'assert host == "192.168.1.223"\n')
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "scattered-constant"]


def test_vendored_trees_are_skipped(tmp_path):
    for i in range(20):
        write(tmp_path, f".venv/lib/pkg{i}.py", 'HOST = "192.168.1.223"\n')
        write(tmp_path, f"node_modules/pkg{i}/index.js", 'HOST = "192.168.1.223"\n')
    report = structure.analyse(tmp_path)
    assert not report.findings, "vendored code is never ours to fix"


def test_an_empty_project_is_not_an_error(tmp_path):
    report = structure.analyse(tmp_path)
    assert report.findings == []


def test_a_missing_directory_is_skipped_not_crashed(tmp_path):
    report = structure.analyse(tmp_path / "nope")
    assert report.skipped, "a check that did not run must say so"


def test_the_config_module_is_where_the_value_belongs(tmp_path):
    """Counting the config module as a violation tells you to remove the value
    from the one place it should be."""
    write(tmp_path, "src/config.py", 'HOST = "192.168.1.223"\n')
    for i in range(5):
        write(tmp_path, f"src/mod{i}.py", 'from .config import HOST\n')
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "scattered-constant"]


def test_a_usage_example_in_a_docstring_is_documentation(tmp_path):
    """`run.py --host 192.168.1.223` in a docstring is documentation. It can go
    stale, which is a different and lesser problem than a coupling, and
    reporting it as one is the noise that gets a checker switched off."""
    for i in range(6):
        write(tmp_path, f"src/mod{i}.py",
              '"""Usage:\n\n    thing.py --host 192.168.1.223\n"""\n\nX = 1\n')
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "scattered-constant"]


def test_a_comment_is_not_code_either(tmp_path):
    for i in range(6):
        write(tmp_path, f"src/mod{i}.py", '# the body lives at 192.168.1.223\nX = 1\n')
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "scattered-constant"]


def test_an_assigned_string_is_still_code(tmp_path):
    """Only bare docstrings are documentation. A value assigned to a name is
    the coupling itself."""
    for i in range(6):
        write(tmp_path, f"src/mod{i}.py", 'HOST = "192.168.1.223"\n')
    report = structure.analyse(tmp_path)
    assert [f for f in report.findings if f.check == "scattered-constant"]


def test_naming_a_pattern_is_not_using_it(tmp_path):
    """Ziggurat flagged ITSELF: structure.py contains
    "spec_from_file_location" as a string it searches for, not as a call. A
    detector that cannot tell a mention from a use will always accuse its own
    source, and anything else that discusses the technique."""
    # Including the parenthesis, which is what the real source contains and
    # what made adding the paren to the pattern fail to fix anything.
    write(tmp_path, "src/checker.py",
          'PATTERNS = ("spec_from_file_location(", "why it matters")\n')
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "dynamic-loading"]


def test_actually_calling_it_is_still_found(tmp_path):
    write(tmp_path, "src/real.py",
          "import importlib.util\n"
          "spec = importlib.util.spec_from_file_location('a', 'a.py')\n")
    report = structure.analyse(tmp_path)
    assert [f for f in report.findings if f.check == "dynamic-loading"]


def test_a_delegating_shim_is_an_alias_not_an_entry_point(tmp_path):
    """The check's own rationale is that each entry point re-decides config,
    argument handling and discovery. A shim that imports one function
    re-decides nothing -- so counting it means counting FILES while claiming to
    count independent implementations.

    This is the refinement that lets a real consolidation register as one.
    """
    write(tmp_path, "pkg/__init__.py")
    write(tmp_path, "bin/tool.py", "from pkg.commands import run\nrun()\n")
    for i in range(14):
        write(tmp_path, f"bin/old{i}.py",
              "import sys\n"
              "from pathlib import Path\n"
              f"from pkg.commands.old{i} import main\n"
              "raise SystemExit(main())\n")
    report = structure.analyse(tmp_path)
    assert not [f for f in report.findings if f.check == "entry-point-sprawl"]


def test_real_sprawl_is_still_sprawl(tmp_path):
    """Fourteen scripts that each define their own logic is the thing the check
    exists for, and must not be excused by this refinement."""
    for i in range(14):
        write(tmp_path, f"bin/thing{i}.py",
              "import argparse\n"
              "def main():\n"
              "    ap = argparse.ArgumentParser()\n"
              "    ap.add_argument('--host', default='10.0.0.1')\n"
              "    return 0\n")
    report = structure.analyse(tmp_path)
    assert [f for f in report.findings if f.check == "entry-point-sprawl"]


def test_a_shim_with_logic_smuggled_in_still_counts(tmp_path):
    """Otherwise the exemption becomes the hiding place."""
    write(tmp_path, "pkg/__init__.py")
    for i in range(14):
        write(tmp_path, f"bin/old{i}.py",
              f"from pkg.commands.old{i} import main\n"
              "def helper():\n"
              "    return 42\n"
              "raise SystemExit(main())\n")
    report = structure.analyse(tmp_path)
    assert [f for f in report.findings if f.check == "entry-point-sprawl"]


# --- the filename from the argument, the directory from a global ------------

def hits(tmp_path):
    return [f for f in structure.analyse(tmp_path).findings
            if f.check == "sibling-from-global"]


def test_a_sibling_located_through_a_global_is_found(tmp_path):
    """The real one, verbatim.

    `_cursor_path` was handed a log and returned the cursor for a DIFFERENT
    log -- same filename, wrong directory. It never raised and never returned
    anything malformed, so the damage appeared two systems away: thinning a
    test fixture named `eye.jsonl` rewrote the production cursor, moving a
    live reader to byte 989 of a two-gigabyte log, on every test run for a day.
    """
    write(tmp_path, "keeping.py", '''
from config import CONFIG

def _cursor_path(stream):
    return CONFIG.path(f"relay-{stream.stem}.json")
''')
    found = hits(tmp_path)
    assert found, "the filename came from the argument and the directory did not"
    assert "CONFIG" in found[0].summary
    assert "stream.stem" in found[0].evidence
    assert found[0].confidence is Confidence.STRUCTURAL


def test_the_division_form_is_found_too(tmp_path):
    """`ROOT / name` is the same mistake with different syntax, and a check
    that only knew one spelling would be a check you could get past by
    reformatting."""
    write(tmp_path, "store.py", '''
ROOT = "/var/lib/thing"

def cache_for(path):
    return ROOT / (path.stem + ".cache")
''')
    assert hits(tmp_path)


def test_deriving_from_the_argument_is_not_reported(tmp_path):
    """The fix must silence it, or the check cannot be acted on."""
    write(tmp_path, "keeping.py", '''
from config import CONFIG

def _cursor_path(stream):
    return stream.parent / f"relay-{stream.stem}.json"
''')
    assert not hits(tmp_path)


def test_a_global_used_without_the_arguments_name_is_not_reported(tmp_path):
    """Copying a template beside a global INTO a given path is ordinary and
    correct. The fault is taking the name from one place and the location from
    another; using a global on its own is not the fault."""
    write(tmp_path, "install.py", '''
from config import CONFIG

def install(dest):
    return CONFIG.path("template.conf"), dest
''')
    assert not hits(tmp_path)


def test_a_function_with_no_path_argument_is_not_reported(tmp_path):
    """With no path in hand, the global is the right answer -- it is the only
    answer. This check is about ignoring a path that was passed."""
    write(tmp_path, "places.py", '''
from config import CONFIG

def cursor():
    return CONFIG.path("relay-eye.json")
''')
    assert not hits(tmp_path)


def test_a_module_or_class_is_not_mistaken_for_a_constant(tmp_path):
    """`Path(...)` and `os.path.join(...)` root at a class and a module, and
    reporting those would bury the real signal in every file that builds a
    path at all."""
    write(tmp_path, "places.py", '''
import os.path
from pathlib import Path

def beside(path):
    return Path(path.parent) / path.name

def also(path):
    return os.path.join(str(path.parent), path.stem + ".bak")
''')
    assert not hits(tmp_path)


def test_tests_and_config_are_not_reported(tmp_path):
    """A config module's whole job is turning constants into paths, and a test
    reaching for a global is reaching into its own fixtures."""
    write(tmp_path, "config.py", '''
ROOT = "/var/lib/thing"

def path_for(path):
    return ROOT / path.name
''')
    write(tmp_path, "tests/test_it.py", '''
ROOT = "/tmp/x"

def helper(path):
    return ROOT / path.name
''')
    assert not hits(tmp_path)
