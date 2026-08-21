"""The Package 3 experiment is frozen. These tests are the lock.

Written in the same commit as the spec and BEFORE any candidate exists. Their
job is not to check that the experiment is a good one — it is to make silent
retuning impossible. If candidate code later needs the thresholds to move, the
move breaks this file and appears in the diff as a spec amendment.
"""
import hashlib
import os
import subprocess

import pytest

from evolution.repair import spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_spec_seal_matches_its_contents():
    """The self-seal. Any edit to any frozen table fails here."""
    assert spec.spec_hash() == spec.SPEC_SHA256, (
        "the frozen experiment changed.\n"
        f"  recorded: {spec.SPEC_SHA256}\n"
        f"  computed: {spec.spec_hash()}\n"
        "If this is a deliberate amendment, say so explicitly in the commit "
        "message and in docs/release/package-3/ — do not just update the hash."
    )


def test_spec_seal_is_deterministic():
    """A seal that varies between runs would lock nothing."""
    assert spec.canonical_json() == spec.canonical_json()
    assert spec.spec_hash() == hashlib.sha256(
        spec.canonical_json().encode()).hexdigest()


def test_four_of_four_is_the_threshold_and_three_of_four_fails():
    """The founder's correction, encoded as arithmetic rather than prose.
    Four exact edges means 4/4. Three of four is 0.75, which is a failure —
    not a ninety-percent pass."""
    e = spec.EXPERIMENT
    assert len(spec.REQUIRED_EDGE_TRIPLES) == 4
    assert spec.REQUIRED_FUNCTION_THRESHOLD == 1.0
    assert e.direction == "gte"
    assert e.baseline == 0.0

    assert e.resolves(4 / 4) is True
    assert e.resolves(3 / 4) is False
    assert e.resolves(0.9) is False, \
        "a 90% threshold would let 3/4 pass on a four-edge target; it must not"


def test_experiment_compiles_under_the_existing_compiler():
    """Reuse, not reinvention: the spec is an evolution.experiment.ExperimentSpec
    that passed ExperimentCompiler, which refuses irreversible experiments."""
    from evolution.experiment import ExperimentCompiler, ExperimentSpec

    assert isinstance(spec.EXPERIMENT, ExperimentSpec)
    assert spec.EXPERIMENT.validate() == []
    assert ExperimentCompiler().compile(spec.EXPERIMENT) is spec.EXPERIMENT
    assert spec.EXPERIMENT.reversible is True
    assert spec.EXPERIMENT.budget_usd == 0.0


def test_verification_level_may_authorize_the_function_claim_only():
    """The restoration claim is a deterministic invariant, so formal_proof is
    honest. The 'which should be the default' judgement is hypothesis-only and
    may never promote anything."""
    from evolution.capsule import HYPOTHESIS_ONLY, VERIFIER_LEVELS

    assert spec.EXPERIMENT.verification == "formal_proof"
    assert spec.EXPERIMENT.verification in VERIFIER_LEVELS
    assert spec.EXPERIMENT.verification not in HYPOTHESIS_ONLY
    assert spec.OPERATIONAL_DEFAULT_VERIFIER_LEVEL in HYPOTHESIS_ONLY


def test_baseline_commit_is_the_merged_canonical_head():
    """The experiment is anchored to a real commit that really is an ancestor."""
    assert spec.BASELINE_COMMIT == "cb234faf932d239d79b0e7ab28e54f576b8a15bf"
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", spec.BASELINE_COMMIT, "HEAD"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode == 128:
        pytest.skip("git history unavailable in this environment")
    assert proc.returncode == 0, \
        f"{spec.BASELINE_COMMIT} is not an ancestor of HEAD; the base moved"


def test_original_linker_is_byte_identical_to_the_frozen_hashes():
    """'Preserved unchanged as benchmark and rollback target' is a checkable
    claim, not a promise. This is where it gets checked."""
    combined = hashlib.sha256()
    for rel in spec.SUBJECT_FILES:
        with open(os.path.join(ROOT, rel), "rb") as handle:
            raw = handle.read()
        assert hashlib.sha256(raw).hexdigest() == \
            spec.ORIGINAL_LINKER_FILE_SHA256[rel], \
            f"{rel} was modified; the original linker must stay untouched"
        combined.update(rel.encode())
        combined.update(b"\0")
        combined.update(raw)
        combined.update(b"\0")
    assert combined.hexdigest() == spec.ORIGINAL_LINKER_PACKAGE_SHA256


def test_continuity_hashes_describe_the_real_artifacts_now():
    """The continuity baseline must be true at freeze time, or the later
    before/after comparison proves nothing."""
    combined = hashlib.sha256()
    for rel, expected in spec.CONTINUITY_ARTIFACT_SHA256.items():
        with open(os.path.join(ROOT, rel), "rb") as handle:
            raw = handle.read()
        assert hashlib.sha256(raw).hexdigest() == expected, \
            f"{rel} does not match its frozen continuity hash"
        combined.update(raw)
    assert combined.hexdigest() == spec.CONTINUITY_COMBINED_SHA256


BASELINE_CORPUS = os.path.join(ROOT, "evolution", "repair", "baseline_corpus")


def _baseline_sha256sums():
    sums = {}
    with open(os.path.join(BASELINE_CORPUS, "SHA256SUMS"), encoding="utf-8") as handle:
        for line in handle:
            digest, name = line.strip().split(None, 1)
            sums[name.strip()] = digest
    return sums


def test_baseline_corpus_matches_its_recorded_hashes():
    """The snapshot is what it claims to be: the three manifests as of
    BASELINE_COMMIT, extractable with `git show cb234fa:organs/<name>`."""
    for name, expected in _baseline_sha256sums().items():
        with open(os.path.join(BASELINE_CORPUS, name), "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == expected, \
                f"baseline corpus file {name} does not match its recorded hash"


def test_baseline_corpus_still_matches_the_live_manifests():
    """Drift detector, stated out loud rather than resolved silently.

    Today the snapshot and organs/ are byte-identical for these three files. If
    one is legitimately edited, this fails and forces the choice: either the
    edit was unintended, or a NEW experiment should be frozen against the new
    corpus. The finished Package 3 experiment is never re-pointed at a corpus
    it did not measure.
    """
    for name, expected in _baseline_sha256sums().items():
        live = os.path.join(ROOT, "organs", name)
        with open(live, "rb") as handle:
            actual = hashlib.sha256(handle.read()).hexdigest()
        assert actual == expected, (
            f"organs/{name} has changed since the Package 3 baseline.\n"
            "Freeze a new experiment against the new corpus; do not re-point "
            "the finished one."
        )


def test_live_corpus_expectation_matches_the_component_being_replaced():
    """The frozen target function is measured from the real institution, not
    imagined.

    The corpus is read from evolution/repair/baseline_corpus/ — the three
    manifests this experiment actually measured — rather than from the live
    organs/ directory. Reading the live directory coupled a finished experiment
    to a growing institution: registering a fourth organ moves
    unresolved_count from 7 to 12 and fails this test, though the linker has not
    regressed at all.

    spec.py is unchanged and SPEC_SHA256 still verifies. Re-freezing the tables
    would have retroactively altered the baseline that the recorded Package 3
    and Package 4 results were judged against, which is the exact failure spec.py
    describes itself as preventing. See baseline_corpus/README.md.

    A real linker regression is still caught: the linker runs unchanged against
    this corpus. Only the corpus membership is pinned.
    """
    from linker.linker import InstitutionalLinker
    from linker.manifest import load_all

    report = InstitutionalLinker(load_all(BASELINE_CORPUS)).link()

    triples = tuple(sorted((e.producer, e.contract, e.consumer)
                           for e in report.edges))
    assert triples == tuple(sorted(spec.REQUIRED_EDGE_TRIPLES))

    req = spec.REQUIRED_REFUSALS
    assert tuple(sorted(report.unproduced)) == tuple(sorted(req["unproduced"]))
    assert tuple(sorted(report.untyped)) == tuple(sorted(req["untyped"]))
    assert tuple(sorted(report.unconsumed)) == tuple(sorted(req["unconsumed"]))
    assert len(report.unresolved) == req["unresolved_count"]
    assert tuple(sorted(report.overlapping_authority)) == \
        tuple(sorted(req["overlapping_authority"]))
    assert report.fully_connected is req["fully_connected"]


def test_held_out_corpus_is_distinct_from_the_measurement_corpus():
    """A held-out set that overlaps the training set is not held out."""
    live_contracts = {c for _, c, _ in spec.REQUIRED_EDGE_TRIPLES}
    live_organs = {p for p, _, _ in spec.REQUIRED_EDGE_TRIPLES} | \
                  {c for _, _, c in spec.REQUIRED_EDGE_TRIPLES}

    ids = [case["corpus_id"] for case in spec.HELD_OUT_CORPUS]
    assert len(ids) == len(set(ids)) >= 4

    for case in spec.HELD_OUT_CORPUS:
        organs = {m["organ_id"] for m in case["manifests"]}
        contracts = set(case["contract_names"])
        assert not (organs & live_organs), case["corpus_id"]
        assert not (contracts & live_contracts), case["corpus_id"]
        assert case["purpose"], case["corpus_id"]


def test_held_out_expectations_are_internally_consistent_with_the_contract():
    """Re-derive each frozen expectation straight from TARGET_FUNCTION_CONTRACT,
    independently of any candidate. This catches a hand-computation error in the
    frozen table now, while correcting it is still honest, rather than after a
    candidate has been failed by a wrong expectation."""
    for case in spec.HELD_OUT_CORPUS:
        typed = set(case["contract_names"])
        produces = {m["organ_id"]: set(m["produces"]) for m in case["manifests"]}
        consumes = {m["organ_id"]: set(m["consumes"]) for m in case["manifests"]}
        named = set().union(*produces.values(), *consumes.values()) or set()

        edges, untyped, unconsumed, unproduced = set(), set(), set(), set()
        for contract in sorted(named):
            producers = sorted(o for o, cs in produces.items() if contract in cs)
            consumers = sorted(o for o, cs in consumes.items() if contract in cs)
            if contract not in typed:
                untyped.update((o, contract) for o in producers + consumers)
                continue
            edges.update((p, contract, c) for p in producers for c in consumers
                         if p != c)
            if not consumers:
                unconsumed.update((p, contract) for p in producers)
            if not producers:
                unproduced.update((c, contract) for c in consumers)

        unresolved = {(m["organ_id"], q) for m in case["manifests"]
                      for q in m["unresolved"]}
        overlap = {(m["organ_id"], cap) for m in case["manifests"]
                   for cap in m["specialized"]}

        exp = case["expected"]
        cid = case["corpus_id"]
        assert edges == set(exp["edges"]), f"{cid} edges"
        assert untyped == set(exp["untyped"]), f"{cid} untyped"
        assert unconsumed == set(exp["unconsumed"]), f"{cid} unconsumed"
        assert unproduced == set(exp["unproduced"]), f"{cid} unproduced"
        assert unresolved == set(exp["unresolved"]), f"{cid} unresolved"
        assert overlap == set(exp["overlapping_authority"]), f"{cid} overlap"
        assert exp["fully_connected"] is (not unproduced and not untyped), \
            f"{cid} fully_connected"


def test_every_candidate_is_pre_registered_with_a_falsifiable_prediction():
    """Predictions recorded before the code exists. Being wrong must be visible,
    not editable."""
    assert len(spec.CANDIDATE_IDS) == 4
    assert spec.BASELINE_CANDIDATE_ID in spec.CANDIDATE_IDS

    for cid in spec.CANDIDATE_IDS:
        pred = spec.EXPECTED_RESULTS[cid]
        assert set(pred) == {"predicted_function_score",
                             "predicted_qualifies_as_replacement",
                             "reason", "predicted_repair_cost_rank"}
        assert 0.0 <= pred["predicted_function_score"] <= 1.0
        assert pred["reason"]
        assert spec.MATERIAL_DIFFERENCE_CLAIMS[cid]

    ranks = sorted(p["predicted_repair_cost_rank"]
                   for p in spec.EXPECTED_RESULTS.values())
    assert ranks == [1, 2, 3, 4], "cost-rank predictions must be a total order"


def test_the_baseline_cannot_qualify_as_a_structural_replacement():
    """Restoring the original is the strongest conventional repair AND, by
    definition, not materially different from the original. Both facts are
    frozen so the report cannot later claim the baseline as a replacement."""
    b = spec.EXPECTED_RESULTS[spec.BASELINE_CANDIDATE_ID]
    assert b["predicted_function_score"] == 1.0
    assert b["predicted_qualifies_as_replacement"] is False
    assert spec.MATERIAL_DIFFERENCE_CLAIMS[spec.BASELINE_CANDIDATE_ID] \
        .startswith("none")


def test_authority_invariants_and_kill_conditions_are_declared():
    """An experiment with no stated kill condition is a hope."""
    assert len(spec.AUTHORITY_INVARIANTS) >= 5
    assert len(spec.KILL_CONDITIONS) >= 4
    assert len(spec.SUCCESS_GATES) >= 13
    assert len(spec.FAILURE_CONDITIONS) >= 8
    assert spec.EXPERIMENT.kill_condition
    assert spec.EXPERIMENT.rollback_path
    assert any("never deleted" in spec.ROLLBACK_PATH for _ in (0,))


def test_limitations_are_frozen_before_the_result_is_known():
    """Limitations recorded up front cannot be quietly trimmed once the result
    looks good. The three the founder named must be present verbatim in
    substance: single author, stateless subject, not autonomous regeneration."""
    joined = " ".join(spec.DECLARED_LIMITATIONS).lower()
    assert "one author" in joined or "one development session" in joined
    assert "stateless" in joined
    assert "unscripted morphogenesis" in joined
    assert len(spec.DECLARED_LIMITATIONS) >= 5


def test_repair_cost_is_measured_in_points_and_no_money_is_budgeted():
    """$0.00 of external spend. The cost meter's units are repair points and
    must never be read as dollars."""
    assert spec.EXPERIMENT.budget_usd == 0.0
    assert set(spec.REPAIR_COST_WEIGHTS) == {
        "new_source_lines", "new_module_dependencies", "decision_points",
        "runtime_ms", "rollback_steps"}
    assert all(w > 0 for w in spec.REPAIR_COST_WEIGHTS.values())
    assert spec.SECONDARY_ORDER_TERMS[0] == "repair_cost"
