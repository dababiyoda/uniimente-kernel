"""Governed recovery: a quarantined capability earns back eligibility, never authority.

Donor: opossum 10.0.0's circuit breaker (analysed with REA, read in source). Its half-open state lets the
next live call through after a fixed timeout. GREG's mutation probes in the sandbox on a fresh frozen-oracle
seed, restores VERIFIED (eligibility) and leaves ATTACHED to the founder or a signed mission scope, backs
off exponentially, stops on flapping, and recovers engines before the constructions built on them.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import genesis as genesis_mod, mechanisms  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.cognition import network  # noqa: E402
from greg.templates import compiled_question, network_in_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

FLOW = ("Plant to North: 10. Plant to South: 5. North to Market: 4. South to Market: 8. North to South: 6. "
        "Maximum flow from Plant to Market.")
STAFFING = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                        {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]},
                        {"id": "Cy", "capacity": 3, "skills": ["packing"]}],
            "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"},
                       {"id": "Dock2", "demand": 3, "skill": "forklift"},
                       {"id": "Line", "demand": 2, "skill": "packing"}]}
NX, SP = "acquired.graph.max_flow.networkx", "acquired.graph.max_flow.scipy"


def lie(runner):
    return network.RUNNERS[runner].replace(
        "def solve(req):", "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):", 1)


def ticks(body, clock, n, step=31):
    out = []
    for _ in range(n):
        out.append(body.tick())
        clock.advance(step)
    return out


def states(results):
    return [r["missions"][0]["state"] for r in results if r.get("missions")]


def probes(body):
    return [e.payload for e in body.journal.replay("capability.probe")]


def lose_every_engine(body, clock, monkeypatch, n=8):
    """The attached engine lies in service and the only alternative lies at qualification."""
    honest = dict(network.RUNNERS)
    monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", lie("networkx.max_flow"))
    monkeypatch.setitem(network.RUNNERS, "scipy.max_flow", lie("scipy.max_flow"))
    out = ticks(body, clock, n)
    return honest, out


def test_a_transiently_faulty_engine_recovers_and_the_mission_closes_without_the_founder(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        assert body.registry.state[NX] == "ATTACHED"
        honest, _ = lose_every_engine(body, clock, monkeypatch)
        assert body.registry.state[NX] == "QUARANTINED" and SP not in body.registry.state
        mission = next(iter(body.engine.book.missions.values()))
        assert mission.blocker and mission.blocker["type"] == "capability"
        assert not probes(body)                                    # nothing probes before the backoff elapses
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", honest["networkx.max_flow"])  # fault clears
        clock.advance(16 * 60)
        result = ticks(body, clock, 3)
        assert [p["passed"] for p in probes(body)] == [True] and probes(body)[0]["attempt"] == 1
        assert {"capability_id": NX, "result": "recovered", "attempt": 1} in result[0]["recovery"]
        assert body.registry.state[NX] == "ATTACHED"
        attached = [e.payload for e in body.journal.replay("capability.state")
                    if e.payload["capability_id"] == NX and e.payload["state"] == "ATTACHED"]
        assert attached[-1]["by"].startswith("founder-signed mission auto_attach")   # authority came from scope
        assert "ACHIEVED" in states(result)
        assert not [e for e in body.journal.replay("decision.answered")]          # no founder answer was needed


def test_a_failed_probe_doubles_the_wait_and_never_restores_eligibility(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        lose_every_engine(body, clock, monkeypatch)              # the lie persists
        clock.advance(16 * 60)
        ticks(body, clock, 1)
        assert [(p["attempt"], p["passed"]) for p in probes(body)] == [(1, False)]
        assert body.registry.state[NX] == "QUARANTINED"
        clock.advance(20 * 60)                                    # under the doubled 30-minute wait
        ticks(body, clock, 1)
        assert len(probes(body)) == 1
        clock.advance(15 * 60)
        ticks(body, clock, 1)
        assert [(p["attempt"], p["passed"]) for p in probes(body)] == [(1, False), (2, False)]
        assert probes(body)[1]["waited_seconds"] == 30 * 60
        assert probes(body)[0]["seed"] != probes(body)[1]["seed"]  # every probe is a fresh oracle draw


def test_flapping_stops_recovery_and_leaves_the_decision_to_the_founder(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        lose_every_engine(body, clock, monkeypatch)
        for n in range(3):          # retained history: three earlier in-service quarantines of the same engine
            body.journal.record("capability.state", {"capability_id": NX, "state": "QUARANTINED",
                                                     "why": f"failed in service: earlier fault {n}",
                                                     "incident": f"earlier-{n}", "at": "2026-01-01T00:00:00Z"},
                                key=[NX, "earlier", n])
        body.journal.record("capability.state", {"capability_id": NX, "state": "QUARANTINED",
                                                 "why": "failed in service: the latest fault", "incident": "latest",
                                                 "at": "2026-01-01T00:00:00Z"}, key=[NX, "latest"])
        clock.advance(48 * 3600)
        result = ticks(body, clock, 1)
        stopped = [e.payload for e in body.journal.replay("capability.recovery_stopped")]
        assert stopped and stopped[0]["why"].startswith("flapping") and not probes(body)
        assert body.registry.state[NX] == "QUARANTINED"
        assert any(r["result"] == "stopped" for r in result[0]["recovery"])


def test_a_changed_identity_is_never_probed_back(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 2)
    real = mechanisms.digest
    monkeypatch.setattr(mechanisms, "digest", lambda dist, prefixes: ("0" * 64, real(dist, prefixes)[1]))
    with Body(home, clock=clock) as body:                       # restart: pinned files changed
        assert body.registry.state[NX] == "QUARANTINED"
        clock.advance(48 * 3600)
        ticks(body, clock, 2)
        assert not probes(body) and body.registry.state[NX] == "QUARANTINED"


def test_an_engine_recovers_before_the_construction_built_on_it(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compiled_question(problem_id="staff-r", data=STAFFING, allow_construction=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        [composed] = [c for c in body.registry.manifests if c.startswith("composed.")]
        assert body.registry.state[composed] == "ATTACHED"
        honest, _ = lose_every_engine(body, clock, monkeypatch, n=10)
        assert body.registry.state[composed] == "QUARANTINED" and body.registry.state[NX] == "QUARANTINED"
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", honest["networkx.max_flow"])
        clock.advance(31 * 60)
        result = ticks(body, clock, 3)
        order = [p["capability_id"] for p in probes(body)]
        assert order == [NX, composed] and all(p["passed"] for p in probes(body))   # engine first, same pass
        assert [r["capability_id"] for r in result[0]["recovery"] if r["result"] == "recovered"] == [NX, composed]
        assert body.registry.state[NX] == "ATTACHED" and body.registry.state[composed] == "ATTACHED"
        engine_attach = [e.payload["by"] for e in body.journal.replay("capability.state")
                         if e.payload["capability_id"] == NX and e.payload["state"] == "ATTACHED"][-1]
        assert engine_attach.endswith("engine of " + composed)     # the exact pinned engine, under the same scope
        clock.advance(61 * 60)                                      # the mission re-observes at its own cadence
        assert "ACHIEVED" in states(ticks(body, clock, 2))


def test_without_a_signed_scope_a_recovered_capability_waits_for_the_founder(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW)))         # no auto_attach signed
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        assert body.registry.state[NX] == "VERIFIED"
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": NX}))       # the founder attaches
    with Body(home, clock=clock) as body:
        body.boot()
        honest, _ = lose_every_engine(body, clock, monkeypatch)   # the attach lands, then the engine lies
        attaches = [e.payload["by"] for e in body.journal.replay("capability.state")
                    if e.payload["capability_id"] == NX and e.payload["state"] == "ATTACHED"]
        assert attaches and "auto_attach" not in attaches[0]
        assert body.registry.state[NX] == "QUARANTINED"
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", honest["networkx.max_flow"])
        clock.advance(16 * 60)
        ticks(body, clock, 3)
        assert [p["passed"] for p in probes(body)] == [True]
        assert body.registry.state[NX] == "VERIFIED"              # eligible again, never re-attached by itself
        mission = next(iter(body.engine.book.missions.values()))
        asks = [e.payload for e in body.journal.replay("decision.requested")
                if e.payload["mission_id"] == mission.mission_id and e.payload["kind"] == "CAPABILITY_ATTACH"]
        named = {c["capability_id"]: c["state"] for c in asks[-1]["evidence"]["registered"]}
        assert named.get(NX) == "VERIFIED"                        # the founder is asked, with the probe on record


def test_a_reescalation_after_a_founder_attach_is_recorded_and_the_body_keeps_running(tmp_path, monkeypatch):
    """Pre-existing defect (reproduced on #173's head bd47242): the identical re-block after an unblock was
    deduplicated into the old block, the mission looked unblocked, re-entered Genesis on its open deficit,
    and the ledger refused the repeated qualification fact, crashing every later tick."""
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": NX}))
    with Body(home, clock=clock) as body:
        body.boot()
        lose_every_engine(body, clock, monkeypatch)            # must not raise
        mission = next(iter(body.engine.book.missions.values()))
        assert mission.blocker and mission.blocker["type"] == "capability"
        blocks = [e for e in body.journal.replay("mission.blocked") if e.payload["mission_id"] == mission.mission_id]
        assert len(blocks) >= 2                                  # the second, identical block is its own fact
        ticks(body, clock, 3)                                    # the body keeps ticking


def test_genesis_reuses_a_recorded_qualification_on_the_same_open_deficit(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", lie("networkx.max_flow"))
    monkeypatch.setitem(network.RUNNERS, "scipy.max_flow", lie("scipy.max_flow"))
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        mission = next(iter(body.engine.book.missions.values()))
        before = len(body.journal.replay("genesis.verified"))
        assert body.genesis.resolve(mission=mission, function="graph.max_flow", purpose="again", now=clock()) is None
        assert len(body.journal.replay("genesis.verified")) == before   # nothing re-run, nothing re-recorded
        results = [e.payload["result"] for e in body.journal.replay("genesis.route")]
        assert sum("recorded; not re-run" in r for r in results) == 2   # both engines' recorded failures reused


def test_the_recovery_mechanism_card_is_complete():
    import json
    from pathlib import Path
    from greg.recombine import CARD_FIELDS
    card = json.loads((Path(__file__).resolve().parents[2] / "docs/mechanisms/MC-0002-governed-half-open-recovery.json")
                      .read_text())
    assert all(card.get(field) for field in CARD_FIELDS)
    assert "ev_bda547f2" in card["evidence_and_uncertainties"]


@pytest.mark.parametrize("outage", ["timeout", "isolation_unavailable"])
def test_an_outage_is_not_a_capability_fault_and_opens_no_deficit(tmp_path, monkeypatch, outage):
    """Gap map (Defect 2, rank 1): the host, not the capability, failed. A package-runner timeout or the
    host's network isolation being unavailable used to read as a capability fault (by message), so a
    working capability was quarantined, a new deficit generation opened, the flapping count grew and
    build budget could be spent. The failure is now typed where it is raised; an outage never
    quarantines or re-forms anything."""
    import subprocess
    from greg.capabilities import CapabilityError
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        assert body.registry.state[NX] == "ATTACHED"
        deficits = len(body.journal.replay("deficit.opened"))

        def down(argv, **kw):
            if outage == "timeout":
                raise subprocess.TimeoutExpired(argv, kw.get("timeout", 1))
            raise CapabilityError("network isolation unavailable; command refused", failure_class="transient")

        monkeypatch.setattr(mechanisms, "run_isolated", down)
        ticks(body, clock, 8)
        assert body.registry.state[NX] == "ATTACHED"
        assert not [e for e in body.journal.replay("capability.state")
                    if e.payload.get("capability_id") == NX and e.payload.get("state") == "QUARANTINED"]
        assert len(body.journal.replay("deficit.opened")) == deficits
        classes = {e.payload.get("failure_class") for e in body.journal.replay("mission.observed")
                   if not e.payload.get("passed") and e.payload.get("failure_class")}
        assert classes == {"transient"}
