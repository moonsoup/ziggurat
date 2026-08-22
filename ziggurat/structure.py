"""Tier 1: what the shape of the tree says, without running anything.

Every check here is a STRUCTURAL FACT -- a file exists, a string appears in N
files, a call is present. Nothing here is a threshold on a quality metric,
because a measure that becomes a target stops being a measure, and because a
gate you can argue with is a gate people learn to ignore.

These checks are not a general theory of architecture. Each one is a failure
that actually happened in a real project, chosen because imports could not see
it:

    entry-point sprawl   24 scripts in bin/, none importing another
    dynamic loading      scripts loading scripts by file path
    scattered constants  one address written into a dozen files
    scattered paths      one data directory named in every module that touched
                         it, so it could not be relocated at all

Neither count is written out, and the reason is worth the space. The number of
checks said "three" for a while after there were four. The number of modules
was written as "twenty-one", then corrected to "22", and a later verification
measured 21 -- because every change to what the checker can SEE changes what
it counts, so any number written in prose is stale by the next commit. Three
commits in a row shipped a comment that disagreed with its own code this way.
A measurement belongs in the output of a run, never in a sentence about it.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

from ziggurat.findings import Confidence, Finding, Report

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", "target", "site-packages", ".mypy_cache", ".pytest_cache",
             ".tox", "vendor", ".idea", ".spi",
             # Framework build output. `.next` held a project's entire
             # bundled `node_modules_*.js`, from which this reported
             # `/robots.txt` across twelve files and `/sitemap.xml` across
             # twelve more -- none of them anybody's source.
             ".next", ".nuxt", ".svelte-kit", ".turbo", ".parcel-cache",
             ".cache", "coverage", ".gradle", ".terraform",
             # A git worktree is a full second copy of the repo. Counting it
             # doubled every file, which put ALL SEVEN of one project's
             # scattered-path findings over the threshold -- their real counts
             # were 2, 2, 2, 3, 3, 3 and 5, every one below the bar. Recorded
             # as "six of seven" for a while, copied from the issue rather
             # than re-measured.
             }

#: Worktrees, excluded by PATH rather than by name. A bare `worktrees` in
#: SKIP_DIRS silences any project that ships a package called that, since
#: SKIP_DIRS matches a single path component wherever it appears. Leaving it
#: to gitignore is not enough either: it works where a project ignores
#: `.claude/` and fails silently where it does not. The pattern is the thing
#: actually meant.
SKIP_PATHS = ((".claude", "worktrees"),)

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

#: A quote-adjacent run containing a slash. Used ONLY for languages this cannot
#: parse; Python goes through the AST, which knows the difference between a
#: string that looks like a path and a string being USED as one.
#:
#: Its predecessor's docstring said "a quoted thing with a slash in it", which
#: was aspirational: `"records/{name}.jsonl"` is a quoted thing with a slash in
#: it and never matched, and every false negative followed from the gap between
#: that sentence and this pattern.
PATH_LITERAL = re.compile(r"""['"]([A-Za-z0-9_\-./]*?/[A-Za-z0-9_\-.]+)['"]""")

#: Calls whose string arguments are paths. This is the whole discriminator, and
#: it replaces asking whether a STRING looks like a path with asking whether it
#: is being USED as one -- which is the only question that separates
#: `Path("records/x")` from `import "os/exec"`, `"Qwen/gemma-2"` and `/game/state`.
#:
#: Pointed at Go and TypeScript projects, the shape-based version reported
#: import specifiers and HuggingFace model IDs: `Qwen/` "written into 32 files",
#: with the advice that relocating it should be a setting.
PATH_CALLS = frozenset({
    # `joinpath` was in JOINING and NOT here, and the guard requires both, so
    # `p.joinpath("records")` was collected by nothing while the comment on
    # JOINING advertised it as an example. A project that joins with
    # .joinpath() rather than / was entirely invisible.
    "Path", "PurePath", "PosixPath", "PurePosixPath", "PureWindowsPath",
    "WindowsPath", "joinpath", "open", "join", "abspath", "realpath",
    "dirname", "basename", "relpath", "expanduser", "mkdir", "makedirs",
    "read_text", "write_text", "read_bytes", "write_bytes", "unlink",
    "rmtree", "copy", "copytree", "move", "glob", "iglob", "rglob", "stat",
    "exists", "isfile", "isdir", "listdir", "walk", "touch", "replace",
})

#: Suffixes that make a literal recognisable as a FILE in a language this
#: cannot parse. Python goes through the AST and needs none of this; for shell,
#: Go and TypeScript the only honest options were to report shape -- which
#: produced thirty HuggingFace model IDs from one project's install scripts --
#: or to report what can actually be recognised. This is the second.
DATA_SUFFIXES = (
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".csv", ".tsv", ".txt", ".log", ".db", ".sqlite", ".sql", ".xml",
    ".html", ".css", ".md", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf",
    ".wav", ".mp3", ".mp4", ".aac", ".m4a", ".zip", ".tar", ".gz", ".apk",
    ".secret", ".pem", ".key", ".crt", ".lock", ".pid", ".sh", ".py",
)

#: Navigation, not a name. Every Python project in existence joins on `..`,
#: and a directory called `.` is nobody's directory.
NAVIGATION = frozenset({".", "..", "./", "../", "/"})

#: Path calls whose ARGUMENTS are themselves paths even when called as a
#: method -- os.path.join(a, b), p.joinpath(c). Everything else called on an
#: object takes options, not paths.
JOINING = frozenset({"join", "joinpath"})

#: Dictionary lookups that wear a method's clothes. `d["data"]` is plainly a
#: lookup and was excluded; `d.get("data")` is a call argument and was not,
#: which inflated two projects' counts by one file each while the subscript
#: beside it was correctly ignored.
LOOKUPS = frozenset({"get", "pop", "setdefault", "getattr", "getenv"})

#: Argparse destinations whose default is a path. An argparse default is the
#: namer nobody finds when relocating, because it reads as configuration.
#:
#: Split by how much the WORD alone proves. `--path`, `--dir`, `--outdir` are
#: about paths and essentially nothing else, so the name carries it. `out`,
#: `to`, `from`, `log`, `dest`, `output` are ordinary option words: matching
#: on those alone reported `--log-level`'s default as the directory `INFO/`,
#: `--output-format`'s as `json/`, `--to`'s as an email address, and
#: `--dest-state`'s as `pending/`. Those need the VALUE to corroborate.
#:
#: A strong word must also be the option's LAST word, because the trailing
#: noun is what the value is OF. `--outdir` and `--out-dir` name a directory;
#: `--filename-case` names a case and its default is `lower`, which this
#: reported as a directory scattered across five files.
STRONG_PATH_OPTIONS = ("path", "dir", "dirs", "directory", "outdir", "folder",
                       "filename", "filepath", "pathname", "workdir")

#: `records` used to sit in this list -- the directory name of the single tree
#: this check was first tuned against, baked into a general-purpose checker.
#: That is a tool memorising its test set, and it is removed.
WEAK_PATH_OPTIONS = ("out", "output", "into", "to", "from", "file", "root",
                     "store", "log", "dest", "target", "source")

#: The union, kept under its original name because something outside this
#: module may import it.
PATH_OPTIONS = STRONG_PATH_OPTIONS + WEAK_PATH_OPTIONS

#: Heads that are not directories however much they look like one. `text/html`
#: is a media type, and the first run of this check duly accused four files of
#: scattering `application/` -- which was `"application/json"`, correctly
#: written in all four.
#: `http:` and `https:` are NOT here: `_is_path` rejects a scheme by its
#: trailing colon. Listing them here would be a THIRD rule: `take()` already
#: rejects `http://` at collection and `_is_path` rejects it again, so the
#: guard is duplicated as it stands. Said the other way round for a while,
#: which was wrong about its own code.
NOT_DIRECTORIES = ("application", "text", "audio", "image", "video",
                   "multipart", "font", "message", "model", "example")


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

    Only LEADING docstrings are dropped -- a module's, a class's, a
    function's. Said "bare string expressions" for a while, which claims more
    than it does: a bare string anywhere else survives. A string assigned to a
    name survives too, and should: it is the coupling itself, not a
    description of one.

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


def _ignored(root: Path) -> set | None:
    """What git says does NOT belong to this project, or None if it cannot say.

    ASK WHAT IS IGNORED, NOT WHAT IS TRACKED. The first version of this asked
    `git ls-files` and scanned only what came back, which is a different
    question with a much worse answer: it makes UNCOMMITTED SOURCE INVISIBLE.

    Measured across 42 projects: 130 files vanished, 88 of them ordinary
    source somebody had written and not yet committed. One project's finding
    -- a hardcoded VPS address in four files -- was cut to two, because two of
    the four were uncommitted. A checker that reports half a number is worse
    than one that reports nothing, and this tool's own README says the number
    IS the measurement. Newly written code is also the code most worth
    checking; a checker blind to it is blind exactly where it is needed.

    Ignored files are what the walk should skip: build output, `.next`
    bundles, vendored copies. That set answers the question `SKIP_DIRS` was
    guessing at, without guessing.

    Returns None when git cannot answer, when the directory is not a
    repository, or when it belongs to an enclosing repository rather than
    having one of its own -- that last case matters: a project sitting inside
    a parent checkout would otherwise be judged by the parent's index and get
    partial visibility with nothing to signal it.
    """
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, timeout=30, check=False)
        if top.returncode != 0:
            return None
        where = top.stdout.decode("utf-8", "replace").strip()
        if not where or Path(where).resolve() != root.resolve():
            # A subdirectory of some other repository. Its index describes a
            # tree this is only part of, so it cannot say what belongs here.
            return None
        done = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--others", "--ignored",
             "--exclude-standard", "--directory"],
            capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    names = [n for n in done.stdout.decode("utf-8", "replace").split("\0") if n]
    return {(root / n).resolve() for n in names}


def _sources(root: Path):
    ignored = _ignored(root) or set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if set(path.parts) & SKIP_DIRS:
            continue
        parts = path.parts
        if any(any(parts[i:i + len(run)] == run
                   for i in range(len(parts) - len(run) + 1))
               for run in SKIP_PATHS):
            continue
        # Ignored itself, or inside an ignored directory. `--directory`
        # collapses a whole ignored tree to one entry, so the parents are
        # checked rather than the leaf.
        here = path.resolve()
        if here in ignored or any(p in ignored for p in here.parents):
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


#: Lines that declare a dependency rather than name a file. Go's `os/exec`,
#: TypeScript's `./client` and Java's `com.x.y` are namespaces, and reporting
#: them as scattered paths made the check useless on every non-Python project
#: it was pointed at -- which was all of them, because it had only ever been
#: run on Python.
IMPORT_LINE = re.compile(
    r"""^\s*(?:import\b|from\b|export\s+[\w*{}\s,]+\s+from\b"""
    r"""|(?:const|let|var)\s+[\w{}\s,]+=\s*require\()""")


def _without_imports(text: str) -> str:
    """The text with dependency declarations removed.

    Whole lines, and a Go import block as a unit -- `import (` opens a
    parenthesised list of bare specifiers with no keyword of their own, so a
    line-by-line rule sees `"os/exec"` sitting alone and calls it a path.
    """
    kept, in_block = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if in_block:
            if stripped.startswith(")"):
                in_block = False
            kept.append("")
            continue
        if re.match(r"^\s*import\s*\($", line):
            in_block = True
            kept.append("")
            continue
        kept.append("" if IMPORT_LINE.match(line) else line)
    return "\n".join(kept)


def _literal_of(node) -> str:
    """The constant text of a node, with expressions left as a placeholder.

    An f-string is a path too: `f"records/{service}.log"` names the directory
    exactly as firmly as a plain string, and the braces are why a
    character-class regex walked past it.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                out.append(part.value)
            else:
                out.append("*")
        return "".join(out)
    return ""


def _call_name(node) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _python_path_strings(text: str) -> set:
    """Strings this module USES as paths, by reading the syntax.

    Asking whether a string is used as a path, rather than whether it looks
    like one, is what lets the same check see `default="records"` and ignore
    `"Qwen/gemma-2-9b-it"`. Both are quoted, both contain no surprises; only
    one of them is handed to a filesystem.

    Covers, in order of how easily each was missed before:

        Path("records/x")           a path call
        root / "records" / name     a division whose operand is a path
        f"records/{service}.log"    an f-string
        default="records"           an argparse default on a path-ish option
        shoot(bod, cam, "records")  positional, when the callee is path-ish

    Returns "" on a syntax error rather than raising: a file that will not
    parse is a file this cannot judge, and refusing to scan the rest of the
    project over one of them would be the wrong trade.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set()

    found: set = set()

    def take(node) -> None:
        literal = _literal_of(node)
        if literal and not literal.startswith(("http://", "https://")):
            found.add(literal)

    for node in ast.walk(tree):
        # Path("x"), open("x"), os.path.join("x", y), p.mkdir(...)
        if isinstance(node, ast.Call):
            name = _call_name(node)
            attribute = isinstance(node.func, ast.Attribute)
            if name in PATH_CALLS and (not attribute or name in JOINING):
                # On a METHOD the path is the object and the arguments are
                # options: `target.open("a")` passes a file MODE, and taking it
                # as a path reported the letter "a" as a scattered directory in
                # six files. Only joining methods take paths as arguments.
                args = node.args[:1] if name == "open" and not attribute \
                    else node.args
                for arg in args:
                    take(arg)
            # add_argument("--out", default="records")
            if name == "add_argument":
                # WHOLE WORDS. Substring matching reported the profile name
                # "balanced" as a scattered directory, because `--profile`
                # contains "file".
                words = set()
                for a in node.args:
                    words.update(re.split(r"[-_]+",
                                          _literal_of(a).lstrip("-").lower()))
                last = ""
                for a in node.args:
                    spelt = _literal_of(a).lstrip("-").lower()
                    if spelt:
                        last = re.split(r"[-_]+", spelt)[-1]
                strong = last in STRONG_PATH_OPTIONS
                weak = bool(words & set(WEAK_PATH_OPTIONS))
                if strong or weak:
                    for kw in node.keywords:
                        if kw.arg not in ("default", "const"):
                            continue
                        # A strong word (`--outdir`) proves it by itself. A
                        # weak one (`--log-level`, `--to`, `--dest-state`) is
                        # an ordinary option word and needs the value to
                        # agree, or the default `INFO` is reported as a
                        # directory scattered across five files.
                        if strong or _value_looks_like_a_path(
                                _literal_of(kw.value)):
                            take(kw.value)

        # root / "records" / name -- a join is a namer with no slash in it,
        # which is how two of these survived a sweep that fixed eighty.
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            for side in (node.left, node.right):
                take(side)

    # UNAMBIGUOUS FILES, WHEREVER THEY SIT.
    #
    # Everything above asks what a string is HANDED TO, which is the right
    # question for a bare word: nothing about `records` says it is a
    # directory. But `records/eye.jsonl` says so by itself -- a separator and
    # a data suffix is a path in a return, in a list, as a dict value, or
    # anywhere else, and no context is needed to tell.
    #
    # Without this the syntax-reading pass was strictly WORSE than the regex
    # it replaced for these forms. Measured: a real finding lost on a real
    # tree, `docs/` named across four modules from inside a list of candidate
    # files, and one file lost on this tool's own reference tree from
    # `Path(args.restore or f"records/{serial}.sh")`.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant, ast.JoinedStr)):
            literal = _literal_of(node)
            if literal and "/" in literal and _recognisable_file(literal):
                take(node)

    return found


def _value_looks_like_a_path(literal: str) -> bool:
    """Does this VALUE read as a path, independently of what it was called?

    Used to corroborate the weak option words. Deliberately generous about
    what a path looks like and deliberately silent on bare words: `records`
    is a perfectly good path value, but so is `INFO` a perfectly good log
    level, and nothing about either string distinguishes them. Where the
    option name is strong the name decides; where it is weak and the value
    says nothing, the honest answer is to stay quiet.
    """
    if not literal:
        return False
    if "@" in literal or "://" in literal:
        return False
    # A slash is not enough on its own. Verified directly against this
    # function: a date `2026/08/22`, a regex `^\d+/\d+$`, a glob `*.py` and an
    # API route `/v1/messages` all answered True, and a `--from`/`--to` pair
    # of dates duly reported `2026/08/22 appears in 5 files`.
    if any(ch in literal for ch in "*?[]^$|+()"):
        return False
    pieces = [bit for bit in literal.replace("\\", "/").split("/") if bit]
    if pieces and all(bit.isdigit() for bit in pieces):
        return False  # a date, a version, a ratio -- not a directory
    return (literal.startswith(("~", "/", "./", "../"))
            or "/" in literal or "\\" in literal
            or literal.lower().endswith(DATA_SUFFIXES))


def _python_bare_strings(text: str) -> set:
    """Bare strings that could be a directory handed to something.

    The second pass used to be a REGEX over the file's text, matching any
    quoted occurrence of a confirmed head. A regex cannot tell
    `capture.shoot(bod, cam, "records")` -- a directory passed positionally,
    which is the case the pass exists for -- from `cell["genes"]`, which is a
    dict lookup and names no directory at all. So one project's `Path("genes")`
    in four files plus `cell["genes"]` in ten reported `genes` as a scattered
    path in FOURTEEN, and any ordinary word confirmed anywhere was amplified
    the same way.

    The syntax knows the difference, so this asks it. Collected: strings in
    call-argument position, and strings assigned to a name. Excluded, because
    none of them can be a path being named:

        d["genes"]              a subscript -- a lookup, not a path
        {"role": "user"}        a dict KEY
        if x == "pending"       a comparison operand
        raise E("no records")   an exception's message

    COLLECT BROADLY, EXCLUDE PRECISELY -- which is the opposite of the first
    attempt and the reason this was rewritten twice. That version collected
    only call arguments and assignment values, on the theory that a path is
    handed to something. It is not: a path is just as much a path in a list of
    candidate files, in a `return`, in a parameter default or as a dict value.
    Measured, it lost a real finding on a real tree -- `docs/` named in four
    of one project's modules, every one of them inside
    `CONTEXT = ["CLAUDE.md", "docs/product-brief.md"]` -- and the exclusions
    it did carry were dead code, because a dict key was never a candidate to
    begin with.

    So every string in the file is a candidate, minus the positions where a
    string cannot be naming a directory:

        d["genes"]              a subscript -- a lookup
        {"role": "user"}        a dict KEY (values are kept: they can be paths)
        if x == "pending"       a comparison operand
        raise E("no records")   an exception's message
        body.get("data")        a dict lookup wearing a method's clothes

    That last one is why this list is not merely "not a call argument".
    `.get("data")` IS a call argument, and it inflated two projects' counts by
    a file each while `d["data"]` next to it was correctly ignored.

    Nothing here is evidence on its own. It is only ever consulted for heads
    the project has ALREADY proved to be directories.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set()

    skip: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            skip.add(id(node.slice))
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if key is not None:
                    skip.add(id(key))
            # A dict VALUE can be a path -- `{"eye": "records/eye.jsonl"}` is
            # a namer like any other, and dropping the whole dict lost it.
            # A BARE word as a dict value is almost always a label:
            # `{"role": "user"}` reported `user/` across six files. So a value
            # is kept when it carries a separator and dropped when it is only
            # a word -- the same trade the weak option words make, and for the
            # same reason: nothing about the string `user` says which it is.
            for value in node.values:
                literal = _literal_of(value)
                if literal and "/" not in literal and "\\" not in literal:
                    skip.add(id(value))
        elif isinstance(node, ast.Compare):
            for side in [node.left, *node.comparators]:
                skip.add(id(side))
        elif isinstance(node, ast.Raise):
            for child in ast.walk(node):
                skip.add(id(child))
        elif isinstance(node, ast.Call) and node.args:
            name = _call_name(node)
            if (isinstance(node.func, ast.Attribute)
                    and name in LOOKUPS):
                skip.add(id(node.args[0]))

    found: set = set()
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, (ast.Constant, ast.JoinedStr)):
            literal = _literal_of(node)
            if literal:
                found.add(literal)
    return found


def _recognisable_file(literal: str) -> bool:
    """Does this literal look like a FILE, rather than merely have a slash?

    Used only where the syntax cannot be read. `records/eye.jsonl` ends in a
    data suffix; `Qwen/Qwen2.5-Coder-7B-Instruct` and `/genes` do not, and
    nothing about their shape distinguishes them from a directory.
    """
    return literal.lower().endswith(DATA_SUFFIXES)


def _is_path(literal: str) -> bool:
    """Is this quoted thing a path at all?

    Rejected at COLLECTION rather than at reporting, because the first version
    guarded only the directory branch and let `application/json` through the
    literal one -- so the check that was written to avoid accusing four files
    of scattering a media type accused four files of scattering a media type.
    A rule applied on one path out of two is not applied.
    """
    head = literal.replace("\\", "/").split("/")[0].lower()
    if head in NOT_DIRECTORIES:
        return False
    # A URL is an address, not a path in this tree.
    return not (head.endswith(":") or "://" in literal)


def _path_head(literal: str) -> str:
    """The directory a literal hangs off, or "" if it does not hang off one.

    `records/eye.jsonl` and `records/ear.jsonl` are two literals and ONE idea.
    Counting them separately reports two small problems and misses the large
    one, which is that the directory itself is named in seventeen places.

    ABSOLUTE paths were silent entirely, which #3 named and the fix for #3
    missed. Splitting on `/` and taking `[0]` yields `""` for anything
    starting with a slash, so no absolute directory was ever grouped and
    `/var/lib/records/x.json` across five files reported nothing. For those
    the head is the PARENT directory rather than the first segment: the whole
    prefix is the idea being repeated, and `/var` alone would lump
    `/var/log` together with `/var/lib`.

    Backslashes are normalised, so a Windows separator names the same
    directory a forward slash does.
    """
    literal = literal.replace("\\", "/")
    # A GLOB IS NOT A NAME. Collecting unambiguous file literals wherever they
    # sit picked up `*/CLAUDE.md` and reported `*/ is written into 8 files` --
    # eight modules that share a search pattern, not a directory anyone could
    # relocate. `?` and `[` are the other two ways to write one.
    if any(ch in literal.split("/")[0] for ch in "*?["):
        return ""
    # `~` is the home directory, so `~/` as a head is every home-relative path
    # in the project lumped together and no directory at all. Treated like an
    # absolute path -- the parent IS the idea being repeated -- so
    # `~/.claude/settings.json` reports `~/.claude` and not `~`.
    if literal.startswith("~/"):
        parent = literal.rsplit("/", 1)[0]
        return parent if parent != "~" else ""
        # `//cdn.example.com/x.js` is an address, not an absolute path.
        return ""
    if literal.startswith("/"):
        parent = literal.rsplit("/", 1)[0]
        return parent if parent.strip("/") else ""
    head = literal.split("/")[0]
    if not head or "." in head or head in NAVIGATION:
        return ""
    # NOT re-checked against NOT_DIRECTORIES here. `_is_path` has already
    # rejected those, so this branch was unreachable -- a rule applied twice on
    # one route and never on the other, which is the fault #1's own commit
    # message complained about, committed in the fix for it.
    return head


def _scattered_paths(files: list, root: Path, report: Report) -> None:
    """Paths written into many files, by literal and by directory.

    Reported as two shapes because they are two faults:

      the same literal in many files      one FILE with many namers
      the same directory in many files    one IDEA with many namers

    The second is the harder one and the one a literal-only check cannot see.
    Measured on the project that prompted this: `records/eye.jsonl` appears in
    a handful of files, which is worth knowing; `records/` in far more of
    them across many more distinct paths, which is why the directory could not
    be moved at all.

    No figures here on purpose. This docstring has carried three different
    pairs -- 17/33, then 22/40, then a verification measuring 21/37 -- and all
    three were honest measurements of different versions of this code. What
    the check can see changes what it counts, so the count belongs in a run.
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
        if path.suffix == ".py":
            # The syntax knows what a regex cannot: whether a string is being
            # USED as a path or merely shaped like one.
            literals = _python_path_strings(text)
        else:
            # No syntax to read, so only literals recognisable as files. The
            # alternative is reporting shape, which on one project's shell
            # scripts meant thirty model IDs advertised as a directory that
            # ought to be relocated.
            literals = {lit for lit in PATH_LITERAL.findall(
                _code_only(path, _without_imports(text)))
                if _recognisable_file(lit)}
        for literal in literals:
            if literal in NAVIGATION or not _is_path(literal):
                continue
            by_literal.setdefault(literal, set()).add(where)
            head = _path_head(literal)
            if head:
                by_head.setdefault(head, set()).add(where)
                names_under.setdefault(head, set()).add(literal)

    # SECOND PASS: a bare mention of a directory this project has ALREADY
    # proved to be a path.
    #
    # `capture.shoot(bod, cam, "records")` passes a directory positionally to a
    # function whose name means nothing to a checker, so the first pass walks
    # past it -- and those are namers like any other. Rather than guess from
    # the string, this uses the project's own evidence: if `records` is handed
    # to Path() or joined with / somewhere, then a bare "records" elsewhere is
    # the same directory being named again.
    #
    # It cannot manufacture a false positive on a project that never treats the
    # string as a path, which is exactly what went wrong when shape alone
    # decided: nothing confirms `Qwen` or `os/exec`, so nothing looks for them.
    #
    # What the head is confirmed BY matters. Everything in `by_head` arrived
    # through a genuine path context -- a path call, a `/` join, an f-string,
    # a corroborated argparse default -- so counting those is sound. What was
    # not sound was the promotion: it matched any quoted occurrence with a
    # regex, so `cell["genes"]` counted as naming a directory. That is now an
    # AST question, asked by `_python_bare_strings`.
    # PROMOTION NEEDS A SLASH, not a count. The two are different claims and
    # conflating them was issue #5.
    #
    # A head seen with something UNDER it -- `records/eye.jsonl` -- has been
    # demonstrated to be a directory, so a bare "records" elsewhere is that
    # same directory named again, and promoting it is sound.
    #
    # A head confirmed only by appearing in four path calls has been
    # demonstrated to be a PATH, which is not the same thing. `Path("cache")`
    # in four files is a real finding on its own; it does not license
    # counting every other bare "cache" in the tree. It did: four
    # `Path("cache")` plus six `print("cache")` were reported as ten files.
    #
    # The count still confirms for REPORTING -- those four files are genuinely
    # naming the same thing -- it just no longer opens the door to promoting
    # strings that were never shown to be paths at all.
    promotable = {h for h in by_head
                  if any(name != h for name in names_under.get(h, ()))}
    for path in files:
        if _is_test(path) or _is_config(path) or path.suffix != ".py":
            continue
        try:
            bare = _python_bare_strings(path.read_text(errors="replace"))
        except OSError:
            continue
        where = str(path.relative_to(root))
        for literal in bare:
            head = _path_head(literal) if "/" in literal else literal
            if head not in promotable:
                continue
            by_head.setdefault(head, set()).add(where)
            # And by literal, or a directory with only ONE name under it
            # reports through the literal branch and never sees these --
            # which left two files uncounted the first time.
            by_literal.setdefault(literal, set()).add(where)
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
