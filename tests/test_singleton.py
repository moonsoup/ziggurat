"""One of a thing the domain has many of.

The fault this finds is not duplication -- the value may be correctly
centralised, which is the right pattern. It is ARITY: one, under a registry
that already keeps many. No duplication check can see that.
"""

from __future__ import annotations

from pathlib import Path

from ziggurat import structure as S


def _project(tmp_path: Path, files: dict) -> Path:
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


FLEET = '''
from dataclasses import dataclass, field

@dataclass
class Node:
    node_id: str = ""
    host: str = ""
    port: int = 22

@dataclass
class Fleet:
    nodes: dict = field(default_factory=dict)
'''

CONFIG = '''
class Config:
    body_host: str = "192.168.1.223"
    timeout_seconds: int = 30
'''


def _readers(count: int, attr: str = "body_host") -> dict:
    return {f"mod{i}.py": f"from x import CONFIG\nv = CONFIG.{attr}\n"
            for i in range(count)}


# --- both facts are required ------------------------------------------------

def test_a_scalar_with_a_matching_collection_is_reported(tmp_path):
    root = _project(tmp_path, {"config.py": CONFIG, "fleet.py": FLEET,
                               **_readers(5)})
    report = S.analyse(root)
    hits = [f for f in report.findings if f.check == "singleton-bottleneck"]
    assert len(hits) == 1
    assert "body_host" in hits[0].summary
    assert "Node.host" in hits[0].summary


def test_a_scalar_with_NO_collection_is_quiet_not_a_finding(tmp_path):
    """A port or a timeout is legitimately one value and has no registry of
    peers. Reporting it is the noise that gets a checker switched off."""
    root = _project(tmp_path, {"config.py": CONFIG,
                               **_readers(6, "timeout_seconds")})
    report = S.analyse(root)
    assert not [f for f in report.findings if f.check == "singleton-bottleneck"]
    assert [q["name"] for q in report.quiet] == ["timeout_seconds"]


def test_the_quiet_entry_still_carries_its_evidence(tmp_path):
    """Kept rather than dropped: 'we looked and found nothing conclusive' is
    itself worth reading."""
    root = _project(tmp_path, {"config.py": CONFIG,
                               **_readers(6, "timeout_seconds")})
    quiet = S.analyse(root).quiet[0]
    assert quiet["declared_in"] == "config.py"
    assert len(quiet["read_by"]) >= S.SINGLETON_AT


# --- the count is a floor, not a judgement ---------------------------------

def test_too_few_readers_is_not_reported_at_all(tmp_path):
    root = _project(tmp_path, {"config.py": CONFIG, "fleet.py": FLEET,
                               **_readers(S.SINGLETON_AT - 1)})
    report = S.analyse(root)
    assert not [f for f in report.findings if f.check == "singleton-bottleneck"]
    assert not report.quiet


# --- how a scalar is matched to a field ------------------------------------

def test_a_qualified_name_matches_the_bare_field(tmp_path):
    """`body_host` is `host` with a qualifier in front -- which is exactly how
    a singleton gets written: THE body's host, as though there were one."""
    assert S._matching_field("body_host", {"host", "port"}) == "host"
    assert S._matching_field("host", {"host"}) == "host"


def test_an_unrelated_name_does_not_match(tmp_path):
    assert S._matching_field("timeout", {"host", "port"}) == ""
    assert S._matching_field("ghost", {"host"}) == ""


def test_a_very_short_field_does_not_match_by_suffix():
    """Matching on two letters would pair almost anything."""
    assert S._matching_field("body_id", {"id"}) == ""


# --- what counts as a scalar ------------------------------------------------

def test_a_container_is_not_a_singleton(tmp_path):
    root = _project(tmp_path, {
        "config.py": "class Config:\n    hosts: dict = {}\n",
        "fleet.py": FLEET,
        **{f"mod{i}.py": "from x import CONFIG\nv = CONFIG.hosts\n"
           for i in range(6)}})
    report = S.analyse(root)
    assert not [f for f in report.findings if f.check == "singleton-bottleneck"]


def test_a_constructed_object_is_not_a_setting(tmp_path):
    """`CONFIG = Config(...)` is read by everything BY DESIGN. Counting its
    readers says nothing about arity."""
    root = _project(tmp_path, {
        "config.py": "class Config:\n    pass\nCONFIG = Config()\n",
        "fleet.py": FLEET,
        **{f"mod{i}.py": "from x import CONFIG\nv = CONFIG\n"
           for i in range(8)}})
    report = S.analyse(root)
    assert not [f for f in report.findings if f.check == "singleton-bottleneck"]
    assert not report.quiet


# --- the structured half ----------------------------------------------------

def test_the_finding_carries_detail_for_a_reader_that_is_not_a_person(tmp_path):
    """An agent planning a change needs every reader and every site, and
    should not have to parse prose to get them."""
    root = _project(tmp_path, {"config.py": CONFIG, "fleet.py": FLEET,
                               **_readers(5)})
    hit = [f for f in S.analyse(root).findings
           if f.check == "singleton-bottleneck"][0]
    assert hit.detail["scalar"] == "body_host"
    assert hit.detail["collected_class"] == "Node"
    assert hit.detail["matching_field"] == "host"
    assert hit.detail["container"] == "nodes"
    assert len(hit.detail["read_by"]) == 5


def test_the_evidence_says_why_no_duplication_check_would_see_it(tmp_path):
    root = _project(tmp_path, {"config.py": CONFIG, "fleet.py": FLEET,
                               **_readers(5)})
    hit = [f for f in S.analyse(root).findings
           if f.check == "singleton-bottleneck"][0]
    assert "centralised" in hit.evidence
    assert "arity" in hit.evidence


def test_it_is_a_structural_fact_not_a_judgement(tmp_path):
    from ziggurat.findings import Confidence

    root = _project(tmp_path, {"config.py": CONFIG, "fleet.py": FLEET,
                               **_readers(5)})
    hit = [f for f in S.analyse(root).findings
           if f.check == "singleton-bottleneck"][0]
    assert hit.confidence is Confidence.STRUCTURAL


# --- the case it was built for ---------------------------------------------

def test_it_finds_the_real_one_in_incarnation():
    """body_host: one value, 14 readers, beside a complete Node/Fleet
    registry. This is the fault the check exists for; if it stops finding it,
    the check has drifted."""
    where = Path.home() / "Software" / "incarnation"
    if not where.is_dir():
        import pytest
        pytest.skip("incarnation is not checked out here")
    hits = {f.detail.get("scalar") for f in S.analyse(where).findings
            if f.check == "singleton-bottleneck"}
    assert "body_host" in hits


# --- a command is not a directory ------------------------------------------

def test_a_shell_command_containing_a_path_is_not_a_directory():
    """`rm -f /boot/firmware/firstrun.sh` was reported as the directory
    `rm -f /`, named in six files -- true of the string, false about the
    codebase. The rule this check keeps relearning: ask whether a string is
    USED as a path, not whether it LOOKS like one."""
    assert S._path_head("rm -f /boot/firmware/firstrun.sh") == ""
    assert S._path_head("sudo install -m 600 /etc/watchpi/x") == ""
    assert S._path_head("cat > /boot/firmware/config.txt") == ""


def test_a_real_path_still_has_a_head():
    assert S._path_head("records/eye.jsonl") == "records"
    assert S._path_head("/var/lib/watchpi/nodes.json") == "/var/lib/watchpi"
