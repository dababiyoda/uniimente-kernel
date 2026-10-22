"""The founder tier: the one ledger fact that separates a founder's closure from a test key's.

N1's kill condition forbids counting "a closure with a test key", and the #137 verifier extended that
to N3, N4, N6 and N7. The ledger can prove which enrolled key signed a mission. It cannot tell
Alfonso's key from a fixture's or a --no-passphrase rehearsal's. So a key reaches the founder tier
only by signing a FOUNDER_TIER attestation, which the CLI signs only after decrypting a
passphrase-protected key file. The tier grants nothing. The predicates in greg/path.py read it to
decide whether a structurally complete closure moves the founder's path.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from greg import cli, metrics
from greg.body import Body
from greg.founder import COMMAND_KINDS, DEVICE_KINDS, FOUNDER_TIER_BODY
from tests.greg_fixtures import (TEST_PASSPHRASE, Clock, attest_founder_tier, drop, make_body, mission, note_check,
                                 signed, workspace)


def greg(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


def inbox(home) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((Path(home) / "inbox").glob("*.json"))]


def note(home, mid: str) -> dict:
    target = workspace(home, mid) / "n.txt"
    return mission(mid, checks=[note_check("n", target, "x")], strategies=[], capabilities=["fs.read"],
                   ceiling="read_only")


def test_only_the_founder_key_signs_the_attestation_and_it_has_one_body():
    assert "FOUNDER_TIER" in COMMAND_KINDS and "FOUNDER_TIER" not in DEVICE_KINDS
    assert FOUNDER_TIER_BODY == {"key_custody": "passphrase"}


def test_the_cli_never_attests_an_unprotected_key(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)                                    # a test fixture's key: no passphrase
    monkeypatch.delenv("GREG_FOUNDER_PASSPHRASE", raising=False)
    code, _, err = greg("--home", home, "founder", "attest", "--key", tmp_path / "founder.pem", "--no-passphrase")
    assert code == 2 and "passphrase-protected" in err and inbox(home) == []
    monkeypatch.setenv("GREG_FOUNDER_PASSPHRASE", "")                 # an empty passphrase is no passphrase
    code, _, err = greg("--home", home, "founder", "attest", "--key", tmp_path / "founder.pem")
    assert code == 2 and inbox(home) == []
    # designation still works without the tier: the rehearsal path, which never counts
    code, out, _ = greg("--home", home, "body", "designate", "--key", tmp_path / "founder.pem", "--no-passphrase")
    assert code == 0 and [e["kind"] for e in inbox(home)] == ["BODY_DESIGNATE"] and len(out.split()) == 1


def test_designation_with_a_protected_key_also_attests_the_tier(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path, passphrase=TEST_PASSPHRASE)
    monkeypatch.setenv("GREG_FOUNDER_PASSPHRASE", TEST_PASSPHRASE.decode())
    code, out, _ = greg("--home", home, "body", "designate", "--key", tmp_path / "founder.pem")
    assert code == 0 and len(out.split()) == 2
    assert sorted(e["kind"] for e in inbox(home)) == ["BODY_DESIGNATE", "FOUNDER_TIER"]
    [tier] = [e for e in inbox(home) if e["kind"] == "FOUNDER_TIER"]
    assert tier["body"] == FOUNDER_TIER_BODY


def test_a_mission_is_at_the_founder_tier_only_after_its_key_attested(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path, passphrase=TEST_PASSPHRASE)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", note(home, "m:before"), now=clock.now))
        body.tick()
        drop(home, signed(key, body_id, "FOUNDER_TIER", {"key_custody": "none"}, now=clock.now))
        body.tick()
        assert body.journal.replay("command.rejected")                  # only the one exact attestation body
        attest_founder_tier(home, tmp_path / "founder.pem", TEST_PASSPHRASE, monkeypatch)
        body.tick()
        drop(home, signed(key, body_id, "MISSION", note(home, "m:after"), now=clock.now))
        body.tick()
        body.journal.record("mission.registered", {"mission_id": "m:crafted", "spec": note(home, "m:crafted"),
                                                   "command_digest": "sha256:none"}, key="m:crafted")
        tiers = metrics.founder_tier(body.journal)
    assert tiers["m:after"]["tier"] == metrics.FOUNDER_TIER and "why_not" not in tiers["m:after"]
    assert tiers["m:before"]["tier"] == metrics.STRUCTURAL_CANDIDATE
    assert "only after this mission was registered" in tiers["m:before"]["why_not"]
    assert tiers["m:crafted"]["why_not"] == "no accepted founder-signed MISSION command registered it"
    assert tiers["m:after"]["key_id"] == tiers["m:before"]["key_id"]


def test_an_unattested_key_never_reaches_the_tier(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", note(home, "m:test-key"), now=clock.now))
        body.tick()
        tiers = metrics.founder_tier(body.journal)
    assert tiers["m:test-key"] == {"tier": metrics.STRUCTURAL_CANDIDATE, "key_id": tiers["m:test-key"]["key_id"],
                                   "why_not": metrics.NOT_FOUNDER_TIER}
    assert metrics.founder_tier(None) == {}


def test_n6_and_n7_gates_stay_external_and_every_later_predicate_reports_its_structure():
    """#137 verifier condition (a): N6's gate (a lawful relationship with a real person) is external and so
    is N7's (whether a second venture could stand alone is Alfonso's judgment); their predicates measure
    the ledger side only. Condition (b): N3, N4, N6 and N7 report structurally_met and evidence_level."""
    from greg import path as devpath
    nodes = {n["id"]: n for n in devpath.load()["nodes"]}
    assert nodes["N6"]["evidence_source"] == "external" and nodes["N6"]["predicate"] == "human_work_shared"
    assert nodes["N7"]["evidence_source"] == "external" and nodes["N7"]["predicate"] == "venture_compounding"
    for node in ("N1", "N2", "N3", "N4", "N6", "N7"):           # #138 port: N1 and N2 share the one rule
        assert "founder tier" in nodes[node]["smallest_next_build"]
    empty = type("J", (), {"replay": lambda self, *a: [], "ledger": type("L", (), {"by_type": lambda s, t: []})()})()
    for name in ("vepmc_at_least_one", "genesis_closure", "business_loop_closed", "sop_compounding",
                 "human_work_shared", "venture_compounding"):
        result = devpath.PREDICATES[name](empty)
        assert result["met"] is False and result["structurally_met"] is False and result["evidence_level"] == "NONE"
    assert set(devpath.PREDICATES) == {"vepmc_at_least_one", "genesis_closure", "business_loop_closed",
                                       "sop_compounding", "human_work_shared", "venture_compounding"}
    vepmc = metrics.vepmc(empty)
    assert vepmc["VEPMC"] == vepmc["structural_candidate_count"] == vepmc["founder_tier_count"] == 0
    assert vepmc["evidence_level"] == "NONE"


class _Event:
    def __init__(self, payload, event_id):
        self.payload, self.event_id = payload, event_id


class _Journal:
    """Just enough of a journal for the path predicates: registered specs, nothing else retained."""
    def __init__(self, specs):
        self.events = {"mission.registered": [_Event({"mission_id": m, "spec": s}, f"e{i}")
                                              for i, (m, s) in enumerate(specs.items())]}

        self.ledger = type("Ledger", (), {"by_type": staticmethod(lambda record_type: [])})()

    def replay(self, kind=None):
        return list(self.events.get(kind, []))


def _fixture_rows(monkeypatch, mids):
    rows = [{"mission_id": m, **{c: True for c in metrics.CONDITIONS}, "fixture_evidence": True, "counts": False,
             "missing": ["no_fixture_evidence"]} for m in mids]
    monkeypatch.setattr(metrics, "vepmc", lambda journal: {"missions": rows, "VEPMC": 0})
    monkeypatch.setattr(metrics, "founder_tier", lambda journal: {m: {"tier": metrics.FOUNDER_TIER} for m in mids})


def test_fixture_closures_never_move_the_path_in_any_predicate(monkeypatch):
    """Merge review of 1e55bbd: VEPMC (this trunk) refuses a closure carrying fixture evidence, but the base's
    path predicates N3, N4 and N6 read the nine conditions directly, so fixture closures at the founder tier
    moved the founder's path. Each predicate now names the fixture evidence as missing."""
    from greg import path as devpath, sop
    mids = ["m:a", "m:b", "m:c", "m:r1", "m:r2", "m:r3"]
    _fixture_rows(monkeypatch, mids)
    monkeypatch.setattr(sop, "trend", lambda journal: {"procedures": [{
        "procedure_id": "sop-x", "state": "RATIFIED", "compounding": True,
        "baseline": {"missions": [{"mission_id": m} for m in mids[:3]]},
        "sop_runs": {"missions": [{"mission_id": m} for m in mids[3:]]}}]})
    n4 = devpath.sop_compounding(None)
    assert not n4["met"] and "fixture_evidence:m:r1" in n4["incomplete"][0]["missing"]

    paid = {"check_id": "paid", "sensor": {"capability": "business.reconcile"}}
    person = {"action_id": "ask", "declined_if": "no", "capability": "human.task"}
    journal = _Journal({"m:a": {"success_checks": [paid], "strategies": []},
                        "m:b": {"success_checks": [], "strategies": [person]}})
    for predicate, mid in ((devpath.business_loop_closed, "m:a"), (devpath.human_work_shared, "m:b")):
        [row] = [r for r in predicate(journal)["incomplete"] if r["mission_id"] == mid]
        assert "no_fixture_evidence" in row["missing"], (predicate.__name__, row)
