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
