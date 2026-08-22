"""Tier 1: what the shape of the tree says, without running anything.

Every check here is a STRUCTURAL FACT -- a file exists, a string appears in N
files, a call is present. Nothing here is a threshold on a quality metric,
because a measure that becomes a target stops being a measure, and because a
gate you can argue with is a gate people learn to ignore.

The three checks are not a general theory of architecture. Each one is a
failure that actually happened in a real project, chosen because imports could
not see it:

    entry-point sprawl   24 scripts in bin/, none importing another
    dynamic loading      scripts loading scripts by file path
    scattered constants  one address written into a dozen files
"""

from __future__ import annotations

import re
from pathlib import Path

from ziggurat.findings import Confidence, Finding, Report

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", "target", "site-packages", ".mypy_cache", ".pytest_cache",
             ".tox", "vendor", ".idea", ".spi"}

SOURCE_SUFFIXES = {".py", ".sh", ".js", ".ts", ".rb", ".go", ".java", ".kt"}

ENTRY_DIRS = ("bin", "scripts", "cmd", "tools")

#: Below this, a set of entry points is a tool with commands rather than a pile
#: of one-offs. Saying otherwise would be the noise that gets checkers disabled.
SPRAWL_AT = 8

#: A literal in fewer files than this is a coincidence. A dozen is a decision
#: nobody made.
SCATTER_AT = 4

#: Matched WITH the opening parenthesis, so that naming a technique is not
#: mistaken for using it. Ziggurat accused its own source of dynamic loading
#: because this very tuple contains the string it searches for -- a detector
#: that cannot tell a mention from a use will accuse anything that discusses
#: the subject, starting with itself.
DYNAMIC_PATTERNS = (
    ("spec_from_file_location(", "python: loads a module from a file path"),
    ("SourceFileLoader(", "python: loads a module from a file path"),
    ("__import__(", "python: import by computed name"),
    ("require(path.", "node: require by computed path"),
)

#: Routable addresses only. Loopback is a statement about this machine, not
#: about a deployment, and 0.0.0.0 means "every interface" rather than a host.
ADDRESS = re.compile(r"\b(?!127\.|0\.0\.0\.0)(?:\d{1,3}\.){3}\d{1,3}\b")

#: A quoted thing with a slash in it. Paths are a far commoner scattered
#: constant than addresses, and this checker could not see one: pointed at a
#: project whose whole data directory was written into seventeen separate
#: modules, it reported nothing, because `ADDRESS` matches dotted quads and a
#: path is not a dotted quad.
PATH_LITERAL = re.compile(r"""['"]([A-Za-z0-9_\-./]*?/[A-Za-z0-9_\-.]+)['"]""")

#: Heads that are not directories however much they look like one. `text/html`
#: is a media type, and the first run of this check duly accused four files of
#: scattering `application/` -- which was `"application/json"`, correctly
#: written in all four.
NOT_DIRECTORIES = ("application", "text", "audio", "image", "video",
                   "multipart", "http:", "https:")


#: Files whose job is to hold configuration. A value appearing HERE is the
#: value being where it belongs, and counting it as a violation would tell you
#: to remove it from the one correct place.
CONFIG_STEMS = {"config", "settings", "constants", "conf", "defaults", "env"}


def _is_config(path: Path) -> bool:
    return path.stem.lower() in CONFIG_STEMS


def _code_only(path: Path, text: str, strip_strings: bool = False) -> str:
    """The text with comments and docstrings removed.

    A usage example in a docstring is DOCUMENTATION. It can go stale, which is
    a different and much smaller problem than a coupling, and reporting it as
    one is the noise that gets a checker switched off.

    Only BARE string expressions are dropped. A string assigned to a name is
    the coupling itself, not a description of one.

    `strip_strings` empties string CONTENTS as well, for the checks where a
    match inside a quote means nothing. A call is not a string literal: naming
    `spec_from_file_location(` in a list of patterns is discussing the
    technique, not using it -- and without this the detector accuses its own
    source, which it duly did.
    """
    if path.suffix != ".py":
        # Line comments for everything else; good enough, and it fails toward
        # reporting rather than toward silence.
        kept = []
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            kept.append(line)
        return "\n".join(kept)

    import ast
    import io
    import tokenize

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text

    drop = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            for line in range(first.lineno, (first.end_lineno or first.lineno) + 1):
                drop.add(line)

    blanks = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                for line in range(token.start[0], token.end[0] + 1):
                    drop.add(line)
            elif strip_strings and token.type == tokenize.STRING:
                blanks.append(token)
    except (tokenize.TokenError, IndentationError):
        pass

    lines = text.splitlines()
    for token in blanks:
        # Single-line strings become empty quotes; multi-line ones are dropped
        # wholesale. Either way the CALL structure around them survives.
        if token.start[0] == token.end[0]:
            row = token.start[0] - 1
            if 0 <= row < len(lines):
                line = lines[row]
                lines[row] = line[: token.start[1]] + '""' + line[token.end[1]:]
        else:
            for line_no in range(token.start[0], token.end[0] + 1):
                drop.add(line_no)

    return "\n".join(line for n, line in enumerate(lines, 1) if n not in drop)


def _is_test(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & {"tests", "test", "spec"}:
        return True
    name = path.name
    return name.startswith("test_") or "_test." in name or ".test." in name


def _sources(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if set(path.parts) & SKIP_DIRS:
            continue
        yield path


def analyse(root) -> Report:
    root = Path(root).resolve()
    report = Report(project=root.name)
    if not root.is_dir():
        return report.skip("structure", f"{root} is not a directory")

    files = list(_sources(root))
    _entry_points(root, files, report)
    _dynamic_loading(files, root, report)
    _scattered_constants(files, root, report)
    _scattered_paths(files, root, report)
    return report


def _is_shim(path: Path) -> bool:
    """Does this entry point delegate, rather than implement?

    The check's rationale is that separate entry points each re-decide
    configuration, argument handling and discovery. A file that defines nothing
    and imports its behaviour re-decides none of that -- it is an alias for a
    command, and counting it means counting FILES while claiming to count
    independent implementations.

    Structural, so it cannot be gamed by intent: a single `def` or `class` and
    it is implementing something again, which is exactly when it stops being a
    shim.
    """
    if path.suffix != ".py":
        return False
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return False
    import ast
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False
    # It must actually delegate somewhere, or it is not a shim, just short.
    return any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def _entry_points(root: Path, files: list, report: Report) -> None:
    entries = [f for f in files
               if any(part in ENTRY_DIRS for part in f.parts)
               and not _is_test(f) and not _is_shim(f)]
    if len(entries) < SPRAWL_AT:
        return
    report.add(Finding(
        check="entry-point-sprawl",
        summary=f"{len(entries)} separate entry points",
        evidence=(f"{len(entries)} executables across "
                  f"{sorted({p.parent.name for p in entries})}. Entry points do "
                  "not import each other, so no import analysis can see this; "
                  "it shows up only as a count."),
        confidence=Confidence.STRUCTURAL,
        paths=tuple(sorted(str(p.relative_to(root)) for p in entries)),
        suggestion=("check whether these are commands of one tool rather than "
                    "separate tools. Subcommands share config, argument "
                    "handling and discovery; parallel scripts share nothing "
                    "and each one re-decides everything."),
    ))


def _dynamic_loading(files: list, root: Path, report: Report) -> None:
    hits = []
    for path in files:
        if _is_test(path):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        code = _code_only(path, text, strip_strings=True)
        for needle, why in DYNAMIC_PATTERNS:
            if needle in code:
                hits.append((str(path.relative_to(root)), why))
                break
    if not hits:
        return
    report.add(Finding(
        check="dynamic-loading",
        summary=f"{len(hits)} file(s) load code by path rather than importing it",
        evidence=("; ".join(f"{p} ({why})" for p, why in hits[:6])
                  + ". This is a real dependency that every import analyser is "
                  "blind to, so the module graph understates the coupling."),
        confidence=Confidence.STRUCTURAL,
        paths=tuple(p for p, _ in hits),
        suggestion=("if the loaded file is worth importing, it belongs in the "
                    "package where it can be imported normally."),
    ))


def _is_path(literal: str) -> bool:
    """Is this quoted thing a path at all?

    Rejected at COLLECTION rather than at reporting, because the first version
    guarded only the directory branch and let `application/json` through the
    literal one -- so the check that was written to avoid accusing four files
    of scattering a media type accused four files of scattering a media type.
    A rule applied on one path out of two is not applied.
    """
    head = literal.split("/")[0].lower()
    if head in NOT_DIRECTORIES:
        return False
    # A URL is an address, not a path in this tree.
    return not (head.endswith(":") or "://" in literal)


def _path_head(literal: str) -> str:
    """The directory a literal hangs off, or "" if it does not hang off one.

    `records/eye.jsonl` and `records/ear.jsonl` are two literals and ONE idea.
    Counting them separately reports two small problems and misses the large
    one, which is that the directory itself is named in seventeen places.
    """
    head = literal.split("/")[0]
    if not head or head.startswith(".") or "." in head:
        return ""
    if head.lower() in NOT_DIRECTORIES:
        return ""
    return head


def _scattered_paths(files: list, root: Path, report: Report) -> None:
    """Paths written into many files, by literal and by directory.

    Reported as two shapes because they are two faults:

      the same literal in many files      one FILE with many namers
      the same directory in many files    one IDEA with many namers

    The second is the harder one and the one a literal-only check cannot see.
    Measured on the project that prompted this: `records/eye.jsonl` appears in
    8 files, which is worth knowing; `records/` appears in 17 across 33
    distinct paths, which is why the directory could not be moved at all.
    """
    by_literal: dict = {}
    by_head: dict = {}
    names_under: dict = {}

    for path in files:
        if _is_test(path) or _is_config(path):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        where = str(path.relative_to(root))
        for literal in set(PATH_LITERAL.findall(_code_only(path, text))):
            if not _is_path(literal):
                continue
            by_literal.setdefault(literal, set()).add(where)
            head = _path_head(literal)
            if head:
                by_head.setdefault(head, set()).add(where)
                names_under.setdefault(head, set()).add(literal)

    for head, paths in sorted(by_head.items()):
        if len(paths) < SCATTER_AT:
            continue
        names = names_under.get(head, set())
        # A directory named once per file is the same fault as a literal named
        # once per file; reporting both would say it twice.
        if len(names) < 2:
            continue
        report.add(Finding(
            check="scattered-path",
            summary=(f"{head}/ is written into {len(paths)} files, "
                     f"as {len(names)} different paths"),
            evidence=(f"{head}/ is named in {len(paths)} separate files: "
                      f"{', '.join(sorted(paths)[:5])}"
                      f"{'...' if len(paths) > 5 else ''}. One IDEA with many "
                      "namers -- moving this directory means finding every one "
                      "of them, and a search you might not finish."),
            confidence=Confidence.STRUCTURAL,
            paths=tuple(sorted(paths)),
            suggestion=("give the directory one name in a config module and "
                        "join onto it, so relocating it is a setting rather "
                        "than an edit per module."),
        ))

    for literal, paths in sorted(by_literal.items()):
        if len(paths) < SCATTER_AT:
            continue
        head = _path_head(literal)
        # Already covered, and more usefully, by the directory finding above.
        if head and len(by_head.get(head, ())) >= SCATTER_AT \
                and len(names_under.get(head, ())) >= 2:
            continue
        report.add(Finding(
            check="scattered-path",
            summary=f"{literal} appears in {len(paths)} files",
            evidence=(f"{literal} is written into {len(paths)} separate files: "
                      f"{', '.join(sorted(paths)[:5])}"
                      f"{'...' if len(paths) > 5 else ''}. One file with many "
                      "namers; renaming or moving it costs every one of them."),
            confidence=Confidence.STRUCTURAL,
            paths=tuple(sorted(paths)),
            suggestion=("name it once where it belongs and import it, so the "
                        "next change is one edit."),
        ))


def _scattered_constants(files: list, root: Path, report: Report) -> None:
    where: dict = {}
    for path in files:
        if _is_test(path) or _is_config(path):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for address in set(ADDRESS.findall(_code_only(path, text))):
            # A dotted quad in a comment is still a dotted quad; version
            # numbers are not, because they do not have four parts.
            where.setdefault(address, set()).add(str(path.relative_to(root)))

    for address, paths in sorted(where.items()):
        if len(paths) < SCATTER_AT:
            continue
        report.add(Finding(
            check="scattered-constant",
            summary=f"{address} appears in {len(paths)} files",
            evidence=(f"{address} is written into {len(paths)} separate files: "
                      f"{', '.join(sorted(paths)[:5])}"
                      f"{'...' if len(paths) > 5 else ''}. One idea should be "
                      "one edit; changing this costs "
                      f"{len(paths)} edits and a search you might not finish."),
            confidence=Confidence.STRUCTURAL,
            paths=tuple(sorted(paths)),
            suggestion=("put it in a config module and read it from there, so "
                        "the next change is one edit."),
        ))
