"""One signed, bounded, revocable grant over reviewed read-only methods (founder directive 2026-11-22, item 2).

Reproduced first, on #196 9b931994: a signed read-only mission whose two checks need two withheld cognition
families (minimax and crowd labelling, both VERIFIED, built and qualified) stops on an attach ask, and after the
founder attaches one family it stops again on the other. With one CAPABILITY_GRANT covering both, the same mission
closes with no attach ask. Revocation and expiry detach what the grant attached, across a restart; a grant cannot
cover anything that spends, sends, publishes, writes or reads credentials, and a device key cannot sign one.
"""
from datetime import timedelta

import pytest

from greg.body import Body
from greg.founder import FounderAuthError
from greg.journal import iso
from greg.missions import MissionError
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

pytest.importorskip("z3")

GAME = {"problem_id": "grant:game", "operation": "minimax", "data": {"payoffs": [[1, -1], [-1, 1]]}}
LABELS = [{"item_id": f"i{i}", "observer_id": f"o{j}", "independence_group": f"g{j}", "label": "a"}
          for i in range(3) for j in range(3)]
CROWD = {"problem_id": "grant:crowd", "operation": "crowd_label", "data": {"classes": ["a", "b"], "labels": LABELS}}
FAMILIES = ("cognition.game", "cognition.crowd")


def two_family_mission(mid="m:two-families"):
    checks = [{"check_id": "value", "description": "minimax value of matching pennies",
               "sensor": {"capability": "cognition.solve", "target": "cognition:game", "params": GAME},
               "predicate": {"op": "equals", "field": "output.value", "value": 0}},
              {"check_id": "labelled", "description": "crowd labels aggregated",
               "sensor": {"capability": "cognition.solve", "target": "cognition:crowd", "params": CROWD},
               "predicate": {"op": "equals", "field": "output.labels.i0", "value": "a"}}]
    strategies = [{"action_id": "game", "capability": "cognition.solve", "target": "cognition:game", "params": GAME,
                   "advances": ["value"], "rationale": "bounded numeric minimax"},
                  {"action_id": "crowd", "capability": "cognition.solve", "target": "cognition:crowd",
                   "params": CROWD, "advances": ["labelled"], "rationale": "aggregate the observers' labels"}]
    return mission(mid, checks=checks, strategies=strategies, capabilities=["cognition.solve"],
                   targets=("cognition:*",), ceiling="read_only")


def attach_asks(body):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]


def run(body, clock, mid, ticks=8):
    for _ in range(ticks):
        body.tick()
        if body.engine.book.missions[mid].status == "ACHIEVED":
            break
        clock.advance(31)
    return body.engine.book.missions[mid].status


def grant_body(body, clock, caps=FAMILIES, *, gid="reviewed-read-only", days=7, uses=50, start=None):
    start = start or clock()
    return {"grant_id": gid, "capabilities": {c: body.registry.manifests[c].digest() for c in caps},
            "data_classes": [], "not_before": iso(start), "expires_at": iso(start + timedelta(days=days)),
            "max_uses": uses, "purpose": "read-only cognition for delegated analysis"}


def test_without_a_grant_each_withheld_method_is_its_own_founder_interruption(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", two_family_mission()))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert run(body, clock, "m:two-families", ticks=3) != "ACHIEVED"
        first = attach_asks(body)
        assert first and set(first[0]["authority_requested"]["capabilities"]) & set(FAMILIES)
        # the founder answers one ask with one attach; the mission reaches the other family and stops again
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.game"}))
        assert run(body, clock, "m:two-families", ticks=4) != "ACHIEVED"
        waiting = {c for a in attach_asks(body) for c in a["authority_requested"]["capabilities"]}
        assert "cognition.crowd" in waiting and body.registry.state["cognition.crowd"] == "VERIFIED"


def test_inside_one_grant_the_mission_selects_and_combines_methods_without_asking_again(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        result = body.apply(signed(key, body_id, "CAPABILITY_GRANT", grant_body(body, clock)))["result"]
        assert sorted(result["attached"]) == sorted(FAMILIES) and result["detached"] == []
    drop(home, signed(key, body_id, "MISSION", two_family_mission()))
    with Body(home, clock=clock) as body:
        body.boot()
        assert run(body, clock, "m:two-families") == "ACHIEVED"
        assert attach_asks(body) == []                               # no founder interruption at all
        states = [e.payload for e in body.journal.replay("capability.state") if e.payload["capability_id"] in FAMILIES]
        assert {s["by"] for s in states} == {"grant"} and {s["grant_id"] for s in states} == {"reviewed-read-only"}
        # every act still went through the Gate: a receipt per observation, none created authority
        receipts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance((r.payload.get("result") or {}).get("output"), dict)
                    and r.payload["result"]["output"].get("method") in FAMILIES]
        assert {r["method"] for r in receipts} == set(FAMILIES)
        assert all(r["authority_created"] is False for r in receipts)
        from greg import method_grant
        [row] = method_grant.report(body, clock())
        assert row["state"] == "ACTIVE" and row["uses"] == len(receipts) and row["max_uses"] == 50


def test_revoked_access_stops_and_stays_stopped_after_restart(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "CAPABILITY_GRANT", grant_body(body, clock)))
        # the founder attached one method on its own as well: revoking the grant must leave that one attached
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.game"}))
        out = body.apply(signed(key, body_id, "CAPABILITY_GRANT_REVOKE",
                                {"grant_id": "reviewed-read-only", "reason": "review finished"}))["result"]
        assert out["detached"] == ["cognition.crowd"]
        assert not body.registry.usable("cognition.crowd")[0] and body.registry.usable("cognition.game")[0]
    drop(home, signed(key, body_id, "MISSION", two_family_mission("m:after-revoke")))
    with Body(home, clock=clock) as body:
        body.boot()
        assert body.registry.state["cognition.crowd"] == "DETACHED"        # the projection survives the restart
        assert run(body, clock, "m:after-revoke", ticks=3) != "ACHIEVED"
        assert "cognition.crowd" in {c for a in attach_asks(body) for c in a["authority_requested"]["capabilities"]}
        before = len(body.journal.replay("capability.state"))
        body.tick()
        assert len(body.journal.replay("capability.state")) == before      # an ended grant never re-attaches
        with pytest.raises(MissionError, match="never re-issued"):          # nor is its id reused
            body.apply(signed(key, body_id, "CAPABILITY_GRANT", grant_body(body, clock)))


def test_a_founder_detach_inside_the_window_is_never_undone_by_the_grant(tmp_path):
    # found by a surviving mutant: the sweep re-attached a granted method the founder had detached on its own
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "CAPABILITY_GRANT", grant_body(body, clock)))
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.crowd"}))
        body.tick()
        clock.advance(60)
        body.tick()
        assert body.registry.state["cognition.crowd"] == "DETACHED" and body.registry.usable("cognition.game")[0]
    with Body(home, clock=clock) as body:
        body.boot()
        body.tick()
        assert body.registry.state["cognition.crowd"] == "DETACHED"


def test_the_window_and_the_use_ceiling_end_the_grant_by_themselves(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        later = clock() + timedelta(hours=1)
        assert body.apply(signed(key, body_id, "CAPABILITY_GRANT",
                                 grant_body(body, clock, days=1, start=later)))["result"]["attached"] == []
        body.tick()
        assert body.registry.state["cognition.game"] == "VERIFIED"         # not before its window opens
        clock.advance(3601)
        body.tick()
        assert body.registry.usable("cognition.game")[0]
        clock.advance(86400)
        body.tick()                                                         # expired: detached on the next turn
        assert not body.registry.usable("cognition.game")[0] and not body.registry.usable("cognition.crowd")[0]
    (tmp_path / "uses").mkdir()
    home2, key2, body_id2, _ = make_body(tmp_path / "uses")
    drop(home2, signed(key2, body_id2, "MISSION", two_family_mission("m:one-use")))
    clock2 = Clock()
    with Body(home2, clock=clock2) as body:
        body.apply(signed(key2, body_id2, "CAPABILITY_GRANT", grant_body(body, clock2, gid="one-use", uses=1)))
        body.boot()
        run(body, clock2, "m:one-use", ticks=4)
        from greg import method_grant
        [row] = method_grant.report(body, clock2())
        assert row["state"] == "EXHAUSTED" and row["uses"] >= 1
        assert not any(body.registry.usable(c)[0] for c in FAMILIES)


def test_consequential_and_sensitive_capabilities_stay_outside_any_grant(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        for outside, why in (("daleobanks.publish", "external_contact"), ("artifact.store", "internal_write"),
                             ("browser.render", "network"), ("brief.freshness", "filesystem"),
                             ("github.pulls", "network")):
            spec = grant_body(body, clock, caps=("cognition.game", outside), gid=f"try-{outside}")
            with pytest.raises(MissionError, match="nothing attached") as refused:
                body.apply(signed(key, body_id, "CAPABILITY_GRANT", spec))
            assert why in str(refused.value)
        assert body.registry.state["cognition.game"] == "VERIFIED"         # one ineligible method refuses the whole
        stale = grant_body(body, clock, gid="stale")
        stale["capabilities"]["cognition.game"] = "sha256:" + "0" * 64
        with pytest.raises(MissionError, match="not the one reviewed"):
            body.apply(signed(key, body_id, "CAPABILITY_GRANT", stale))
        sensitive = grant_body(body, clock, gid="classes")
        with pytest.raises(MissionError, match="at most 30 days"):
            body.apply(signed(key, body_id, "CAPABILITY_GRANT", {**sensitive, "expires_at": iso(clock() + timedelta(days=31))}))
        body.registry.set_state("cognition.crowd", "QUARANTINED")
        with pytest.raises(MissionError, match="QUARANTINED"):
            body.apply(signed(key, body_id, "CAPABILITY_GRANT", grant_body(body, clock, gid="quarantined")))
        assert not body.journal.replay("capability.grant")


def test_a_device_key_cannot_sign_a_grant(tmp_path):
    from greg.founder import DEVICE_KINDS
    assert "CAPABILITY_GRANT" not in DEVICE_KINDS and "CAPABILITY_GRANT_REVOKE" not in DEVICE_KINDS
    home, key, body_id, _ = make_body(tmp_path)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    stranger = Ed25519PrivateKey.generate()
    clock = Clock()
    with Body(home, clock=clock) as body:
        with pytest.raises(FounderAuthError):
            body.apply(signed(stranger, body_id, "CAPABILITY_GRANT", grant_body(body, clock)))
        assert body.registry.state["cognition.game"] == "VERIFIED"
