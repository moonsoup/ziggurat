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
import re
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


#: A C translation unit's shape is read by LINE, not parsed. Shape has never
#: looked inside a body, so a C parser would be a dependency bought for nothing.
#: Everything below is anchored at column zero: in C, and emphatically in
#: decompiler output, a definition starts there and a body never does.
_C_FUNCTION = re.compile(r"^[A-Za-z_][^;=(){}]*?([A-Za-z_]\w*)\s*\(", re.M)
_C_TAGGED_TYPE = re.compile(r"^(?:typedef\s+)?(?:struct|union|enum)\s+([A-Za-z_]\w*)", re.M)
_C_TYPEDEF = re.compile(r"^typedef\s+[^;{}]*?([A-Za-z_]\w*)\s*;", re.M)
_C_GLOBAL = re.compile(
    r"^(?:(?:static|extern|const|volatile|register)\s+)*"
    r"[A-Za-z_][\w \t*]*?([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*(?:=[^;]*)?;", re.M)

#: A keyword caught by one of the patterns above is never a name the file
#: defines. Without this, `return x;` at column zero would contribute `return`.
_C_KEYWORDS = frozenset("""
auto break case char const continue default do double else enum extern float for goto if
inline int long register restrict return short signed sizeof static struct switch typedef
union unsigned void volatile while _Bool _Complex
""".split())


def _c_top_level_names(path: Path) -> list:
    """Names a C translation unit contributes: definitions, prototypes, types, globals."""
    try:
        source = path.read_text(errors="replace")
    except OSError:
        return []
    names = set()
    for pattern in (_C_FUNCTION, _C_TAGGED_TYPE, _C_TYPEDEF, _C_GLOBAL):
        names.update(pattern.findall(source))
    return sorted(names - _C_KEYWORDS)


#: Which reader answers for which suffix. Adding a language is one entry.
NAME_READERS = {".py": _top_level_names, ".c": _c_top_level_names, ".h": _c_top_level_names}

#: Every suffix shape can read, and the default set `shape()` walks.
SHAPE_SUFFIXES = tuple(NAME_READERS)

#: `int main(` at column zero, the C equivalent of a `__main__` guard.
_C_MAIN = re.compile(r"^[A-Za-z_][\w \t*]*\bmain\s*\(", re.M)


def _is_entry_point(path: Path, source: str) -> bool:
    if path.suffix in (".c", ".h"):
        return bool(_C_MAIN.search(source)) or path.parent.name in {"bin", "scripts"}
    return "__main__" in source or path.parent.name in {"bin", "scripts"}


def shape(root, suffixes=None) -> dict:
    """The structural fingerprint of a project.

    `suffixes` pins which files count. The default is every language shape can
    read; passing `(".py",)` reproduces the Python-only walk exactly, so a
    caller that wants the old fingerprint can still ask for it.
    """
    root = Path(root)
    wanted = tuple(suffixes) if suffixes else SHAPE_SUFFIXES
    modules = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in wanted or not path.is_file():
            continue
        if any(part in SKIP for part in path.parts):
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        reader = NAME_READERS.get(path.suffix, _top_level_names)
        relative = str(path.relative_to(root))
        modules[relative] = {
            "names": reader(path),
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
