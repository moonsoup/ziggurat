"""A cheap fingerprint of a project's shape, so the report can stay expensive."""

import pytest
from ziggurat import shape


def project(tmp_path, files):
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return tmp_path


def test_an_unchanged_project_has_an_unchanged_shape(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "def one():\n    return 1\n"})
    first = shape.shape(root)
    second = shape.shape(root)
    assert shape.digest(first) == shape.digest(second)
    assert shape.differences(first, second) == []


def test_rewriting_a_function_body_is_invisible(tmp_path) -> None:
    """The whole saving. An edit inside a function cannot create an entry
    point, scatter a constant, or add a module -- so it must not cost a full
    architecture report."""
    root = project(tmp_path, {"a.py": "def one():\n    return 1\n"})
    before = shape.shape(root)
    (root / "a.py").write_text(
        "def one():\n    total = 0\n    for i in range(10):\n"
        "        total += i * 3\n    return total\n")
    assert shape.differences(before, shape.shape(root)) == []


def test_a_new_module_moves_the_shape(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n"})
    before = shape.shape(root)
    (root / "b.py").write_text("y = 2\n")
    moved = shape.differences(before, shape.shape(root))
    assert any("new module: b.py" in line for line in moved), moved


def test_a_new_entry_point_is_called_out_as_one(tmp_path) -> None:
    """The finding this tool most wants to catch: a second way in."""
    root = project(tmp_path, {"a.py": "x = 1\n"})
    before = shape.shape(root)
    (root / "run.py").write_text("if __name__ == '__main__':\n    pass\n")
    moved = shape.differences(before, shape.shape(root))
    assert any("entry point" in line for line in moved), moved


def test_a_constant_escaping_into_a_module_is_seen(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n"})
    before = shape.shape(root)
    (root / "a.py").write_text("x = 1\nTIMEOUT = 30\n")
    moved = shape.differences(before, shape.shape(root))
    assert any("TIMEOUT" in line for line in moved), moved


def test_a_removed_module_is_seen(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    before = shape.shape(root)
    (root / "b.py").unlink()
    assert any("module gone" in line
               for line in shape.differences(before, shape.shape(root)))


def test_generated_and_vendored_directories_are_not_the_project(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n",
                              "__pycache__/junk.py": "z = 3\n",
                              "node_modules/dep.py": "w = 4\n"})
    modules = shape.shape(root)["modules"]
    assert set(modules) == {"a.py"}


def test_a_file_that_will_not_parse_does_not_stop_the_sweep(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n", "broken.py": "def (:\n"})
    modules = shape.shape(root)["modules"]
    assert "broken.py" in modules and modules["broken.py"]["names"] == []


def test_the_first_run_has_nothing_to_compare_against(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n"})
    assert shape.differences({}, shape.shape(root))


def test_the_fingerprint_survives_a_restart(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n"})
    state = tmp_path / "state" / "shape.json"
    fingerprint = shape.shape(root)
    shape.save(state, fingerprint)
    assert shape.digest(shape.load(state)) == shape.digest(fingerprint)


def test_a_corrupt_fingerprint_is_treated_as_absent(tmp_path) -> None:
    state = tmp_path / "shape.json"
    state.write_text("{not json")
    assert shape.load(state) == {}


def test_what_moved_is_said_not_merely_counted(tmp_path) -> None:
    """"The shape changed" is not actionable. "Three new entry points
    appeared" is."""
    root = project(tmp_path, {"a.py": "x = 1\n"})
    before = shape.shape(root)
    (root / "b.py").write_text("def helper():\n    pass\n")
    moved = shape.differences(before, shape.shape(root))
    assert all(isinstance(line, str) and line for line in moved)


# ------------------------------------------------------------------------- C

C_MODULE = """\
/* FUN_00401230 @ 0x00401230  segment text */

#include <stdio.h>

typedef unsigned int undefined4;

struct Person {
    byte Type;
};

static int g_line_count = 0;

undefined4 * __cdecl Module_Map__GetCell(short x,short y)

{
  int local_4;
  if (x < 0) {
    return 0;
  }
  for (local_4 = 0; local_4 < 8; local_4 = local_4 + 1) {
    g_line_count = g_line_count + 1;
  }
  return 0;
}
"""


def test_c_modules_contribute_their_top_level_names(tmp_path) -> None:
    root = project(tmp_path, {"src/map.c": C_MODULE})
    names = shape.shape(root)["modules"]["src/map.c"]["names"]
    assert "Module_Map__GetCell" in names
    assert "Person" in names
    assert "undefined4" in names
    assert "g_line_count" in names


def test_a_c_body_is_as_invisible_as_a_python_one(tmp_path) -> None:
    root = project(tmp_path, {"src/map.c": C_MODULE})
    before = shape.shape(root)
    (root / "src/map.c").write_text(C_MODULE.replace(
        "    g_line_count = g_line_count + 1;",
        "    g_line_count = g_line_count + 2;\n    printf(\"%d\", g_line_count);"))
    assert shape.differences(before, shape.shape(root)) == []


def test_control_flow_at_column_zero_is_not_mistaken_for_a_name(tmp_path) -> None:
    root = project(tmp_path, {"src/odd.c": "int f(void)\n{\nreturn 1;\n}\n"})
    assert shape.shape(root)["modules"]["src/odd.c"]["names"] == ["f"]


def test_a_c_main_is_an_entry_point(tmp_path) -> None:
    root = project(tmp_path, {
        "src/main.c": "int main(int argc, char **argv)\n{\n  return 0;\n}\n",
        "src/lib.c": "int helper(void)\n{\n  return 0;\n}\n",
    })
    modules = shape.shape(root)["modules"]
    assert modules["src/main.c"]["entry"] is True
    assert modules["src/lib.c"]["entry"] is False


def test_the_python_only_walk_is_still_available(tmp_path) -> None:
    root = project(tmp_path, {"a.py": "x = 1\n", "src/map.c": C_MODULE})
    assert list(shape.shape(root, suffixes=(".py",))["modules"]) == ["a.py"]
    assert set(shape.shape(root)["modules"]) == {"a.py", "src/map.c"}


# --- 2026-09-17: drift said "unchanged" while the report changed ------------

import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

CLI = [sys.executable, str(Path(__file__).resolve().parent.parent
                           / "bin" / "ziggurat.py")]


def _drift(root, state, *extra):
    return subprocess.run([*CLI, "drift", str(root), "--state", str(state),
                           *extra], capture_output=True, text=True,
                          check=True).stdout


@pytest.mark.xfail(strict=True, reason="#18")
def test_drift_reruns_when_a_body_edit_creates_a_finding(tmp_path) -> None:
    """The fingerprint's premise was that no finding can be created by
    editing inside a function. Five of the six structural checks read
    function bodies. Adding `return Path("records/a3.jsonl")` to an existing
    function took the report from nothing to a finding, and drift said
    `shape unchanged`."""
    root = tmp_path / "proj"
    files = {f"m{i}.py": f'def f():\n    return Path("records/a{i}.jsonl")\n'
             for i in range(3)}
    files["m3.py"] = "def f():\n    return None\n"
    project(root, files)
    state = tmp_path / "state.json"
    _drift(root, state)
    (root / "m3.py").write_text('def f():\n    return Path("records/a3.jsonl")\n')
    out = _drift(root, state)
    assert "shape unchanged" not in out, out
    assert "records/" in out, out


@pytest.mark.xfail(strict=True, reason="#18")
def test_drift_sees_a_new_shell_script(tmp_path) -> None:
    """The report reads shell, JS, TS, Go and more; the fingerprint read
    only Python and C, so a new `scripts/deploy.sh` moved nothing."""
    root = tmp_path / "proj"
    project(root, {"a.py": "x = 1\n"})
    state = tmp_path / "state.json"
    _drift(root, state)
    (root / "scripts").mkdir()
    (root / "scripts" / "deploy.sh").write_text("#!/bin/sh\necho hi\n")
    out = _drift(root, state)
    assert "shape unchanged" not in out, out


def test_drift_is_still_silent_when_nothing_changed(tmp_path) -> None:
    root = tmp_path / "proj"
    project(root, {"a.py": "def one():\n    return 1\n"})
    state = tmp_path / "state.json"
    _drift(root, state)
    assert "shape unchanged" in _drift(root, state)


def test_a_comment_edit_is_not_worth_a_report(tmp_path) -> None:
    root = tmp_path / "proj"
    project(root, {"a.py": "def one():\n    return 1\n"})
    state = tmp_path / "state.json"
    _drift(root, state)
    (root / "a.py").write_text("def one():\n    # the only one\n    return 1\n")
    assert "shape unchanged" in _drift(root, state)


@pytest.mark.xfail(strict=True, reason="#18")
def test_the_names_only_fingerprint_is_still_available(tmp_path) -> None:
    """The cheaper, blinder gate is kept for whoever hooked it for its
    price -- asked for by name, and documented for what it cannot see."""
    root = tmp_path / "proj"
    project(root, {"a.py": "def one():\n    return 1\n"})
    state = tmp_path / "state.json"
    _drift(root, state, "--names-only")
    (root / "a.py").write_text("def one():\n    return 2\n")
    assert "shape unchanged" in _drift(root, state, "--names-only")


@pytest.mark.xfail(strict=True, reason="#12")
def test_an_ancestor_named_build_does_not_empty_the_shape(tmp_path) -> None:
    root = project(tmp_path / "build" / "proj", {"a.py": "x = 1\n"})
    assert shape.shape(root)["modules"], "the whole project was skipped"
