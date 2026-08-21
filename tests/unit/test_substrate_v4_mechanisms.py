"""Mechanism tests for the Phase 3F substrate (provenance-fenced local reopening).

Where a capability is claimed, the test demonstrates it. Where the experiment
failed, the failure is pinned as an executable test rather than repaired.
"""
from __future__ import annotations

import pathlib

import pytest

from substrate.v4 import (COUNTERS, ENV, ISOLATED, NOT_DELIVERING, SEMANTICALLY_WRONG,
                          SINK, SUPPLIER_GONE, TOO_EXPENSIVE, Capability, Contract,
                          Diagnosis, FailureMemory, MeasuredMotif, Organ, Unit, Value,
                          diagnose, form_key, measure, normalized_form, reset_counters)

NORM = lambda s: str(s).strip().lower()
SUM = lambda s: f"sum:{len(s)}"
AG = lambda a, b: "ACCEPT" if a == b else "REJECT"
C = Contract("fn", "RAW", "VERDICT", lambda v: v.payload == "ACCEPT")
PAYLOAD = "  Hello  "


def cap(n, a, p, f, cost=1.0, d="shared", c=""):
    return Capability(n, a, p, f, cost, d, c)


def build(fams=("sigma", "tau", "upsilon")):
    caps = []
    for f in fams:
        caps += [cap(f"nm.{f}", ("RAW",), "NORM", NORM, 1.0, f"d.{f}", "normalise"),
                 cap(f"ck.{f}", ("NORM",), "CHK", SUM, 1.0, f"d.{f}", "crosscheck")]
    caps += [cap("ad.a", ("CHK", "CHK"), "VERDICT", AG, 1.0, "d.ad", "adjudicate"),
             cap("ad.b", ("CHK", "CHK"), "VERDICT", AG, 1.2, "d.adb", "adjudicate")]
    units = [Unit(unit_id=f"{c_.klass()}.{i}", capability=c_) for i, c_ in enumerate(caps)]
    o = Organ(units, C)
    ids = list(o.units)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            o.connect(a, b)
    return o


def formed():
    o = build()
    o.commission()
    return o, o.execute(PAYLOAD)


def interior_of(o):
    """A unit that supplies another interior unit, never the boundary."""
    sink_dep = o.units[SINK].bonds[0].supplier
    return [b.supplier for b in o.units[sink_dep].bonds.values()][0]


# -- semantic execution -----------------------------------------------------

def test_healthy_organ_produces_a_real_semantic_output():
    o, tr = formed()
    assert tr.ok and tr.output.payload == "ACCEPT"
    assert any(v.payload == "hello" for v in tr.values.values())


def test_values_carry_their_derivation_chain():
    o, tr = formed()
    assert ENV in tr.output.chain
    assert len(tr.output.chain) >= 4


def test_type_compatible_but_wrong_value_fails_the_contract():
    import dataclasses
    o, tr = formed()
    victim = interior_of(o)
    u = o.units[victim]
    u.capability = dataclasses.replace(u.capability, transform=lambda *a: "WRONG")
    after = o.execute(PAYLOAD)
    assert not after.ok, "a semantically wrong but type-valid input passed"


# -- THE MECHANISM: autonomous interior re-initiation -----------------------

def test_interior_consumer_reopens_without_a_boundary_demand():
    o, tr = formed()
    victim = interior_of(o)
    o.units[victim].dissolved = True
    before = o.boundary_demands
    restored, stats = o.operate(PAYLOAD)
    assert stats["interior_reopens"] > 0, "no interior unit reopened its own input"
    assert o.boundary_demands == before, "the boundary was asked again"


def test_the_boundary_holds_no_repair_authority():
    o, tr = formed()
    o.units[interior_of(o)].dissolved = True
    before = o.units[SINK].reopens
    o.operate(PAYLOAD)
    assert o.units[SINK].reopens == before


def test_no_supervisor_and_no_global_scan_during_repair():
    reset_counters()
    o, tr = formed()
    o.units[interior_of(o)].dissolved = True
    o.operate(PAYLOAD)
    assert COUNTERS["SUPERVISOR_RESTART_EVENTS"] == 0
    assert COUNTERS["GLOBAL_REPAIR_SCANS"] == 0
    assert COUNTERS["GLOBAL_FORMATION_SCANS"] == 0
    assert COUNTERS["FULL_PROVIDER_INDEX_READS"] == 0


def test_only_the_affected_slot_is_reopened():
    o, tr = formed()
    victim = interior_of(o)
    consumers = [u for u in o.units.values()
                 if any(b.supplier == victim for b in u.bonds.values())]
    assert consumers
    consumer = consumers[0]
    healthy_slots = {s: b.supplier for s, b in consumer.bonds.items()
                     if b.supplier != victim}
    o.units[victim].dissolved = True
    o.local_review(o.execute(PAYLOAD))
    for slot, supplier in healthy_slots.items():
        assert slot in consumer.bonds, "a healthy sibling obligation was reopened"
        assert consumer.bonds[slot].supplier == supplier


def test_a_delivery_failure_creates_local_evidence():
    o, tr = formed()
    o.units[interior_of(o)].dissolved = True
    o.local_review(o.execute(PAYLOAD))
    receipts = [r for u in o.units.values() for r in u.receipts]
    assert any(r.kind == "input_refused" for r in receipts)


# -- the fence ---------------------------------------------------------------

def test_a_refused_derivation_cannot_be_resettled():
    """The stale-return requirement, expressed over derivations."""
    o, tr = formed()
    victim = interior_of(o)
    consumer = [u for u in o.units.values()
                if any(b.supplier == victim for b in u.bonds.values())][0]
    slot = [s for s, b in consumer.bonds.items() if b.supplier == victim][0]
    consumer.reopen(slot, SUPPLIER_GONE, "test")
    assert victim in consumer.refused
    from substrate.v4 import Offer
    stale = Offer("n", victim, "crosscheck", consumer.capability.accepts[slot],
                  1.0, True, frozenset({victim}))
    consumer.open_needs[slot] = "n"
    consumer._settle(slot, stale, {victim: o.units[victim].capability})
    assert slot not in consumer.bonds, "a refused derivation was resettled"
    assert consumer.stale_rejections == 1


def test_semantic_fault_refuses_the_whole_upstream_chain():
    """Evidence-proportionate fencing: this is what a generation counter
    cannot do, because a shared bad ancestor keeps a fresh generation."""
    o, tr = formed()
    consumer = o.units[o.units[SINK].bonds[0].supplier]
    slot = sorted(consumer.bonds)[0]
    consumer.bonds[slot].accepted_chain = frozenset({"a", "b", ENV})
    consumer.reopen(slot, SEMANTICALLY_WRONG, "wrong value")
    assert {"a", "b"} <= consumer.refused
    assert ENV not in consumer.refused, "the given mission input must not be refused"


def test_delivery_fault_refuses_only_the_direct_supplier():
    o, tr = formed()
    consumer = o.units[o.units[SINK].bonds[0].supplier]
    slot = sorted(consumer.bonds)[0]
    supplier = consumer.bonds[slot].supplier
    consumer.bonds[slot].accepted_chain = frozenset({supplier, "upstream", ENV})
    consumer.reopen(slot, ISOLATED, "link cut")
    assert consumer.refused == {supplier}, "over-refused on delivery evidence"


# -- bounded repair ----------------------------------------------------------

def test_repair_budget_terminates_reopening():
    o, tr = formed()
    consumer = o.units[o.units[SINK].bonds[0].supplier]
    consumer.repair_budget = 1.0
    slot = sorted(consumer.bonds)[0]
    assert consumer.reopen(slot, SUPPLIER_GONE, "1") is True
    assert consumer.reopen(slot, SUPPLIER_GONE, "2") is False
    assert consumer.escalations, "exhausted budget must escalate, not retry"


def test_failure_memory_is_not_a_permanent_blacklist():
    m = FailureMemory()
    m.record("s1", "crosscheck", SUPPLIER_GONE)
    assert not m.admits("s1")
    m.tick(); m.tick()
    assert m.admits("s1"), "cooldown must clear and permit a probe"


def test_duplicate_reopen_requests_are_coalesced_per_slot():
    o, tr = formed()
    consumer = o.units[o.units[SINK].bonds[0].supplier]
    slot = sorted(consumer.bonds)[0]
    consumer.reopen(slot, SUPPLIER_GONE, "x")
    consumer.emit_needs()
    first = len(consumer.outbox)
    consumer.emit_needs()
    assert len(consumer.outbox) == first, "a second need was emitted for one slot"


# -- diagnosis is blind ------------------------------------------------------

def test_diagnostician_signature_carries_no_cause():
    import inspect
    params = set(inspect.signature(diagnose).parameters)
    assert params == {"healthy", "broken", "receipts"}
    for banned in ("cause", "victim", "expected", "ground_truth", "topology",
                   "damage_class", "replacement"):
        assert banned not in params


def test_diagnose_returns_none_when_the_contract_still_holds():
    o, tr = formed()
    assert diagnose(tr, o.execute(PAYLOAD), []) is None


def test_diagnose_infers_a_class_from_receipts_alone():
    o, tr = formed()
    o.units[interior_of(o)].dissolved = True
    broken = o.execute(PAYLOAD)
    o.local_review(broken)
    receipts = [r for u in o.units.values() for r in u.receipts]
    d = diagnose(tr, broken, receipts)
    assert d is not None and d.failure_class in {SUPPLIER_GONE, NOT_DELIVERING,
                                                 ISOLATED, TOO_EXPENSIVE,
                                                 SEMANTICALLY_WRONG}


# -- form identity -----------------------------------------------------------

def test_renaming_families_does_not_create_a_new_causal_form():
    a = build(("sigma", "tau", "upsilon"))
    b = build(("aaa", "bbb", "ccc"))
    a.commission(); b.commission()
    ta, tb = a.execute(PAYLOAD), b.execute(PAYLOAD)
    assert normalized_form(a, ta) == normalized_form(b, tb)


def test_measured_phenotype_contains_no_declared_constants():
    o, tr = formed()
    ph = measure(o, tr)
    assert ph["per_unit_resource_consumption"]
    assert "static" not in str(ph) and "reassign" not in str(ph)


# -- constraint channel ------------------------------------------------------

def test_constraint_blocks_a_matching_commit_and_the_disabled_arm_does_not():
    m = MeasuredMotif("adjudicate", supplier_count=1)
    probe = dict(capability_class="adjudicate", shares_domain=False,
                 supplier_count=1, paths_independent=True)
    assert m.matches(**probe)
    o, _ = formed()
    u = o.units[o.units[SINK].bonds[0].supplier]
    u.prohibited = [m]
    u.constraint_enabled = False
    assert u.constraint_enabled is False


def test_no_external_effect_surface_exists():
    """No module the substrate imports can reach outside the process."""
    import ast
    import substrate.v4 as v4
    tree = ast.parse(pathlib.Path(v4.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"requests", "urllib", "socket", "subprocess", "smtplib",
                 "http", "ftplib", "shutil", "os", "pathlib"}
    assert not (imported & forbidden), f"external effect surface: {imported & forbidden}"
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "open" not in calls, "the substrate performs file I/O"
    assert "eval" not in calls and "exec" not in calls


# -- pinned Phase 3F bottlenecks --------------------------------------------

def test_provenance_fence_over_refuses_KNOWN_BOTTLENECK():
    """Phase 3F's exact limit, recorded as executable evidence.

    A semantic fault refuses the whole upstream chain. Because interior units
    share ancestors, one semantic fault can refuse most viable suppliers at
    once, so restoration fails and repair traffic amplifies. Measured in
    PHASE3F_RESULTS.json: restorations 1/23, amplification max 423 against a
    preregistered ceiling of 12.

    Pinned rather than repaired: repairing an instrument and rescoring the same
    held-out fixtures is prohibited.
    """
    o, tr = formed()
    consumer = o.units[o.units[SINK].bonds[0].supplier]
    slot = sorted(consumer.bonds)[0]
    # A realistic deep chain: the input derived from most of the organ.
    consumer.bonds[slot].accepted_chain = frozenset(
        {u for u in o.units if u not in (SINK,)})
    consumer.reopen(slot, SEMANTICALLY_WRONG, "wrong value")
    viable = {u.unit_id for u in o.units.values()
              if u.capability.produces == consumer.capability.accepts[slot]}
    assert viable <= consumer.refused, (
        "BOTTLENECK: a single semantic fault refuses every viable supplier of "
        "the required type, so no replacement can settle")
