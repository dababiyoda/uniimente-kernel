"""Peer evidence must be a refutable claim, never an unverifiable one.

BLK-6 in the frozen contract records that the ladder understates the peers: code
really implemented in DALEOBANKS or WealthMachineIntelligence stood at BLUEPRINT
because the binder can only see this repository. Owner: CLAUDE.

The wrong fix is letting the binder read a sibling checkout — a rung that depends
on what happens to be on this machine is not reproducible. The fix here is an
attestation pinned to a commit and carrying content digests, so a third party can
fetch that commit and prove it wrong.

These tests hold the line between "attested" and "verified now", and refuse every
shape of attestation that could not be checked.
"""
from __future__ import annotations

import json
import os

import pytest

from blueprint.evidence import EvidenceRef, resolve
from blueprint.ladder import EvidenceKind
from blueprint.peer_evidence import (
    ATTESTATION_VERSION,
    AttestedPath,
    PeerAttestation,
    PeerEvidenceError,
    attest,
    load_all,
    split_locator,
)

COMMIT = "a" * 40
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _path(**kw) -> AttestedPath:
    base = {"path": "services/x.py", "kind": "file", "size": 10,
            "digest": "sha256:" + "b" * 64}
    base.update(kw)
    return AttestedPath(**base)


def _attestation(**kw) -> PeerAttestation:
    base = {"organ": "peerorgan", "repository": "owner/Repo", "commit": COMMIT,
            "attested_at": "2026-08-21T00:00:00+00:00", "method": "read a checkout",
            "paths": (_path(),)}
    base.update(kw)
    return PeerAttestation(**base)


def _ref(locator: str) -> EvidenceRef:
    return EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, locator)


# ------------------------------------------------------------- anchoring rules
@pytest.mark.parametrize("commit", ["", "abc", "a" * 39, "HEAD", "A" * 40])
def test_an_attestation_must_pin_a_full_commit(commit):
    """Without a full SHA nobody can fetch the tree and refute the claim."""
    with pytest.raises(PeerEvidenceError) as exc:
        _attestation(commit=commit)
    assert "commit" in str(exc.value)


def test_a_repository_must_be_fetchable_by_name():
    with pytest.raises(PeerEvidenceError) as exc:
        _attestation(repository="Repo")
    assert "owner/name" in str(exc.value)


def test_an_attestation_naming_no_paths_attests_nothing():
    with pytest.raises(PeerEvidenceError):
        _attestation(paths=())


def test_an_attestation_may_not_repeat_a_path():
    with pytest.raises(PeerEvidenceError):
        _attestation(paths=(_path(), _path(size=20)))


def test_a_file_must_carry_a_digest():
    with pytest.raises(PeerEvidenceError) as exc:
        _path(digest=None)
    assert "sha256" in str(exc.value)


def test_a_zero_byte_peer_file_is_refused_like_a_local_one():
    """The same rule the kernel applies to its own implementation paths."""
    with pytest.raises(PeerEvidenceError) as exc:
        _path(size=0)
    assert "not code" in str(exc.value)


# ------------------------------------------------------------ derived, not told
def test_attest_refuses_a_path_that_does_not_exist(tmp_path):
    """An attestation asserts these things exist, so it must not be
    constructible when they do not."""
    (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(PeerEvidenceError) as exc:
        attest("peerorgan", "owner/Repo", COMMIT, str(tmp_path),
               ["real.py", "imaginary.py"])
    assert "imaginary.py" in str(exc.value)


def test_attest_records_the_real_bytes(tmp_path):
    import hashlib

    body = b"def go():\n    return 1\n"
    (tmp_path / "m.py").write_bytes(body)
    attestation = attest("peerorgan", "owner/Repo", COMMIT, str(tmp_path), ["m.py"])
    recorded = attestation.by_path()["m.py"]
    assert recorded.size == len(body)
    assert recorded.digest == "sha256:" + hashlib.sha256(body).hexdigest()


def test_attest_refuses_a_path_escaping_the_checkout(tmp_path):
    with pytest.raises(PeerEvidenceError):
        attest("peerorgan", "owner/Repo", COMMIT, str(tmp_path), ["../secrets"])


def test_attest_refuses_an_empty_directory(tmp_path):
    (tmp_path / "hollow").mkdir()
    with pytest.raises(PeerEvidenceError):
        attest("peerorgan", "owner/Repo", COMMIT, str(tmp_path), ["hollow"])


# --------------------------------------------------------------- the resolver
def _tree(tmp_path, attestation: PeerAttestation | None) -> str:
    directory = tmp_path / "blueprint" / "attestations"
    directory.mkdir(parents=True)
    if attestation is not None:
        (directory / f"{attestation.organ}.json").write_text(
            json.dumps(attestation.to_obj()), encoding="utf-8")
    return str(tmp_path)


def test_an_attested_path_resolves_and_says_attested_not_present(tmp_path):
    """The wording is the honesty: the binder never saw the peer tree."""
    root = _tree(tmp_path, _attestation())
    resolution = resolve(_ref("peer:peerorgan/services/x.py"), root)
    assert resolution.ok
    assert "attested in owner/Repo at commit aaaaaaa" in resolution.detail
    assert "present" not in resolution.detail


def test_a_peer_path_with_no_attestation_is_refused(tmp_path):
    root = _tree(tmp_path, None)
    resolution = resolve(_ref("peer:peerorgan/services/x.py"), root)
    assert not resolution.ok
    assert "no attestation on record" in resolution.detail


def test_attesting_a_repository_does_not_attest_every_path_in_it(tmp_path):
    root = _tree(tmp_path, _attestation())
    resolution = resolve(_ref("peer:peerorgan/services/other.py"), root)
    assert not resolution.ok
    assert "does not cover" in resolution.detail


@pytest.mark.parametrize("locator", ["peer:", "peer:organ", "peer:/path", "peer:organ/"])
def test_a_malformed_peer_locator_is_refused(tmp_path, locator):
    assert split_locator(locator) is None
    assert not resolve(_ref(locator), _tree(tmp_path, _attestation())).ok


def test_an_unknown_attestation_version_reads_as_no_attestation(tmp_path):
    obj = _attestation().to_obj()
    obj["version"] = ATTESTATION_VERSION + 1
    directory = tmp_path / "blueprint" / "attestations"
    directory.mkdir(parents=True)
    (directory / "peerorgan.json").write_text(json.dumps(obj), encoding="utf-8")
    assert load_all(str(tmp_path)) == {}
    assert not resolve(_ref("peer:peerorgan/services/x.py"), str(tmp_path)).ok


def test_a_local_path_still_resolves_locally(tmp_path):
    """The peer branch must not capture ordinary locators."""
    assert resolve(_ref("shell/pipeline.py"), ROOT).ok


# ------------------------------------------------------------ the real records
def test_the_committed_attestations_are_anchored_and_cover_declared_paths():
    """Every attested path is one an organ manifest actually declares."""
    from blueprint.peer_evidence import PEERS, declared_paths

    on_record = load_all()
    assert on_record, "the repository should carry peer attestations"
    for organ, attestation in on_record.items():
        assert len(attestation.commit) == 40
        assert "/" in attestation.repository
        assert attestation.limitations, f"{organ} records no limitations"
        if organ in PEERS:
            declared = set(declared_paths(PEERS[organ][1]))
            attested = set(attestation.by_path())
            assert attested <= declared, (
                f"{organ} attests {attested - declared}, which no manifest declares"
            )


def test_every_manifest_declared_path_is_attested():
    """The manifests' own claims check out; a missing one would be a finding."""
    from blueprint.peer_evidence import PEERS, declared_paths

    on_record = load_all()
    for organ, (_, manifest) in PEERS.items():
        if organ not in on_record:
            continue
        missing = set(declared_paths(manifest)) - set(on_record[organ].by_path())
        assert missing == set(), f"{organ} declares but cannot attest {missing}"


def test_no_gap_still_claims_the_boundary_cannot_be_crossed():
    """Drift guard. The mechanism exists, so the old excuse must not survive.

    #32's gap asserted the kernel "can bind no implementation path across a
    repository boundary". That was true when written and is now false, and a
    stale reason is worse than no reason: it points future work at a problem
    already solved.
    """
    from blueprint.registry import BINDINGS

    stale = [
        (technology_id, gap)
        for technology_id, binding in BINDINGS.items()
        for gap in binding.gaps
        if "can bind no implementation path across a repository boundary" in gap
    ]
    assert stale == [], f"gaps still blame the repository boundary: {stale}"


def test_crossing_the_boundary_did_not_raise_a_single_rung():
    """The mechanism landed; no binding was re-rated on the strength of it.

    Deciding that a peer's code satisfies a kernel technology is a judgment about
    what the peer implements, and nineteen such judgments at once is how a ladder
    inflates. The mechanism is built and the mappings are left for a deliberate
    pass.
    """
    from blueprint.critical_path import compute

    counts = {rung: len(ids) for rung, ids in compute().by_rung().items()}
    assert counts == {"BLUEPRINT": 17, "SKETCHED": 1, "BUILT": 5,
                      "EXERCISED": 22, "PROVEN": 10, "HARDENED": 0,
                      "UNSUPPORTED": 0}, counts


def test_peer_evidence_grants_nothing():
    import blueprint.peer_evidence as module

    for name in ("authorize", "activate", "grant", "approve", "execute"):
        assert not hasattr(module, name)
