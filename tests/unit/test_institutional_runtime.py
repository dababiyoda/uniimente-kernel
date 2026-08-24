"""The institution boots, remembers what it did, and refuses bad ground.

The Infinite Goal Chase recompute named composing a durable runtime as the Alpha
bottleneck and stated the falsification test in one sentence:

    run a governed action, discard every object, boot again from the same
    directory, and find the witness, the chain and the inbox intact.

That test is `test_a_governed_action_survives_a_full_restart` below. The rest of
this file is the ground it stands on, and the three defects composing the
runtime surfaced — each demonstrated before it was fixed, none of them reachable
while the gate and the spine were built on separate in-memory ledgers.
"""
from __future__ import annotations

import os

import pytest

from events.spine import Event, EventSpine
from policy.engine import Proposal
from provenance.ledger import ConstitutionMismatch, EvidenceLedger
from runtime import BootRefused, InstitutionalRuntime

SANDBOX_CONTAINMENT = {
    "contained": True, "reversible": True, "observable": True,
    "killable": True, "proportionate": True,
}
PEER = "spiffe://uniimente.internal/organ/daleobanks"


@pytest.fixture()
def state_dir(tmp_path):
    return str(tmp_path / "institution")


def _actor(runtime):
    return runtime.passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["draft.publish"],
        budget_ceiling_usd=5.0, consequence_class="external_contact")


def _proposal(actor_id: str) -> Proposal:
    return Proposal(
        actor=actor_id, legal_principal="alfonso_lopez",
        action_class="draft.publish", objective="runtime.restart.proof",
        payload={"text": "a governed action that must outlive its process"},
        target="sandbox:outbox", consequence_class="external_contact",
        evidence_confidence=0.9, evidence_refs=["sha256:" + "a" * 64],
        estimated_cost_usd=0.0, requested_capability="draft.publish",
        expected_outcome="draft queued", context=dict(SANDBOX_CONTAINMENT))


def _run_one_governed_action(runtime):
    """One complete pass through the canonical gate. Returns the ActionRecord."""
    actor = _actor(runtime)
    proposal = _proposal(actor.passport_id)
    grant = runtime.gate.grants.issue_single_action(
        proposal=proposal, policy_version=runtime.gate.policy_version)
    return runtime.gate.run(
        proposal, standing_grant=grant,
        executor=lambda p: {"observed_outcome": "draft queued",
                            "result_class": "positive"})


def _peer_event(event_id: str = "EV-PEER-1") -> Event:
    event = Event(type="bridge.opportunity_signal_received", source=PEER,
                  actor=PEER, payload={"packet_id": "OPP-1"},
                  legal_principal="Alfonso Lopez")
    event.event_id = event_id
    return event


# ===================================================================== the test
def test_a_governed_action_survives_a_full_restart(state_dir):
    """The falsification the recompute asked for, run end to end.

    Every object is discarded between the two halves — gate, ledger, spine,
    memory, passports. Nothing but the state directory crosses the boundary.
    """
    first = InstitutionalRuntime.boot(state_dir)
    assert first.report.resumed is False

    record = _run_one_governed_action(first)
    assert record.state == "recorded", record.refusal_reasons
    assert record.receipt_hash is not None

    first.spine.ingest(_peer_event())
    first.spine.outbox_stage(Event(
        type="external.draft_ready", source="spiffe://uniimente.internal/kernel/x",
        actor="kernel", payload={"draft": "queued"}, legal_principal="alfonso"))

    witness_count = len(first.ledger.by_type("witness"))
    receipt = record.receipt_hash
    first.shutdown(sealed_by="alfonso", reason="end of session")

    # Nothing but the directory survives.
    del first, record

    second = InstitutionalRuntime.boot(state_dir)

    assert second.report.resumed is True
    assert second.report.chain_verified is True
    # the witness
    assert len(second.ledger.by_type("witness")) == witness_count >= 1
    assert second.ledger.find(receipt) is not None, "the receipt is still findable"
    # the chain
    ok, detail = second.ledger.verify_chain()
    assert ok, detail
    # the inbox
    assert second.spine.ingest(_peer_event()) is None, "replay protection resumed"
    # the outbox
    assert len(second.outstanding_deliveries) == 1
    assert second.outstanding_deliveries[0].type == "external.draft_ready"


def test_the_second_boot_reads_the_same_action_back_as_history(state_dir):
    """Resuming is not just "the file parses" — the action is still legible."""
    first = InstitutionalRuntime.boot(state_dir)
    record = _run_one_governed_action(first)
    action_id = record.action_id
    del first, record

    second = InstitutionalRuntime.boot(state_dir)
    lifecycle = [r.payload for r in second.ledger.by_type("event")
                 if r.payload.get("action_id") == action_id]
    assert [p["type"] for p in lifecycle][0] == "action.proposed"
    assert "action.recorded" in {p["type"] for p in lifecycle}


# ============================================ identity is re-issued, not restored
def test_boot_does_not_restore_identities(state_dir):
    """The asymmetry the module is built around.

    Passports are capped at a one-hour TTL by construction. Carrying one across
    a restart would use a process boundary to extend an authority the
    institution deliberately made short-lived. Evidence persists; permission
    does not.
    """
    first = InstitutionalRuntime.boot(state_dir)
    actor = _actor(first)
    assert first.passports.verify(actor.passport_id)[0] is True
    del first

    second = InstitutionalRuntime.boot(state_dir)
    assert second.report.identities_restored == 0
    ok, why = second.passports.verify(actor.passport_id)
    assert ok is False and why == "unknown_identity"


def test_an_action_by_a_pre_restart_identity_is_refused(state_dir):
    """The consequence of the above, asserted rather than described."""
    first = InstitutionalRuntime.boot(state_dir)
    actor = _actor(first)
    del first

    second = InstitutionalRuntime.boot(state_dir)
    proposal = _proposal(actor.passport_id)
    record = second.gate.run(
        proposal,
        standing_grant=second.gate.grants.issue_single_action(
            proposal=proposal, policy_version=second.gate.policy_version),
        executor=lambda p: {"observed_outcome": "x", "result_class": "positive"})
    assert record.state == "refused"
    assert any("identity" in r for r in record.refusal_reasons)


# ================================================================= fail-closed
def test_boot_refuses_a_chain_written_under_a_different_constitution(state_dir):
    """Defect 2, at the level that makes it reachable.

    A state directory is the first thing that lets law and history disagree:
    an in-memory ledger dies with the process that made it, so it can never be
    opened under different law.
    """
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "ledger.jsonl")
    EvidenceLedger("sha256:" + "f" * 64, path=path).append("witness", {"x": 1})

    with pytest.raises(BootRefused, match="anchored to"):
        InstitutionalRuntime.boot(state_dir)


def test_the_lawful_path_past_a_constitutional_move_is_a_record(state_dir):
    """Fail-closed with no way forward is a different bug. There is a way, and
    it leaves a permanent, attributable trace."""
    first = InstitutionalRuntime.boot(state_dir)
    real = first.compiled.constitution_hash
    path = os.path.join(state_dir, "ledger.jsonl")
    del first

    ledger = EvidenceLedger(real, path=path)
    ledger.adopt_constitution("sha256:" + "9" * 64,
                              authorized_by="Alfonso Lopez",
                              reason="hypothetical ratified amendment")
    del ledger

    # The chain now expects the amended constitution, so the live one is refused.
    with pytest.raises(BootRefused, match="anchored to"):
        InstitutionalRuntime.boot(state_dir)

    transitions = EvidenceLedger("sha256:" + "9" * 64, path=path).by_type(
        "constitution_transition")
    assert len(transitions) == 1
    assert transitions[0].payload["from_hash"] == real
    assert transitions[0].payload["authorized_by"] == "Alfonso Lopez"


def test_uniimente_may_not_authorize_its_own_change_of_law(state_dir):
    first = InstitutionalRuntime.boot(state_dir)
    with pytest.raises(ConstitutionMismatch, match="may not authorize its own"):
        first.ledger.adopt_constitution("sha256:" + "9" * 64,
                                        authorized_by="UNIIMENTE",
                                        reason="self-promotion")


def test_boot_refuses_a_corrupted_chain(state_dir):
    """A tampered state directory must not start a working-looking institution."""
    first = InstitutionalRuntime.boot(state_dir)
    _run_one_governed_action(first)
    path = os.path.join(state_dir, "ledger.jsonl")
    del first

    lines = open(path, encoding="utf-8").read().splitlines()
    lines[2] = lines[2].replace('"record_type": "event"', '"record_type": "witness"')
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    with pytest.raises(BootRefused, match="not trustworthy"):
        InstitutionalRuntime.boot(state_dir)


def test_boot_has_no_argument_that_skips_the_constitution_check():
    """The founder's ruling prohibits a standing "exception because the check is
    inconvenient" mechanism. The absence of the flag is the enforcement, so it
    is asserted rather than trusted to review."""
    import inspect
    signature = inspect.signature(InstitutionalRuntime.boot)
    assert set(signature.parameters) == {"state_dir", "env"}


# ============================================ the gate/spine namespace collision
def test_replay_ignores_action_lifecycle_records(state_dir):
    """Defect 3, pre-existing and unreachable until something composed them.

    `ConsequenceGate._transition` writes `record_type="event"` records with no
    `source`; `EventSpine.replay()` assumed every such record was one of its
    own and raised `KeyError: 'source'`. Confirmed against unmodified main
    before the fix.
    """
    runtime = InstitutionalRuntime.boot(state_dir)
    _run_one_governed_action(runtime)

    action_records = [r for r in runtime.ledger.by_type("event")
                      if r.payload.get("type", "").startswith("action.")]
    assert action_records, "the gate wrote lifecycle records into the event bucket"

    replayed = runtime.spine.replay()          # must not raise
    assert all(not e.type.startswith("action.") for e in replayed)


def test_every_spine_view_uses_the_same_discriminator():
    """Two of three views guarded; the third did not, and that was the defect.

    Pinning the shared predicate rather than the three call sites: a fourth view
    written without it should fail here, not in production.
    """
    import ast
    import inspect

    source = inspect.getsource(EventSpine)
    tree = ast.parse(source.lstrip())
    views = {"replay", "_outbox_from_ledger", "_seen_from_ledger"}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in views:
            calls = {n.func.attr for n in ast.walk(node)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
            assert "_spine_payloads" in calls, (
                f"{node.name} reads the ledger without the shared discriminator")


# ==================================================================== the outbox
def test_a_staged_delivery_survives_a_restart(state_dir):
    """Defect 1. An outbox exists to survive the crash between deciding to send
    and sending; this one was a plain list."""
    first = InstitutionalRuntime.boot(state_dir)
    first.spine.outbox_stage(Event(
        type="external.one", source="spiffe://uniimente.internal/kernel/x",
        actor="kernel", payload={}, legal_principal="alfonso"))
    del first

    second = InstitutionalRuntime.boot(state_dir)
    assert [e.type for e in second.outstanding_deliveries] == ["external.one"]


def test_a_refused_delivery_is_still_owed_after_a_restart(state_dir):
    """The subtle half. `outbox_flush` re-keeps a refused event, so rebuilding
    must too — otherwise a restart silently discharges everything the mediator
    ever declined, and the debt disappears without the delivery happening."""
    first = InstitutionalRuntime.boot(state_dir)
    for name in ("external.kept", "external.sent"):
        first.spine.outbox_stage(Event(
            type=name, source="spiffe://uniimente.internal/kernel/x",
            actor="kernel", payload={}, legal_principal="alfonso"))
    first.spine.outbox_flush(mediator=lambda e: e.type == "external.sent")
    in_process = [e.type for e in first.spine._outbox]
    del first

    second = InstitutionalRuntime.boot(state_dir)
    assert [e.type for e in second.outstanding_deliveries] == in_process == ["external.kept"]


def test_a_flushed_delivery_is_not_owed_twice(state_dir):
    first = InstitutionalRuntime.boot(state_dir)
    first.spine.outbox_stage(Event(
        type="external.sent", source="spiffe://uniimente.internal/kernel/x",
        actor="kernel", payload={}, legal_principal="alfonso"))
    first.spine.outbox_flush(mediator=lambda e: True)
    del first

    assert InstitutionalRuntime.boot(state_dir).outstanding_deliveries == []


# ================================================================== the boot record
def test_the_restart_itself_becomes_institutional_memory(state_dir):
    """A body that forgets it restarted has a gap in its own history."""
    InstitutionalRuntime.boot(state_dir)
    InstitutionalRuntime.boot(state_dir)
    third = InstitutionalRuntime.boot(state_dir)

    boots = [r.payload for r in third.ledger.by_type("event")
             if r.payload.get("type") == "runtime.booted"]
    assert len(boots) == 3
    assert [b["resumed"] for b in boots] == [False, True, True]
    assert all(b["identities_restored"] == 0 for b in boots)


def test_booting_twice_resumes_one_chain_rather_than_starting_two(state_dir):
    first = InstitutionalRuntime.boot(state_dir)
    _run_one_governed_action(first)
    depth = len(first.ledger.records)
    del first

    second = InstitutionalRuntime.boot(state_dir)
    assert len(second.ledger.records) == depth + 1        # +1 for its own boot record
    assert os.listdir(state_dir) == ["ledger.jsonl"]


# ================================================================ adoption, counted
#: Bridge libraries that fall back to an ephemeral ledger when no caller
#: injects one. These are the real backlog: they are libraries, so adoption
#: happens at a composition root that hands them a durable ledger, and
#: `runtime/session.py` does that for exactly one of the three.
#:
#: The first version of this constant said 6 and the README called the work
#: "mechanical". Both were wrong, and checking each module individually is what
#: showed it: two of the six are the closure harness, one is a deliberately
#: self-contained command, and the three that remain need a composition root
#: rather than an edit. Corrected here rather than left as a tidy number.
RECORDED_EPHEMERAL_FALLBACK = 3

#: Modules whose own ledger is correct and must NOT be migrated. Each is here
#: for a stated reason, not to make a number smaller — and each was checked
#: individually after the first version of this probe lumped all six together
#: and the README called the remaining work "mechanical", which was wrong.
#:
#: `closure/*_registry.py` are the verification harness. A closure check must be
#: self-contained and deterministic; one that read accumulated state would pass
#: or fail depending on what had happened earlier, which is the opposite of a
#: check. `kernel_registry.py` additionally boots the runtime inside the
#: `runtime` closures — the module being *exercised*, not a caller having
#: *adopted* it, and counting that would inflate the number using the very test
#: written to measure it.
#:
#: `bridges/closure_verdict.py` RUNS the chain it then assesses, deliberately.
#: Its docstring records that an earlier version assessed an empty ledger and
#: printed OPEN, "which understates the finding in the flattering direction".
#: Pointing it at a state directory would make the whole-body verdict depend on
#: which directory you passed — a design change with a real trade-off, not a
#: migration.
VERIFICATION_HARNESS = (
    "closure/kernel_registry.py",
    "closure/advantage_registry.py",
    "closure/commercial_registry.py",
    "bridges/closure_verdict.py",
)


def test_the_migration_backlog_is_counted_not_asserted():
    """Building a thing is not using it, and only one of those is progress.

    This mirrors `_asymmetric_identity_is_only_one_edge_deep` deliberately, and
    it has already been re-pointed once for the same reason that probe was:
    the first version asked "does anything boot?", `runtime/session.py` answered
    yes within hours, and a check that can never fail again has stopped
    measuring anything. So it now counts what is measurably still open — the
    six modules that still build their own in-memory ledger — rather than the
    question that has been settled.

    Fails in BOTH directions on purpose. Migrating a module breaks this test,
    and whoever migrates it updates the count and the recompute in the same
    change, which is the procedure #25, #26, #30 and #48 already follow.
    """
    import os

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    own_ledger, boots = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {"tests", "__pycache__", "evolution"}
                       and not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            # `runtime/__init__.py` defines boot and `provenance/ledger.py`
            # defines the ledger; neither can be a caller of itself.
            if rel in ("runtime/__init__.py", "provenance/ledger.py"):
                continue
            if rel in VERIFICATION_HARNESS:
                continue
            source = open(os.path.join(dirpath, name), encoding="utf-8",
                          errors="ignore").read()
            if "EvidenceLedger(" in source:
                own_ledger.append(rel)
            if "InstitutionalRuntime.boot" in source:
                boots.append(rel)

    assert boots, (
        "nothing boots the runtime; it would be built-and-unused, the state "
        "identity/pki/ was in before Bridge A adopted it")
    assert len(own_ledger) == RECORDED_EPHEMERAL_FALLBACK, (
        f"the backlog changed: {len(own_ledger)} bridge libraries fall back to "
        f"an ephemeral ledger ({sorted(own_ledger)}), the recorded count is "
        f"{RECORDED_EPHEMERAL_FALLBACK}. Update RECORDED_EPHEMERAL_FALLBACK and "
        f"docs/INFINITE_GOAL_CHASE_RECOMPUTE together — and if a module belongs "
        f"in VERIFICATION_HARNESS instead, say why there rather than here.")


def test_one_bridge_of_three_is_driven_over_a_durable_ledger():
    """Breadth, counted — the `_asymmetric_identity_is_only_one_edge_deep` shape.

    Bridges A, B and C all accept an injected ledger. A composition root exists
    for one of them. Asserting "a composition root exists" would be true and
    would stop being informative immediately, so this counts which bridges it
    can actually drive.
    """
    from runtime.session import Session

    driven = [name for name in dir(Session) if name.startswith("traverse_")]
    assert driven == ["traverse_signal_to_venture"], (
        f"the session drives {driven}; update this count and the recompute "
        f"together when Bridge B or C gets a composition root")


# ============================================================== no external reach
def test_the_runtime_opens_no_socket_and_grants_nothing():
    """It composes. It does not connect, and it does not authorise."""
    import ast
    import inspect

    import runtime as runtime_module

    tree = ast.parse(inspect.getsource(runtime_module))
    imported = {n.module.split(".")[0] for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.Import) for a in n.names}

    for forbidden in ("socket", "http", "urllib", "requests", "httpx", "asyncio"):
        assert forbidden not in imported, f"runtime/ reached for {forbidden}"

    source = inspect.getsource(runtime_module)
    assert "issue_single_action" not in source, (
        "the runtime must not mint grants; authorising an external act stays a "
        "separate, visible act by the caller")
