"""Things in a tree that are not the project's own code, as one class.

Ziggurat has learned this file by file: a git worktree doubled every count, a
`.next` bundle produced twelve scattered paths from somebody else's minified
JavaScript, a committed `.venv` offered twenty vendored modules, and a custody
tool's state file co-changed with everything (#30). Each was fixed on its own,
and the next member of the class was found by a reviewer rather than by a test.

So this asserts the property directly: adding tool state, an index, a cache, a
worktree, a vendored tree or generated output to a project must not change what
Ziggurat says about it.
"""

from __future__ import annotations

import subprocess

from ziggurat import history, report, structure


def git(root, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "-c", "commit.gpgsign=false", *args],
                   cwd=root, check=True, capture_output=True)


#: The project's own code: a real scattered path and a real coupled pair.
OWN = {f"pkg/m{i}.py": f'p = Path("records/a{i}.jsonl")\n' for i in range(5)}

#: Everything a tree accumulates that nobody in the project authored.
#: Each group is large enough to CROSS the reporting threshold on its own, so a
#: test comparing clean with dirty cannot pass by everything being below the bar.
NOT_OURS = {
    ".stop-guessing/ledger/custody.jsonl": '{"seq": 0}\n',
    ".stop-guessing/state/8159588e.df5dd269.json": '{"posture": "observe"}\n',
    ".spi/index.json": '{"items": []}\n',
    "__pycache__/m0.cpython-311.pyc": "\x00\x00\n",
    **{f".claude/worktrees/branch/pkg/m{i}.py": f'p = Path("records/a{i}.jsonl")\n'
       for i in range(5)},
    **{f"node_modules/pkg{i}/index.js": f'a = "/public/robots{i}.txt"\n' for i in range(5)},
    **{f".venv/lib/site-packages/dep{i}.py": f'p = Path("deps/d{i}.jsonl")\n' for i in range(5)},
    **{f"dist/chunk{i}.js": f'a = "/public/sitemap{i}.xml"\n' for i in range(5)},
}


def _build(root, files):
    for name, text in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def _findings(root):
    return sorted(f"{f.check}: {f.summary}" for f in report.analyse(root).findings)


def test_what_nobody_authored_changes_nothing(tmp_path):
    clean = _build(tmp_path / "clean", dict(OWN))
    dirty = _build(tmp_path / "dirty", {**OWN, **NOT_OURS})
    for root in (clean, dirty):
        git(root, "init", "-q")
        git(root, "add", "-A", "-f")          # -f: tracked even if a .gitignore would exclude
        git(root, "commit", "-q", "-m", "one")

    assert _findings(clean) == _findings(dirty), (
        f"clean={_findings(clean)}\ndirty={_findings(dirty)}")


def test_the_project_itself_is_still_seen(tmp_path):
    """The control: the fixture's own scattered path must be found, or the test
    above would pass by finding nothing at all."""
    root = _build(tmp_path / "only-ours", dict(OWN))
    assert any("records/" in f for f in _findings(root)), _findings(root)
    assert structure.analyse(root).scanned == 5


def test_a_coupled_pair_of_ours_survives_the_noise(tmp_path):
    root = tmp_path / "coupled"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    for i in range(10):          # >= MIN_SHARED * 2, or history is skipped entirely
        _build(root, {"a.py": f"x = {i}\n", "b.py": f"y = {i}\n",
                      ".stop-guessing/state/s.json": f'{{"n": {i}}}\n'})
        git(root, "add", "-A", "-f")
        git(root, "commit", "-q", "-m", f"both {i}")
    summaries = " ".join(f.summary for f in history.analyse(root).findings)
    assert "a.py and b.py" in summaries, summaries
    assert ".stop-guessing" not in summaries, summaries


def test_a_minified_bundle_is_not_the_project_either(tmp_path):
    """A vendored bundle nobody would name: oligolia keeps a 3Dmol build at
    `structure_viewer/assets/3Dmol-min.js`, which no directory-name list
    catches, and its literals read like anyone else's
    (moonsoup/spindlebox#33)."""
    root = tmp_path / "with-bundle"
    _build(root, dict(OWN))
    bundle = "var a=1;" + ";".join(f'x{i}="/public/robots{i}.txt"' for i in range(120))
    assert len(bundle) > 2000
    for i in range(5):
        _build(root, {f"assets/vendor{i}-min.js": bundle + "\n"})
    git(root, "init", "-q")
    git(root, "add", "-A", "-f")
    git(root, "commit", "-q", "-m", "one")

    found = _findings(root)
    assert any("records/" in f for f in found), found          # ours, still seen
    assert not any("public" in f for f in found), found        # theirs, not read
    assert structure.analyse(root).scanned == 5
