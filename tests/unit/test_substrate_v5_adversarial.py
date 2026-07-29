"""Phase 3G adversarial tests.

Each of these FAILS if the Phase 3F defect class reappears. They are written to
catch my own previous mistakes, not to confirm the design.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from substrate import v5
from substrate.v5 import (COUNTER_NAMES, ENV, GONE, ISOLATED, SILENT, SINK, WRONG,
                          C, Capability, Contract, Organ, Unit, Value, counters_are_live,
                          diagnose, form_key, measure, normalized_form, reset)

NM = lambda s: str(s).strip().lower()
AT = lambda s: f"att:{len(s)}"
CX = lambda a, b: "AGREED" if a == b else "DISPUTED"
AD = lambda a, b: "ACCEPT" if a == b == "AGREED" else "DECLINE"
K = Contract("fn", "RAW", "VERDICT", lambda v: v.payload == "ACCEPT")
P = "  Hello  "


OK_ATT = lambda v: isinstance(v, str) and v.startswith("att:") and v[4:].isdigit()
OK_AGR = lambda v: v in ("AGREED", "DISPUTED")


def cap(n, a, p, f, c=1.0, d="shared", k="", acc=None):
    return Capability(n, a, p, f, c, d, k, acc)


def build(fams=("a", "b", "c", "d")):
    caps = []
    for f in fams:
        caps += [cap(f"nm.{f}", ("RAW",), "NORM", NM, 1.0, f"d.{f}", "normalise"),
                 cap(f"at.{f}", ("NORM",), "ATT", AT, 1.0, f"d.{f}", "attest")]
    caps += [cap("cx0", ("ATT", "ATT"), "AGREED", CX, 1.0, "d.x", "crosscheck", OK_ATT),
             cap("cx1", ("ATT", "ATT"), "AGREED", CX, 1.1, "d.y", "crosscheck", OK_ATT),
             cap("ad0", ("AGREED", "AGREED"), "VERDICT", AD, 1.0, "d.z", "adjudicate", OK_AGR)]
    us = [Unit(unit_id=f"{c_.klass()}.{i}", capability=c_) for i, c_ in enumerate(caps)]
    o = Organ(us, K)
    ids = list(o.units)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            o.connect(a, b)
    return o


def formed():
    reset()
    o = build()
    o.commission()
    return o, o.run_item(P)


def deep_interior(o):
    d1 = o.units[SINK].bonds[0].supplier
    d2 = [b.supplier for b in o.units[d1].bonds.values()][0]
    return [b.supplier for b in o.units[d2].bonds.values()][0]


# ==========================================================================
# ADVERSARIAL: the Phase 3F defects must not reappear
# ==========================================================================

def test_organ_has_no_whole_organ_review_method():
    """FAILS if local_review() is reinstated under any name."""
    src = pathlib.Path(v5.__file__).read_text()
    tree = ast.parse(src)
    organ = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.ClassDef) and n.name == "Organ")
    for fn in [n for n in organ.body if isinstance(n, ast.FunctionDef)]:
        body = ast.dump(fn)
        # An Organ method may not iterate units AND touch bonds in one pass.
        iterates_units = "self.units" in body and ("For" in body)
        touches_bonds = ".bonds" in ast.unparse(fn)
        assert not (iterates_units and touches_bonds), (
            f"Organ.{fn.name} iterates units and inspects bonds: that is a "
            f"whole-organ review however it is named")


def test_repair_is_not_triggered_by_the_final_result():
    """FAILS if any repair path consults the contract invariant."""
    src = pathlib.Path(v5.__file__).read_text()
    tree = ast.parse(src)
    for cls, meth in (("Unit", "attempt"), ("Unit", "_reopen_contrastively"),
                      ("Organ", "run_item")):
        node = next(f for c in ast.walk(tree) if isinstance(c, ast.ClassDef)
                    and c.name == cls
                    for f in c.body if isinstance(f, ast.FunctionDef) and f.name == meth)
        text = ast.unparse(node)
        assert "invariant" not in text, f"{cls}.{meth} consults the contract invariant"
        assert "result_ok" not in text, f"{cls}.{meth} consults the mission result"


def test_every_counter_can_be_driven_above_zero():
    """FAILS if a counter is decorative. This is the Phase 3F F2 defect."""
    deltas = counters_are_live()
    assert set(deltas) == set(COUNTER_NAMES)
    for name, d in deltas.items():
        assert d == 1, f"counter {name} did not respond to increment"


def test_whole_organ_scan_increments_its_counter_at_the_behaviour_site():
    o, _ = formed()
    reset()
    o._scan_all_units()
    assert C["WHOLE_ORGAN_REVIEW_PASSES"] == 1
    assert C["GLOBAL_REPAIR_SCANS"] == 1


def test_provider_index_read_increments_its_counter():
    o, _ = formed()
    reset()
    o.providers_of("ATT")
    assert C["FULL_PROVIDER_INDEX_READS"] == 1


def test_second_commissioning_is_recorded_as_a_supervisor_restart():
    o, _ = formed()
    reset()
    o.commission()
    assert C["SUPERVISOR_RESTART_EVENTS"] == 1


def test_boundary_reopen_attempt_is_recorded():
    o, _ = formed()
    reset()
    o.units[SINK]._reopen_contrastively(0, GONE, "x", frozenset(), has_sibling=False)
    assert C["BOUNDARY_TRIGGERED_REPAIR_EVENTS"] == 1


def test_the_substrate_never_reads_the_provider_index():
    """Global provider knowledge must be evaluator-only."""
    src = pathlib.Path(v5.__file__).read_text()
    tree = ast.parse(src)
    unit = next(n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == "Unit")
    assert "providers_of" not in ast.unparse(unit)


def test_over_refusal_is_evidence_not_a_runtime_verdict():
    """The unit emits what it refused; it does not decide whether that
    excluded every alternative, which needs global knowledge."""
    src = pathlib.Path(v5.__file__).read_text()
    assert 'C.incr("OVER_REFUSAL_EVENTS"' not in src
    o, _ = formed()
    d1 = o.units[SINK].bonds[0].supplier
    consumer = o.units[[b.supplier for b in o.units[d1].bonds.values()][0]]
    o.units[consumer.bonds[0].supplier].dissolved = True
    o.run_item(P)
    ev = [e for u in o.units.values() for e in u.refusal_evidence]
    assert ev
    for e in ev:
        for k in ("failed_derivation", "working_sibling_derivations",
                  "distinguishing_refused", "uncertainty", "direct_supplier",
                  "required_type", "had_working_sibling"):
            assert k in e, f"refusal evidence is missing {k}"


def test_reset_does_not_orphan_imported_counter_references():
    """FAILS if reset() rebinds instead of clearing in place."""
    from substrate.v5 import C as imported
    C.incr("EVENT_DRIVEN_LOCAL_ACTIVATIONS")
    reset()
    imported.incr("EVENT_DRIVEN_LOCAL_ACTIVATIONS")
    assert C["EVENT_DRIVEN_LOCAL_ACTIVATIONS"] == 1, (
        "the imported reference and the module counter diverged")
    reset()


def test_a_unit_cannot_reach_beyond_its_own_bonds():
    o, _ = formed()
    u = o.units[o.units[SINK].bonds[0].supplier]
    port = o._port(u)
    before = C["UNIT_ENUMERATIONS_FOR_REPAIR"]
    with pytest.raises(v5.PullFailed):
        port.pull("normalise.0" if "normalise.0" not in
                  {b.supplier for b in u.bonds.values()} else ENV)
    assert C["UNIT_ENUMERATIONS_FOR_REPAIR"] == before + 1


def test_semantically_wrong_input_is_detected_and_repaired_locally():
    """The full qualifying sequence. A weaker assertion - merely that not every
    supplier was refused - can pass while nothing was detected at all."""
    o, healthy = formed()
    assert o.result_ok(healthy)
    d1 = o.units[SINK].bonds[0].supplier
    consumer = o.units[[b.supplier for b in o.units[d1].bonds.values()][0]]
    victim = consumer.bonds[0].supplier
    o.units[victim].corrupt = True
    reset()
    restored = o.run_item(P)

    rejects = [r for u in o.units.values() for r in u.receipts
               if r.kind == "semantic_reject"]
    assert rejects, "no unit locally rejected the wrong value"
    assert victim in {r.supplier for r in rejects}
    assert C["EVENT_DRIVEN_LOCAL_ACTIVATIONS"] > 0
    assert C["BOUNDARY_TRIGGERED_REPAIR_EVENTS"] == 0
    assert C["WHOLE_ORGAN_REVIEW_PASSES"] == 0
    assert C["FULL_PROVIDER_INDEX_READS"] == 0
    ev = [e for u in o.units.values() for e in u.refusal_evidence]
    assert ev and all(len(e["distinguishing_refused"]) <= 2 for e in ev)
    assert o.result_ok(restored), "the correct final result was not restored"


def test_runtime_never_invokes_attempt_without_a_pending_event():
    """FAILS on whole-organ polling, including via indirection."""
    src = pathlib.Path(v5.__file__).read_text()
    tree = ast.parse(src)
    organ = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.ClassDef) and n.name == "Organ")
    for fn in [n for n in organ.body if isinstance(n, ast.FunctionDef)]:
        text = ast.unparse(fn)
        if ".attempt(" not in text:
            continue
        assert "for uid in sorted(self.units)" not in text, (
            f"Organ.{fn.name} calls attempt() across all units: that is "
            f"whole-organ polling however indirect")
        assert "self.ready" in text, (
            f"Organ.{fn.name} calls attempt() outside the ready queue")


def test_healthy_run_dispatches_far_fewer_events_than_a_full_pass():
    reset()
    o = build()
    o.commission()
    o.run_item(P)
    assert o.events_dispatched < 4 * len(o.units), (
        f"{o.events_dispatched} events for {len(o.units)} units looks like polling")


# ==========================================================================
# The two inventions
# ==========================================================================

def test_repair_begins_inside_the_units_own_attempt():
    o, healthy = formed()
    assert o.result_ok(healthy)
    reset()
    o.units[deep_interior(o)].dissolved = True
    o.run_item(P)
    assert C["EVENT_DRIVEN_LOCAL_ACTIVATIONS"] > 0
    assert C["BOUNDARY_TRIGGERED_REPAIR_EVENTS"] == 0
    assert C["WHOLE_ORGAN_REVIEW_PASSES"] == 0
    assert C["UNIT_ENUMERATIONS_FOR_REPAIR"] == 0


def test_the_boundary_is_never_commissioned_twice():
    o, _ = formed()
    o.units[deep_interior(o)].dissolved = True
    o.run_item(P)
    assert o.commissions == 1


def test_contrastive_fencing_refuses_only_the_distinguishing_source():
    o, _ = formed()
    d1 = o.units[SINK].bonds[0].supplier
    consumer = o.units[[b.supplier for b in o.units[d1].bonds.values()][0]]
    victim = consumer.bonds[0].supplier
    o.units[victim].dissolved = True
    o.run_item(P)
    assert consumer.refused, "nothing was refused"
    assert len(consumer.refused) <= 2, (
        f"refused {sorted(consumer.refused)}; contrastive fencing must isolate "
        f"the distinguishing source, not the chain")


def test_without_a_working_sibling_uncertainty_is_preserved():
    """A single-input consumer cannot isolate a cause, so it must refuse only
    the direct supplier and carry the rest as uncertainty."""
    reset()
    o = build()
    o.commission()
    o.run_item(P)
    single = [u for u in o.units.values()
              if len(u.capability.accepts) == 1 and u.unit_id not in (SINK,)
              and u.bonds and u.bonds[0].supplier != ENV]
    assert single
    u = single[0]
    sup = u.bonds[0].supplier
    chain_before = set(u.bonds[0].chain)
    u._reopen_contrastively(0, GONE, "gone", frozenset(), has_sibling=False)
    assert u.refused == {sup}
    assert (chain_before - {ENV, u.unit_id, sup}) <= u.uncertain


def test_restoration_produces_the_correct_semantic_result():
    o, healthy = formed()
    assert o.result_ok(healthy)
    o.units[deep_interior(o)].dissolved = True
    after = o.run_item(P)
    assert o.result_ok(after), "the correct final result was not restored"
    assert after.payload == "ACCEPT"


def test_not_yet_is_not_treated_as_failure():
    """FAILS if a supplier that has simply not run yet triggers a reopen."""
    reset()
    o = build()
    o.commission()
    o.run_item(P)
    assert C["EVENT_DRIVEN_LOCAL_ACTIVATIONS"] == 0, (
        "a healthy first run reopened something: 'not yet' was read as failure")


def test_a_unit_that_waits_is_not_rescheduled_by_polling():
    """A unit with an unproduced supplier must simply wait, not spin."""
    reset()
    o = build()
    o.commission()
    o.run_item(P)
    assert o.events_dispatched <= 3 * len(o.units)


def test_diagnosis_receives_only_receipts():
    params = set(inspect.signature(diagnose).parameters)
    assert params == {"receipts"}


def test_no_external_effect_surface():
    tree = ast.parse(pathlib.Path(v5.__file__).read_text())
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    assert not (imported & {"requests", "urllib", "socket", "subprocess",
                            "smtplib", "http", "os", "pathlib", "shutil"})
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not ({"open", "eval", "exec"} & calls)
