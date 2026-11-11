"""A retained Gate receipt is reported as the call that produced it reported it, whenever it is asked about.

Found by an adversarial review of #290/#291 and confirmed by a skeptic; the defect predates both (it is on #196's
8d205324). ``AuthorityOffice.act`` answered DONE for any retained receipt of the same proposal without reading the
receipt's result. A capability that refused or failed leaves a negative receipt, and the first call answers REFUSED;
a body stopped between that receipt and the mission's record of it asked the same proposal again after the restart
and was told DONE:

- a signed compensation its capability refused was on the record as DONE, and the COMPENSATION ask never reached
  the founder;
- a read its capability refused passed an ``absent`` check, and the mission was recorded achieved.

Every test here but one (``test_only_a_positive_result_is_done``, which reads result shapes with no body) runs on a
real Body and crosses a real restart: the Body is closed and opened again on the same home, in this process. ``Killed``
stands in for SIGKILL: a BaseException nothing in the body handles. No test here kills a real process. The founder
key is a per-test Ed25519 key, not Alfonso's; ``test.probe`` and the interrupted worker are test doubles, said where
they are used.

Three more defects of the same family were found while checking every consumer of the outcome, and are covered here:
a body stopped between a refused compensation's record and its question lost the question; a recovered receipt of an
interrupted worker was recorded DONE with its signed cap booked as spent; and a retained refusal under the earlier
scope form lost its reason and failure class. Three tests pass before this change and pin what it must not alter (a
reused success, a reused success under the earlier scope form, a refused strategy recovered after a kill). A fourth
was measured first and marked as a strict expected failure, then fixed: a dispatch the Gate held and the body never
recorded was settled only on a live mission, so one the founder ended before the restart lost it (the last three
tests).
"""
from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace

import pytest

from greg import capabilities, templates
from greg.authority import ActionOutcome, AuthorityOffice
from greg.body import Body, Layout
from greg.capabilities import CapabilityError, CapabilityManifest, InvocationContext
from greg.lightcone import LightCone
from greg.missions import MissionEngine
from tests.greg_fixtures import (Clock, drop, horizon, make_body, mission, note_check, signed, workspace,
                                 write_strategy)

MID = "m:retained"
PROBE = "test.probe"
REUSED = "retained receipt reused after restart"


class Killed(BaseException):
    """SIGKILL, as far as the body can tell: nothing after it runs."""


def probe_body(adapter):
    """A Body with one more ATTACHED read-only capability, ``test.probe``, run by ``adapter`` (a test double)."""
    class ProbeBody(Body):
        def open(self):
            super().open()
            self.registry.register(CapabilityManifest(
                capability_id=PROBE, version="1.0.0", provider="test", function=PROBE,
                description="does what the test says", route="api", consequence_class="read_only",
                inputs={"probe": "str"}, outputs={"text": "str"}, strengthens=("proof",), target_prefix="probe:",
                retry_safe=False), adapter, state="ATTACHED")
            return self
    return ProbeBody


def act(body, home, data, *, capability, params, target, cost=0.0, budget=0.0, attempt="same"):
    """One direct call of the body's own office, with the capability's registered manifest and adapter."""
    manifest = body.registry.manifests[capability]
    cone = LightCone(capabilities=frozenset({capability}), targets=("fs:*", "probe:*"),
                     max_consequence_class="read_only", budget_usd=budget, horizon=horizon())
    ctx = InvocationContext(workspace=workspace(home, MID), read_roots=(data,), secrets=body.secrets,
                            manifest=manifest, journal=body.journal, artifact_root=body.layout.artifacts)
    return body.office.act(mission_id=MID, cone=cone, command_digest="sha256:" + "0" * 64, manifest=manifest,
                           adapter=body.registry.adapters[capability], ctx=ctx, params=params, target=target,
                           cost_usd=cost, expected_outcome="observation captured", evidence_refs=[], attempt=attempt,
                           spent_usd=0.0, approved_scopes=set())


def gate_records(body, outcome) -> dict:
    """What the Gate and the office kept for this one proposal: its dispatch claims, receipts and issued grants."""
    claims = [r for r in body.ledger.by_type("grant_dispatch") if r.payload["proposal_id"] == outcome.proposal_id]
    grants = {c.payload["grant_id"] for c in claims}
    return {"dispatch_claims": len(claims),
            "receipts": sorted(r.hash for r in body.ledger.by_type("receipt") if r.payload["grant_id"] in grants),
            "grants_issued": len([r for r in body.ledger.by_type("event")
                                  if r.payload.get("type") == "greg.authority.grant_issued"
                                  and r.payload.get("proposal_id") == outcome.proposal_id])}


# -- the office, called directly -------------------------------------------------------------------------------

def test_a_refused_read_asked_again_after_a_restart_is_the_same_refusal(tmp_path):
    """The built-in fs.read refuses a path outside the read roots: a negative receipt, REFUSED. The same act asked
    again by the restarted body is that refusal, field for field, with the same receipt and no second dispatch.
    Before: DONE, "retained receipt reused after restart"."""
    home, _, _, data = make_body(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("not in the read roots")
    kw = dict(capability="fs.read", params={"path": str(outside)}, target="fs:outside.txt")
    with Body(home) as body:
        first = act(body, home, data, **kw)
        receipt = body.ledger.find(first.receipt_hash)
        kept = gate_records(body, first)
    assert first.status == "REFUSED" and receipt.payload["result"]["result_class"] == "negative"
    assert first.reasons == [receipt.payload["result"]["observed_outcome"]]
    assert kept == {"dispatch_claims": 1, "receipts": [first.receipt_hash], "grants_issued": 1}
    with Body(home) as body:                       # the restart
        again = act(body, home, data, **kw)
        after = gate_records(body, again)
    assert again.status == "REFUSED", "a retained refusal was reported " + again.status
    assert again.receipt_hash == first.receipt_hash and again.output is None and again.cost_usd == 0.0
    assert asdict(again) == asdict(first)
    assert after == kept, "no second dispatch, receipt or grant"


@pytest.mark.parametrize("failure_class", [None, "executor_error", "transient"])
def test_a_retained_refusal_keeps_its_reason_and_its_failure_class(tmp_path, failure_class):
    """The failure class decides what the mission does next (Genesis re-forms a capability only for
    ``executor_error``), so a retained refusal keeps the one its capability raised."""
    calls = []

    def fails(params, ctx):
        calls.append(ctx.grant_id)
        raise CapabilityError("probe exited 3", failure_class=failure_class)
    home, _, _, data = make_body(tmp_path)
    ProbeBody = probe_body(fails)
    kw = dict(capability=PROBE, params={"probe": "once"}, target="probe:x")
    with ProbeBody(home) as body:
        first = act(body, home, data, **kw)
    with ProbeBody(home) as body:
        again = act(body, home, data, **kw)
        after = gate_records(body, again)
    assert (first.status, first.reasons, first.failure_class) == (
        "REFUSED", ["capability refused: probe exited 3"], failure_class)
    assert asdict(again) == asdict(first)
    assert len(calls) == 1 and after == {"dispatch_claims": 1, "receipts": [first.receipt_hash], "grants_issued": 1}


def test_a_positive_retained_receipt_is_still_done_with_the_output_and_cost_it_had(tmp_path):
    """Unchanged: a completed action is reused, never redone, with the output its receipt kept (the cut form and the
    whole output in the artifact store) and the cost the action was signed at."""
    calls = []

    def answers(params, ctx):
        calls.append(ctx.grant_id)
        return {"text": "long " * 8000, "probe": params["probe"]}
    home, _, _, data = make_body(tmp_path)
    ProbeBody = probe_body(answers)
    kw = dict(capability=PROBE, params={"probe": "once"}, target="probe:x", cost=0.25, budget=1.0)
    with ProbeBody(home) as body:
        first = act(body, home, data, **kw)
    with ProbeBody(home) as body:
        again = act(body, home, data, **kw)
        after = gate_records(body, again)
    assert (first.status, first.reasons, first.cost_usd) == ("DONE", [], 0.25)
    assert first.output["probe"] == "once" and first.output["text"]["truncated"] and first.output_artifact["address"]
    assert asdict(again) == {**asdict(first), "reasons": [REUSED]}
    assert len(calls) == 1 and after == {"dispatch_claims": 1, "receipts": [first.receipt_hash], "grants_issued": 1}


@pytest.mark.parametrize("refuses", [True, False])
def test_a_retained_receipt_under_the_earlier_scope_form_is_read_the_same_way(tmp_path, monkeypatch, refuses):
    """A paid scope once left the mission's spend state out (before #157). A receipt retained under that form is
    found again by its legacy proposal and never redispatched; a refusal among them keeps its own reason and failure
    class (it was reported as "retained legacy receipt; no redispatch", with neither), and a completed one is DONE
    as before. This branch had no test."""
    calls = []

    def adapter(params, ctx):
        calls.append(ctx.grant_id)
        if refuses:
            raise CapabilityError("probe exited 3", failure_class="executor_error")
        return {"text": "answered"}
    home, _, _, data = make_body(tmp_path)
    ProbeBody = probe_body(adapter)
    kw = dict(capability=PROBE, params={"probe": "once"}, target="probe:x", cost=0.25, budget=1.0)
    current = AuthorityOffice.scope_digest
    monkeypatch.setattr(AuthorityOffice, "scope_digest", staticmethod(lambda **k: current(
        **{name: value for name, value in k.items() if name not in ("spent_usd", "budget_usd")})))
    with ProbeBody(home) as body:                  # the body as it ran under the earlier scope form
        first = act(body, home, data, **kw)
    monkeypatch.undo()
    with ProbeBody(home) as body:
        again = act(body, home, data, **kw)
        after = gate_records(body, again)
    assert first.scope_digest == current(mission_id=MID, capability_id=PROBE, params={"probe": "once"},
                                         target="probe:x", consequence_class="read_only", cost_usd=0.25)
    assert again.proposal_id == first.proposal_id and again.scope_digest == first.scope_digest
    if refuses:
        assert (first.status, first.failure_class) == ("REFUSED", "executor_error")
        assert asdict(again) == asdict(first)
    else:
        assert first.status == "DONE"
        assert asdict(again) == {**asdict(first), "reasons": ["retained legacy receipt; no redispatch"]}
    assert len(calls) == 1 and after == {"dispatch_claims": 1, "receipts": [first.receipt_hash], "grants_issued": 1}


UNKNOWN = "the receipt does not say whether the capability acted (result class {!r}); its outcome is unknown and " \
          "must be reconciled"


@pytest.mark.parametrize("result, status, reasons", [
    ({"result_class": "positive", "output": {"n": 1}, "observed_outcome": "observation captured"}, "DONE", []),
    ({"result_class": "negative", "observed_outcome": "capability refused: no"}, "REFUSED", ["capability refused: no"]),
    ({"result_class": "negative"}, "REFUSED", ["capability failed"]),
    # the three other classes of contracts/outcome.schema.json, which this office's executor never writes
    ({"result_class": "inconclusive", "observed_outcome": "half done"}, "UNCERTAIN", [UNKNOWN.format("inconclusive")]),
    ({"result_class": "zero_response", "output": {"n": 1}}, "UNCERTAIN", [UNKNOWN.format("zero_response")]),
    ({"result_class": "harm", "observed_outcome": "it broke something"}, "UNCERTAIN", [UNKNOWN.format("harm")]),
    # missing and malformed
    ({"observed_outcome": "no class recorded", "output": {"n": 1}}, "UNCERTAIN", [UNKNOWN.format(None)]),
    ({"result_class": "POSITIVE", "output": {"n": 1}}, "UNCERTAIN", [UNKNOWN.format("POSITIVE")]),
    ({"result_class": ["positive"]}, "UNCERTAIN", [UNKNOWN.format(["positive"])]),
    ({}, "UNCERTAIN", [UNKNOWN.format(None)]),
    (None, "UNCERTAIN", [UNKNOWN.format(None)]),
    ("positive", "UNCERTAIN", [UNKNOWN.format(None)]),
    (["result_class", "positive"], "UNCERTAIN", [UNKNOWN.format(None)]),
])
def test_a_receipt_is_read_by_its_result_class_and_an_unreadable_one_is_unknown(result, status, reasons):
    """The one reading of a receipt. Positive is done; negative is the capability's refusal; anything else does not
    say whether the capability acted, so it is neither: it is unknown, with nothing booked and no output passed on.
    (Read as a refusal, the mission would try the action again and could repeat an effect that already happened.)"""
    receipt = SimpleNamespace(hash="sha256:" + "a" * 64, payload={"grant_id": "g", "result": result})
    out = AuthorityOffice.outcome_of(receipt, cost_usd=2.0, proposal_id="p", scope_digest="s")
    assert out == ActionOutcome(status, reasons, "p", "s", output={"n": 1} if status == "DONE" else None,
                                receipt_hash=receipt.hash, grant_id="g", cost_usd=2.0 if status == "DONE" else 0.0)


# -- through the mission engine --------------------------------------------------------------------------------

def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind, mid):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


def kill_once(monkeypatch, method: str):
    """The body dies the first time the engine reaches ``method``; the restarted body runs it normally."""
    real, armed = getattr(MissionEngine, method), {"on": True}

    def dies(self, *args, **kwargs):
        if armed["on"]:
            armed["on"] = False
            raise Killed(f"SIGKILL at {method}")
        return real(self, *args, **kwargs)
    monkeypatch.setattr(MissionEngine, method, dies)


def kill_before_record(body, kind: str):
    """This body dies when it is about to record ``kind``: whatever the Gate kept before that is retained."""
    record = body.journal.record

    def dies(name, data, **kw):
        if name == kind:
            raise Killed(f"SIGKILL before {kind}")
        return record(name, data, **kw)
    body.journal.record = dies


# a signed compensation the fs.write adapter refuses: its path does not name its signed target
BROKEN = {"capability": "fs.write", "params": {"relative_path": "other.txt", "content": "original"},
          "target": "workspace:note.txt"}
BROKEN_REASON = "capability refused: write path 'workspace:other.txt' does not match the signed target " \
                "'workspace:note.txt'"


def compensation_run(tmp, monkeypatch, kill: str | None) -> dict:
    """An executed write whose mission is abandoned, and whose signed compensation the capability refuses. ``kill``:
    the body dies before it records the compensation ("record": the Gate's negative receipt is retained), or between
    that record and its question to the founder ("ask"); then it restarts. Returns what the body ends with."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    mid = "m:compensate-refused"
    note = workspace(home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    spec = mission(mid, checks=[note_check("c", note, "final")],
                   strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=BROKEN)],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        assert note.read_text() == "draft"
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "ABANDONED", "reason": "not wanted"}))
        if kill == "record":
            kill_before_record(body, "mission.compensated")
        elif kill == "ask":
            kill_once(monkeypatch, "_compensation_ask")
        if kill is None:
            tick(body, clock, 3)
        else:
            with pytest.raises(Killed):
                tick(body, clock, 3)
            negative = [r for r in body.ledger.by_type("receipt") if r.payload["result"]["result_class"] == "negative"]
            assert len(negative) == 1                           # the Gate kept the capability's refusal
            assert len(facts(body, "mission.compensated", mid)) == (0 if kill == "record" else 1)
            assert "COMPENSATION" not in [r["kind"] for r in body.engine.book.open_requests()]
    with Body(home, clock=clock) as body:                       # the restart (the control simply runs on)
        tick(body, clock, 3)
        done = facts(body, "mission.compensated", mid)
        asked = [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        return {"compensated": [(c["status"], c["reasons"], body.ledger.find(c["receipt"]).payload["result"][
                    "result_class"]) for c in done],
                "asked_about": [(r["action_id"], r["evidence"]["compensation_failed"]) for r in asked],
                "open_asks": sorted(r["kind"] for r in body.engine.book.open_requests()),
                "note": note.read_text(), "status": body.engine.book.missions[mid].status,
                "dispatch_claims": len(body.ledger.by_type("grant_dispatch")),
                "receipts": len(body.ledger.by_type("receipt"))}


@pytest.mark.parametrize("kill", ["record", "ask"])
def test_a_refused_compensation_ends_the_same_and_reaches_the_founder_whenever_the_body_is_killed(
        tmp_path, monkeypatch, kill):
    """The reviewer's case ("record") and the second window found beside it ("ask"). Before: killed before the
    record, the restarted body recorded the compensation DONE over the Gate's negative receipt and asked nobody;
    killed after it, the record stayed REFUSED and the question was never asked."""
    control = compensation_run(tmp_path / "control", monkeypatch, None)
    assert control["compensated"] == [("REFUSED", [BROKEN_REASON], "negative")]
    assert control["asked_about"] == [("w", [BROKEN_REASON])] and control["note"] == "draft"
    killed = compensation_run(tmp_path / "killed", monkeypatch, kill)
    assert [c[0] for c in killed["compensated"]] != ["DONE"], "a compensation the capability refused is recorded DONE"
    assert killed["asked_about"], "the founder is never asked about the effect the refused compensation left"
    assert killed == control


def sensor_run(tmp, kill: bool, typed: bool = False) -> dict:
    """A mission whose one check passes when its reading has no ``error`` field, and whose sensor refuses: the
    built-in fs.read of a path outside the read roots, or (``typed``) the ``test.probe`` double raising a typed
    failure. ``kill``: the body dies between the Gate's receipt of that refusal and the observation's record, and
    restarts at the same clock instant (a frozen or stepped-back clock: an observation's attempt is its count and
    its time, so the same proposal is asked again)."""
    def fails(params, ctx):
        raise CapabilityError("probe exited 3", failure_class="executor_error")
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    outside = tmp / "outside.txt"
    outside.write_text("nothing here says error")
    mid = "m:refused-read"
    sensor = {"capability": PROBE, "params": {"probe": "once"}, "target": "probe:x"} if typed else \
        {"capability": "fs.read", "params": {"path": str(outside)}, "target": "fs:outside.txt"}
    check = {"check_id": "c", "description": "the reading reports no error", "sensor": sensor,
             "predicate": {"op": "absent", "field": "error"}}
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[check], strategies=[write_strategy("w", "w.txt", "x", ["c"])],
        capabilities=["fs.read", "fs.write", PROBE], targets=("fs:*", "workspace:*", "probe:*"))))
    TheBody, clock = probe_body(fails), Clock()
    if kill:
        with TheBody(home, clock=clock) as body:
            kill_before_record(body, "mission.observed")
            with pytest.raises(Killed):
                body.tick()
            assert [r.payload["result"]["result_class"] for r in body.ledger.by_type("receipt")] == ["negative"]
            assert not facts(body, "mission.observed", mid)
    with TheBody(home, clock=clock) as body:                    # the restart, at the same instant
        body.tick()
        first = {"observed": [(o["passed"], o["detail"].replace(str(tmp), "<tmp>"), o.get("failure_class"))
                              for o in facts(body, "mission.observed", mid)],
                 "achieved": len(facts(body, "mission.achieved", mid)),
                 "dispatch_claims": len(body.ledger.by_type("grant_dispatch")),
                 "grants_issued": len([r for r in body.ledger.by_type("event")
                                       if r.payload.get("type") == "greg.authority.grant_issued"]),
                 "receipts": [r.payload["result"]["result_class"] for r in body.ledger.by_type("receipt")]}
        clock.advance(1)
        tick(body, clock, 2)
        return {"first_tick": first, "status": body.engine.book.missions[mid].status,
                "achieved": len(facts(body, "mission.achieved", mid)),
                "actions": [(a["action_id"], a["status"]) for a in facts(body, "mission.action", mid)],
                "open_asks": sorted(r["kind"] for r in body.engine.book.open_requests())}


@pytest.mark.parametrize("typed, observed", [
    (False, (False, "sensor REFUSED: capability refused: path <tmp>/outside.txt outside permitted roots", None)),
    (True, (False, "sensor REFUSED: capability refused: probe exited 3", "executor_error")),
])
def test_a_refused_read_reused_after_a_restart_passes_no_check_and_closes_no_mission(tmp_path, typed, observed):
    """Before: the reused refusal was DONE with no output, ``absent`` passed on it, and the mission was recorded
    achieved on a reading its capability had refused. The observation also keeps the refusal's failure class, which
    is what the engine's self-repair counts."""
    control = sensor_run(tmp_path / "control", False, typed)
    assert control["first_tick"] == {"observed": [observed], "achieved": 0, "dispatch_claims": 1, "grants_issued": 1,
                                     "receipts": ["negative"]}
    assert control["achieved"] == 0
    killed = sensor_run(tmp_path / "killed", True, typed)
    assert killed["first_tick"]["observed"][0][0] is False, "a refused read is recorded as a passing observation"
    assert killed["achieved"] == 0 and killed["status"] != "ACHIEVED"
    assert killed == control


def strategy_run(tmp, kill: bool) -> dict:
    """A strategy its capability refuses (the write names another path than its signed target). ``kill``: the body
    dies between the Gate's negative receipt and the action's record; the restarted body settles the dispatch from
    the Gate's own record before anything else."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    mid = "m:refused-write"
    note = workspace(home, mid) / "note.txt"
    refused = {**write_strategy("w", "note.txt", "draft", ["c"]),
               "params": {"relative_path": "other.txt", "content": "draft"}}
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("c", note, "draft")], strategies=[refused], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        if kill:
            kill_before_record(body, "mission.action")
            with pytest.raises(Killed):
                tick(body, clock, 3)
            assert not facts(body, "mission.action", mid)
        else:
            tick(body, clock, 3)
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        return {"actions": [(a["action_id"], a["attempt"], a["status"], a["reasons"], a["cost_usd"])
                            for a in facts(body, "mission.action", mid)],
                "written": note.exists(), "status": body.engine.book.missions[mid].status,
                "open_asks": sorted(r["kind"] for r in body.engine.book.open_requests()),
                "negative_receipts": len([r for r in body.ledger.by_type("receipt")
                                          if r.payload["result"]["result_class"] == "negative"])}


def test_a_refused_strategy_recovered_after_a_kill_is_recorded_as_the_refusal_it_was(tmp_path):
    """Already right before this change (the recovery read the result itself); now read by the office's one function,
    so this pins that the recovered record equals the unkilled one."""
    control = strategy_run(tmp_path / "control", False)
    assert control["actions"] == [("w", 0, "REFUSED", [
        "capability refused: write path 'workspace:other.txt' does not match the signed target 'workspace:note.txt'"],
        0.0)]
    assert control["negative_receipts"] == 1 and not control["written"]
    assert strategy_run(tmp_path / "killed", True) == control


def worker_run(tmp, monkeypatch, kill: bool) -> dict:
    """A commissioned worker that was interrupted: its adapter returns its GREG-collected summary with status
    UNCERTAIN, and the Gate keeps a positive receipt of that collection. The adapter here is a test double returning
    that summary shape (the real one needs a provider and the worker envelope). ``kill``: the body dies between that
    receipt and the action's record."""
    calls = []

    def interrupted(params, ctx):
        calls.append(ctx.grant_id)
        return {"status": "UNCERTAIN", "work_order": params["order"], "worker": {"interrupted": True, "cost_usd": None},
                "spend": {"status": "unknown", "reserved_usd": 1.0}}
    manifest, _ = capabilities.BUILTINS["worker.commission"]
    monkeypatch.setitem(capabilities.BUILTINS, "worker.commission", (manifest, interrupted))
    data = tmp / "data"
    (data / "repo").mkdir(parents=True)
    home, key, body_id, _ = make_body(tmp, read_roots=[data])
    spec = templates.code_change(repo=str(data / "repo"), objective="interrupted work", order="o1", provider="script",
                                 allowed_paths=["pkg/*"], budget_usd=1.0, workspace_root=Layout(home).workspace)
    mid = spec["mission_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        if kill:
            kill_before_record(body, "mission.action")
            with pytest.raises(Killed):
                tick(body, clock, 2)
            kept = [(r.payload["result"]["result_class"], r.payload["result"]["output"].get("status"))
                    for r in body.ledger.by_type("receipt") if isinstance(r.payload["result"].get("output"), dict)]
            assert ("positive", "UNCERTAIN") in kept and not facts(body, "mission.action", mid)
        else:
            tick(body, clock, 2)
    with Body(home, clock=clock) as body:
        tick(body, clock, 2)
        state = body.engine.book.missions[mid]
        return {"actions": [(a["action_id"], a["status"], a["cost_usd"], a.get("reserved_usd"), a["reasons"])
                            for a in facts(body, "mission.action", mid)],
                "spent_usd": state.spent_usd, "reserved_usd": state.reserved_usd,
                "blocker": (state.blocker or {}).get("type"),
                "open_asks": sorted(r["kind"] for r in body.engine.book.open_requests()), "worker_runs": len(calls)}


def test_an_interrupted_workers_receipt_recovered_after_a_kill_is_reconciled_not_recorded_done(tmp_path, monkeypatch):
    """The same mistake in the engine's own recovery: the receipt is positive (collection completed), but what it
    says is that the worker was interrupted. The dispatch read that; the recovery did not. Before: the restarted body
    recorded the action DONE, booked the signed $1.00 as spent and asked for no reconciliation."""
    control = worker_run(tmp_path / "control", monkeypatch, False)
    assert control["actions"] == [("commission-worker", "UNCERTAIN", 0.0, 1.0, [
        "worker execution interrupted; partial outcome and spend require reconciliation"])]
    assert (control["spent_usd"], control["reserved_usd"], control["blocker"]) == (0.0, 1.0, "reconciliation")
    assert control["open_asks"] == ["RECONCILIATION"] and control["worker_runs"] == 1
    killed = worker_run(tmp_path / "killed", monkeypatch, True)
    assert [a[1] for a in killed["actions"]] != ["DONE"], "an interrupted worker's receipt is recorded as DONE"
    assert killed == control


# -- a mission the founder ends before the restarted body steps it ----------------------------------------------

def ended_run(tmp, how: str) -> dict:
    """A body dies with a dispatch the Gate holds and the mission never recorded; the founder abandons the mission
    while the body is down; the body restarts. ``how``: "written" (the write ran and the Gate receipted it),
    "refused" (the capability refused it: a negative receipt) or "unknown" (the body died inside the adapter: a
    dispatch claim and no receipt). Returns what the restarted body ends with."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    mid = "m:ended-before-recovery"
    note = workspace(home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    strategy = write_strategy("w", "note.txt", "draft", ["c"])
    if how == "refused":
        strategy = {**strategy, "params": {"relative_path": "other.txt", "content": "draft"}}
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("c", note, "final")], strategies=[strategy], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        if how == "unknown":
            def dies(params, ctx):
                raise Killed("SIGKILL inside the adapter")
            body.registry.adapters["fs.write"] = dies
        else:
            kill_before_record(body, "mission.action")
        with pytest.raises(Killed):
            tick(body, clock, 3)
        assert not facts(body, "mission.action", mid)
        [intent] = facts(body, "mission.dispatching", mid)
    drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "ABANDONED", "reason": "not wanted"}))
    with Body(home, clock=clock) as body:
        writes = []
        real = body.registry.adapters["fs.write"]
        body.registry.adapters["fs.write"] = lambda params, ctx: (writes.append(params), real(params, ctx))[1]
        tick(body, clock, 4)
        state = body.engine.book.missions[mid]
        return {"status": state.status, "note": note.read_text(),
                "actions": [(a["action_id"], a["attempt"], a["status"]) for a in facts(body, "mission.action", mid)],
                "reasons": [a["reasons"] for a in facts(body, "mission.action", mid)],
                "compensation_required": [c["action_id"] for c in facts(body, "mission.compensation_required", mid)],
                "open_asks": sorted(r["kind"] for r in body.engine.book.open_requests()),
                "spent_usd": state.spent_usd, "writes_after_restart": len(writes),
                "claims": len([r for r in body.ledger.by_type("grant_dispatch")
                               if r.payload.get("proposal_id") == intent["proposal_id"]])}


def test_a_receipted_write_the_body_did_not_record_is_accounted_for_when_its_mission_is_ended(tmp_path):
    """Before: the recovery ran only on a live mission, so the executed write was never recorded and never named as
    needing compensation. The ended mission showed no action at all."""
    ended = ended_run(tmp_path / "written", "written")
    assert ended["note"] == "draft"                                   # the write happened and the Gate receipted it
    assert ended["actions"] == [("w", 0, "DONE")]
    assert ended["compensation_required"] == ["w"]
    assert (ended["status"], ended["claims"], ended["writes_after_restart"]) == ("ABANDONED", 1, 0)


def test_a_refusal_the_body_did_not_record_stays_a_refusal_when_its_mission_is_ended(tmp_path):
    """The Gate holds a negative receipt. The ended mission records the refusal it was: nothing ran, so nothing is
    named as needing compensation, nobody is asked, and nothing is dispatched again."""
    ended = ended_run(tmp_path / "refused", "refused")
    assert ended["actions"] == [("w", 0, "REFUSED")]
    assert ended["reasons"] == [["capability refused: write path 'workspace:other.txt' does not match the signed "
                                 "target 'workspace:note.txt'"]]
    assert (ended["compensation_required"], ended["open_asks"], ended["note"]) == ([], [], "original")
    assert (ended["status"], ended["claims"], ended["writes_after_restart"], ended["spent_usd"]) == (
        "ABANDONED", 1, 0, 0.0)


def test_an_unknown_outcome_the_body_did_not_record_is_asked_about_when_its_mission_is_ended(tmp_path):
    """The Gate holds a dispatch claim and no receipt: the body cannot know whether the write ran. The ended mission
    records it UNCERTAIN and asks the founder once. Nothing is undone, and nothing is dispatched again, before the
    founder says what that dispatch did."""
    ended = ended_run(tmp_path / "unknown", "unknown")
    assert ended["actions"] == [("w", 0, "UNCERTAIN")]
    assert ended["open_asks"] == ["RECONCILIATION"]
    assert (ended["compensation_required"], ended["note"]) == ([], "original")
    assert (ended["status"], ended["claims"], ended["writes_after_restart"]) == ("ABANDONED", 1, 0)
