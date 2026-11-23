"""Acceptance J.G4: a capability that Capability Genesis formed measurably improves a later related mission.

Mission J: "an earlier verified improvement or acquired capability measurably improves a later related task ...
The gain must be attributable to the retained mechanism." This is the acquired-capability branch.

Mission A meets a missing function (markdown.unchecked_count). The builder writes a wrong candidate, then a correct
one; the frozen founder oracle verifies it, and it is attached. The Body is restarted. Mission B has a different
mission id and different data, and needs the same function. The dividend is measured, not inferred from registry rows:

* builder invocations, the signed build spend, and ticks to ACHIEVED, for B with the retained capability, against
  the same mission B on a fresh home (the ablation without the earlier formation);
* B is served by the very capability A formed (the receipt's witness names it), and is appraised.

The second ablation is the founder's: after a signed CAPABILITY_DETACH, B gets no dividend. Without a build budget it
escalates; with one, the builder is called again, and its identical rebuild is refused rather than attached, so a
founder detach cannot be bypassed by rebuilding.

In-process Body with a test clock and a deterministic builder that reports a cost per call (SANDBOX); the founder
key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

from greg import builders
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed
from tests.unit.test_greg_genesis_builder import CONTRACT, FUNCTION, GOOD, WRONG

PRICE = 0.05                                    # what each build call reports it cost
FIRST_DOC, FIRST_COUNT = "- [ ] a\n- [x] b\n* [ ] c\n", 2
LATER_DOC, LATER_COUNT = "+ [ ] x\n  - [ ] y\n- [X] z\n\t* [ ] w\n", 3


class PricedBuilder(builders.StaticBuilder):
    """StaticBuilder that bills each call, so a build that should not happen shows up as spend."""

    def build(self, request, feedback=None):
        return {**super().build(request, feedback), "cost_usd": PRICE}


def _spec(data, mission_id, text, expected, *, budget=1.0):
    doc = data / f"{mission_id.replace(':', '_')}.md"
    doc.write_text(text)
    check = {"check_id": "open-items-counted", "description": "the number of open items is known",
             "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": f"fs:{doc.name}"},
             "predicate": {"op": "equals", "field": "unchecked", "value": expected}}
    spec = mission(mission_id, checks=[check], strategies=[], ceiling="read_only", budget=budget,
                   capabilities=["fs.read", f"built.{FUNCTION}.*"], auto_attach=True)
    spec["capability_specs"] = [dict(CONTRACT, build_budget_usd=min(CONTRACT["build_budget_usd"], budget))]
    return spec


def _run(home, builder, mission_id, ticks=5):
    """Open the Body, tick it, and return (body, ticks to the mission's first ACHIEVED or None)."""
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    achieved_at = None
    for tick in range(1, ticks + 1):
        clock.advance(30)
        states = {m["mission_id"]: m["state"] for m in body.tick()["missions"]}
        if achieved_at is None and states.get(mission_id) == "ACHIEVED":
            achieved_at = tick
    return body, achieved_at


def _measure(body) -> dict:
    j = body.journal
    return {"deficits": len(j.replay("deficit.opened")), "built": len(j.replay("genesis.built")),
            "routes": len(j.replay("genesis.route")), "verified": len(j.replay("genesis.verified")),
            "spend": round(sum(e.payload.get("cost_usd") or 0.0
                               for kind in ("genesis.built", "genesis.unbuilt") for e in j.replay(kind)), 6)}


def _form_first(tmp_path):
    """Mission A forms the capability; returns (home, key, body_id, data, capability_id, A's measurements)."""
    tmp_path.mkdir(parents=True)
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, "m:first", FIRST_DOC, FIRST_COUNT)))
    builder = PricedBuilder(WRONG, GOOD, identity="static-test")
    body, ticks = _run(home, builder, "m:first")
    try:
        assert ticks is not None, "mission A closes through the built capability"
        cid = body.journal.replay("capability.registered")[0].payload["manifest"]["capability_id"]
        assert body.registry.state[cid] == "ATTACHED"
        first = {**_measure(body), "calls": len(builder.calls), "ticks": ticks}
    finally:
        body.close()
    assert {k: first[k] for k in ("deficits", "built", "verified", "spend", "calls")} == {
        "deficits": 1, "built": 2, "verified": 2, "spend": 2 * PRICE, "calls": 2}
    return home, key, body_id, data, cid, first


def test_a_capability_formed_for_one_mission_serves_a_later_one_with_no_build_and_fewer_ticks(tmp_path):
    home, key, body_id, data, cid, first = _form_first(tmp_path / "retained")

    # Mission B, after a restart, with the capability retained. A builder is present and would bill if called.
    drop(home, signed(key, body_id, "MISSION", _spec(data, "m:later", LATER_DOC, LATER_COUNT)))
    builder = PricedBuilder(GOOD, GOOD, identity="static-test")
    body, ticks = _run(home, builder, "m:later")
    try:
        retained = {**_measure(body), "calls": len(builder.calls), "ticks": ticks}
        appraised = [e.payload for e in body.journal.replay("mission.appraised")
                     if e.payload.get("mission_id") == "m:later"]
        observed = [e.payload for e in body.journal.replay("mission.observed")
                    if e.payload["mission_id"] == "m:later" and e.payload["passed"]]
        grant = body.ledger.find(observed[-1]["receipt"]).payload["grant_id"]
        [witness] = [r.payload for r in body.ledger.by_type("witness") if r.payload.get("grant_id") == grant]
    finally:
        body.close()

    # Ablation: the same mission B on a fresh home, where nothing was formed before it.
    (tmp_path / "fresh").mkdir()
    fresh_home, fresh_key, fresh_id, fresh_data = make_body(tmp_path / "fresh")
    drop(fresh_home, signed(fresh_key, fresh_id, "MISSION", _spec(fresh_data, "m:later", LATER_DOC, LATER_COUNT)))
    fresh_builder = PricedBuilder(WRONG, GOOD, identity="static-test")
    fresh_body, fresh_ticks = _run(fresh_home, fresh_builder, "m:later")
    try:
        ablated = {**_measure(fresh_body), "calls": len(fresh_builder.calls), "ticks": fresh_ticks}
    finally:
        fresh_body.close()

    assert ticks is not None and appraised and appraised[-1]["verdict"] == "VERIFIED", "B closes, appraised VERIFIED"
    assert witness["capability"] == cid, "B was served by the capability A formed"
    # Nothing new was formed or paid for: the counts are A's, unchanged.
    unchanged = ("deficits", "built", "verified", "routes", "spend")
    assert {k: retained[k] for k in unchanged} == {k: first[k] for k in unchanged}
    assert retained["calls"] == 0
    # The dividend is attributable: without the earlier formation the same mission pays for it again.
    assert ablated["deficits"] == 1 and ablated["calls"] == 2 and ablated["spend"] == 2 * PRICE
    assert ablated["verified"] == 2 and ablated["routes"] > 0
    assert ablated["ticks"] is not None and ticks < ablated["ticks"]


def test_after_a_founder_detach_the_later_mission_gets_no_dividend_and_a_rebuild_is_not_attached(tmp_path):
    for budget in (0.0, 1.0):
        home, key, body_id, data, cid, first = _form_first(tmp_path / f"budget-{budget}")
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}))
        drop(home, signed(key, body_id, "MISSION", _spec(data, "m:later", LATER_DOC, LATER_COUNT, budget=budget)))
        builder = PricedBuilder(GOOD, identity="static-test")
        body, ticks = _run(home, builder, "m:later")
        try:
            after = _measure(body)
            routes = [e.payload for e in body.journal.replay("genesis.route")]
            later = {e.payload["deficit_id"] for e in body.journal.replay("deficit.opened")} - {routes[0]["deficit_id"]}
            later_routes = [(r["route"], r["result"]) for r in routes if r["deficit_id"] in later]
            state = body.registry.state[cid]
        finally:
            body.close()
        assert ticks is None, "with the founder's detach standing, mission B does not close"
        assert after["deficits"] == first["deficits"] + 1, "B opens its own deficit"
        assert state == "DETACHED", "the founder's detach stands"
        assert ("founder", "escalated") in later_routes
        if budget == 0.0:
            assert builder.calls == [] and after["spend"] == first["spend"]
            assert ("builder", "no founder-signed build budget remains") in later_routes
        else:
            # The builder is paid again; its identical code maps to the detached capability and is not attached.
            assert builder.calls and after["spend"] > first["spend"]
            assert ("builder", "founder-detached; explicit attach required") in later_routes
