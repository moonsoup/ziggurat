"""Tier 1: what the git history says about which files move together."""

import subprocess

from ziggurat import history
from ziggurat.findings import Confidence


def git(tmp_path, *args):
    subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, check=False)


def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    return tmp_path


def commit(tmp_path, files, message="c"):
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", message)


def test_files_that_always_change_together_are_reported(tmp_path):
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"a.py": f"# {i}", "b.py": f"# {i}"}, f"c{i}")
    report = history.analyse(tmp_path)
    coupled = [f for f in report.findings if f.check == "change-coupling"]
    assert coupled, "8 of 8 commits touching both should be reported"
    assert "a.py" in coupled[0].evidence and "b.py" in coupled[0].evidence


def test_it_is_reported_as_empirical_not_structural(tmp_path):
    """Co-committal is a proxy. Files can change together coincidentally, and
    a gate built on that would be Goodhart bait."""
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"a.py": f"# {i}", "b.py": f"# {i}"}, f"c{i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert coupled[0].confidence is Confidence.EMPIRICAL


def test_the_caveat_travels_with_the_finding(tmp_path):
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"a.py": f"# {i}", "b.py": f"# {i}"}, f"c{i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert "coincidence" in coupled[0].evidence.lower() or \
           "coincidental" in coupled[0].evidence.lower()


def test_files_that_change_apart_are_not_coupled(tmp_path):
    repo(tmp_path)
    for i in range(6):
        commit(tmp_path, {"a.py": f"# {i}"}, f"a{i}")
    for i in range(6):
        commit(tmp_path, {"b.py": f"# {i}"}, f"b{i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert not coupled


def test_a_single_shared_commit_is_not_a_pattern(tmp_path):
    """One commit touching two files is a commit, not a coupling."""
    repo(tmp_path)
    commit(tmp_path, {"a.py": "x", "b.py": "y"})
    for i in range(6):
        commit(tmp_path, {"a.py": f"# {i}"}, f"a{i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert not coupled


def test_a_sweeping_commit_does_not_couple_everything_to_everything(tmp_path):
    """A rename or a licence header touches every file at once and would
    otherwise manufacture coupling between all of them."""
    repo(tmp_path)
    wide = {f"m{i}.py": "x" for i in range(40)}
    commit(tmp_path, wide, "add a licence header everywhere")
    commit(tmp_path, wide, "and again")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert not coupled, "commits touching everything carry no information"


def test_a_repo_with_no_history_is_skipped_not_crashed(tmp_path):
    repo(tmp_path)
    report = history.analyse(tmp_path)
    assert report.skipped and not report.findings


def test_a_directory_that_is_not_a_repo_is_skipped(tmp_path):
    report = history.analyse(tmp_path)
    assert report.skipped
    assert "git" in report.skipped[0][1].lower()


def test_build_artifacts_are_not_coupling(tmp_path):
    """The first real run drowned in .apk/.dex/.idsig pairs changing together
    100% of the time. They are outputs of one build step -- trivially true and
    architecturally silent, and exactly the noise that gets a tool switched
    off."""
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"build/app.apk": f"{i}", "build/classes.dex": f"{i}",
                          "build/app.apk.idsig": f"{i}"}, f"c{i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert not coupled, "generated artifacts are not an architectural signal"


def test_real_source_coupling_still_surfaces_alongside_artifacts(tmp_path):
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"build/app.apk": f"{i}",
                          "src/a.py": f"# {i}", "src/b.py": f"# {i}"}, f"c{i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert coupled, "the source pair should still be found"
    assert all(".apk" not in p for f in coupled for p in f.paths)


def test_a_file_and_its_own_test_are_not_a_finding(tmp_path):
    """They SHOULD change together -- that is the practice working, not a
    coupling problem. Reporting it is noise of a subtler kind than build
    artifacts: it is true, and it is not a fault."""
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"src/triage.py": f"# {i}",
                          "tests/test_triage.py": f"# {i}"}, f"c{i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert not coupled


def test_two_unrelated_modules_are_still_a_finding(tmp_path):
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"src/alpha.py": f"# {i}",
                          "src/beta.py": f"# {i}"}, f"c{i}")
    assert [f for f in history.analyse(tmp_path).findings
            if f.check == "change-coupling"]


def test_version_manifests_do_not_couple_to_everything(tmp_path):
    """pyproject.toml and __init__.py changed together 100% of the time in a
    real project -- because every release bumps the version in both. That is
    PROCESS coupling, not architecture, and it is the documented false-positive
    mode of co-change analysis."""
    repo(tmp_path)
    for i in range(8):
        commit(tmp_path, {"pyproject.toml": f'version="0.{i}"',
                          "pkg/__init__.py": f'__version__="0.{i}"'}, f"release {i}")
    coupled = [f for f in history.analyse(tmp_path).findings
               if f.check == "change-coupling"]
    assert not coupled


# --- 2026-09-17: a second independent verification ---------------------------

def test_a_ratio_counts_every_commit_that_touched_the_file(tmp_path):
    """Commits touching only one file were dropped BEFORE the denominator was
    counted. Two files with ten commits each, four of them shared, were
    reported as changing together 100% of the time -- the true figure is 40%,
    under the bar."""
    repo(tmp_path)
    for i in range(6):
        commit(tmp_path, {"a.py": f"x = {i}\n"}, f"a alone {i}")
        commit(tmp_path, {"b.py": f"x = {i}\n"}, f"b alone {i}")
    for i in range(4):
        commit(tmp_path, {"a.py": f"y = {i}\n", "b.py": f"y = {i}\n"}, f"both {i}")
    found = history.analyse(tmp_path).findings
    assert not found, [f.summary for f in found]


def test_the_evidence_gives_the_real_commit_counts(tmp_path):
    repo(tmp_path)
    commit(tmp_path, {"a.py": "x = 0\n"}, "a alone")
    for i in range(4):  # history shorter than this is skipped outright
        commit(tmp_path, {"c.py": f"z = {i}\n"}, f"elsewhere {i}")
    for i in range(4):
        commit(tmp_path, {"a.py": f"y = {i}\n", "b.py": f"y = {i}\n"}, f"both {i}")
    found = history.analyse(tmp_path).findings
    assert found and "a.py has 5 commits" in found[0].evidence, \
        [f.evidence for f in found]


def test_no_coupled_pair_is_dropped_by_a_display_cap(tmp_path):
    """Only the forty most-shared pairs were ever looked at. The rest were
    dropped without a word, however coupled."""
    repo(tmp_path)
    for n in range(45):
        for i in range(4):
            commit(tmp_path, {f"q{n}/a.py": f"x = {i}\n",
                              f"q{n}/b.py": f"x = {i}\n"}, f"pair {n} {i}")
    found = [f for f in history.analyse(tmp_path).findings
             if f.summary.startswith("q")]
    assert len(found) == 45, len(found)


def test_the_readable_report_says_how_many_it_did_not_list(tmp_path):
    """A cap on what a PERSON reads, never on what is judged: every pair is
    still a finding, and the report says how many it held back."""
    from ziggurat.findings import SHOWN_PER_CHECK, Finding, Report

    report = Report(project="p")
    for n in range(SHOWN_PER_CHECK + 5):
        report.add(Finding(check="change-coupling", summary=f"pair {n}",
                           evidence="e", confidence=Confidence.EMPIRICAL))
    text = report.render()
    assert f"pair {SHOWN_PER_CHECK - 1}" in text
    assert f"pair {SHOWN_PER_CHECK}" not in text
    assert "and 5 more change-coupling findings not listed" in text
    assert f"pair {SHOWN_PER_CHECK + 4}" in report.render(full=True)
    assert len(report.as_dict()["findings"]) == SHOWN_PER_CHECK + 5
