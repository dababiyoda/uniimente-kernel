"""Cortex 0.2.2 on GREG's own path: three defects verified on 2026-10-21 by independent reproduction.

* A cortex-contract receipt labelled every non-answer ANSWERED_WITHIN_SCOPE (the dataclass default), which the
  founder console, the phone app and the disclosure package showed next to PROHIBITED or ABSTAIN.
* A composition recipe answered a high-consequence request as ANSWERED, where every other route says
  WORLD_UNVERIFIED.
* A high-consequence formal request could never be answered: the compiler's own control flag
  formalization_complete was forwarded to the cortex, whose strict payload contract refused it.
"""
import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from greg.cognition import compiler  # noqa: E402
from greg.cognition.contracts import outcome_state_for  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.settlement import _valid_receipt  # noqa: E402

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
OPT = {"option_id": "O1", "action_class": "draft.prepare", "target": "internal://drafts",
       "consequence_class": "internal_write", "reversibility": "reversible", "cost_usd": 0.0,
       "harm": {}, "evidence_statuses": ["internally_observed"], "advantage": {"v": 1}}
MANDATE = {"record_id": "m1", "kind": "founder_mandate", "origin": "founder_signed",
           "body": {"scope": {"action_classes": ["draft.*"], "targets": ["internal://*"],
                              "max_consequence_class": "internal_write"}}}


def policy(verdict):
    return {"record_id": f"p-{verdict}", "kind": "policy_decision", "origin": "kernel_policy_engine",
            "body": {"subject": "O1", "verdict": verdict}}


def req(pid, records, payload=None):
    return {"problem_id": pid, "problem": {"question": "Which option?",
                                           "payload": payload or {"options": [OPT], "declared": DECL}},
            "records": records, "routing": "static"}


CASES = {
    "recommend": (req("allow", [MANDATE, policy("allow")]), False, "NONE"),
    "gate_failed": (req("deny", [MANDATE, policy("deny")]), False, "PROHIBITED"),
    "gate_unresolved": (req("none", []), False, "HUMAN_REVIEW_REQUIRED"),
    "worker_contract_error": (req("bad", [], {"options": [{**OPT, "consequence_class": "galactic"}],
                                              "declared": DECL}), False, "ABSTAIN"),
    "router_detached": (req("det", [MANDATE, policy("allow")]), True, "CAPABILITY_DEFICIT"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_cortex_receipts_outcome_label_follows_its_abstention_state(name):
    params, detach, expected_state = CASES[name]
    registry = registry_view()
    if detach:
        registry.set_state("cognition.cortex", "DETACHED")
    r = reason(params, registry=registry)
    assert r["abstention_state"] == expected_state
    assert r["outcome_state"] == outcome_state_for(r["abstention_state"])
    if r["abstention_state"] != "NONE":
        assert r["outcome_state"] != "ANSWERED_WITHIN_SCOPE"
    assert _valid_receipt(r)


# ------------------------------------------------------------------ the Competency Compiler
NOISE = [0.05, -0.12, 0.08, 0.15, -0.04, 0.1, -0.09, 0.02, 0.11, -0.13, 0.06, 0.0, -0.07, 0.12, 0.03]
TRACK = {"observed_today": [round(110 * (1 + e)) for e in NOISE],
         "standing_plan": {"blocks": [100.0] * 48, "decision_block": 16},
         "staffing": {"block_seconds": 1800.0, "mean_service_time": 1200.0, "target_wait": 120.0,
                      "max_wait_probability": 0.2, "agent_cost": 1.0, "shortage_penalty": 10.0},
         "tracker": {"q": 1e-5, "r": 0.01, "prior": {"mean": [1.0, 0.0], "var": [0.04, 1e-5]}}}


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")


@pytest.fixture
def attached():
    r = registry_view()
    for cid in ("cognition.basal_kalman", "cognition.queue_erlang"):
        r.set_state(cid, "ATTACHED")
    return r


def compile_(registry, geometry, data, **extra):
    return reason({"problem_id": "p", "compile": {"geometry": geometry, "data": data, **extra}}, registry=registry)


@pytest.mark.parametrize("geometry,consequence", [
    ({"consequence_class": "financial"}, None), ({"consequence_class": "irreversible"}, None),
    ({"consequence_class": "external_contact"}, None),
    ({"consequence_class": "internal_write"}, {"financial": 0.9}), ({}, {"physical": 0.9})])
def test_a_high_consequence_composition_is_a_conditional_result_never_answered(attached, geometry, consequence):
    r = compile_(attached, geometry, TRACK, **({"consequence": consequence} if consequence else {}))
    assert r["method_or_composition_selected"] == "composition:track_then_staff"
    assert r["state"] == "WORLD_UNVERIFIED", r["state"]
    assert type(r["result"]["agents"]) is int            # the answer is kept, labelled conditional
    assert r["authority_created"] is False


def test_a_read_only_composition_is_still_answered(attached):
    r = compile_(attached, {"consequence_class": "read_only"}, TRACK)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "composition:track_then_staff"


def test_a_complete_high_consequence_formal_request_reaches_the_organ_and_is_escalated():
    """The compiler's own flag no longer blocks the organ ("unknown payload keys"); with the compile's consequence
    forwarded (item 19) the cortex escalates a financial question exactly as on its direct path, keeping the
    answer for the human who decides."""
    from cortex.examples import STAFFING
    registry = registry_view()
    flagged = {**STAFFING["payload"], "formalization_complete": True}
    high = compile_(registry, {"geometry": "optimization", "consequence_class": "financial"}, flagged)
    assert not any("unknown payload keys" in a for a in high["abstentions"])
    inner = high["selected_receipt"]
    assert high["state"] == inner["abstention_state"] == "HUMAN_REVIEW_REQUIRED"
    assert inner["proof_artifact"]["disposition"]["kind"] == "handoff" and inner["output"]["answer"] is not None
    assert compile_(registry, {"geometry": "optimization"}, flagged)["state"] == "ANSWERED"
    unflagged = compile_(registry, {"geometry": "optimization", "consequence_class": "financial"},
                         STAFFING["payload"])
    assert unflagged["state"] == "FORMALIZATION_INCOMPLETE"


# ------------------------------------------------------------------ the seed path's outcome projection
def test_a_settled_outcome_never_credits_a_method_whose_claim_never_ran(tmp_path):
    import greg.cognition.seed_path as sp
    import greg.routing as routing
    from greg.body import Body
    from greg.capabilities import BUILTINS, InvocationContext
    from greg.templates import cognitive_problem
    from tests.greg_fixtures import Clock, drop, make_body, signed
    from tests.unit.test_greg_cognition_seed_path import estimation, evidence, problem
    home, key, bid, _ = make_body(tmp_path)
    p = problem('estimation', estimation(), name='unrun-method')
    p['claims'].append({'claim_id': 'sem', 'kind': 'semantic', 'data': evidence(), 'conditions': {}})
    spec = cognitive_problem(p)
    drop(home, signed(key, bid, 'MISSION', spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(1)
        r = body.journal.replay('cognition.receipt')[0]
        sem = next(c for c in r.payload['claims'] if c['claim_id'] == 'sem')
        assert sem['reasons'] == ['CAPABILITY_UNAVAILABLE'] and sem['verification'] is None   # precondition
        ctx = InvocationContext(tmp_path, (), None, BUILTINS['cognition.settle'][0], journal=body.journal,
                                mission_id=spec['mission_id'], authority_ref='fixture-signed-observation',
                                grant_id='fixture-only')
        out = sp.settle({'outcome_id': 'o1', 'receipt_id': r.payload['receipt_id'], 'tier': 'synthetic',
                         'score': 1.0, 'evidence_refs': [r.event_id], 'supersedes': None, 'conditions': {}}, ctx)
        rows = {row['method']['method']: row for row in routing.cognitive_knowledge(body.journal)}
    assert [m['method'] for m in out['unexecuted_methods']] == [sem['method']]   # listed, not dropped silently
    assert rows['interval-product/1']['scores'] == [1.0]          # the method that ran keeps its observation
    assert sem['method'] not in rows                               # the method that never ran gets none


# ------------------------------------------------------------------ evaluation integrity (verified 2026-10-21)
def _mini_seed_suite(tmp_path, monkeypatch, strata=('optimization', 'semantic', 'missing_evidence')):
    import json
    from greg.cognition import seed_evaluation as E
    from greg.cognition.contracts import digest
    suite = json.loads(E.SUITE.read_text())
    cases = [next(c for c in suite['cases'] if c['stratum'] == s) for s in strata]
    mini = {**suite, 'cases': cases}
    frozen = json.loads(E.FREEZE.read_text())
    frozen.update(suite_digest=digest(mini), code_digests=E.code_digests())   # a legitimate gate pass, not a bypass
    (tmp_path / 's.json').write_text(json.dumps(mini))
    (tmp_path / 'f.json').write_text(json.dumps(frozen))
    monkeypatch.setattr(E, 'SUITE', tmp_path / 's.json')
    monkeypatch.setattr(E, 'FREEZE', tmp_path / 'f.json')
    return E, cases


def test_an_unconfigured_model_baseline_books_no_call_and_is_never_called_measured(tmp_path, monkeypatch):
    E, cases = _mini_seed_suite(tmp_path, monkeypatch)
    r = E.always_llm(cases[0]['request'], registry_view(), None)
    assert r['model_provenance'] is None and r['compute_cost']['model_calls'] == 0
    rep = E.assess(tmp_path / 'out.json', model_config=None)
    assert not any(row['always_llm']['receipt']['model_provenance'] for row in rep['results'])
    assert rep['baseline_status']['always_local_llm'].startswith('NOT_RUN')
    unserved = [row for row in rep['results'] if row['always_llm']['receipt']['method'] == 'baseline.always_local_llm']
    assert unserved and all(row['always_llm']['loss'] is None and row['always_llm']['ran'] is False for row in unserved)


def test_a_declared_baseline_with_errored_items_is_not_a_run_baseline():
    from cortex.evaluation import scoring as S
    routed = {"status": "RUN", "summary": {"critical_errors": 0, "gate_violations": 0, "errors": 0, "n": 3}}
    arms = {"routed_seed": routed}
    for name in S.THRESHOLDS["declared_baselines"]:
        arms[name] = {"status": "RUN", "summary": {"errors": 3, "n": 3, "critical_errors": 0},
                      "paired_gain_vs_routed": {"ci95": [0.9, 1.0]}}
    verdict = S.exit_verdict(arms)
    assert verdict["verdict"] == "INCONCLUSIVE" and verdict["promote"] is False
    assert all("errored" in r for r in verdict["reasons"] if "not run" in r)


def test_a_repeated_arm_runs_once_or_not_at_all():
    from cortex.evaluation import crossgeo, run as R
    with pytest.raises(SystemExit, match="repeated arm"):
        R.run("smoke", ["routed_seed", "routed_seed"])
    with pytest.raises(SystemExit, match="repeated arm"):
        crossgeo.run_partition("dev", ("routed_greg", "routed_greg"))
    with pytest.raises(SystemExit, match="unknown arm"):
        crossgeo.run_partition("dev", ("routed_greg", "static_routr"))
    with pytest.raises(SystemExit, match="unknown arm"):
        R.run("smoke", ["routed_seed", "always_abstian"])


def test_an_observed_freeze_is_never_overwritten(tmp_path, monkeypatch):
    from cortex.evaluation import crossgeo, run as R
    for module, argv in ((R, ["--freeze"]), (crossgeo, ["--freeze"])):
        existing = tmp_path / f"{module.__name__}.json"
        existing.write_text("{}")
        monkeypatch.setattr(module, "MANIFEST", existing)
        with pytest.raises(SystemExit, match="refusing to overwrite"):
            module.main(argv)
        assert existing.read_text() == "{}"


class _ProbeOnlyModel:
    """Answers the probe; every real item exceeds the client timeout."""
    def complete(self, system, user):
        if user == "{}":
            return '{"ok": true}'
        import socket
        raise socket.timeout("timed out")


class _GarbageModel:
    def complete(self, system, user):
        return '{"ok": true}' if user == "{}" else "not json"


def test_a_model_that_never_answers_an_item_is_not_a_run_baseline(monkeypatch):
    from cortex.evaluation import crossgeo as C
    from cortex.evaluation import crossgeo_arms as A
    from cortex.evaluation import crossgeo_loss as L
    monkeypatch.setattr(A, "model_probe", lambda: (_ProbeOnlyModel(), None))
    part = C.run_partition("dev", ("routed_greg", "static_router", "always_llm"))
    assert part["arms"]["always_llm"]["status"] == "INCOMPLETE" and part["incomplete_rows"]["always_llm"]
    assert "always_llm" not in C.compare(part)          # no paired "gain" over an arm that never answered
    v = L.verdict(part["arms"], part["rows"], part["rows"], None)
    assert "always_llm" in v["not_run"] and "always_llm" in (v.get("claim_limit") or "")
    monkeypatch.setattr(A, "model_probe", lambda: (_GarbageModel(), None))
    garbage = C.run_partition("dev", ("routed_greg", "always_llm"))
    assert garbage["arms"]["always_llm"]["status"] == "RUN"     # malformed output stays a scored task failure
    assert all(r["components"].get("task_failure") == 1.0 for r in garbage["rows"]["always_llm"])


# ------------------------------------------------------------------ the compiler runs only the organ it selected
FM = {"requirement": "a + b <= 5",
      "variables": [{"name": "a", "sort": "int", "lo": 0, "hi": 5}, {"name": "b", "sort": "int", "lo": 0, "hi": 5}],
      "obligations": [{"id": "O1", "text": "a + b at most 5"}],
      "constraints": [{"id": "K1", "covers": ["O1"], "expr": ["<=", ["+", "a", "b"], 5]}]}
EM = {"target": {"name": "w", "unit": "USD/week"}, "expression": ["*", "n", "p"],
      "variables": [{"name": "n", "unit": "item/week", "low": 10, "high": 20},
                    {"name": "p", "unit": "USD/item", "low": 3, "high": 5}]}


def _executed(compile_receipt):
    inner = compile_receipt["selected_receipt"]
    return [p["organ_id"] for p in inner["proof_artifact"]["output"]["per_route"]]


def test_an_organ_frozen_evidence_rejected_never_runs_under_another_organs_label(monkeypatch):
    real = compiler.evidence_index()
    monkeypatch.setattr(compiler, "evidence_index", lambda path=None: {
        **real, "organs": {"cognition.cortex.estimation.fermi": {"status": "REJECTED"}}})
    c = reason({"problem_id": "rejected-organ", "compile": {"data": {"formal_model": FM, "estimation_model": EM,
                                                                      "declared": DECL}}}, registry=registry_view())
    assert c["method_or_composition_selected"] == "cognition.cortex.formal.z3"
    assert not any(o.startswith("cortex.estimation.fermi") for o in _executed(c))
    assert any(t.get("operator_id") == "single_organ_payload" for t in c["transformations"])


def test_the_high_consequence_gate_covers_what_runs_with_another_part_present():
    """With a financial consequence and no declared geometry the compiler selects Fermi; the formal model beside it
    must not run as well, past the formal organ's own FORMALIZATION_INCOMPLETE gate."""
    c = compile_(registry_view(), {"consequence_class": "financial"}, {"formal_model": FM, "estimation_model": EM})
    assert c["method_or_composition_selected"] == "cognition.cortex.estimation.fermi"
    assert _executed(c) == ["cortex.estimation.fermi@0.1.0"]
    alone = compile_(registry_view(), {"geometry": "constraint_feasibility", "consequence_class": "financial"},
                     {"formal_model": FM})
    assert alone["state"] == "FORMALIZATION_INCOMPLETE"


def _h_e02_without_declared():
    import copy
    from cortex.evaluation.run import load_items
    item = copy.deepcopy(next(i["problem"] for i in load_items("heldout") if i["item_id"] == "H-E02"))
    return item, {k: v for k, v in item["payload"].items() if k != "declared"}


@pytest.mark.parametrize("geometry,consequence", [({"consequence_class": "financial"}, None),
                                                  ({"consequence_class": "internal_write"}, {"financial": 0.9})])
def test_the_compiles_consequence_reaches_the_organ_it_selects(geometry, consequence):
    item, data = _h_e02_without_declared()
    c = compile_(registry_view(), geometry, data, **({"consequence": consequence} if consequence else {}))
    inner = c["selected_receipt"]["proof_artifact"]
    assert inner["geometry"]["consequence_class"] == "financial"
    assert inner["disposition"]["kind"] != "recommend"
    assert c["consequence_forwarded"]["to"] == "financial" and c["consequence_class"] == "financial"


def test_a_lower_compile_consequence_never_lowers_the_payloads_own():
    item, data = _h_e02_without_declared()
    c = compile_(registry_view(), {"consequence_class": "read_only"},
                 {**data, "declared": {"consequence_class": "financial", "reversibility": "reversible"}})
    assert c["selected_receipt"]["proof_artifact"]["geometry"]["consequence_class"] == "financial"
    assert "consequence_forwarded" not in c


# ------------------------------------------------------------------ a protection matter is a handoff, never a gap
PARTY = {"affected_party": "person-1", "immediate_harm": 0.8, "continuing_harm": 0.4, "evidence_at_risk": True}


@pytest.mark.parametrize("data", [{"affected_party": PARTY},
                                  {"victim_protection": {"relevant": True, "required_actions": [
                                      "immediate_protection", "evidence_preservation", "escalation"],
                                      "evidence_access": "need_to_know"}}])
def test_a_protection_matter_takes_the_human_route_before_any_deficit(data):
    c = compile_(registry_view(), {"geometry": "strategic"}, data)
    assert c["state"] == "HUMAN_JUDGMENT_REQUIRED" and c["capability_deficit"] is None
    assert c["method_or_composition_selected"] == "human:qualified_judgment"
    assert any("protection matter" in a for a in c["abstentions"])


def test_an_affected_party_is_the_protection_reviews_native_input():
    registry = registry_view()
    registry.set_state("cognition.protection", "ATTACHED")
    calm = {**PARTY, "immediate_harm": 0, "continuing_harm": 0}
    c = compile_(registry, {"geometry": "strategic"}, {"affected_party": calm})
    assert "cognition.protection" in c["methods_considered"]
    assert c["state"] != "CAPABILITY_DEFICIT"


def test_crossgeo_hashes_the_manifest_bytes_it_checked_and_reports_their_planning(tmp_path, monkeypatch):
    import hashlib
    import json
    from cortex.evaluation import crossgeo as C
    manifest = tmp_path / "freeze.json"
    manifest.write_text(json.dumps({"inputs": C.freeze_inputs(), "frozen_at": "2026-10-21T00:00:00Z",
                                    "planning": {"planned_heldout_n": 7}}))
    monkeypatch.setattr(C, "MANIFEST", manifest)
    checked = C._check_freeze("heldout")
    assert checked["_sha256"] == "sha256:" + hashlib.sha256(manifest.read_bytes()).hexdigest()
    manifest.write_text(json.dumps({"planning": {"planned_heldout_n": 999}}))   # edited after the partitions ran
    heldout = {"arms": {}, "rows": {}, "freeze_manifest_sha256": checked["_sha256"], "frozen_at": checked["frozen_at"],
               "planning": checked["planning"]}
    seen = {}
    monkeypatch.setattr(C.L, "verdict", lambda arms, h, a, planning: seen.setdefault("planning", planning) and {})
    monkeypatch.setattr(C.L, "regret", lambda rows: {})
    monkeypatch.setattr(C, "determinism", lambda items: {})
    monkeypatch.setattr(C, "load", lambda partition: [])
    assert C.report(heldout, {"arms": {}, "rows": {}})["planning"] == {"planned_heldout_n": 7}
    assert seen["planning"] == {"planned_heldout_n": 7}    # the verdict's power rule read the checked planning
