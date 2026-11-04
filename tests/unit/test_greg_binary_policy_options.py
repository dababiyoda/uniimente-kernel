"""What each binary-license policy option does to the body's own self-repair (BINARY_LICENSE_POLICY.md).

Measurement, not activation: the active policy stays P0 (`test_neither_draft_is_active_until_the_founder_adopts_it`).
The founder detaches the acquired ``sha256sum`` and a second signed mission needs ``hash.sha256`` again, so Capability
Genesis repairs the function from the remaining candidates. On a Debian-family body ``shasum`` belongs to ``perl``,
whose DEP-5 file names licenses GREG does not classify, and ``openssl`` is Apache-2.0. In-process Body with a test
clock (SANDBOX); per-test founder key.
"""
from __future__ import annotations

import hashlib

import pytest

from greg import genesis as genesis_mod, licensing
from greg.body import Body
from tests.greg_fixtures import Clock, make_body, mission, signed
from tests.unit.test_greg_missions import events, run, submit

needs = pytest.mark.skipif(
    any(genesis_mod.installed_binary(n) is None for n in ("sha256sum", "shasum", "openssl"))
    or licensing.system_binary(genesis_mod.installed_binary("shasum") or "/") is None,
    reason="needs sha256sum, shasum and openssl on a dpkg body")


def _repair(tmp_path, monkeypatch, available):
    found = {n: genesis_mod.installed_binary(n) for n in available}
    monkeypatch.setattr(genesis_mod, "installed_binary", lambda name: found.get(name))
    home, key, body_id, data = make_body(tmp_path)
    target = data / "evidence.bin"
    target.write_bytes(b"independent evidence")
    check = {"check_id": "digest", "description": "digest remains correct",
             "sensor": {"function": "hash.sha256", "params": {"path": str(target)}, "target": "fs:evidence.bin"},
             "predicate": {"op": "equals", "field": "sha256", "value": hashlib.sha256(target.read_bytes()).hexdigest()}}
    scope = dict(capabilities=["fs.read", "acquired.hash.sha256.*"], ceiling="read_only", auto_attach=True)
    submit(home, key, body_id, "MISSION", mission("m:first", checks=[check], strategies=[], **scope))
    assert run(home, Clock(), ticks=4)[0]["m:first"].status == "ACHIEVED"
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "acquired.hash.sha256.sha256sum"}))
    submit(home, key, body_id, "MISSION", mission("m:repair", checks=[check], strategies=[], **scope))
    status = run(home, Clock(), ticks=4)[0]["m:repair"].status
    with Body(home) as body:
        attached = sorted(c for c, s in body.registry.state.items() if s == "ATTACHED" and c.startswith("acquired."))
    return status, attached, [e["why"] for e in events(home, "deficit.awaiting_attach")]


@needs
def test_under_p0_self_repair_relies_on_a_binary_whose_license_greg_cannot_classify(tmp_path, monkeypatch):
    assert licensing.system_binary(genesis_mod.installed_binary("shasum"))["verdict"] == "UNCLASSIFIED_PRIOR_BEHAVIOUR"
    status, attached, _ = _repair(tmp_path, monkeypatch, ("sha256sum", "shasum", "openssl"))
    assert (status, attached) == ("ACHIEVED", ["acquired.hash.sha256.shasum"])    # openssl is never reached


@needs
@pytest.mark.xfail(strict=True, reason="measured defect: under P4c a license hold on one candidate ends the repair "
                                       "instead of trying the next, cleared candidate (openssl); see "
                                       "BINARY_LICENSE_POLICY.md. Remove this mark when Genesis falls through.")
def test_under_p4c_a_license_hold_on_one_candidate_does_not_end_self_repair(tmp_path, monkeypatch):
    monkeypatch.setattr(licensing, "ACTIVE_BINARY_POLICY", "P4c")
    status, attached, whys = _repair(tmp_path, monkeypatch, ("sha256sum", "shasum", "openssl"))
    assert (status, attached) == ("ACHIEVED", ["acquired.hash.sha256.openssl"]), whys
