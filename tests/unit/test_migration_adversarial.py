"""The fifteen adversarial tests the founder required, plus the seam invariants.

The order below matches the founder's list. Each one is an attack, not a happy
path: a Package that only demonstrates its own success has demonstrated nothing.
"""
import ast
import importlib
import os

import pytest

from events import engine as seam
from events.spine import (DurableWorkflow, EventError, EventSpine, WorkflowFailed,
                          WorkflowKilled, WorkflowStep, durable_workflow,
                          resume_workflow)
from evolution.migration import migrate, spec
from evolution.migration.engines import ENGINES, JournalEngine, TokenEngine, UNDO_KEY
from evolution.migration.schema import make_validator, validate_checkpoint
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def spine():
    return EventSpine(EvidenceLedger("sha256:" + "0" * 64))


def steps(names, calls, failing=None, approval=None):
    out = []
    for n in names:
        f = n == failing

        def run(s, _n=n, _f=f):
            calls.append(_n)
            if _f:
                raise RuntimeError("boom")
            return {_n: 1}

        out.append(WorkflowStep(name=n, run=run,
                                compensate=lambda s, _n=n: calls.append("undo:" + _n),
                                max_retries=0, approval_wait=(n == approval)))
    return out


def validator_for(names, sp, wid):
    def prior():
        recs = [r.payload for r in sp.ledger.by_type("workflow")
                if r.payload.get("workflow_id") == wid]
        return recs[-1]["status"] if recs else None
    return make_validator(step_names=names, prior_status_fn=prior)


# ==========================================================================
# 1. candidate attempts to append a malformed checkpoint
# ==========================================================================

def test_1_malformed_checkpoint_is_refused_before_append():
    """The founder's correction. Not detected afterwards — refused, so the bad
    record never enters the chain at all."""
    sp, wid, calls = spine(), "p4x-mal", []

    class Malformed(ENGINES["W1-projection"]):
        def _checkpoint(self, note):
            self.spine.ledger.append("workflow", {
                "workflow_id": "other", "cursor": 99, "status": "running",
                "state": {}, "note": note, "actor": "",
                "legal_principal": "UNIIMENTE", "at": "2026-01-01T00:00:00Z"})

    before = len(sp.ledger.records)
    with seam.activate(Malformed, provider_id="mal", workflow_ids=[wid],
                       activated_by="test", validator=validator_for(["a"], sp, wid)):
        with pytest.raises(seam.EngineRefused):
            durable_workflow(sp, wid, steps(["a"], calls), actor="x",
                             legal_principal="alfonso_lopez").execute()

    assert [r for r in sp.ledger.by_type("workflow")] == [], \
        "a malformed checkpoint reached the ledger"
    refusals = [r.payload for r in sp.ledger.by_type("event")
                if r.payload.get("type") == spec.REFUSAL_EVENT_TYPE]
    assert len(refusals) == 1
    assert len(sp.ledger.records) - before == 1, "only the refusal was appended"
    ok, _ = sp.ledger.verify_chain()
    assert ok
    problems = " ".join(refusals[0]["problems"])
    assert "UNIIMENTE" in problems and "identity mismatch" in problems


def test_1b_a_valid_checkpoint_still_appends():
    """A guard that refuses everything is not a guard."""
    sp, wid, calls = spine(), "p4x-ok", []
    with seam.activate(ENGINES["W1-projection"], provider_id="W1-projection",
                       workflow_ids=[wid], activated_by="test",
                       validator=validator_for(["a", "b"], sp, wid)):
        durable_workflow(sp, wid, steps(["a", "b"], calls), actor="x",
                         legal_principal="alfonso_lopez").execute()
    assert [r for r in sp.ledger.by_type("workflow")], "nothing was appended"
    assert calls == ["a", "b"]


# ==========================================================================
# 2. duplicate step names create an ambiguous reverse migration
# ==========================================================================

def test_2_duplicate_step_names_cause_refusal_not_a_guess():
    payload = {"workflow_id": "w", "cursor": 1, "status": "interrupted",
               "state": {}, "note": "n", "actor": "a",
               "legal_principal": "alfonso_lopez", "at": "t"}
    dup = ["s1", "s2", "s1"]

    fwd = migrate.forward(payload, dup)
    assert fwd.payload is None and fwd.ambiguous
    assert "duplicate step names" in fwd.reason

    rev = migrate.reverse({**payload, "completed_steps": ["s1"], "next_step": "s2"}, dup)
    assert rev.payload is None and rev.ambiguous
    assert "more than one index" in rev.reason

    # And unique names still work, so the refusal is specific, not blanket.
    ok = migrate.round_trip(payload, ["s1", "s2", "s3"])
    assert ok.payload is not None and ok.payload["cursor"] == 1


# ==========================================================================
# 3. off-by-one migration at the last step
# ==========================================================================

@pytest.mark.parametrize("cursor", [0, 1, 2, 3])
def test_3_migration_round_trips_exactly_at_every_boundary(cursor):
    """Including cursor == len(steps), the end-of-workflow boundary where an
    off-by-one would silently drop or repeat the final step."""
    names = ["s1", "s2", "s3"]
    payload = {"workflow_id": "w", "cursor": cursor, "status": "interrupted",
               "state": {"x": 1}, "note": "n", "actor": "a",
               "legal_principal": "alfonso_lopez", "at": "t"}

    fwd = migrate.forward(payload, names)
    assert fwd.payload is not None
    assert fwd.payload["completed_steps"] == names[:cursor]
    assert fwd.payload["next_step"] == (names[cursor] if cursor < 3 else None)

    rt = migrate.round_trip(payload, names)
    assert rt.payload == payload, f"round trip lossy at cursor={cursor}"


def test_3b_out_of_range_cursor_is_refused():
    names = ["s1", "s2"]
    for bad in (-1, 3, 99):
        r = migrate.forward({"cursor": bad}, names)
        assert r.payload is None and r.ambiguous


# ==========================================================================
# 4. workflow resumed more than once
# ==========================================================================

@pytest.mark.parametrize("cid", ["W1-projection", "W2-token"])
def test_4_repeated_resume_never_re_executes_completed_work(cid):
    sp, wid, calls = spine(), "p4x-twice", []
    names = ["a1", "a2", "a3"]
    with seam.activate(ENGINES[cid], provider_id=cid, workflow_ids=[wid],
                       activated_by="test", validator=validator_for(names, sp, wid)):
        wf = durable_workflow(sp, wid, steps(names, calls), actor="x",
                              legal_principal="alfonso_lopez")
        with pytest.raises(WorkflowKilled):
            wf.execute(kill_at_step="a2")
        first = resume_workflow(sp, wid, steps(names, calls))
        with pytest.raises(WorkflowKilled):
            first.execute(kill_at_step="a3")
        second = resume_workflow(sp, wid, steps(names, calls))
        second.execute()

    assert calls == ["a1", "a2", "a3"], f"{cid} re-executed completed work: {calls}"
    assert second.status == "completed"


# ==========================================================================
# 5. compensated terminal workflow attempts to resume
# ==========================================================================

@pytest.mark.parametrize("cid", list(ENGINES))
def test_5_terminal_workflow_stays_terminal(cid):
    sp, wid, calls = spine(), "p4x-term", []
    names = ["g1", "g2"]
    with seam.activate(ENGINES[cid], provider_id=cid, workflow_ids=[wid],
                       activated_by="test", validator=validator_for(names, sp, wid)):
        wf = durable_workflow(sp, wid, steps(names, calls, failing="g2"),
                              actor="x", legal_principal="alfonso_lopez")
        with pytest.raises(WorkflowFailed):
            wf.execute()
        with pytest.raises(EventError, match="nothing to resume"):
            resume_workflow(sp, wid, steps(names, calls))


def test_5b_validator_refuses_any_successor_to_a_terminal_status():
    for terminal in spec.TERMINAL_STATUSES:
        problems = validate_checkpoint(
            {"workflow_id": "w", "cursor": 0, "status": "running", "state": {},
             "note": "n", "actor": "a", "legal_principal": "alfonso_lopez",
             "at": "t"},
            {"workflow_id": "w", "provider_id": "W0-original",
             "prior_status": terminal, "step_names": ["x"]})
        assert any("terminal" in p for p in problems), terminal


# ==========================================================================
# 6. unapproved gated step after migration
# ==========================================================================

@pytest.mark.parametrize("cid", list(ENGINES))
def test_6_unapproved_gate_stays_closed(cid):
    sp, wid, calls = spine(), "p4x-gate", []
    names = ["p1", "p2"]
    with seam.activate(ENGINES[cid], provider_id=cid, workflow_ids=[wid],
                       activated_by="test", validator=validator_for(names, sp, wid)):
        wf = durable_workflow(sp, wid, steps(names, calls, approval="p2"),
                              actor="x", legal_principal="alfonso_lopez")
        with pytest.raises(WorkflowKilled):
            wf.execute(approver=lambda step: False)
    assert calls == ["p1"], f"{cid} ran an unapproved gated step"


# ==========================================================================
# 7. candidate drops state keys
# ==========================================================================

def test_7_dropping_a_required_state_key_is_detected_as_state_loss():
    """Not a schema error — a schema-valid checkpoint that has lost work."""
    names = ["s1", "s2"]
    full = {"workflow_id": "w", "cursor": 1, "status": "interrupted",
            "state": {"s1": 1}, "note": "n", "actor": "a",
            "legal_principal": "alfonso_lopez", "at": "t"}
    lossy = {k: v for k, v in full.items() if k != "note"}

    result = migrate.forward(lossy, names)
    assert "note" in result.lost_keys, "a dropped carried key went unnoticed"

    rt = migrate.round_trip(full, names)
    assert rt.payload == full and not rt.lost_keys


def test_7b_state_pollution_is_caught_even_when_execution_is_correct():
    """W3 preserves exactly-once and still fails, because it writes its own
    bookkeeping into the caller's state namespace. Correct execution is not the
    same as a preserved state contract."""
    sp, wid, calls = spine(), "p4x-pollute", []
    names = ["s1", "s2"]
    with seam.activate(JournalEngine, provider_id="W3-journal", workflow_ids=[wid],
                       activated_by="test", validator=validator_for(names, sp, wid)):
        wf = durable_workflow(sp, wid, steps(names, calls), actor="x",
                              legal_principal="alfonso_lopez")
        wf.execute()

    assert calls == ["s1", "s2"], "exactly-once was preserved"
    assert UNDO_KEY in wf.state, "W3's frozen claim is that the stack lives in state"
    assert wf.state != {"s1": 1, "s2": 1}, \
        "the polluted state must be visibly different from the original's"


# ==========================================================================
# 8. candidate duplicates completed work
# ==========================================================================

def test_8_a_duplicating_engine_is_caught():
    """The control that matters: an engine that re-runs a completed step must be
    detected, not smoothed over."""
    sp, wid, calls = spine(), "p4x-dup", []
    names = ["d1", "d2"]

    class Duplicating(ENGINES["W1-projection"]):
        @staticmethod
        def resume(spine_, workflow_id, steps_):
            wf = ENGINES["W1-projection"].resume(spine_, workflow_id, steps_)
            wf.cursor = 0          # forget everything: re-run completed work
            return wf

    with seam.activate(Duplicating, provider_id="dup", workflow_ids=[wid],
                       activated_by="test", validator=validator_for(names, sp, wid)):
        wf = durable_workflow(sp, wid, steps(names, calls), actor="x",
                              legal_principal="alfonso_lopez")
        with pytest.raises(WorkflowKilled):
            wf.execute(kill_at_step="d2")
        resume_workflow(sp, wid, steps(names, calls)).execute()

    assert calls == ["d1", "d1", "d2"], "the duplicating engine did not duplicate"
    assert calls.count("d1") == 2
    # And this is exactly what the exactly-once gate scores as failure.
    assert tuple(calls) != ("d1", "d2")


def test_8b_completed_steps_may_not_contain_duplicates():
    problems = validate_checkpoint(
        {"workflow_id": "w", "completed_steps": ["a", "a"], "next_step": "b",
         "status": "running", "state": {}, "note": "n", "actor": "x",
         "legal_principal": "alfonso_lopez", "at": "t"},
        {"workflow_id": "w", "provider_id": "W2-token", "step_names": ["a", "b"]})
    assert any("duplicates" in p for p in problems)


# ==========================================================================
# 9 & 10. legal principal tampering
# ==========================================================================

def test_9_changing_the_legal_principal_mid_workflow_is_refused():
    problems = validate_checkpoint(
        {"workflow_id": "w", "cursor": 0, "status": "running", "state": {},
         "note": "n", "actor": "x", "legal_principal": "", "at": "t"},
        {"workflow_id": "w", "provider_id": "W0-original", "step_names": ["a"]})
    assert any("legal principal" in p for p in problems)


def test_10_uniimente_as_legal_principal_is_refused_everywhere():
    problems = validate_checkpoint(
        {"workflow_id": "w", "cursor": 0, "status": "running", "state": {},
         "note": "n", "actor": "x", "legal_principal": "UNIIMENTE", "at": "t"},
        {"workflow_id": "w", "provider_id": "W0-original", "step_names": ["a"]})
    assert any("UNIIMENTE is never a legal principal" in p for p in problems)

    for cls in [DurableWorkflow, *ENGINES.values()]:
        with pytest.raises((EventError, Exception)):
            cls(spine(), "w", [], actor="x", legal_principal="UNIIMENTE")


# ==========================================================================
# 11. provider activation leaks outside its scope
# ==========================================================================

def test_11_activation_does_not_leak_outside_its_scope():
    sp = spine()
    assert seam.assert_default_is_original()

    with seam.activate(TokenEngine, provider_id="W2-token", workflow_ids=["p4x-in"],
                       activated_by="test", validator=lambda p, c: []):
        assert seam.is_active() and seam.active_provider_id() == "W2-token"
        # allowlisted -> replacement
        engine_in, _ = seam.resolve(sp, "p4x-in")
        assert engine_in is TokenEngine
        # NOT allowlisted -> the original, even while a replacement is active
        engine_out, spine_out = seam.resolve(sp, "some-other-workflow")
        assert engine_out is DurableWorkflow
        assert spine_out is sp, "a non-allowlisted workflow got a wrapped spine"

    assert seam.assert_default_is_original()
    assert seam.resolve(sp, "p4x-in")[0] is DurableWorkflow


def test_11b_activation_leaks_nothing_when_the_body_raises():
    with pytest.raises(RuntimeError):
        with seam.activate(TokenEngine, provider_id="W2-token",
                           workflow_ids=["x"], activated_by="test",
                           validator=lambda p, c: []):
            raise RuntimeError("boom")
    assert seam.assert_default_is_original()


def test_11c_activation_refuses_what_would_make_scope_ambiguous():
    with pytest.raises(seam.ActivationRefused, match="allowlist"):
        with seam.activate(TokenEngine, provider_id="p", workflow_ids=[],
                           activated_by="t", validator=lambda p, c: []):
            pass
    with pytest.raises(seam.ActivationRefused, match="pre-append validation"):
        with seam.activate(TokenEngine, provider_id="p", workflow_ids=["x"],
                           activated_by="t", validator=None):
            pass
    with pytest.raises(seam.ActivationRefused, match="own promotion"):
        with seam.activate(TokenEngine, provider_id="p", workflow_ids=["x"],
                           activated_by="p", validator=lambda p, c: []):
            pass
    with pytest.raises(seam.ActivationRefused, match="never 'activated'"):
        with seam.activate(DurableWorkflow, provider_id="W0", workflow_ids=["x"],
                           activated_by="t", validator=lambda p, c: []):
            pass
    with seam.activate(TokenEngine, provider_id="a", workflow_ids=["x"],
                       activated_by="t", validator=lambda p, c: []):
        with pytest.raises(seam.ActivationRefused, match="already active"):
            with seam.activate(TokenEngine, provider_id="b", workflow_ids=["y"],
                               activated_by="t", validator=lambda p, c: []):
                pass
    assert seam.assert_default_is_original()


# ==========================================================================
# 12. process restart fails to restore the original provider
# ==========================================================================

def test_12_the_original_is_the_provider_after_a_process_restart():
    """Nothing is persisted, so a restart cannot restore a replacement. Proved
    by reloading the module — the closest in-process analogue of a restart."""
    reloaded = importlib.reload(seam)
    assert reloaded.assert_default_is_original()
    assert not reloaded.is_active()
    assert reloaded.active_provider_id() is None

    tree = ast.parse(open(os.path.join(ROOT, "events", "engine.py")).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            assert name not in {"dump", "dumps", "write", "save"}, \
                f"the seam persists activation via {name}(); a restart could " \
                f"then restore a replacement"

    # No permanent-default setter may EXIST. Checked as a definition rather than
    # a substring, so the docstring may name what the module deliberately omits.
    defined = {n.name for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "set_default" not in defined
    assert not hasattr(reloaded, "set_default"), \
        "a permanent-default setter would let a replacement install itself"


# ==========================================================================
# 13. rollback after partial replacement
# ==========================================================================

def test_13_rollback_after_a_partial_replacement_resumes_from_valid_state():
    """A replacement runs half the workflow, then is withdrawn mid-flight. The
    original must pick up from the last valid checkpoint without re-running."""
    sp, wid, calls = spine(), "p4x-partial", []
    names = ["r1", "r2", "r3"]

    with seam.activate(TokenEngine, provider_id="W2-token", workflow_ids=[wid],
                       activated_by="test", validator=validator_for(names, sp, wid)):
        wf = durable_workflow(sp, wid, steps(names, calls), actor="x",
                              legal_principal="alfonso_lopez")
        with pytest.raises(WorkflowKilled):
            wf.execute(kill_at_step="r2")
        assert isinstance(wf, TokenEngine)
    # Scope exited: the original is the provider again.
    assert seam.assert_default_is_original()

    last = [r.payload for r in sp.ledger.by_type("workflow")
            if r.payload["workflow_id"] == wid][-1]
    assert "completed_steps" in last, "the replacement wrote its own schema"

    # The original cannot read W2's schema directly, so rollback migrates back —
    # which is precisely what the reverse migration exists for.
    reverted = migrate.reverse(last, names)
    assert reverted.payload is not None, reverted.reason
    assert reverted.payload["cursor"] == 1
    assert reverted.payload["state"] == {"r1": 1}
    sp.ledger.append("workflow", {**reverted.payload, "note": "rolled_back"})

    resumed = resume_workflow(sp, wid, steps(names, calls))
    assert isinstance(resumed, DurableWorkflow)
    resumed.execute()
    assert calls == ["r1", "r2", "r3"], f"rollback re-ran completed work: {calls}"
    assert resumed.state == {"r1": 1, "r2": 1, "r3": 1}


# ==========================================================================
# 14. shutdown during replacement
# ==========================================================================

def test_14_shutdown_succeeds_while_a_replacement_is_active():
    from memory.affect import AffectController

    sp, wid = spine(), "p4x-shutdown"
    with seam.activate(TokenEngine, provider_id="W2-token", workflow_ids=[wid],
                       activated_by="test", validator=lambda p, c: []):
        controller = AffectController()
        controller.trigger("degraded", intensity=0.9, trigger_event_id="mid")
        assert controller.shutdown() == "shutdown_complete"

        from compiler.ucl_compiler import compile_constitution
        compiled = compile_constitution(ROOT)
        assert any(r.rule_id == "deny_by_default" for r in compiled.rules)
    assert seam.assert_default_is_original()


# ==========================================================================
# 15. external effect attempts
# ==========================================================================

def test_15_no_candidate_module_reaches_for_authority_or_the_outside_world():
    """Static half; the enforced out-of-process half is in
    tests/unit/test_migration_inertness.py."""
    forbidden = {"socket", "urllib", "requests", "subprocess", "http",
                 "policy", "authority", "capital", "constitution", "identity",
                 "capabilities", "embassy"}
    for name in ("engines.py", "migrate.py", "schema.py"):
        path = os.path.join(ROOT, "evolution", "migration", name)
        tree = ast.parse(open(path).read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & forbidden), f"{name} imports {imported & forbidden}"


# ==========================================================================
# Seam invariants and canonical substitution evidence
# ==========================================================================

def test_the_canonical_construction_sites_actually_route_through_the_seam():
    """Package 3's substitution never touched a canonical site. This asserts
    Package 4's does — by AST, at the exact files the spec froze."""
    for rel in ("closure/kernel_registry.py", "loom/weaver.py"):
        source = open(os.path.join(ROOT, rel)).read()
        assert "durable_workflow(" in source, f"{rel} does not use the seam"
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "import" in stripped:
                continue
            assert "DurableWorkflow(" not in stripped, \
                f"{rel} still constructs the original directly: {stripped}"


def test_verifier_v3_closures_run_through_the_seam_and_still_pass():
    """The canonical runtime path, exercised. If the seam broke the engine, V3
    would fail — which is the failure mode Package 3 structurally could not have."""
    from closure.kernel_registry import build_registry

    report = build_registry().verify_module("events")
    assert report.complete, f"events closures failed through the seam: {report}"
    results = {c.closure: c for c in report.closures}
    for name in ("evidence", "regenerative"):
        assert results[name].ok, \
            f"events.{name} closure failed through the seam: {results[name].detail}"


def test_the_original_remains_directly_constructible():
    """Founder requirement: the seam adds a governed path, it does not remove
    the plain one."""
    sp, calls = spine(), []
    wf = DurableWorkflow(sp, "direct", steps(["a"], calls), actor="x",
                         legal_principal="alfonso_lopez")
    wf.execute()
    assert wf.status == "completed" and calls == ["a"]


def test_the_seam_is_a_no_op_when_nothing_is_active():
    """With no replacement active, resolve returns the original AND the spine
    unchanged — so the default path allocates nothing and behaves identically."""
    sp = spine()
    engine, resolved = seam.resolve(sp, "anything")
    assert engine is DurableWorkflow
    assert resolved is sp


def test_guarded_ledger_passes_non_checkpoint_records_straight_through():
    """The seam governs the engine, not the ledger's other users."""
    inner = EvidenceLedger("sha256:" + "0" * 64)
    guard = seam.GuardedLedger(inner=inner, validator=lambda p, c: ["always bad"],
                               context={})
    guard.append("event", {"type": "unrelated.fact"})
    assert len(inner.records) == 2
    with pytest.raises(seam.EngineRefused):
        guard.append("workflow", {"anything": True})
    assert guard.head == inner.head, "delegation broke"
