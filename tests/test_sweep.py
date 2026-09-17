"""Running the report across many projects, and diffing two runs of it.

A checker change is proven against real trees, not against the fixture it was
written for: every false positive this tool has shipped passed its own tests.
`sweep` records what the checker said about every project; `compare` says what
a change to the checker changed about what it says.
"""

import json
import subprocess
import sys
from pathlib import Path

from ziggurat import sweep


def project(root: Path, files: dict) -> Path:
    for name, source in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source)
    return root


SCATTERED = {f"m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(5)}


def test_every_project_directory_gets_a_record(tmp_path) -> None:
    root = tmp_path / "software"
    project(root / "alpha", SCATTERED)
    project(root / "beta", {"one.py": "x = 1\n"})
    out = tmp_path / "out"

    written = sweep.run(root, out, only=["structure"])

    assert sorted(p.name for p in written) == ["alpha.json", "beta.json"]
    alpha = json.loads((out / "alpha.json").read_text())
    assert any(f["check"] == "scattered-path" for f in alpha["findings"])


def test_a_record_says_how_many_files_were_looked_at(tmp_path) -> None:
    """The number that tells "found nothing" from "looked at nothing"."""
    root = tmp_path / "software"
    project(root / "alpha", SCATTERED)
    out = tmp_path / "out"
    sweep.run(root, out, only=["structure"])
    assert json.loads((out / "alpha.json").read_text())["scanned"] == 5


def test_hidden_directories_and_loose_files_are_not_projects(tmp_path) -> None:
    root = tmp_path / "software"
    project(root / "alpha", {"one.py": "x = 1\n"})
    project(root / ".cache", {"junk.py": "x = 1\n"})
    (root / "notes.txt").write_text("not a project\n")
    assert [p.name for p in sweep.projects(root)] == ["alpha"]


def _record(out: Path, name: str, scanned: int, summaries: list) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps({
        "project": name, "scanned": scanned, "skipped": [], "quiet": [],
        "findings": [{"check": c, "summary": s, "paths": []}
                     for c, s in summaries]}))


def test_compare_names_what_appeared_and_what_vanished(tmp_path) -> None:
    before, after = tmp_path / "before", tmp_path / "after"
    _record(before, "alpha", 10, [("scattered-path", "old/ in 4 files")])
    _record(after, "alpha", 10, [("scattered-path", "new/ in 5 files")])

    lines = sweep.compare(before, after)

    assert "alpha" in lines[0]
    assert any(line.strip() == "- scattered-path: old/ in 4 files"
               for line in lines)
    assert any(line.strip() == "+ scattered-path: new/ in 5 files"
               for line in lines)


def test_compare_reports_a_change_in_what_was_looked_at(tmp_path) -> None:
    """A fix that makes the checker see more, or less, is a change even when
    no finding moved -- and the silent version of it is how a checker goes
    blind without anybody noticing."""
    before, after = tmp_path / "before", tmp_path / "after"
    _record(before, "alpha", 0, [])
    _record(after, "alpha", 122, [])
    assert any("scanned 0 -> 122" in line for line in sweep.compare(before, after))


def test_compare_is_silent_about_a_project_nothing_changed_in(tmp_path) -> None:
    before, after = tmp_path / "before", tmp_path / "after"
    _record(before, "alpha", 3, [("x", "y")])
    _record(after, "alpha", 3, [("x", "y")])
    assert sweep.compare(before, after) == []


def test_compare_names_a_project_present_on_one_side_only(tmp_path) -> None:
    before, after = tmp_path / "before", tmp_path / "after"
    _record(before, "gone", 3, [])
    _record(after, "new", 3, [])
    lines = sweep.compare(before, after)
    assert any("gone" in line and "only in before" in line for line in lines)
    assert any("new" in line and "only in after" in line for line in lines)


def test_the_cli_sweeps_and_compares(tmp_path) -> None:
    """Through the real entry point, as a person or a hook would run it."""
    cli = [sys.executable, str(Path(__file__).resolve().parent.parent
                               / "bin" / "ziggurat.py")]
    root = tmp_path / "software"
    project(root / "alpha", SCATTERED)
    first, second = tmp_path / "first", tmp_path / "second"

    subprocess.run([*cli, "sweep", str(root), "--out", str(first),
                    "--only", "structure"], check=True, capture_output=True)
    (root / "alpha" / "m0.py").write_text("x = 1\n")
    subprocess.run([*cli, "sweep", str(root), "--out", str(second),
                    "--only", "structure"], check=True, capture_output=True)
    done = subprocess.run([*cli, "compare", str(first), str(second)],
                          check=True, capture_output=True, text=True)

    assert "alpha" in done.stdout
    assert "5 files" in done.stdout and "4 files" in done.stdout
