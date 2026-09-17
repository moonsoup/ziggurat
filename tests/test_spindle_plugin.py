"""Ziggurat as a SPIndlebox plugin: the same answer, through the platform.

The claim this file exists to hold down is EQUIVALENCE. A check moved behind a
plugin contract must say exactly what it said before, or the move has changed
the tool while claiming only to rehouse it.

No test here skips when spindlebox is missing. A verification that quietly
does not run is the failure mode this whole exercise is about, so an absent
platform is a failure, loudly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "bin" / "ziggurat.py"


def git(root, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "-c", "commit.gpgsign=false", *args],
                   cwd=root, check=True, capture_output=True)


@pytest.fixture(scope="module")
def spindlebox():
    """The platform, or a failure -- never a skip."""
    try:
        import spindlebox  # noqa: F401
        from spindlebox import plugins, reporting  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment failure
        pytest.fail(
            "spindlebox is not importable, so the plugin cannot be verified: "
            f"{exc}. Install it (`pip install -e .` in ~/Software/spindlebox) "
            "rather than letting these tests pass by not running.")
    from spindlebox import plugins

    plugins.forget()
    loaded = plugins.loaded()
    assert "ziggurat" in loaded, (
        "the ziggurat entry point is not installed: "
        f"loaded={sorted(loaded)} problems={plugins.problems()}. "
        "Run `pip install -e .` in this repo.")
    return loaded["ziggurat"]


@pytest.fixture
def coupled(tmp_path):
    """A project whose history couples two files, and one that has no history."""
    root = tmp_path / "coupled"
    (root / "pkg").mkdir(parents=True)
    git(root, "init", "-q")
    for i in range(6):
        (root / "a.py").write_text(f"x = {i}\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", f"a {i}")
        (root / "b.py").write_text(f"y = {i}\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", f"b {i}")
    for i in range(5):
        (root / "a.py").write_text(f"z = {i}\n")
        (root / "b.py").write_text(f"z = {i}\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", f"both {i}")
    return root


def _standalone(path, *args):
    done = subprocess.run([sys.executable, str(BIN), "report", str(path),
                           "--only", "history", "--json", *args],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def _through_plugin(path):
    from spindlebox import reporting

    stack = reporting.all_stacks()["ziggurat:change-coupling"]
    ctx = reporting.run_stack(stack, {"root": str(path), "format": "json"})
    return json.loads(ctx["output"])


# --- the contract -----------------------------------------------------------

def test_the_stack_is_listed_and_type_checks(spindlebox) -> None:
    from spindlebox import reporting

    stacks = reporting.all_stacks()
    assert "ziggurat:change-coupling" in stacks
    assert reporting.check_stack(stacks["ziggurat:change-coupling"]) == []


def test_the_plugin_declares_the_platform_contract(spindlebox) -> None:
    from spindlebox import plugins

    assert spindlebox.api == plugins.PLUGIN_API
    assert spindlebox.name == "ziggurat"


# --- equivalence ------------------------------------------------------------

def test_the_plugin_says_what_the_standalone_tool_says(spindlebox, coupled) -> None:
    expected = _standalone(coupled)
    got = _through_plugin(coupled)["results"]["coupled"]
    assert got == expected


def test_a_project_with_no_history_is_skipped_identically(spindlebox, tmp_path) -> None:
    """The case a table would lose: a check that could not run at all."""
    root = tmp_path / "bare"
    root.mkdir()
    (root / "m.py").write_text("x = 1\n")
    expected = _standalone(root)
    got = _through_plugin(root)["results"]["bare"]
    assert got == expected
    assert got["skipped"], "a project with no git history must say so"


def test_the_same_answer_through_the_real_cli(spindlebox, coupled) -> None:
    """Byte-for-byte, through the entry point a person would type."""
    direct = subprocess.run([sys.executable, str(BIN), "report", str(coupled),
                             "--only", "history", "--json"],
                            capture_output=True, text=True, check=True)
    viaplatform = subprocess.run(
        [sys.executable, "-m", "spindlebox", "ziggurat", "report", str(coupled),
         "--only", "history", "--json"], capture_output=True, text=True, check=True)
    assert viaplatform.stdout == direct.stdout


def test_a_missing_project_is_reported_not_dropped(spindlebox, tmp_path) -> None:
    from spindlebox import reporting

    stack = reporting.all_stacks()["ziggurat:change-coupling"]
    with pytest.raises(Exception):
        reporting.run_stack(stack, {"root": str(tmp_path / "nonsuch"),
                                    "format": "json"})


# --- the standalone tool is unchanged ---------------------------------------

def test_the_bin_script_still_works_without_the_platform() -> None:
    """`bin/ziggurat.py` is a delegate now, and must still run on its own --
    the import contract proves no other module reaches for spindlebox."""
    done = subprocess.run([sys.executable, str(BIN), "--help"],
                          capture_output=True, text=True, check=True)
    for command in ("report", "drift", "sweep", "compare"):
        assert command in done.stdout
