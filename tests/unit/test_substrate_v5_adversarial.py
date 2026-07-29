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


def cap(n, a, p, f, c=1.0, d="shared", k=""):
    return Capability(n, a, p, f, c, d, k)


def build(fams=("a", "b", "c", "d")):
    caps = []
    for f in fams:
        caps += [cap(f"nm.{f}", ("RAW",), "NORM", NM, 1.0, f"d.{f}", "normalise"),
                 cap(f"at.{f}", ("NORM",), "ATT", AT, 1.0, f"d.{f}", "attest")]
    caps += [cap("cx0", ("ATT", "ATT"), "AGREED", CX, 1.0, "d.x", "crosscheck"),
             cap("cx1", ("ATT", "ATT"), "AGREED", CX, 1.1, "d.y", "crosscheck"),
             cap("ad0", ("AGREED", "AGREED"), "VERDICT", AD, 1.0, "d.z", "adjudicate")]
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


def test_counters_are_incremented_somewhere_in_the_module():
    """FAILS if a counter exists but no code path ever increments it."""
    src = pathlib.Path(v5.__file__).read_text()
    exempt = {"SUPERVISOR_RESTART_EVENTS", "GLOBAL_REPAIR_SCANS",
              "FULL_PROVIDER_INDEX_READS", "TARGET_TOPOLOGY_LEAKAGE_EVENTS",
              "UNAUTHORIZED_EXTERNAL_EFFECTS", "WHOLE_ORGAN_REVIEW_PASSES"}
    for name in COUNTER_NAMES:
        if name in exempt:
            continue  # these measure behaviours the design must never perform
        assert f'C.incr("{name}"' in src, (
            f"{name} is never incremented: it would report zero regardless")


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


def test_semantic_fault_does_not_refuse_every_producer():
    """FAILS if Phase 3F's over-refusal returns."""
    o, healthy = formed()
    d1 = o.units[SINK].bonds[0].supplier
    consumer = o.units[[b.supplier for b in o.units[d1].bonds.values()][0]]
    victim = consumer.bonds[0].supplier
    o.units[victim].corrupt = True
    o.run_item(P)
    producers = {u.unit_id for u in o.units.values()
                 if u.capability.produces == consumer.capability.accepts[0]}
    assert not consumer.would_refuse_everything(producers), (
        "a single fault refused every producer of the required type")


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
