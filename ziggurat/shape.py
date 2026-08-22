"""A cheap fingerprint of a project's SHAPE, so the report can stay expensive.

Running a full architecture report on every action is too costly to live with,
and running it never is how a project drifts. The way out is that the two
questions have very different prices: deciding WHETHER the architecture could
have changed is nearly free, and only the answer "yes" is worth paying for.

Every finding this tool produces is structural -- entry points, dynamic
loading, constants scattered across modules, files that change together. Not
one of them can be created by editing inside an existing function. They appear
when the SHAPE moves: a module is added, a script becomes a second way in, a
constant escapes into a new file.

So the fingerprint covers exactly that and deliberately nothing else:

    which modules exist
    which of them look like entry points
    the top-level names each one defines

It does not hash file contents. A body rewritten inside its own function is
invisible here, and should be -- that is the whole saving. Two projects with
identical shapes and completely different implementations fingerprint the same,
which sounds like a flaw and is the point.

WHAT THIS CANNOT SEE. Change coupling is history, not shape: two files can
start changing together without either being touched structurally. A shape
gate will not notice that, so it is not a substitute for running the full
report periodically -- it is a way to catch the structural half immediately and
leave the historical half to a slower rhythm.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

#: Directories that are never part of a project's own shape.
SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
        ".pytest_cache", "build", "dist", ".ruff_cache"}


def _top_level_names(path: Path) -> list:
    """Names a module defines at the top level. Bodies are not looked at."""
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except (SyntaxError, OSError, ValueError):
        return []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return sorted(set(names))


def _is_entry_point(path: Path, source: str) -> bool:
    return "__main__" in source or path.parent.name in {"bin", "scripts"}


def shape(root) -> dict:
    """The structural fingerprint of a project."""
    root = Path(root)
    modules = {}
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP for part in path.parts):
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        relative = str(path.relative_to(root))
        modules[relative] = {
            "names": _top_level_names(path),
            "entry": _is_entry_point(path, source),
        }
    return {"modules": modules}


def digest(fingerprint: dict) -> str:
    return hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()[:16]


def differences(before: dict, after: dict) -> list:
    """What moved, in words. Empty means the shape is unchanged.

    Reported rather than merely counted, because "the shape changed" is not
    actionable and "three new entry points appeared" is.
    """
    old = (before or {}).get("modules", {})
    new = (after or {}).get("modules", {})
    moved = []

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    for name in added:
        moved.append(f"new module: {name}"
                     + ("  (and it is an entry point)" if new[name]["entry"] else ""))
    for name in removed:
        moved.append(f"module gone: {name}")

    for name in sorted(set(old) & set(new)):
        was, now = old[name], new[name]
        if was["entry"] != now["entry"]:
            moved.append(f"{name} " + ("became" if now["entry"] else "stopped being")
                         + " an entry point")
        gained = sorted(set(now["names"]) - set(was["names"]))
        lost = sorted(set(was["names"]) - set(now["names"]))
        if gained:
            moved.append(f"{name} defines new top-level names: {', '.join(gained[:6])}"
                         + (" ..." if len(gained) > 6 else ""))
        if lost:
            moved.append(f"{name} no longer defines: {', '.join(lost[:6])}"
                         + (" ..." if len(lost) > 6 else ""))
    return moved


def load(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save(path, fingerprint: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(fingerprint, sort_keys=True, indent=1))
    tmp.replace(path)
