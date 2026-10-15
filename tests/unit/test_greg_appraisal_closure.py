"""Appraise the selected closure, not a worker's possibly incomplete history.

The appraiser is a real separate process, the commands are Ed25519-signed,
and every receipt used by these attacks was produced by the real Kernel Gate.
The attacker can append worker claims but cannot manufacture founder authority.
"""
import pytest

from greg.body import Body
from tests.greg_fixtures import make_body, mission, note_check, signed, workspace, write_strategy


def _register(body, key, body_id, mid, checks, *, closure=None):
    spec = mission(mid, checks=checks,
                   strategies=[write_strategy("effect", "effect.txt", "done", [checks[0]["check_id"]])],
                   capabilities=["fs.read", "fs.write"], closure=closure)
    body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
    return body.engine.book.missions[mid]


def _read(body, state, check, *, claimed_check=None, attempt=0):
    sensor = check["sensor"]
    manifest, adapter, _ = body.engine._resolve(sensor)
    outcome = body.office.act(
        mission_id=state.mission_id, cone=state.cone, command_digest=state.command_digest,
        manifest=manifest, adapter=adapter, ctx=body.engine._context(state, manifest),
        params=sensor.get("params", {}), target=sensor["target"], cost_usd=0.0,
        expected_outcome="observation captured", evidence_refs=[], attempt=f"audit:{check['check_id']}:{attempt}",
        spent_usd=0.0, approved_scopes=set())
    assert outcome.status == "DONE", outcome.reasons
    body.journal.record("mission.observed", {
        "mission_id": state.mission_id, "check_id": claimed_check or check["check_id"],
        "receipt": outcome.receipt_hash, "passed": True, "detail": "worker claim", "rung": 0,
    }, key=[state.mission_id, claimed_check or check["check_id"], outcome.receipt_hash])
    return outcome.receipt_hash


def _claim(body, mid, evidence, *, held=False, key="attack"):
    return body.journal.record("mission.held" if held else "mission.achieved", {
        "mission_id": mid, "evidence": evidence, "actions_done": 1,
        "note": "untrusted worker closure claim",
    }, key=[mid, key])


def _write(body, state, *, attempt=0, projection=None, record=True):
    manifest, adapter, _ = body.engine._resolve({"capability": "fs.write"})
    outcome = body.office.act(
        mission_id=state.mission_id, cone=state.cone, command_digest=state.command_digest,
        manifest=manifest, adapter=adapter, ctx=body.engine._context(state, manifest),
        params={"relative_path": "effect.txt", "content": "done"}, target="workspace:effect.txt", cost_usd=0.0,
        expected_outcome="strategy executed", evidence_refs=[], attempt=attempt,
        spent_usd=0.0, approved_scopes=set())
    assert outcome.status == "DONE", outcome.reasons
    data = {
        "mission_id": state.mission_id, "action_id": "effect", "attempt": attempt,
        "status": "DONE", "capability": "fs.write", "receipt": outcome.receipt_hash,
        "scope_digest": outcome.scope_digest,
        **(projection or {}),
    }
    if record:
        body.journal.record("mission.action", data, key=[state.mission_id, "effect", attempt])
    return data


def test_unobserved_bounded_goal_is_refuted_by_the_separate_process(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:unobserved"
    check = note_check("n", workspace(home, mid) / "missing.txt", "done")
    with Body(home) as body:
        _register(body, key, body_id, mid, [check])
        _claim(body, mid, [])
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "REFUTED", verdict
    assert not verdict["checks"]["checks_rederived_from_receipts"]
    assert any("no fresh observation" in f for f in verdict["findings"])


def test_observed_subset_cannot_close_a_bounded_mission(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:partial-observations"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "a.txt").write_text("done")
    checks = [note_check("a", folder / "a.txt", "done"), note_check("b", folder / "b.txt", "done")]
    with Body(home) as body:
        state = _register(body, key, body_id, mid, checks)
        receipt = _read(body, state, checks[0])
        _claim(body, mid, [receipt])
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "REFUTED", verdict
    assert any("b: no fresh observation" in f for f in verdict["findings"])


@pytest.mark.parametrize("duplicate", ["registration", "closure"])
def test_ambiguous_registration_or_closure_is_refuted(tmp_path, duplicate):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:ambiguous-" + duplicate
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check])
        receipt = _read(body, state, check)
        _claim(body, mid, [receipt])
        if duplicate == "registration":
            body.journal.record("mission.registered", {
                "mission_id": mid, "spec": state.spec, "command_digest": state.command_digest,
            }, key="duplicate")
        else:
            _claim(body, mid, [receipt], key="duplicate")
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "REFUTED", verdict
    assert not verdict["checks"]["registered_once" if duplicate == "registration" else "achieved_claimed"]


@pytest.mark.parametrize("signed_kind", ["bounded", "infinite"])
def test_worker_cannot_change_the_signed_closure_kind(tmp_path, signed_kind):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:wrong-closure-" + signed_kind
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    held = signed_kind == "bounded"
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check], closure={"kind": signed_kind})
        receipt = _read(body, state, check)
        event = _claim(body, mid, [receipt], held=held)
        verdict = body.appraise(mid, closure_event=event.event_id if held else None)
    assert verdict["verdict"] == "REFUTED", verdict
    assert not verdict["checks"]["closure_matches_signed_rule"]


def test_pre_action_observation_cannot_prove_the_action_outcome(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:pre-action-proof"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check])
        receipt = _read(body, state, check)
        # Complete a real Gate action after that observation. The world
        # still passes, but no post-action receipt establishes its outcome.
        _write(body, state)
        _claim(body, mid, [receipt])
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "REFUTED", verdict
    assert any("no fresh observation" in f for f in verdict["findings"])


@pytest.mark.parametrize("substitution", ["foreign-mission", "other-sensor", "not-closure-evidence"])
def test_a_true_receipt_must_belong_to_this_closure_and_signed_sensor(tmp_path, substitution):
    home, key, body_id, folder = make_body(tmp_path)
    mid = "m:substitution"
    for name in ("a", "b"):
        (folder / f"{name}.txt").write_text("done")
    check = note_check("a", folder / "a.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check])
        if substitution == "foreign-mission":
            foreign = _register(body, key, body_id, "m:foreign", [check])
            receipt = _read(body, foreign, check)
            body.journal.record("mission.observed", {
                "mission_id": mid, "check_id": "a", "receipt": receipt,
                "passed": True, "detail": "borrowed foreign receipt", "rung": 0,
            }, key="borrowed")
        else:
            sensor = note_check("b", folder / "b.txt", "done") if substitution == "other-sensor" else check
            receipt = _read(body, state, sensor, claimed_check="a")
        _claim(body, mid, [] if substitution == "not-closure-evidence" else [receipt])
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "REFUTED", verdict
    assert not verdict["checks"]["closure_evidence_bound"]
    assert any("not bound" in f for f in verdict["findings"])


def test_honest_ladder_hold_requires_cumulative_checks_but_not_inactive_checks(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:ladder-hold"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    for name in ("a", "b"):
        (folder / f"{name}.txt").write_text("done")
    checks = [note_check(name, folder / f"{name}.txt", "done") for name in ("a", "b", "inactive")]
    with Body(home) as body:
        state = _register(body, key, body_id, mid, checks,
                          closure={"kind": "infinite", "ladder": [["a"], ["b"]]})
        _write(body, state)
        a, b = [_read(body, state, check) for check in checks[:2]]
        event = _claim(body, mid, [a, b], held=True)
        verdict = body.appraise(mid, closure_event=event.event_id)
    assert verdict["verdict"] == "VERIFIED", verdict


def test_last_rung_alone_cannot_prove_a_cumulative_ladder_hold(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:ladder-subset"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "b.txt").write_text("done")
    checks = [note_check(name, folder / f"{name}.txt", "done") for name in ("a", "b")]
    with Body(home) as body:
        state = _register(body, key, body_id, mid, checks,
                          closure={"kind": "infinite", "ladder": [["a"], ["b"]]})
        receipt = _read(body, state, checks[1])
        event = _claim(body, mid, [receipt], held=True)
        verdict = body.appraise(mid, closure_event=event.event_id)
    assert verdict["verdict"] == "REFUTED", verdict
    assert any("a: no fresh observation" in f for f in verdict["findings"])


def test_standing_hold_requires_new_action_and_observation_since_previous_hold(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:standing-replay"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check], closure={"kind": "infinite"})
        _write(body, state)
        receipt = _read(body, state, check)
        first = _claim(body, mid, [receipt], held=True, key="first")
        assert body.appraise(mid, closure_event=first.event_id)["verdict"] == "VERIFIED"
        second = _claim(body, mid, [receipt], held=True, key="repeat-with-no-work")
        verdict = body.appraise(mid, closure_event=second.event_id)
        assert verdict["verdict"] == "REFUTED", verdict
        assert not verdict["checks"]["closure_matches_signed_rule"]
        _write(body, state, attempt=1)
        # A new worker observation claim tries to recycle the first hold's
        # genuine sensor receipt after the second real action.
        body.journal.record("mission.observed", {
            "mission_id": mid, "check_id": "n", "receipt": receipt,
            "passed": True, "detail": "old receipt replayed", "rung": 0,
        }, key="replayed-observation")
        third = _claim(body, mid, [receipt], held=True, key="recycled-proof")
        verdict = body.appraise(mid, closure_event=third.event_id)
    assert verdict["verdict"] == "REFUTED", verdict
    assert not verdict["checks"]["closure_evidence_bound"]


def test_distinct_checks_may_share_one_exact_sensor_receipt(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:shared-sensor"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done and true")
    checks = [note_check("done", folder / "n.txt", "done"), note_check("true", folder / "n.txt", "true")]
    with Body(home) as body:
        state = _register(body, key, body_id, mid, checks)
        receipt = _read(body, state, checks[0])
        body.journal.record("mission.observed", {
            "mission_id": mid, "check_id": "true", "receipt": receipt,
            "passed": True, "detail": "same exact sensor supports a second predicate", "rung": 0,
        }, key="second-check")
        _claim(body, mid, [receipt, receipt])
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "VERIFIED", verdict


@pytest.mark.parametrize("bad_receipt", [None, "sensor-receipt"])
def test_claimed_completed_action_needs_its_own_strategy_gate_receipt(tmp_path, bad_receipt):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:unproven-action"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check], closure={"kind": "infinite"})
        borrowed = _read(body, state, check) if bad_receipt else None
        body.journal.record("mission.action", {
            "mission_id": mid, "action_id": "effect", "attempt": 0,
            "status": "DONE", "capability": "fs.write", "receipt": borrowed,
            "scope_digest": "worker-imagined-scope",
        }, key="unproven-action")
        receipt = _read(body, state, check, attempt=1)
        event = _claim(body, mid, [receipt], held=True)
        verdict = body.appraise(mid, closure_event=event.event_id)
    assert verdict["verdict"] == "REFUTED", verdict
    assert verdict["checks"]["checks_rederived_from_receipts"]
    assert verdict["checks"]["closure_evidence_bound"]
    assert not verdict["checks"]["exactly_once"]


def test_later_actions_and_approval_requests_do_not_rewrite_a_prior_closure(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:historical-closure"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check])
        _write(body, state)
        receipt = _read(body, state, check)
        _claim(body, mid, [receipt])
        assert body.appraise(mid)["verdict"] == "VERIFIED"
        action = body.journal.replay("mission.action")[0].payload
        body.journal.record("decision.requested", {
            "mission_id": mid, "request_id": "future-approval", "kind": "APPROVAL",
            "scope_digest": action["scope_digest"],
        }, key="future-approval")
        body.journal.record("mission.action", {
            **action, "action_id": "future-claim", "receipt": None,
        }, key="future-claim")
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "VERIFIED", verdict


def test_a_later_gated_action_claim_does_not_rewrite_a_prior_closure_s_preconditions(tmp_path):
    """Preconditions are judged inside the closure window too (port 2026-10-14): a gated action claimed after
    the closure, behind a failing observation, is not evidence about the closure already appraised."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:historical-precondition"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    for name in ("pre", "n"):
        (folder / f"{name}.txt").write_text("done")
    pre, check = note_check("pre", folder / "pre.txt", "done"), note_check("n", folder / "n.txt", "done")
    spec = mission(mid, checks=[pre, check], capabilities=["fs.read", "fs.write"],
                   strategies=[write_strategy("effect", "effect.txt", "done", ["n"], requires=["pre"])])
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions[mid]
        _read(body, state, pre)                                     # the precondition held when it ran
        _write(body, state)
        receipts = [_read(body, state, c, attempt=1) for c in (pre, check)]
        _claim(body, mid, receipts)
        assert body.appraise(mid)["verdict"] == "VERIFIED"
        body.journal.record("mission.observed", {"mission_id": mid, "check_id": "pre", "receipt": None,
                                                 "passed": False, "detail": "later failing reading", "rung": 0},
                            key="later-failing")
        action = body.journal.replay("mission.action")[0].payload
        body.journal.record("mission.action", {**action, "attempt": 9}, key="later-gated-claim")
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "VERIFIED", verdict["findings"]
    assert verdict["checks"]["preconditions_honored"]


@pytest.mark.parametrize("projection", [{"capability": "fs.read"}, {"scope_digest": "worker-invented-scope"}])
def test_action_projection_cannot_relabel_its_real_capability_or_approval_scope(tmp_path, projection):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:relabeled-action"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check])
        _write(body, state, projection=projection)
        receipt = _read(body, state, check)
        _claim(body, mid, [receipt])
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "REFUTED", verdict
    assert verdict["checks"]["closure_evidence_bound"]
    assert not verdict["checks"]["exactly_once"]


def test_delayed_action_claim_cannot_turn_old_gate_work_into_a_new_hold(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:delayed-action"
    folder = workspace(home, mid)
    folder.mkdir(parents=True)
    (folder / "n.txt").write_text("done")
    check = note_check("n", folder / "n.txt", "done")
    with Body(home) as body:
        state = _register(body, key, body_id, mid, [check], closure={"kind": "infinite"})
        _write(body, state)
        delayed = _write(body, state, attempt=1, record=False)
        receipt = _read(body, state, check)
        first = _claim(body, mid, [receipt], held=True, key="first")
        assert body.appraise(mid, closure_event=first.event_id)["verdict"] == "VERIFIED"
        body.journal.record("mission.action", delayed, key="delayed-action-claim")
        receipt = _read(body, state, check, attempt=1)
        second = _claim(body, mid, [receipt], held=True, key="second")
        verdict = body.appraise(mid, closure_event=second.event_id)
    assert verdict["verdict"] == "REFUTED", verdict
    assert verdict["checks"]["closure_evidence_bound"]
    assert not verdict["checks"]["exactly_once"]


# -- typed handoffs (2026-10-14 port onto the convergence line) ----------------------------------------
# greg/missions.py resolves a strategy's signed ``bind`` edges and every inline ``$from_action`` reference
# before office.act, and AuthorityOffice.scope_digest hashes the bound params. #138's binder recomputed the
# scope from the signed (unresolved) params, which refutes every legitimate handoff closure. The port
# re-derives the handed params from this mission's own receipts as they stood before the grant.

def _run(body, clock, ticks=8):
    states = []
    for _ in range(ticks):
        clock.advance(60)
        states.append(body.tick()["missions"][0]["state"])
        if states[-1] == "ACHIEVED":
            break
    return states


def test_a_closure_through_a_signed_bind_edge_verifies_with_the_resolved_params(tmp_path):
    import hashlib
    from tests.greg_fixtures import Clock, drop
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:composed"
    root = workspace(home, mid)
    expected = "digest of a: " + hashlib.sha256(b"alive 41").hexdigest()
    edge = {"param": "content", "from": {"action_id": "write-a", "field": "sha256"}, "type": "string",
            "template": "digest of a: {value}"}
    spec = mission(mid, checks=[note_check("a", root / "a.txt", "alive"), note_check("b", root / "b.txt", expected)],
                   strategies=[write_strategy("write-a", "a.txt", "alive 41", ["a"]),
                               {"action_id": "write-b", "capability": "fs.write",
                                "params": {"relative_path": "b.txt"}, "bind": [edge], "target": "workspace:b.txt",
                                "advances": ["b"], "requires": ["a"], "rationale": "derive b from a's receipt"}],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert _run(body, clock)[-1] == "ACHIEVED"
        verdict = body.appraise(mid)
    assert verdict["verdict"] == "VERIFIED", verdict["findings"]
    assert verdict["checks"]["closure_evidence_bound"] and verdict["checks"]["exactly_once"]


def _handoff_mission(home, mid):
    """A sensor whose path is the producer's receipted output, resolved by the engine at observation time."""
    produced = {"$from_action": {"action_id": "write-a", "field": "path", "type": "string"}}
    check = {"check_id": "a", "description": "the file the strategy wrote contains done",
             "sensor": {"capability": "fs.read", "params": {"path": produced}, "target": "fs:a.txt"},
             "predicate": {"op": "contains", "field": "text", "value": "done"}}
    return mission(mid, checks=[check], strategies=[write_strategy("write-a", "a.txt", "done", ["a"])],
                   capabilities=["fs.read", "fs.write"]), check


def test_a_sensor_fed_by_an_inline_handoff_verifies_with_the_resolved_params(tmp_path):
    from tests.greg_fixtures import Clock, drop
    home, key, body_id, _ = make_body(tmp_path)
    spec, _ = _handoff_mission(home, "m:handoff-sensor")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert _run(body, clock)[-1] == "ACHIEVED"
        verdict = body.appraise("m:handoff-sensor")
    assert verdict["verdict"] == "VERIFIED", verdict["findings"]
    assert verdict["checks"]["closure_evidence_bound"]


@pytest.mark.parametrize("read", ["resolved", "substituted"])
def test_a_handoff_sensor_receipt_must_carry_the_params_this_mission_resolved(tmp_path, read):
    """A worker reads another file through the same signed sensor capability and target: the receipt is
    genuine Gate output, but not for the params the mission's own producer receipt resolves to. The same
    read with the params the producer's receipt resolves to is bound (the control)."""
    home, key, body_id, folder = make_body(tmp_path)
    mid = "m:handoff-" + read
    spec, check = _handoff_mission(home, mid)
    (folder / "elsewhere.txt").write_text("done")
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions[mid]
        manifest, adapter, _ = body.engine._resolve({"capability": "fs.write"})
        outcome = body.office.act(
            mission_id=mid, cone=state.cone, command_digest=state.command_digest, manifest=manifest,
            adapter=adapter, ctx=body.engine._context(state, manifest),
            params={"relative_path": "a.txt", "content": "done"}, target="workspace:a.txt", cost_usd=0.0,
            expected_outcome="strategy executed", evidence_refs=[], attempt=0, spent_usd=0.0,
            approved_scopes=set())
        body.journal.record("mission.action", {
            "mission_id": mid, "action_id": "write-a", "attempt": 0, "status": "DONE", "capability": "fs.write",
            "receipt": outcome.receipt_hash, "scope_digest": outcome.scope_digest}, key=[mid, "write-a", 0])
        path = outcome.output["path"] if read == "resolved" else str(folder / "elsewhere.txt")
        receipt = _read(body, state, {**check, "sensor": {**check["sensor"], "params": {"path": path}}})
        _claim(body, mid, [receipt])
        verdict = body.appraise(mid)
    if read == "resolved":
        assert verdict["verdict"] == "VERIFIED", verdict["findings"]
        return
    assert verdict["verdict"] == "REFUTED", verdict
    assert not verdict["checks"]["closure_evidence_bound"] and verdict["checks"]["exactly_once"]
    assert any("a: receipt not bound" in f for f in verdict["findings"])


# -- a dispatch the founder reconciled as executed (acceptance gap H.G10) -----------------------------------------
# The recovery harness (tests/integration/test_greg_recovery_scenarios_process.py) SIGKILLs a body after fs.write
# wrote its file and before the Gate's receipt; the founder answers reconcile_executed. The appraiser re-derives
# closures from receipts only, so it withholds VERIFIED. Before the fix it also reported a "duplicate receipt or
# dispatch claim" that does not exist: one claim, no receipt, no second dispatch.

def test_a_founder_reconciled_dispatch_is_named_as_such_not_reported_as_a_duplicate(tmp_path):
    from greg.capabilities import BUILTINS
    from tests.greg_fixtures import Clock, drop
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:reconciled"
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "settled")],
        strategies=[write_strategy("w", "n.txt", "settled", ["n"])], capabilities=["fs.read", "fs.write"])))
    manifest, write = BUILTINS["fs.write"]

    def receipt_lost(params, ctx):            # the real write happens; the body loses power before its receipt
        write(params, ctx)
        raise RuntimeError("power lost after the write, before the Gate's receipt")

    clock = Clock()
    with Body(home, clock=clock) as body:
        body.registry.register(manifest, receipt_lost, state="ATTACHED")
        body.boot()
        _run(body, clock, ticks=2)
        [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "RECONCILIATION"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "reconcile_executed"}))
        assert _run(body, clock)[-1] == "ACHIEVED"
        claims = {r.payload["grant_id"] for r in body.ledger.by_type("grant_dispatch")}
        receipts = [r.payload["grant_id"] for r in body.ledger.by_type("receipt")]
        verdict = body.journal.replay("mission.appraised")[-1].payload
    assert ask["authority_requested"]["grant_id"] in claims and ask["authority_requested"]["grant_id"] not in receipts
    assert len(receipts) == len(set(receipts))                       # there is no duplicate to report
    assert verdict["verdict"] == "REFUTED" and verdict["checks"]["exactly_once"] is False
    assert not [f for f in verdict["findings"] if "duplicate" in f], verdict["findings"]
    assert [f for f in verdict["findings"] if f.startswith("w: ") and "founder reconciliation" in f], verdict["findings"]
