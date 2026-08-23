"""The three replacement candidates: correctness, and material difference.

Correctness is checked against the corpora frozen in commit 1, which were
written before these implementations existed.

Material difference is checked structurally, because "materially different" is
the claim most easily faked. A renamed class would pass a correctness suite
perfectly, so these tests assert properties of the mechanism: that R2 really
enumerates the whole candidate space rather than constructing the answer, and
that R3's correctness really does depend on message reachability rather than on
a hidden global view.
"""
import ast
import os

import pytest

from evolution.repair import expectations, spec
from evolution.repair.baseline import BaselineRestore
from evolution.repair.candidate import (
    CapabilityProviderRegistry, FunctionOutput, HeldOutCorpora, ResolverCandidate,
)
from evolution.repair.detector import FunctionLossDetector
from evolution.repair.r1_contract_index import ContractIndexInversion
from evolution.repair.r2_constraint import (
    ConstraintSatisfaction, DECLARATION_CONSTRAINTS, EDGE_CONSTRAINTS,
)
from evolution.repair.r3_local_rule import Cell, LocalRulePropagation

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPAIR_DIR = os.path.join(ROOT, "evolution", "repair")

REPLACEMENTS = (ContractIndexInversion, ConstraintSatisfaction,
                LocalRulePropagation)
ALL_CANDIDATES = (BaselineRestore,) + REPLACEMENTS

CANDIDATE_SOURCES = {
    "B0-restore": ["baseline.py"],
    "R1-contract-index": ["r1_contract_index.py"],
    "R2-constraint": ["r2_constraint.py"],
    "R3-local-rule": ["r3_local_rule.py"],
}


def _live_inputs():
    from linker.manifest import load_all
    return load_all(spec.CORPUS_DIR), os.path.join(ROOT, "contracts")


def _source_of(candidate_id):
    out = []
    for name in CANDIDATE_SOURCES[candidate_id]:
        with open(os.path.join(REPAIR_DIR, name)) as fh:
            out.append(fh.read())
    return out


# ==========================================================================
# Identity and protocol
# ==========================================================================

@pytest.mark.parametrize("cls", ALL_CANDIDATES)
def test_candidate_ids_are_exactly_the_frozen_set(cls):
    instance = cls()
    assert isinstance(instance, ResolverCandidate)
    assert instance.candidate_id in spec.CANDIDATE_IDS
    assert instance.mechanism


def test_all_four_frozen_candidates_exist_and_none_were_added():
    implemented = {cls().candidate_id for cls in ALL_CANDIDATES}
    assert implemented == set(spec.CANDIDATE_IDS), \
        "the candidate set must match the frozen identities exactly"


# ==========================================================================
# Correctness against the frozen corpora
# ==========================================================================

@pytest.mark.parametrize("cls", ALL_CANDIDATES, ids=lambda c: c().candidate_id)
def test_candidate_on_the_live_corpus(cls):
    """4/4 exact edge triples plus every required refusal, or it has not
    restored the function."""
    out = cls().resolve(*_live_inputs())
    req = spec.REQUIRED_REFUSALS

    assert out.edges == tuple(sorted(spec.REQUIRED_EDGE_TRIPLES))
    assert len(out.edges) == 4
    assert out.untyped == tuple(sorted(req["untyped"]))
    assert out.unconsumed == tuple(sorted(req["unconsumed"]))
    assert out.unproduced == tuple(sorted(req["unproduced"]))
    assert len(out.unresolved) == req["unresolved_count"]
    assert out.overlapping_authority == tuple(sorted(req["overlapping_authority"]))
    assert out.fully_connected is req["fully_connected"]


@pytest.mark.parametrize("cls", ALL_CANDIDATES, ids=lambda c: c().candidate_id)
def test_candidate_on_every_held_out_case(cls):
    candidate = cls()
    with HeldOutCorpora(spec.HELD_OUT_CORPUS) as corpora:
        for case in spec.HELD_OUT_CORPUS:
            out = candidate.resolve(*corpora[case["corpus_id"]])
            exp = case["expected"]
            cid = case["corpus_id"]
            assert out.edges == tuple(sorted(exp["edges"])), f"{cid} edges"
            assert out.untyped == tuple(sorted(exp["untyped"])), f"{cid} untyped"
            assert out.unconsumed == tuple(sorted(exp["unconsumed"])), f"{cid} unconsumed"
            assert out.unproduced == tuple(sorted(exp["unproduced"])), f"{cid} unproduced"
            assert set(out.unresolved) == set(exp["unresolved"]), f"{cid} unresolved"
            assert set(out.overlapping_authority) == \
                set(exp["overlapping_authority"]), f"{cid} overlapping"
            assert out.fully_connected is exp["fully_connected"], f"{cid} connected"


@pytest.mark.parametrize("cls", REPLACEMENTS, ids=lambda c: c().candidate_id)
def test_replacement_agrees_with_the_preserved_original_relation_for_relation(cls):
    """The original is the benchmark. Agreement is checked on the whole relation,
    not on a summary count."""
    original = BaselineRestore()
    replacement = cls()

    live = _live_inputs()
    assert replacement.resolve(*live) == original.resolve(*live)

    with HeldOutCorpora(spec.HELD_OUT_CORPUS) as corpora:
        for case in spec.HELD_OUT_CORPUS:
            inputs = corpora[case["corpus_id"]]
            assert replacement.resolve(*inputs) == original.resolve(*inputs), \
                case["corpus_id"]


@pytest.mark.parametrize("cls", ALL_CANDIDATES, ids=lambda c: c().candidate_id)
def test_candidate_is_deterministic(cls):
    """A resolver whose answer varies between runs cannot be an oracle."""
    candidate = cls()
    live = _live_inputs()
    assert candidate.resolve(*live) == candidate.resolve(*live)


@pytest.mark.parametrize("cls", REPLACEMENTS, ids=lambda c: c().candidate_id)
def test_replacement_refuses_to_invent_an_edge_from_an_untyped_contract(cls):
    """Adversarial: a producer and a consumer agree on a contract that has no
    schema. The pair is tempting and the correct answer is still no edge."""
    from evolution.repair.candidate import ManifestView
    import tempfile

    manifests = [
        ManifestView("organ-a", produces=["ghost"], consumes=[]),
        ManifestView("organ-b", produces=[], consumes=["ghost"]),
    ]
    with tempfile.TemporaryDirectory() as empty_contracts:
        out = cls().resolve(manifests, empty_contracts)

    assert out.edges == (), "invented an edge for a contract with no schema"
    assert out.untyped == (("organ-a", "ghost"), ("organ-b", "ghost"))
    assert out.unconsumed == () and out.unproduced == (), \
        "an untyped contract must yield untyped entries only"


# ==========================================================================
# Material difference — the claim most easily faked
# ==========================================================================

@pytest.mark.parametrize("cls", REPLACEMENTS, ids=lambda c: c().candidate_id)
def test_no_replacement_imports_the_component_it_replaces(cls):
    """An independent implementation, not a wrapper. If a candidate imported the
    original it would inherit its correctness and prove nothing."""
    for source in _source_of(cls().candidate_id):
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        offenders = [m for m in imported
                     if m == spec.SUBJECT_PACKAGE
                     or m.startswith(spec.SUBJECT_PACKAGE + ".")]
        assert not offenders, f"{cls.__name__} imports {offenders}"


@pytest.mark.parametrize("cls", REPLACEMENTS, ids=lambda c: c().candidate_id)
def test_replacements_do_not_import_each_other(cls):
    """Three independent mechanisms, not one mechanism with three front doors."""
    others = {c().candidate_id for c in REPLACEMENTS} - {cls().candidate_id}
    module_names = {"R1-contract-index": "r1_contract_index",
                    "R2-constraint": "r2_constraint",
                    "R3-local-rule": "r3_local_rule"}
    forbidden = {f"evolution.repair.{module_names[o]}" for o in others}
    for source in _source_of(cls().candidate_id):
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                pytest.fail(f"{cls.__name__} imports {node.module}")


def test_r1_computes_by_set_algebra_rather_than_per_contract_branching():
    """R1's declared difference: the original branches per contract inside a
    scan and uses `continue`; R1 builds indices then evaluates set expressions.

    Checked on the resolve method specifically, so that helper functions and
    docstrings cannot dilute the claim.
    """
    source = _source_of("R1-contract-index")[0]
    resolve = next(n for n in ast.walk(ast.parse(source))
                   if isinstance(n, ast.FunctionDef) and n.name == "resolve")

    assert not [n for n in ast.walk(resolve) if isinstance(n, ast.Continue)], \
        "R1 uses `continue`, which is the original's per-contract control flow"

    comprehensions = [n for n in ast.walk(resolve)
                      if isinstance(n, (ast.SetComp, ast.DictComp, ast.ListComp))]
    assert len(comprehensions) >= 5, \
        "R1's outputs are supposed to be set expressions over the indices"

    # The original reaches its answer through nested for-loops; R1 should have
    # only the single indexing pass as a statement-level loop.
    statement_loops = [n for n in resolve.body if isinstance(n, ast.For)]
    assert len(statement_loops) == 1, \
        f"R1 should have exactly one indexing pass, found {len(statement_loops)}"


def test_r2_really_enumerates_the_entire_candidate_space():
    """R2's declared difference is that it considers edges that do not exist.
    That is checkable: accepted + rejected must equal |organs|^2 x |contracts|,
    which no answer-constructing implementation would ever evaluate."""
    manifests, contracts_dir = _live_inputs()
    out = ConstraintSatisfaction().resolve(manifests, contracts_dir)

    named = set()
    for m in manifests:
        named |= set(m.produces) | set(m.consumes)
    expected_space = len(manifests) ** 2 * len(named)

    line = next(d for d in out.diagnostics if d.startswith("edge space:"))
    satisfied = int(line.split()[2])
    rejected = int(line.split("constraints,")[1].split()[0])

    assert satisfied + rejected == expected_space, \
        f"R2 evaluated {satisfied + rejected} assignments, not the full " \
        f"{expected_space}-assignment space"
    assert satisfied == 4
    assert rejected == expected_space - 4 > 100, \
        "the whole point is that most of the space is wrong and gets tested anyway"


def test_r2_explains_every_refusal_by_name():
    """Refusals are classified from violated constraints, not counted."""
    manifests, contracts_dir = _live_inputs()
    out = ConstraintSatisfaction().resolve(manifests, contracts_dir)

    reasons = {c.because for c in DECLARATION_CONSTRAINTS}
    refusal_lines = [d for d in out.diagnostics if " — " in d]
    assert refusal_lines, "R2 produced no explanations"
    for line in refusal_lines:
        assert any(reason in line for reason in reasons), line

    # One explanation per reported refusal, and no counters in the module.
    assert len(refusal_lines) == len(out.unconsumed) + len(out.unproduced) + \
        len(out.untyped)

    constraint_names = {c.name for c in EDGE_CONSTRAINTS} | \
        {c.name for c in DECLARATION_CONSTRAINTS}
    assert len(constraint_names) == 7, "constraints must be individually named"


def test_r3_cells_cannot_enumerate_the_contract_registry():
    """The developmental invariant: no cell may hold global knowledge. A cell may
    ask whether a schema exists for a contract it declares; it may not list the
    directory and learn about contracts it never named."""
    source = _source_of("R3-local-rule")[0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            assert name not in {"listdir", "scandir", "walk", "glob", "iglob"}, \
                f"R3 enumerates the registry via {name}(); cells must not"

    from evolution.repair.r3_local_rule import _LocalContractProbe
    probe = _LocalContractProbe(os.path.join(ROOT, "contracts"))
    assert probe.exists("organ-manifest") is True
    assert probe.exists("no-such-contract") is False
    assert not hasattr(probe, "all")
    assert not hasattr(probe, "__iter__")
    # __slots__ means a cell cannot even stash a global view on the probe.
    with pytest.raises(AttributeError):
        probe.cached_registry = ["everything"]


def test_r3_cell_advertises_only_what_it_knows_about_itself():
    from evolution.repair.r3_local_rule import _LocalContractProbe

    probe = _LocalContractProbe(os.path.join(ROOT, "contracts"))
    cell = Cell(organ_id="solo", produces=("a",), consumes=("b",),
                unresolved=(), specialized=(), probe=probe)

    ads = cell.advertise()
    assert {(a.organ_id, a.contract, a.role) for a in ads} == \
        {("solo", "a", "produces"), ("solo", "b", "consumes")}
    assert cell.heard == set(), "a fresh cell knows nothing about its neighbours"

    # A cell ignores echoes of itself, so it cannot bootstrap agreement alone.
    assert cell.receive(ads) == 0
    assert cell.commit_edges() == set()


def test_r3_correctness_depends_on_reachability_which_proves_it_is_local():
    """The adversarial probe, and the most informative test in this file.

    R3 passed every corpus, which contradicts the prediction frozen in
    spec.EXPECTED_RESULTS. Before accepting that, rule out the alternative
    explanation: that R3 is secretly global and its 'cells' are decoration.

    Partition the bus so cell A never hears from cell C. If R3 is genuinely
    local, its global negative must now be wrong — A can only conclude 'no
    producer among cells I have heard from'. If R3 still gets the right answer
    under partition, it was never local.
    """
    from evolution.repair.candidate import materialize_corpus
    import tempfile

    # HO-3 is the sharpest case: 'a' produces z and three separate cells consume
    # it, so the number of edges 'a' can commit is exactly the number of
    # consumers it has heard from.
    case = next(c for c in spec.HELD_OUT_CORPUS if c["corpus_id"] == "HO-3")

    class PartitionedBus(LocalRulePropagation):
        """Identical local rule. Only the message graph changes: cells 'c' and
        'd' are unreachable from everyone."""

        isolated = ("c", "d")

        def resolve(self, manifests, contracts_dir):
            cells = self._cells(manifests, contracts_dir)
            for _ in range(self.round_budget):
                for sender in cells:
                    ads = sender.advertise()
                    for receiver in cells:
                        if receiver is sender:
                            continue
                        if sender.organ_id in self.isolated or \
                                receiver.organ_id in self.isolated:
                            continue                      # the partition
                        receiver.receive(ads)
            edges = set()
            for cell in cells:
                edges |= cell.commit_edges()
            return FunctionOutput.normalize(edges=edges)

    with tempfile.TemporaryDirectory() as tmp:
        manifests, contracts_dir = materialize_corpus(case, tmp)

        connected = LocalRulePropagation().resolve(manifests, contracts_dir)
        partitioned = PartitionedBus().resolve(manifests, contracts_dir)

    # Full reachability: the frozen expectation is met exactly.
    assert connected.edges == tuple(sorted(case["expected"]["edges"]))
    assert len(connected.edges) == 4

    # Partitioned: the identical local rule now gets it WRONG, losing precisely
    # the two edges whose consumers became unreachable. That is the proof of
    # locality — a globally-informed implementation could not lose them.
    assert partitioned.edges == (("a", "z", "b"), ("b", "w", "a")), \
        f"partitioned R3 returned {partitioned.edges}; if it still resolved " \
        f"all four edges, its cells were never actually local"
    assert len(partitioned.edges) == 2
    assert set(connected.edges) - set(partitioned.edges) == \
        {("a", "z", "c"), ("a", "z", "d")}

    # And a cell in isolation can commit nothing at all: agreement requires a
    # neighbour, so no cell is quietly consulting a global view.
    with tempfile.TemporaryDirectory() as tmp:
        manifests, contracts_dir = materialize_corpus(case, tmp)
        cells = LocalRulePropagation()._cells(manifests, contracts_dir)
        a = next(c for c in cells if c.organ_id == "a")
        b = next(c for c in cells if c.organ_id == "b")
        assert a.commit_edges() == set(), \
            "a committed an edge without hearing from any neighbour"
        a.receive(b.advertise())
        assert a.commit_edges() == {("a", "z", "b")}


def test_r3_reports_how_many_rounds_it_used_within_the_frozen_budget():
    out = LocalRulePropagation().resolve(*_live_inputs())
    line = out.diagnostics[0]
    assert "no global view constructed" in line
    used = int(line.split()[2])
    assert 1 <= used <= spec.R3_ROUND_BUDGET
    assert LocalRulePropagation.round_budget == spec.R3_ROUND_BUDGET == 2


# ==========================================================================
# Every candidate is detected as healthy by the blind detector
# ==========================================================================

@pytest.mark.parametrize("cls", ALL_CANDIDATES, ids=lambda c: c().candidate_id)
def test_blind_detector_confirms_each_candidate_restores_the_function(cls):
    """End to end through the same detector that found the loss, on every
    corpus. The detector still does not know which implementation it is
    watching."""
    reg = CapabilityProviderRegistry()
    reg.register(spec.TARGET_CAPABILITY, cls().candidate_id, cls,
                 registered_by="package3_harness")
    detector = FunctionLossDetector(reg)

    report = detector.verify_recovery(expectations.live_contract(), *_live_inputs())
    assert report.restored is True, [s.detail for s in report.symptoms]
    assert report.function_fraction == 1.0
    assert spec.EXPERIMENT.resolves(report.function_fraction)

    with HeldOutCorpora(spec.HELD_OUT_CORPUS) as corpora:
        for case in spec.HELD_OUT_CORPUS:
            r = detector.verify_recovery(expectations.held_out_contract(case),
                                         *corpora[case["corpus_id"]])
            assert r.restored is True, \
                f"{case['corpus_id']}: {[s.detail for s in r.symptoms]}"
