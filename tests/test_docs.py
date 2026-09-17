"""What the documentation says the tool does, checked against what it does.

Prose about this tool has gone stale three times, each time the same way: a
check was added and the list describing the checks was not. A measurement in
a sentence is stale by the next commit; so is a list. This makes the list a
test, so the next check cannot ship without it.
"""

import ast
import configparser
import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
PACKAGE = HERE / "ziggurat"


def _checks(module: str) -> set:
    """Every check name a module can report, read from its Finding calls."""
    tree = ast.parse((PACKAGE / f"{module}.py").read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Finding":
            for kw in node.keywords:
                if kw.arg == "check" and isinstance(kw.value, ast.Constant):
                    names.add(kw.value.value)
    return names


def _normal(text: str) -> str:
    return re.sub(r"[-_\s]+", " ", text.lower())


@pytest.mark.xfail(strict=True, reason="#24")
def test_the_readme_names_every_check() -> None:
    readme = _normal((HERE / "README.md").read_text())
    missing = sorted(c for c in _checks("structure") | _checks("history")
                     if _normal(c) not in readme)
    assert not missing, f"README does not describe: {missing}"


@pytest.mark.xfail(strict=True, reason="#24")
def test_the_structure_docstring_names_every_structure_check() -> None:
    doc = _normal(ast.get_docstring(ast.parse(
        (PACKAGE / "structure.py").read_text())) or "")
    missing = sorted(c for c in _checks("structure") if _normal(c) not in doc)
    assert not missing, f"structure.py's docstring does not describe: {missing}"


@pytest.mark.xfail(strict=True, reason="#24")
def test_every_module_is_under_the_import_contract() -> None:
    """A module the layers contract does not name is a module it does not
    check. `shape` was imported by the CLI and outside the contract."""
    cfg = configparser.ConfigParser()
    cfg.read(HERE / ".importlinter")
    named = " ".join(section.get("layers", "") + " " + section.get("modules", "")
                     for section in cfg.values())
    modules = {f"ziggurat.{p.stem}" for p in PACKAGE.glob("*.py")
               if p.stem != "__init__"}
    missing = sorted(m for m in modules if m not in named)
    assert not missing, f".importlinter does not place: {missing}"
