"""The live constitutional tripwire, attacked.

CONTRADICTION-0002 Option A moved a duty out of a sealed experiment and into
`governance/integrity/`. A tripwire that only proves it says "ok" on a clean
tree proves almost nothing — the whole value is in what it refuses. So most of
this file is attacks: silent edits, forged baselines, rewritten history,
undeclared additions.

The last two tests are the ones that matter most for the ruling. They assert the
*separation* itself: that the historical experiment is no longer the live
tripwire, and that the two mechanisms can disagree without either being wrong.
"""
from __future__ import annotations

import hashlib
import os
import shutil

import pytest

from governance.integrity import (
    AMENDMENTS, GENESIS_SHA256, Amendment, BrokenChain, Verdict,
    authorized_baseline, verify)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture()
def tree(tmp_path):
    """A throwaway copy of the twelve real artifacts.

    Attacks mutate constitutional files. None of them may touch the real tree,
    so every test that writes runs here.
    """
    for rel in GENESIS_SHA256:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, rel), dst)
    return tmp_path


# -- the baseline is true of the real institution ---------------------------

def test_every_genesis_hash_describes_the_live_artifact():
    """The baseline has to start out true, or every later verdict is noise."""
    for rel, expected in GENESIS_SHA256.items():
        with open(os.path.join(ROOT, rel), "rb") as handle:
            assert _sha(handle.read()) == expected, f"{rel} drifted from genesis"


def test_the_live_institution_is_currently_intact():
    report = verify()
    assert report.intact, f"unexpected findings: {report.findings}"
    assert len(report.statuses) == 12


# -- attacks ----------------------------------------------------------------

def test_a_silent_edit_to_the_constitution_is_caught(tree):
    """The whole point. No record, no authorisation, changed bytes."""
    target = tree / "constitution/constitution.ucl"
    target.write_bytes(target.read_bytes() + b"\n// quietly appended\n")

    report = verify(root=str(tree))

    assert not report.intact
    finding, = [s for s in report.findings]
    assert finding.artifact == "constitution/constitution.ucl"
    assert finding.verdict is Verdict.UNAUTHORISED_CHANGE


def test_a_silent_edit_to_the_consequence_gate_is_caught(tree):
    """The gate is constitutional in effect: it decides what may become real."""
    target = tree / "policy/consequence_gate.py"
    target.write_bytes(target.read_bytes() + b"\n# quietly appended\n")

    report = verify(root=str(tree))

    assert not report.intact
    assert report.findings[0].verdict is Verdict.UNAUTHORISED_CHANGE


def test_an_authorised_amendment_is_accepted(tree):
    """The mechanism must let the institution lawfully change, or it is just an
    expensive way to freeze."""
    target = tree / "constitution/participant-rights.ucl"
    before = _sha(target.read_bytes())
    target.write_bytes(target.read_bytes() + b"\n// ratified change\n")
    after = _sha(target.read_bytes())

    amendments = (Amendment(
        artifact="constitution/participant-rights.ucl",
        from_sha256=before, to_sha256=after,
        authorization="docs/deliberations/FOUNDER-RULING-2026-08-23-"
                      "infinite-goal-chase.md",
        date="2026-08-23", reason="test fixture"),)

    report = verify(root=str(tree), amendments=amendments)

    assert report.intact
    status, = [s for s in report.statuses if s.artifact.endswith(
        "participant-rights.ucl")]
    assert status.amendments == 1


def test_a_record_that_does_not_follow_from_the_chain_is_refused(tree):
    """Forging a baseline by writing a record that starts from nowhere."""
    amendments = (Amendment(
        artifact="constitution/constitution.ucl",
        from_sha256="0" * 64, to_sha256="1" * 64,
        authorization="docs/deliberations/FOUNDER-RULING-2026-08-23-"
                      "infinite-goal-chase.md",
        date="2026-08-23", reason="forged"),)

    with pytest.raises(BrokenChain, match="claims to start from"):
        verify(root=str(tree), amendments=amendments)


def test_rewriting_history_to_fit_todays_bytes_breaks_the_chain(tree):
    """Two amendments, then the first is 'corrected' so the second no longer
    follows. The attack this design exists to stop is exactly this: making a
    past record say whatever today needs it to say."""
    rel = "authority/authority-matrix.yaml"
    target = tree / rel
    v0 = _sha(target.read_bytes())
    target.write_bytes(target.read_bytes() + b"\n# step one\n")
    v1 = _sha(target.read_bytes())
    target.write_bytes(target.read_bytes() + b"\n# step two\n")
    v2 = _sha(target.read_bytes())

    auth = ("docs/deliberations/FOUNDER-RULING-2026-08-23-"
            "infinite-goal-chase.md")
    honest = (
        Amendment(rel, v0, v1, auth, "2026-08-23", "one"),
        Amendment(rel, v1, v2, auth, "2026-08-23", "two"),
    )
    assert verify(root=str(tree), amendments=honest).intact

    tampered = (
        Amendment(rel, v0, v2, auth, "2026-08-23", "one, rewritten"),
        Amendment(rel, v1, v2, auth, "2026-08-23", "two"),
    )
    with pytest.raises(BrokenChain):
        verify(root=str(tree), amendments=tampered)


def test_an_amendment_to_an_undeclared_artifact_is_refused(tree):
    """A record cannot bring a new artifact under governance by mentioning it —
    that would let an amendment define its own subject."""
    amendments = (Amendment(
        artifact="constitution/invented.ucl",
        from_sha256="0" * 64, to_sha256="1" * 64,
        authorization="docs/deliberations/FOUNDER-RULING-2026-08-23-"
                      "infinite-goal-chase.md",
        date="2026-08-23", reason="invented"),)

    with pytest.raises(BrokenChain, match="no genesis hash"):
        verify(root=str(tree), amendments=amendments)


def test_a_new_constitutional_file_nobody_declared_is_a_finding(tree):
    """Adding law is a constitutional change even though no baseline moved."""
    (tree / "constitution/annexe.ucl").write_text("// undeclared law\n")

    report = verify(root=str(tree))

    assert not report.intact
    finding, = report.findings
    assert finding.artifact == "constitution/annexe.ucl"
    assert finding.verdict is Verdict.UNGOVERNED_ADDITION


def test_a_deleted_constitutional_artifact_is_a_finding(tree):
    """Deletion must not read as 'unchanged'."""
    (tree / "constitution/shutdown-policy.ucl").unlink()

    report = verify(root=str(tree))

    finding, = report.findings
    assert finding.verdict is Verdict.MISSING
    assert finding.observed_sha256 is None


# -- the mechanism may not authorise itself ---------------------------------

def test_every_amendment_on_record_cites_a_document_that_exists():
    """An authorisation that points nowhere is not an authorisation."""
    for am in AMENDMENTS:
        assert os.path.isfile(os.path.join(ROOT, am.authorization)), (
            f"amendment to {am.artifact} cites {am.authorization}, "
            "which does not exist")


def test_nothing_in_the_package_writes_an_amendment_record():
    """Authorisation enters this module only by a human editing the source.

    Asserted over the AST rather than by reading: a helper that appended to
    AMENDMENTS would be the module granting itself the power to legalise a
    change it just observed.
    """
    import ast

    package = os.path.join(ROOT, "governance", "integrity")
    for name in sorted(os.listdir(package)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(package, name), "rb") as handle:
            tree_ = ast.parse(handle.read(), filename=name)
        for node in ast.walk(tree_):
            if isinstance(node, ast.Call):
                func = node.func
                attr = getattr(func, "attr", None)
                if attr in {"append", "extend", "insert"}:
                    target = getattr(func.value, "id", None)
                    assert target != "AMENDMENTS", (
                        f"{name} mutates the amendment record at runtime")
            # No file writing anywhere in the package.
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                mode = ""
                for arg in node.args[1:2]:
                    mode = getattr(arg, "value", "")
                for kw in node.keywords:
                    if kw.arg == "mode":
                        mode = getattr(kw.value, "value", "")
                assert "w" not in mode and "a" not in mode, (
                    f"{name} opens a file for writing")


def test_the_package_does_not_import_the_sealed_experiment():
    """The independence the ruling turns on.

    Importing `evolution.repair.spec` would re-fuse the two mechanisms the
    founder separated: the next constitutional amendment would once again have
    to move a sealed experiment's baseline. Twelve duplicated hex strings are
    the price of that independence and are cheaper than the coupling.
    """
    import ast

    package = os.path.join(ROOT, "governance", "integrity")
    for name in sorted(os.listdir(package)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(package, name), "rb") as handle:
            tree_ = ast.parse(handle.read(), filename=name)
        for node in ast.walk(tree_):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("evolution"), name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("evolution"), name


# -- the separation itself ---------------------------------------------------

def test_the_sealed_experiment_is_no_longer_the_live_tripwire():
    """CONTRADICTION-0002, closed and pinned.

    The historical fingerprint must read frozen bytes; the live tripwire must
    read the live tree. If a future session repoints either at the other's
    input, the duties re-fuse and this fails.
    """
    from evolution.repair import spec
    from evolution.repair.harness import (continuity_fingerprint,
                                          live_continuity_fingerprint)

    assert continuity_fingerprint() == spec.CONTINUITY_COMBINED_SHA256

    baseline = authorized_baseline()
    combined = hashlib.sha256()
    for rel in spec.CONTINUITY_ARTIFACT_SHA256:
        with open(os.path.join(ROOT, rel), "rb") as handle:
            combined.update(handle.read())
    assert live_continuity_fingerprint() == combined.hexdigest()
    assert set(baseline) == set(spec.CONTINUITY_ARTIFACT_SHA256)


def test_the_two_readings_may_disagree_without_either_being_wrong(tree):
    """The property the whole ruling exists to create.

    A lawfully amended constitution makes the live tree differ from freeze-time
    bytes. Before today that was a failing sealed experiment. Now: the
    historical run still reproduces, and the live tripwire still says intact,
    *at the same time*, because they are reading different things for different
    reasons.
    """
    from evolution.repair import spec
    from evolution.repair.harness import continuity_fingerprint

    rel = "constitution/sovereignty.ucl"
    target = tree / rel
    before = _sha(target.read_bytes())
    target.write_bytes(target.read_bytes() + b"\n// ratified amendment\n")
    after = _sha(target.read_bytes())

    amendments = (Amendment(
        rel, before, after,
        "docs/deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md",
        "2026-08-23", "founder-ratified"),)

    # Live: changed, and authorised.
    assert verify(root=str(tree), amendments=amendments).intact
    # Historical: untouched, still reproduces its recorded answer.
    assert continuity_fingerprint() == spec.CONTINUITY_COMBINED_SHA256
    # And the live bytes genuinely differ from freeze-time truth.
    assert after != spec.CONTINUITY_ARTIFACT_SHA256[rel]
