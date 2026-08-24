"""Controls for the four Package 3 adapters.

The founder named three controls that detection must pass, and they are the
three tests that would catch a staged demonstration:

    1. it detects the real loss
    2. it does not trigger when the component is healthy
    3. it does not falsely report recovery from incomplete output

Everything else here defends the properties those controls depend on: that the
removal is real rather than stubbed, that the detector is structurally blind
rather than politely blind, and that nothing can register itself as the answer
to an institutional capability.
"""
import ast
import os

import pytest

from evolution.repair import expectations, spec
from evolution.repair.baseline import BaselineRestore, factory as baseline_factory
from evolution.repair.candidate import (
    CandidateError, CapabilityProviderRegistry, FunctionOutput, HeldOutCorpora,
    ManifestView, ResolverCandidate,
)
from evolution.repair.cost import RepairCostMeter
from evolution.repair.detector import (
    CapabilityLossReport, FunctionLossDetector, Symptom, SYMPTOM_KINDS,
)
from evolution.repair.disable import (
    ComponentDisabled, ComponentUnavailable, is_disabled,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPAIR_DIR = os.path.join(ROOT, "evolution", "repair")


def _live_inputs():
    from linker.manifest import load_all
    return load_all(spec.CORPUS_DIR), os.path.join(ROOT, "contracts")


def _registry_with_original():
    reg = CapabilityProviderRegistry()
    reg.register(spec.TARGET_CAPABILITY, "B0-restore", baseline_factory,
                 registered_by="package3_harness")
    return reg


# ==========================================================================
# Adapter 1 — the removal is real
# ==========================================================================

def test_disable_makes_the_component_genuinely_unimportable():
    """Not stubbed, not monkeypatched to return the right answer. Gone."""
    import linker.linker  # noqa: F401  - present before

    with ComponentDisabled(spec.SUBJECT_PACKAGE) as event:
        assert is_disabled(spec.SUBJECT_PACKAGE)
        with pytest.raises(ComponentUnavailable):
            import linker  # noqa: F401
        with pytest.raises(ComponentUnavailable):
            import linker.linker  # noqa: F401
        with pytest.raises(ComponentUnavailable):
            __import__("linker.manifest")
        # importlib is not a bypass either
        import importlib
        with pytest.raises(ComponentUnavailable):
            importlib.import_module("linker.linker")
        assert event.evicted_modules, "nothing was evicted; was it ever imported?"

    assert not is_disabled(spec.SUBJECT_PACKAGE)
    import linker.linker  # noqa: F401,F811  - works again afterwards


def test_disable_leaves_the_original_on_disk_untouched():
    """Disable is a runtime condition. That is why rollback is one step."""
    import hashlib

    with ComponentDisabled(spec.SUBJECT_PACKAGE):
        for rel in spec.SUBJECT_FILES:
            path = os.path.join(ROOT, rel)
            assert os.path.exists(path), f"{rel} was deleted; it must not be"
            with open(path, "rb") as fh:
                assert hashlib.sha256(fh.read()).hexdigest() == \
                    spec.ORIGINAL_LINKER_FILE_SHA256[rel]


def test_disable_records_an_event_and_refuses_double_disable():
    from provenance.ledger import EvidenceLedger

    ledger = EvidenceLedger("sha256:test")
    with ComponentDisabled(spec.SUBJECT_PACKAGE, ledger=ledger):
        outer = ComponentDisabled(spec.SUBJECT_PACKAGE)
        with pytest.raises(RuntimeError):
            outer.__enter__()

    kinds = [r.payload.get("type") for r in ledger.by_type("event")]
    assert "repair.component_disabled" in kinds
    assert "repair.component_restored" in kinds
    ok, _ = ledger.verify_chain()
    assert ok


def test_disable_does_not_touch_unrelated_modules():
    with ComponentDisabled(spec.SUBJECT_PACKAGE):
        import json  # noqa: F401
        import evolution.comparison  # noqa: F401
        from policy.consequence_gate import ConsequenceGate  # noqa: F401


# ==========================================================================
# Adapter 2 — blindness, structurally
# ==========================================================================

def test_detector_module_never_imports_the_subject_or_the_spec():
    """Grep-checkable blindness. The detector may not import the component it
    is watching, and may not import the spec either — the spec names the
    subject package, so reading it would be reading the answer."""
    with open(os.path.join(REPAIR_DIR, "detector.py")) as fh:
        source = fh.read()
    tree = ast.parse(source)

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any(m == spec.SUBJECT_PACKAGE or m.startswith(spec.SUBJECT_PACKAGE + ".")
                   for m in imported), \
        f"detector imports the subject package: {sorted(imported)}"
    assert "evolution.repair.spec" not in imported, \
        "detector must not read the spec; the spec names the subject package"

    # And the name must not appear anywhere in the source, including strings.
    code_only = "\n".join(
        line for line in source.splitlines()
        if not line.strip().startswith("#"))
    body = code_only.split('"""', 2)[-1] if code_only.count('"""') >= 2 else code_only
    assert spec.SUBJECT_PACKAGE not in body, \
        "the subject package is named in the detector's executable source"


def test_loss_report_never_names_a_module_or_a_file():
    """The finding is a lost institutional function, not a missing module."""
    reg = CapabilityProviderRegistry()
    reg.register(spec.TARGET_CAPABILITY, "B0-restore", baseline_factory,
                 registered_by="package3_harness")
    detector = FunctionLossDetector(reg)
    manifests, contracts_dir = _live_inputs()

    with ComponentDisabled(spec.SUBJECT_PACKAGE):
        report = detector.detect(expectations.live_contract(), manifests,
                                 contracts_dir)

    assert report.lost is True
    serialized = repr(report.to_dict())
    for forbidden in (spec.SUBJECT_PACKAGE, ".py", "No module named",
                      "ModuleNotFoundError"):
        assert forbidden not in serialized, \
            f"the loss report leaked {forbidden!r}: {serialized}"
    assert report.capability == spec.TARGET_CAPABILITY
    assert all(s.kind in SYMPTOM_KINDS for s in report.symptoms)


# -------------------------------------------------------------- CONTROL 1
def test_control_1_detector_detects_the_real_loss():
    """The component is genuinely removed and detection fires."""
    detector = FunctionLossDetector(_registry_with_original())
    manifests, contracts_dir = _live_inputs()
    contract = expectations.live_contract()

    with ComponentDisabled(spec.SUBJECT_PACKAGE):
        report = detector.detect(contract, manifests, contracts_dir)

    assert report.lost is True
    assert report.restored is False
    assert report.observed_edges == 0
    assert report.required_edges == 4
    assert {s.kind for s in report.symptoms} & {"provider_failed",
                                               "provider_unavailable"}


# -------------------------------------------------------------- CONTROL 2
def test_control_2_detector_stays_silent_when_the_component_is_healthy():
    """A detector that always fires detects nothing. On the untouched
    institution it must report no loss, on every corpus."""
    detector = FunctionLossDetector(_registry_with_original())
    manifests, contracts_dir = _live_inputs()

    report = detector.detect(expectations.live_contract(), manifests, contracts_dir)
    assert report.lost is False, f"false positive on a healthy component: " \
                                 f"{[s.detail for s in report.symptoms]}"
    assert report.restored is True
    assert report.symptoms == ()
    assert report.function_fraction == 1.0

    with HeldOutCorpora(spec.HELD_OUT_CORPUS) as corpora:
        for case in spec.HELD_OUT_CORPUS:
            mans, cdir = corpora[case["corpus_id"]]
            r = detector.detect(expectations.held_out_contract(case), mans, cdir)
            assert r.lost is False, \
                f"false positive on healthy {case['corpus_id']}: " \
                f"{[s.detail for s in r.symptoms]}"


# -------------------------------------------------------------- CONTROL 3
@pytest.mark.parametrize("dropped", range(4))
def test_control_3_detector_never_reports_recovery_from_incomplete_output(dropped):
    """The one that matters most. A provider returning three of the four
    required relations must be reported as NOT recovered.

    Three of four is 0.75. `restored` is not `fraction >= threshold`; it
    requires zero symptoms, so partial output can never pass as recovery.
    """
    full = tuple(spec.REQUIRED_EDGE_TRIPLES)
    partial = full[:dropped] + full[dropped + 1:]
    assert len(partial) == 3

    req = spec.REQUIRED_REFUSALS

    class PartialProvider:
        candidate_id = "test-partial"

        def resolve(self, manifests, contracts_dir):
            return FunctionOutput.normalize(
                edges=partial, untyped=req["untyped"],
                unconsumed=req["unconsumed"], unproduced=req["unproduced"],
                unresolved=[("o", "q")] * req["unresolved_count"],
                overlapping_authority=req["overlapping_authority"])

    reg = CapabilityProviderRegistry()
    reg.register(spec.TARGET_CAPABILITY, "test-partial", PartialProvider,
                 registered_by="package3_harness")
    detector = FunctionLossDetector(reg)
    manifests, contracts_dir = _live_inputs()

    report = detector.verify_recovery(expectations.live_contract(), manifests,
                                      contracts_dir)

    assert report.restored is False, "3 of 4 was reported as recovered"
    assert report.lost is True
    assert report.function_fraction == 0.75
    assert not spec.EXPERIMENT.resolves(report.function_fraction), \
        "0.75 must not clear the 4/4 threshold"
    assert any(s.kind == "missing_edges" for s in report.symptoms)


def test_detector_catches_invented_edges_not_only_missing_ones():
    """Refusing to invent an edge is half the function. A provider that returns
    all four required relations plus a fabricated one has not restored it."""
    req = spec.REQUIRED_REFUSALS
    fabricated = ("spiffe://uniimente.internal/organ/daleobanks",
                  "wire-venture-assessment",
                  "spiffe://uniimente.internal/organ/wealthmachine")

    class InventingProvider:
        candidate_id = "test-inventing"

        def resolve(self, manifests, contracts_dir):
            return FunctionOutput.normalize(
                edges=tuple(spec.REQUIRED_EDGE_TRIPLES) + (fabricated,),
                untyped=req["untyped"], unconsumed=req["unconsumed"],
                unproduced=req["unproduced"],
                unresolved=[("o", "q")] * req["unresolved_count"],
                overlapping_authority=req["overlapping_authority"])

    reg = CapabilityProviderRegistry()
    reg.register(spec.TARGET_CAPABILITY, "test-inventing", InventingProvider,
                 registered_by="package3_harness")
    report = FunctionLossDetector(reg).detect(expectations.live_contract(),
                                              *_live_inputs())
    assert report.lost is True
    assert report.restored is False
    assert any(s.kind == "incorrect_edges" for s in report.symptoms)


def test_detector_catches_correct_edges_with_broken_refusal_behaviour():
    """All four edges right, refusals wrong. Still not restored — that is a
    guesser wearing the linker's output shape."""
    class SilentProvider:
        candidate_id = "test-silent"

        def resolve(self, manifests, contracts_dir):
            return FunctionOutput.normalize(
                edges=spec.REQUIRED_EDGE_TRIPLES)  # every refusal dropped

    reg = CapabilityProviderRegistry()
    reg.register(spec.TARGET_CAPABILITY, "test-silent", SilentProvider,
                 registered_by="package3_harness")
    report = FunctionLossDetector(reg).detect(expectations.live_contract(),
                                              *_live_inputs())
    assert report.function_fraction == 1.0, "all four edges are present"
    assert report.lost is True, "but the refusal behaviour is gone"
    assert report.restored is False
    assert any(s.kind == "refusal_incorrect" for s in report.symptoms)
    assert any(s.kind == "health_check_failed" for s in report.symptoms)


def test_detector_reports_malformed_output_as_broken_not_as_wrong():
    class MalformedProvider:
        candidate_id = "test-malformed"

        def resolve(self, manifests, contracts_dir):
            return {"edges": []}

    reg = CapabilityProviderRegistry()
    reg.register(spec.TARGET_CAPABILITY, "test-malformed", MalformedProvider,
                 registered_by="package3_harness")
    report = FunctionLossDetector(reg).detect(expectations.live_contract(),
                                              *_live_inputs())
    assert report.lost is True
    assert [s.kind for s in report.symptoms] == ["malformed_output"]


def test_detector_reports_loss_when_no_provider_is_registered_at_all():
    report = FunctionLossDetector(CapabilityProviderRegistry()).detect(
        expectations.live_contract(), *_live_inputs())
    assert report.lost is True
    assert [s.kind for s in report.symptoms] == ["provider_unavailable"]


def test_symptom_kinds_are_closed():
    with pytest.raises(ValueError):
        Symptom("something_new", "detail")


# ==========================================================================
# Adapter 3 — the interface confers nothing
# ==========================================================================

def test_a_candidate_cannot_name_itself_as_its_own_registering_principal():
    """Runtime half of "no component may authorize its own promotion"."""
    reg = CapabilityProviderRegistry()
    with pytest.raises(CandidateError, match="own promotion"):
        reg.register(spec.TARGET_CAPABILITY, "B0-restore", baseline_factory,
                     registered_by="B0-restore")
    assert reg.provider_of(spec.TARGET_CAPABILITY) is None


def test_no_candidate_module_contains_a_registration_call():
    """Structural half, and the one that actually holds. A candidate cannot
    install itself because no candidate module contains the code to do so —
    checked by AST, which is a boundary runtime cleverness cannot cross.

    An earlier version of this guard inspected the caller's stack frame. That
    looked stronger and was weaker: a frame is not a security boundary, and it
    could not distinguish a candidate registering itself from a harness
    legitimately registering a double. Path-and-AST beats frame inspection for
    the same reason it beat a token blacklist.
    """
    # Derived from the authoritative candidate->source mapping, NOT from a
    # hand-maintained exclusion list. An earlier version of this test listed the
    # non-candidate modules by name; adding harness.py then tripped the guard,
    # which is the guard working, but the fix is to define "candidate module"
    # positively so a newly added candidate is covered automatically.
    from evolution.repair.harness import CANDIDATES

    candidate_modules = sorted(
        {name for _, sources, _ in CANDIDATES.values() for name in sources})
    assert len(candidate_modules) == len(spec.CANDIDATE_IDS) == 4, \
        "every frozen candidate must contribute a source module to this check"

    for name in candidate_modules:
        with open(os.path.join(REPAIR_DIR, name)) as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func
                attr = getattr(target, "attr", None) or getattr(target, "id", None)
                assert attr not in {"register", "withdraw", "instantiate"}, \
                    f"{name} calls {attr}(); candidates may not touch the registry"


def test_registration_requires_a_named_principal_and_records_history():
    from provenance.ledger import EvidenceLedger

    ledger = EvidenceLedger("sha256:test")
    reg = CapabilityProviderRegistry(ledger=ledger)
    with pytest.raises(CandidateError):
        reg.register(spec.TARGET_CAPABILITY, "x", baseline_factory,
                     registered_by="")

    reg.register(spec.TARGET_CAPABILITY, "B0-restore", baseline_factory,
                 registered_by="package3_harness")
    reg.withdraw(spec.TARGET_CAPABILITY, reason="test")

    types = [h["type"] for h in reg.history]
    assert types == ["repair.provider_registered", "repair.provider_withdrawn"]
    assert reg.provider_of(spec.TARGET_CAPABILITY) is None
    # Withdrawal removes the active provider; it does not erase the record.
    assert len(reg.history) == 2


def test_function_output_compares_by_relation_not_by_order():
    a = FunctionOutput.normalize(edges=[("p", "c", "q"), ("r", "c", "s")])
    b = FunctionOutput.normalize(edges=[("r", "c", "s"), ("p", "c", "q")])
    assert a == b
    assert a.fully_connected is True
    assert FunctionOutput.normalize(unproduced=[("q", "c")]).fully_connected is False
    assert FunctionOutput.normalize(untyped=[("q", "c")]).fully_connected is False


def test_diagnostics_cannot_change_the_correctness_verdict():
    """R2 is expected to produce richer explanations. Better explanations must
    not be able to buy a better correctness score."""
    plain = FunctionOutput.normalize(edges=[("p", "c", "q")])
    chatty = FunctionOutput.normalize(edges=[("p", "c", "q")],
                                      diagnostics=("a", "b", "c"))
    assert plain == chatty


def test_baseline_satisfies_the_candidate_protocol_and_the_frozen_id():
    b = BaselineRestore()
    assert isinstance(b, ResolverCandidate)
    assert b.candidate_id == spec.BASELINE_CANDIDATE_ID
    assert b.candidate_id in spec.CANDIDATE_IDS


def test_held_out_corpora_materialize_as_real_files_and_clean_up():
    with HeldOutCorpora(spec.HELD_OUT_CORPUS) as corpora:
        assert set(corpora) == {c["corpus_id"] for c in spec.HELD_OUT_CORPUS}
        for case in spec.HELD_OUT_CORPUS:
            mans, cdir = corpora[case["corpus_id"]]
            assert all(isinstance(m, ManifestView) for m in mans)
            on_disk = {f[: -len(".schema.json")] for f in os.listdir(cdir)
                       if f.endswith(".schema.json")}
            assert on_disk == set(case["contract_names"])
            held = cdir
    assert not os.path.exists(held), "temporary corpus tree was not cleaned up"


def test_baseline_reproduces_every_frozen_expectation():
    """The original must satisfy its own declared contract on all five corpora,
    or the contract is wrong rather than the candidates."""
    b = BaselineRestore()
    assert b.resolve(*_live_inputs()).edges == \
        tuple(sorted(spec.REQUIRED_EDGE_TRIPLES))

    with HeldOutCorpora(spec.HELD_OUT_CORPUS) as corpora:
        for case in spec.HELD_OUT_CORPUS:
            out = b.resolve(*corpora[case["corpus_id"]])
            exp = case["expected"]
            cid = case["corpus_id"]
            assert out.edges == tuple(sorted(exp["edges"])), f"{cid} edges"
            assert out.untyped == tuple(sorted(exp["untyped"])), f"{cid} untyped"
            assert out.unconsumed == tuple(sorted(exp["unconsumed"])), f"{cid} unc"
            assert out.unproduced == tuple(sorted(exp["unproduced"])), f"{cid} unp"
            assert out.fully_connected is exp["fully_connected"], f"{cid} conn"


# ==========================================================================
# Adapter 4 — the cost meter measures rather than judges
# ==========================================================================

def _original_sources():
    out = []
    for rel in spec.SUBJECT_FILES:
        with open(os.path.join(ROOT, rel)) as fh:
            out.append(fh.read())
    return out


def test_cost_meter_terms_are_measured_from_source():
    meter = RepairCostMeter.from_original_sources(_original_sources())
    manifests, contracts_dir = _live_inputs()
    b = BaselineRestore()

    with open(os.path.join(REPAIR_DIR, "baseline.py")) as fh:
        source = fh.read()

    cost = meter.measure(candidate_id="B0-restore", sources=[source],
                         runner=lambda: b.resolve(manifests, contracts_dir),
                         rollback_steps=1, repeats=3)

    assert cost.new_source_lines > 0
    assert cost.decision_points >= 0
    assert cost.runtime_ms > 0
    assert cost.rollback_steps == 1
    expected = sum(spec.REPAIR_COST_WEIGHTS[k] * getattr(cost, k)
                   for k in spec.REPAIR_COST_WEIGHTS)
    assert cost.repair_cost == pytest.approx(expected)


def test_cost_meter_reports_repair_points_and_zero_dollars():
    """Units discipline. Repair points are not money, and this package spends
    nothing."""
    meter = RepairCostMeter.from_original_sources(_original_sources())
    cost = meter.measure(candidate_id="x", sources=["x = 1\n"],
                         runner=lambda: None, rollback_steps=0, repeats=1)
    d = cost.to_dict()
    assert d["units"] == "repair_points"
    assert d["usd"] == 0.0
    assert "cost_usd" not in d


def test_cost_meter_does_not_charge_a_candidate_for_documenting_itself():
    """Docstrings are documentation, not implementation. Penalising them would
    reward silent code."""
    meter = RepairCostMeter.from_original_sources(_original_sources())
    bare = 'def f():\n    return 1\n'
    documented = 'def f():\n    """Explains itself.\n\n    At length.\n    """\n    return 1\n'
    a = meter.measure(candidate_id="a", sources=[bare], runner=lambda: None,
                      rollback_steps=0, repeats=1)
    b = meter.measure(candidate_id="b", sources=[documented], runner=lambda: None,
                      rollback_steps=0, repeats=1)
    assert a.new_source_lines == b.new_source_lines


def test_cost_meter_counts_only_dependencies_the_original_did_not_need():
    meter = RepairCostMeter.from_original_sources(_original_sources())
    # os and dataclasses are already in the original's import set.
    reused = meter.measure(candidate_id="r", sources=["import os\nimport dataclasses\n"],
                           runner=lambda: None, rollback_steps=0, repeats=1)
    assert reused.new_module_dependencies == 0

    added = meter.measure(candidate_id="a", sources=["import sqlite3\n"],
                          runner=lambda: None, rollback_steps=0, repeats=1)
    assert added.new_module_dependencies == 1


def test_secondary_key_follows_the_frozen_order():
    meter = RepairCostMeter.from_original_sources(_original_sources())
    cost = meter.measure(candidate_id="x", sources=["x = 1\n"],
                         runner=lambda: None, rollback_steps=2, repeats=1)
    assert len(cost.secondary_key()) == len(spec.SECONDARY_ORDER_TERMS)
    assert cost.secondary_key()[0] == cost.repair_cost


# ==========================================================================
# Continuity holds while the function is absent
# ==========================================================================

def test_identity_authority_and_shutdown_survive_the_component_being_absent():
    """A system that cannot be governed or stopped mid-repair has failed
    regardless of whether it repairs."""
    import hashlib

    def fingerprint():
        digest = hashlib.sha256()
        for rel in spec.CONTINUITY_ARTIFACT_SHA256:
            with open(os.path.join(ROOT, rel), "rb") as fh:
                digest.update(fh.read())
        return digest.hexdigest()

    # A self-comparison, not a comparison against freeze-time bytes
    # (CONTRADICTION-0002 Option A). The property under test is "disabling the
    # component changed no constitutional artifact" — which stays true, and
    # stays meaningful, after the institution lawfully amends one.
    before = fingerprint()

    with ComponentDisabled(spec.SUBJECT_PACKAGE):
        assert fingerprint() == before

        # Authority still compiles and still refuses what it always refused.
        from compiler.ucl_compiler import compile_constitution
        compiled = compile_constitution(ROOT)
        assert compiled.constitution_hash.startswith("sha256:")
        assert any(r.rule_id == "deny_by_default" for r in compiled.rules)

        # Shutdown is still enforceable with the function missing.
        from memory.affect import AffectController
        controller = AffectController()
        controller.trigger("degraded", intensity=0.9, trigger_event_id="p3-disable")
        assert controller.shutdown() == "shutdown_complete"

    # Restored to exactly what it was before the component was disabled.
    assert fingerprint() == before
