"""Cognition through signed missions, the real Gate, retained receipts and restart."""
import subprocess

import pytest

from greg.body import Body
from greg.cognition.settlement import competence
from tests.greg_fixtures import Clock, drop, make_body, mission, signed


def test_cognition_is_durable_receipted_and_reobserved_on_the_existing_body(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "real:numeric", "operation": "calculate", "data": {"expression": "0.1+0.2"}}
    spec = mission("m:cognition", checks=[{
        "check_id": "exact", "description": "independently checked exact arithmetic",
        "sensor": {"capability": "cognition.solve", "target": "cognition:arithmetic", "params": params},
        "predicate": {"op": "equals", "field": "output.exact", "value": "3/10"}}],
        strategies=[{"action_id": "recompute", "capability": "cognition.solve", "target": "cognition:arithmetic",
                     "params": params, "advances": ["exact"], "rationale": "recompute the exact numerical answer"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        outcome = body.tick()
        assert outcome["missions"][0]["state"] == "ACHIEVED"
        receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
        cognitive = next(r for r in receipts if isinstance(r, dict) and r.get("problem_id") == "real:numeric")
        assert cognitive["method"] == "cognition.exact" and cognitive["authority_created"] is False
        appraised = body.journal.replay("mission.appraised")[-1].payload
        assert appraised["verdict"] == "VERIFIED", appraised
        assert len(competence(body.journal)) == 1
        assert len(body.journal.replay("cognition.settled")) == 1
        from greg.cognition.cells import cells
        cell = cells(body.journal, body.registry)[0]
        assert cell["local_state"]["observed"] == 1 and cell["local_state"]["correct"] == 1
        assert cell["authority_ceiling"] == "read_only"
        cell_id = cell["cell_id"]
        count = len(body.ledger.by_type("receipt"))
    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.ledger.by_type("receipt")) == count
        assert len(body.journal.replay("cognition.settled")) == 1
        assert next(iter(competence(body.journal).values()))["count"] == 1
        assert cells(body.journal, body.registry)[0]["cell_id"] == cell_id
        assert body.office.gate is not None
        body.journal.record("mission.appraised", {"mission_id": "m:cognition", "verdict": "REFUTED", "checks": {}},
                            key="later-independent-refutation")
        assert competence(body.journal) == {} and cells(body.journal, body.registry) == []


def test_detachment_survives_restart_and_solver_cannot_bypass_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.exact"}))
    with Body(home) as body:
        manifest, adapter = body.registry.manifests["cognition.solve"], body.registry.adapters["cognition.solve"]
        from greg.capabilities import InvocationContext
        ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest,
                                target="cognition:test", capability_registry=body.registry)
        out = adapter({"problem_id": "detached", "operation": "calculate", "data": {"expression": "1+1"}}, ctx)
        assert out["abstention_state"] == "CAPABILITY_DEFICIT" and out["output"] is None


def test_console_exposes_scoped_cognitive_result_from_retained_receipt(tmp_path):
    from greg.console import Console, render_home
    home,key,body_id,_=make_body(tmp_path)
    params={"problem_id":"console:exact", "operation":"calculate", "data":{"expression":"2+3"}}
    spec=mission("m:console-cognition", checks=[{"check_id":"sum", "description":"exact sum", "sensor":{"capability":"cognition.solve","target":"cognition:sum","params":params},"predicate":{"op":"equals","field":"output.exact","value":"5"}}],strategies=[],capabilities=["cognition.solve"],targets=("cognition:*",),ceiling="read_only")
    drop(home,signed(key,body_id,"MISSION",spec))
    with Body(home) as body:body.boot();body.tick()
    console=Console(home)
    snapshot=console.snapshot();assert snapshot['cognitive'][0]['method']=='cognition.exact'
    assert snapshot['cognitive'][0]['selection_rationale']
    assert snapshot['cognitive'][0]['proof_class']=='exact_calculation'
    page=render_home(console).decode()
    assert 'console:exact' in page and 'Next permitted step' in page and 'Uncertainty:' in page and 'Evidence:' in page
    assert 'and a Mac body' not in page
    from greg import remote
    from greg.founder import sign_read
    from datetime import datetime, timezone
    import json, pytest
    with pytest.raises(remote.RemoteError):
        remote.handle(home, 'GET', '/api/status', {}, b'')
    now=datetime.now(timezone.utc)
    headers=sign_read(key,body_id=body_id,method='GET',path='/api/status',now=now)
    response=remote.handle(home,'GET','/api/status',headers,b'',now=now)
    data=json.loads(response[2])['data']
    assert data['cognitive'][0]['receipt_id']==snapshot['cognitive'][0]['receipt_id']


def test_a_cognition_deficit_opens_capability_genesis_then_asks_the_founder_once(tmp_path):
    """Directive 2026-10-07 section 24: no fitting intelligence -> Genesis search -> one founder ask."""
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "real:residual", "compile": {"geometry": {"geometry": "optimization",
                                                                      "subgeometry": "unseen_structure"},
                                                         "data": {"mystery_field": 1}}}
    spec = mission("m:residual", checks=[{
        "check_id": "answered", "description": "a competent method answered",
        "sensor": {"capability": "cognition.solve", "target": "cognition:residual", "params": params},
        "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:residual",
                     "params": params, "advances": ["answered"], "rationale": "compile the residual geometry"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        for _ in range(3):
            body.tick()
        state = body.engine.book.missions["m:residual"]
        asks = [e.payload for e in body.journal.replay("decision.requested") if e.payload["mission_id"] == "m:residual"]
        assert state.blocker and state.blocker["type"] == "capability"
        assert state.blocker["function"] == "cognition.optimization:unseen_structure"
        assert [a["kind"] for a in asks] == ["CAPABILITY_ATTACH"]
        done = [e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == "m:residual"]
        assert len(done) == 1 and done[0]["status"] == "DONE"


@pytest.mark.parametrize("first_solve", ["answers", "times_out"])
def test_recombined_native_game_uses_same_gate_appraisal_and_learning_after_restart(tmp_path, monkeypatch, first_solve):
    # A first solve that times out (a cold solver under load) abstains with no verification ("NOT_RUN"); the mission
    # closes on a later solve. The receipt checked below is the one the passing observation was served by, never
    # simply the first receipt for the problem, which was an abstention in that case (acceptance run, 2026-10-16).
    if first_solve == "times_out":
        from greg.cognition import cortex
        real, calls = cortex._numeric, []

        def cold(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired("cognition.game", 1)
            return real(*args, **kwargs)
        monkeypatch.setattr(cortex, "_numeric", cold)
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "qualified:game", "operation": "minimax",
              "data": {"payoffs": [[1, -1], [-1, 1]]}}
    spec = mission("m:native-game", checks=[{
        "check_id": "value", "description": "check encoded minimax value",
        "sensor": {"capability": "cognition.solve", "target": "cognition:game", "params": params},
        "predicate": {"op": "equals", "field": "output.value", "value": 0}}],
        strategies=[{"action_id": "recompute", "capability": "cognition.solve", "target": "cognition:game",
                     "params": params, "advances": ["value"], "rationale": "bounded numeric minimax"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    with Body(home) as body:
        # Non-seed families start withheld (VERIFIED) on every body; the founder attaches them.
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.game"}))
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        # The converged engine acts in one tick and books the achieved closure on the next. Under host
        # load a budget-bounded solve may abstain (TIMEOUT/BUDGET_EXHAUSTED); that observation is
        # inconclusive, the engine backs off and re-observes, and the strategy is never blamed for it.
        for _ in range(6):
            body.tick()
            if body.engine.book.missions["m:native-game"].status == "ACHIEVED":
                break
            clock.advance(31)
        assert body.engine.book.missions["m:native-game"].status == "ACHIEVED"
        assert not [e for e in body.journal.replay("routing.outcome")
                    if e.payload["mission_id"] == "m:native-game"], "an abstaining sensor never books a strategy ineffective"
        [*_, passed] = [e.payload for e in body.journal.replay("mission.observed")
                        if e.payload["mission_id"] == "m:native-game" and e.payload["passed"]]
        cognitive = body.ledger.find(passed["receipt"]).payload["result"]["output"]
        assert cognitive["problem_id"] == "qualified:game"
        assert cognitive["method"] == "cognition.game" and cognitive["method_version"] == "0.3.0"
        assert cognitive["evaluator"] == "greg.cognition.verification/0.3.0"
        assert cognitive["evaluator_result"]["checks"]["independent_minimax_primal_dual"]
        assert cognitive["authority_created"] is False and cognitive["empirical_validity"] == "WORLD_UNVERIFIED"
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
        count = len(body.ledger.by_type("receipt"))
    with Body(home, clock=clock) as body:
        body.boot()
        body.tick()
        assert len(body.ledger.by_type("receipt")) == count
        history = competence(body.journal)
        assert len(history) == 1
        assert next(iter(history))[:2] == ("cognition.game", "0.3.0")


def test_a_compiled_request_settles_the_method_it_executed_and_links_the_compile_receipt(tmp_path):
    """Audit 31.12/31.13: compile receipts never settled, so Layer 5 decisions never fed competence and
    outcome_link stayed empty. The compiler now carries the executed method's own receipt; settlement credits that
    method (never the compiler's label) and the link projection names the outcome for both receipts."""
    from greg.cognition.settlement import receipt_links
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "real:compiled", "compile": {"geometry": {"consequence_class": "read_only"},
                                                         "data": {"expression": "0.1+0.2"}}}
    spec = mission("m:compiled", checks=[{
        "check_id": "exact", "description": "the compiled method's exact answer",
        "sensor": {"capability": "cognition.solve", "target": "cognition:compiled", "params": params},
        "predicate": {"op": "equals", "field": "result.exact", "value": "3/10"}}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:compiled",
                     "params": params, "advances": ["exact"], "rationale": "compile and answer"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        compiled = next(r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                        if (r.payload["result"].get("output") or {}).get("problem_id") == "real:compiled")
        assert compiled["schema"].startswith("greg-competency-compilation/")
        assert compiled["method_or_composition_selected"] == "cognition.exact"
        assert compiled["outcome_link"] is None                         # immutable as issued; the link is projected
        settled = [e.payload for e in body.journal.replay("cognition.settled")]
        assert len(settled) == 1 and settled[0]["method"] == "cognition.exact"
        assert settled[0]["compile_receipt"] == compiled["receipt_id"]
        assert settled[0]["cognitive_receipt"] == compiled["selected_receipt"]["receipt_id"]
        rows = competence(body.journal)
        assert [k[0] for k in rows] == ["cognition.exact"] and next(iter(rows.values()))["correct"] == 1
        links = receipt_links(body.journal)
        assert links[compiled["receipt_id"]]["outcome_link"] == body.journal.replay("cognition.settled")[0].event_id
        assert links[compiled["receipt_id"]]["later_appraisal"] == settled[0]["appraisal_event"]
        assert links[compiled["receipt_id"]] == links[compiled["selected_receipt"]["receipt_id"]]
    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.journal.replay("cognition.settled")) == 1          # restart re-settles nothing
        body.journal.record("mission.appraised", {"mission_id": "m:compiled", "verdict": "REFUTED", "checks": {}},
                            key="later-refutation")
        from greg.cognition.settlement import reconcile
        reconcile(body.journal)
        assert competence(body.journal) == {}
        assert receipt_links(body.journal)[compiled["receipt_id"]]["invalidated"] is True


def test_a_forged_compile_receipt_settles_nothing():
    from greg.cognition.settlement import _compiled
    from greg.cognition.cortex import reason, registry_view
    r = reason({"problem_id": "forge", "compile": {"geometry": {}, "data": {"expression": "1+1"}}},
               registry=registry_view())
    assert _compiled(r) is r
    assert _compiled({**r, "method_or_composition_selected": "cognition.optimization"}) is None   # digest breaks
    swapped = {**r, "selected_receipt": {**r["selected_receipt"], "receipt_id": "sha256:" + "0" * 64}}
    assert _compiled(swapped) is None
    assert _compiled({**r, "authority_created": True}) is None


def test_goal_gravity_pulls_an_unattached_family_with_its_admission_evidence(tmp_path):
    """The Mind connected to the persistent goal: an abstaining receipt becomes one precise founder ask."""
    home, key, body_id, _ = make_body(tmp_path)
    labels = [{"item_id": f"i{i}", "observer_id": f"o{j}", "independence_group": f"g{j}", "label": "a"}
              for i in range(3) for j in range(3)]
    params = {"problem_id": "crowd:labels", "operation": "crowd_label", "data": {"classes": ["a", "b"], "labels": labels}}
    check = {"check_id": "labelled", "description": "crowd labels aggregated",
             "sensor": {"capability": "cognition.solve", "target": "cognition:crowd", "params": params},
             "predicate": {"op": "equals", "field": "output.labels.i0", "value": "a"}}
    spec = mission("m:crowd", checks=[check], strategies=[{
        "action_id": "aggregate", "capability": "cognition.solve", "target": "cognition:crowd", "params": params,
        "advances": ["labelled"], "rationale": "aggregate the observers' labels"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        body.tick()
        asks = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]
        assert len(asks) == 1, asks
        ask = asks[0]
        assert "greg attach cognition.crowd" in ask["recommendation"]
        family = next(f for f in ask["evidence"]["families"] if f["capability"] == "cognition.crowd")
        assert family["layer"] == 2 and family["admission"]
        assert ask["authority_requested"]["spend"] == "none requested"
        assert not body.registry.usable("cognition.crowd")[0]           # asking attached nothing
        body.tick()
        assert len([e for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]) == 1
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.crowd"}))
        outcome = body.tick()
        assert outcome["missions"][0]["state"] == "ACHIEVED", outcome




def test_a_re_digested_compile_receipt_must_list_its_selected_receipt():
    """Review 2026-10-14: no test pinned the 'selected receipt is one of intermediate_receipts' check (the swapped
    case above is caught by the digest). A compile receipt re-digested after its intermediate receipts were
    rewritten keeps a valid identity and still names a selected receipt it never ran: it settles nothing."""
    from greg.cognition.contracts import digest
    from greg.cognition.settlement import _compiled
    from greg.cognition.cortex import reason, registry_view
    r = reason({"problem_id": "listed", "compile": {"geometry": {}, "data": {"expression": "1+1"}}},
               registry=registry_view())
    body = {k: v for k, v in r.items() if k != "receipt_id"}
    body["intermediate_receipts"] = ["sha256:" + "1" * 64]
    unlisted = {**body, "receipt_id": digest(body)}
    assert _compiled(unlisted) is None
    body["intermediate_receipts"] = list(r["intermediate_receipts"])     # control: listed again, it settles
    assert _compiled({**body, "receipt_id": digest(body)}) is not None


def test_a_world_unverified_compile_settles_no_competence_although_its_organ_answered(tmp_path):
    """Review 2026-10-14: a high-consequence compile that runs a cortex organ ends WORLD_UNVERIFIED while the
    organ's own receipt answered NONE and verified. Only the compile-state check keeps that conditional result out
    of settlement, and no test pinned it. The mission is achieved and appraised; nothing is credited.

    Cortex 0.2.2 forwards the compile's declared class to the organ, so a financial class now escalates there and
    the organ no longer answers. The case this test pins (the compile conditional, its organ answered) is a high
    harm the cortex's own rule does not raise to a class: a reputation harm of 0.6 under internal_write."""
    from greg.cognition.contracts import digest
    from greg.cognition.settlement import _compiled, measured_outcomes
    saas = {"target": {"name": "spend", "unit": "USD/year"},
            "variables": [{"name": "seats", "unit": "count", "low": 40, "high": 80},
                          {"name": "price", "unit": "USD/count/month", "low": 20, "high": 35}],
            "expression": ["*", "seats", "price"]}
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "real:conditional", "compile": {"geometry": {"consequence_class": "internal_write"},
                                                            "data": {"estimation_model": saas},
                                                            "consequence": {"reputation": 0.6}}}
    spec = mission("m:conditional", checks=[{
        "check_id": "conditional", "description": "the compiled estimate is a conditional result",
        "sensor": {"capability": "cognition.solve", "target": "cognition:conditional", "params": params},
        "predicate": {"op": "equals", "field": "state", "value": "WORLD_UNVERIFIED"}}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:conditional",
                     "params": params, "advances": ["conditional"], "rationale": "compile the estimate"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        compiled = next(r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                        if (r.payload["result"].get("output") or {}).get("problem_id") == "real:conditional")
        selected = compiled["selected_receipt"]
        assert compiled["state"] == "WORLD_UNVERIFIED" and selected["method"] == "cognition.cortex.estimation.fermi"
        assert selected["abstention_state"] == "NONE"
        assert selected["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
        assert body.journal.replay("cognition.settled") == [] and competence(body.journal) == {}
        assert measured_outcomes(body.journal) == [] and _compiled(compiled) is None
        relabelled = {k: v for k, v in compiled.items() if k != "receipt_id"}
        relabelled["state"] = "ANSWERED"                                  # control: only the state differs
        assert _compiled({**relabelled, "receipt_id": digest(relabelled)}) is not None
