"""FROZEN experiment specification for Package 3. Written BEFORE any candidate.

Nothing in this module may change once committed. It is self-sealing: the
canonical JSON of every frozen table is hashed into `SPEC_SHA256`, and
`tests/unit/test_repair_spec_frozen.py` fails the build if the hash drifts.
That is the mechanism preventing candidate code from silently retuning the
experiment it is being judged by. A later amendment is possible — it is just
not silent: it changes the hash, breaks the test, and appears in the diff as
what it is.

The experiment itself is an `evolution.experiment.ExperimentSpec` compiled by
the existing `ExperimentCompiler`, which refuses irreversible or unfalsifiable
experiments. No second experiment format was invented.

READ THE THRESHOLD CAREFULLY. The target function is FOUR exact edge triples.
The success threshold is therefore 4/4 = 1.0. Three of four is 0.75, which is
a FAILURE, not a ninety-percent pass. `REQUIRED_FUNCTION_THRESHOLD` encodes
this and `ExperimentSpec.resolves()` enforces it.
"""
from __future__ import annotations

import hashlib
import json
import os

from evolution.experiment import ExperimentCompiler, ExperimentSpec

# --------------------------------------------------------------------------
# 1. Baseline provenance — what this experiment is anchored to
# --------------------------------------------------------------------------

BASELINE_BRANCH = "release/canonical-v1"
BASELINE_COMMIT = "cb234faf932d239d79b0e7ab28e54f576b8a15bf"

#: The component under replacement, preserved unchanged as permanent benchmark,
#: strongest conventional repair option, and rollback target.
SUBJECT_PACKAGE = "linker"
SUBJECT_FILES = ("linker/__init__.py", "linker/linker.py", "linker/manifest.py")

#: sha256 of each subject file at BASELINE_COMMIT, and of the package as a
#: whole (path + NUL + bytes + NUL, in SUBJECT_FILES order). Any edit to the
#: original linker is therefore detectable, which is how "preserved unchanged"
#: becomes a checkable claim instead of a promise.
ORIGINAL_LINKER_FILE_SHA256 = {
    "linker/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "linker/linker.py": "cc28da68d2ea5ca45faad557e82c9128ab8a76eea1d373d13f7bc2c5a6e2c181",
    "linker/manifest.py": "b7b14a9177717ae0cdd8a5c702a1efc202b522f2e488a7666042d7e9aab8e33f",
}
ORIGINAL_LINKER_PACKAGE_SHA256 = \
    "a42812d1ec701b71f71ca64f3d083939a42aeba4bece90d74713bd2c01a5e556"

# --------------------------------------------------------------------------
# 2. The target function — the declared capability, not an implementation
# --------------------------------------------------------------------------

#: The institutional function at risk. The detector is given THIS NAME and the
#: contract below. It is never told which module provides it.
TARGET_CAPABILITY = "institutional.cross_organ_edge_resolution"

TARGET_FUNCTION_CONTRACT = """\
Given a set of organ manifests and the institutional contract set, resolve
every typed edge producer -> contract -> consumer, and refuse to invent any
edge, identity, or authority that cannot be proved from the inputs.

An edge exists if and only if:
  (a) some organ P names the contract in contracts.produces, and
  (b) some organ Q != P names the same contract in contracts.consumes, and
  (c) a schema file for that contract exists in the contract set.

Everything unprovable is reported, never guessed:
  untyped     a named contract with no schema file, per naming organ
  unconsumed  a typed contract produced by someone, consumed by no one
  unproduced  a typed contract consumed by someone, produced by no one
  unresolved  each manifest's open questions, carried verbatim
  overlapping_authority  each SPECIALIZED organ-local capability
A contract that is untyped yields untyped entries only: it must NOT also be
reported as unconsumed or unproduced.
"""

_O = "spiffe://uniimente.internal/organ/"

#: THE FOUR EXACT EDGE TRIPLES. This is the function. 4/4 or failure.
REQUIRED_EDGE_TRIPLES = (
    (f"{_O}daleobanks", "wire-opportunity-packet", f"{_O}constitutional-controller"),
    (f"{_O}daleobanks", "wire-opportunity-packet", f"{_O}wealthmachine"),
    (f"{_O}wealthmachine", "wire-venture-assessment", f"{_O}constitutional-controller"),
    (f"{_O}wealthmachine", "wire-venture-assessment", f"{_O}daleobanks"),
)

#: The refusal behaviour that must survive replacement, measured on the live
#: corpus. A candidate that resolves all four edges but stops refusing has not
#: restored the function — it has replaced a linker with a guesser.
REQUIRED_REFUSALS = {
    "unproduced": ((f"{_O}constitutional-controller", "organ-manifest"),),
    "untyped": (),
    "unconsumed": (
        (f"{_O}constitutional-controller", "capability-grant"),
        (f"{_O}constitutional-controller", "context-packet"),
        (f"{_O}constitutional-controller", "decision"),
        (f"{_O}constitutional-controller", "event"),
        (f"{_O}constitutional-controller", "evidence"),
        (f"{_O}constitutional-controller", "opportunity-packet"),
        (f"{_O}constitutional-controller", "outcome"),
        (f"{_O}constitutional-controller", "venture-assessment"),
        (f"{_O}constitutional-controller", "venture-cell-charter"),
        (f"{_O}daleobanks", "context-packet"),
        (f"{_O}wealthmachine", "venture-assessment"),
    ),
    "unresolved_count": 7,
    "overlapping_authority": (
        (f"{_O}daleobanks", "daleobanks.constitution_service"),
        (f"{_O}wealthmachine", "wealthmachine.risk_management"),
    ),
    "fully_connected": False,
}

#: 4 of 4. Not 0.9. Encoded as a fraction so `ExperimentSpec.resolves()`
#: arithmetic is unambiguous: 3/4 = 0.75 < 1.0 and therefore fails.
REQUIRED_FUNCTION_THRESHOLD = 1.0
POST_DISABLE_BASELINE = 0.0

# --------------------------------------------------------------------------
# 3. Measurement corpus and held-out corpus
# --------------------------------------------------------------------------

#: AMENDED 2026-08-22 under founder ruling FOUNDER-RULING-2026-08-22, which
#: approved Option A of DEC-OM-002. This is a deliberate spec amendment and it
#: moves SPEC_SHA256; the procedure the seal's own test prescribes — say so in
#: the commit message and in docs/release/package-3/ — has been followed.
#:
#: It previously read `"manifests": "organs/*.manifest.yaml"` with
#: `corpus_id: "LIVE"`: a sealed experiment bound to a mutable directory. That
#: binding is CONTRADICTION-0001. An experiment whose inputs can change cannot
#: be reproduced, and the recorded Package 3 run could not be re-executed and
#: get its recorded answer once two new organ manifests took the live corpus
#: from 7 unresolved rows to 17.
#:
#: **No expectation value is changed by this amendment.** REQUIRED_EDGE_TRIPLES,
#: REQUIRED_REFUSALS and unresolved_count = 7 are exactly as frozen. Only the
#: binding from experiment to input is corrected, from a live glob to the
#: byte-identical freeze-time snapshot under `evolution/repair/corpus/`.
#:
#: This corpus answers "can the historical experiment be reproduced?" — nothing
#: else. It is NOT a statement about the institution's current health, and
#: `evolution/repair/live_health.py` exists so the two can never be confused.
MEASUREMENT_CORPUS = {
    "corpus_id": "FROZEN-627ec48",
    "manifests": "evolution/repair/corpus/*.manifest.yaml",
    "contracts": "contracts/*.schema.json",
    "expected": "REQUIRED_EDGE_TRIPLES + REQUIRED_REFUSALS",
    "amended_by": "FOUNDER-RULING-2026-08-22 (DEC-OM-002 Option A)",
    "supersedes": {"corpus_id": "LIVE", "manifests": "organs/*.manifest.yaml"},
}

#: Absolute path to the frozen corpus, so no caller reconstructs it by hand.
CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")

#: HELD-OUT CORPUS. Inputs and expected outputs are frozen here, in the first
#: commit, before any candidate exists. Expectations were derived by hand from
#: TARGET_FUNCTION_CONTRACT — not by running any implementation. If a candidate
#: later disagrees with one of these, either the candidate is wrong or this
#: table is wrong, and correcting the table is a visible spec amendment that
#: breaks SPEC_SHA256. That asymmetry is the whole point.
#:
#: Each case is (manifests, contract_names). A manifest is
#: {organ_id, produces, consumes, unresolved, specialized}.
HELD_OUT_CORPUS = (
    {
        "corpus_id": "HO-1",
        "purpose": "self-loop only: one organ both produces and consumes; "
                   "an edge needs two distinct organs, and a self-loop is "
                   "neither an edge nor a refusal",
        "contract_names": ("x",),
        "manifests": (
            {"organ_id": "a", "produces": ("x",), "consumes": ("x",),
             "unresolved": (), "specialized": ()},
            {"organ_id": "b", "produces": (), "consumes": (),
             "unresolved": (), "specialized": ()},
        ),
        "expected": {
            "edges": (),
            "untyped": (),
            "unconsumed": (),
            "unproduced": (),
            "unresolved": (),
            "overlapping_authority": (),
            "fully_connected": True,
        },
    },
    {
        "corpus_id": "HO-2",
        "purpose": "untyped suppresses refusal accounting: a contract with no "
                   "schema is reported untyped for BOTH namers and must not "
                   "also appear as unconsumed or unproduced",
        "contract_names": (),
        "manifests": (
            {"organ_id": "a", "produces": ("y",), "consumes": (),
             "unresolved": (), "specialized": ()},
            {"organ_id": "b", "produces": (), "consumes": ("y",),
             "unresolved": (), "specialized": ()},
        ),
        "expected": {
            "edges": (),
            "untyped": (("a", "y"), ("b", "y")),
            "unconsumed": (),
            "unproduced": (),
            "unresolved": (),
            "overlapping_authority": (),
            "fully_connected": False,
        },
    },
    {
        "corpus_id": "HO-3",
        "purpose": "fan-out and fan-in: one producer to three consumers plus a "
                   "return edge; cardinality must be exact, not merely non-zero",
        "contract_names": ("w", "z"),
        "manifests": (
            {"organ_id": "a", "produces": ("z",), "consumes": ("w",),
             "unresolved": (), "specialized": ()},
            {"organ_id": "b", "produces": ("w",), "consumes": ("z",),
             "unresolved": (), "specialized": ()},
            {"organ_id": "c", "produces": (), "consumes": ("z",),
             "unresolved": (), "specialized": ()},
            {"organ_id": "d", "produces": (), "consumes": ("z",),
             "unresolved": (), "specialized": ()},
        ),
        "expected": {
            "edges": (("a", "z", "b"), ("a", "z", "c"), ("a", "z", "d"),
                      ("b", "w", "a")),
            "untyped": (),
            "unconsumed": (),
            "unproduced": (),
            "unresolved": (),
            "overlapping_authority": (),
            "fully_connected": True,
        },
    },
    {
        "corpus_id": "HO-4",
        "purpose": "mixed refusals with a global negative: an orphan consumer "
                   "(nobody produces q) and an orphan producer (nobody "
                   "consumes r), plus carried unresolved questions and a "
                   "SPECIALIZED overlap. The global negative is the case a "
                   "purely local rule is least able to decide.",
        "contract_names": ("p", "q", "r"),
        "manifests": (
            {"organ_id": "a", "produces": ("p",), "consumes": ("q",),
             "unresolved": (), "specialized": ()},
            {"organ_id": "b", "produces": (), "consumes": ("p",),
             "unresolved": ("waiting on founder ratification",
                            "credential is an external dependency"),
             "specialized": ()},
            {"organ_id": "c", "produces": ("r",), "consumes": (),
             "unresolved": (), "specialized": ("c.local_gate",)},
        ),
        "expected": {
            "edges": (("a", "p", "b"),),
            "untyped": (),
            "unconsumed": (("c", "r"),),
            "unproduced": (("a", "q"),),
            "unresolved": (("b", "waiting on founder ratification"),
                           ("b", "credential is an external dependency")),
            "overlapping_authority": (("c", "c.local_gate"),),
            "fully_connected": False,
        },
    },
)

# --------------------------------------------------------------------------
# 4. Candidates and their pre-registered expected results
# --------------------------------------------------------------------------

#: Candidate identities are frozen. No candidate may be added, renamed, or
#: withdrawn after this commit.
CANDIDATE_IDS = ("B0-restore", "R1-contract-index", "R2-constraint", "R3-local-rule")

#: The baseline is the strongest conventional repair. It is NOT a qualifying
#: structural replacement — restoring the original cannot be "materially
#: different from the original" — so it is scored on function and excluded from
#: the structural-replacement verdict. It stays in the comparison permanently.
BASELINE_CANDIDATE_ID = "B0-restore"

#: PRE-REGISTERED PREDICTIONS. Recorded before a line of candidate code exists,
#: so that being wrong is visible rather than editable. A prediction that only
#: survives when correct is not a prediction.
EXPECTED_RESULTS = {
    "B0-restore": {
        "predicted_function_score": 1.0,
        "predicted_qualifies_as_replacement": False,
        "reason": "it IS the original; it restores 4/4 by construction and "
                  "fails the materially-different gate by definition",
        "predicted_repair_cost_rank": 1,
    },
    "R1-contract-index": {
        "predicted_function_score": 1.0,
        "predicted_qualifies_as_replacement": True,
        "reason": "inverted index plus set algebra is a faithful restatement of "
                  "the same relation; expected to win among replacements on "
                  "function and cost",
        "predicted_repair_cost_rank": 2,
    },
    "R2-constraint": {
        "predicted_function_score": 1.0,
        "predicted_qualifies_as_replacement": True,
        "reason": "generate-and-test over the full candidate space is sound but "
                  "quadratic; expected to win on diagnostic quality and to lose "
                  "on resource use and complexity",
        "predicted_repair_cost_rank": 3,
    },
    "R3-local-rule": {
        "predicted_function_score": 0.0,
        "predicted_qualifies_as_replacement": False,
        "reason": "a cell that sees only its own manifest can conclude 'no "
                  "producer among cells I have heard from', which is not the "
                  "global negative the contract requires. Predicted to pass "
                  "LIVE, HO-1, HO-2 and HO-3 and to be at risk on HO-4's "
                  "orphan consumer. Predicted last on the secondary ordering. "
                  "If R3 scores 1.0 the Package-2 hub-dependence finding does "
                  "not transfer to this topology and that must be reported as "
                  "a failed prediction.",
        "predicted_repair_cost_rank": 4,
    },
}

#: Every candidate must be materially different from the original in DATA FLOW
#: and DECISION STRUCTURE, not in naming. Frozen declarations, checked in review
#: and asserted structurally by the test suite.
MATERIAL_DIFFERENCE_CLAIMS = {
    "B0-restore": "none — this is the original algorithm, retained as baseline",
    "R1-contract-index": "single indexing pass builds contract -> (producers, "
                         "consumers); edges and all refusals are then set "
                         "algebra over those indices. The original scans "
                         "manifests and branches per contract with counters.",
    "R2-constraint": "enumerates the full (producer, contract, consumer) "
                     "candidate space and filters it through an ordered list of "
                     "named, self-explaining constraints; refusals are derived "
                     "by classifying constraint violations, not by counting.",
    "R3-local-rule": "no global resolver: each organ is a cell holding only its "
                     "own manifest, exchanging contract advertisements over "
                     "bounded rounds; an edge is committed only on local "
                     "agreement between two cells.",
}

#: R3's declared round budget. Fixed in advance so the local rule gets a fair
#: shot and cannot be tuned to the answer afterwards.
R3_ROUND_BUDGET = 2

# --------------------------------------------------------------------------
# 5. Repair-cost meter — frozen formula
# --------------------------------------------------------------------------

#: repair_cost = sum(weight * measured term). Units are repair points, NOT
#: dollars: the cash cost of this entire package is $0.00 and no field here
#: should ever be read as money.
REPAIR_COST_WEIGHTS = {
    "new_source_lines": 1.0,        # non-blank, non-comment lines added
    "new_module_dependencies": 25.0,  # imports the original did not need
    "decision_points": 4.0,         # if / for / while / except / comprehension-if
    "runtime_ms": 0.5,              # median wall time over the measurement corpus
    "rollback_steps": 50.0,         # operations to return to the original path
}

#: Frozen secondary ordering, applied ONLY among candidates that tie on the
#: primary function metric. Lower is better on every term. This is what the
#: founder's "resource use, repair work, complexity, rollback cost" reduces to.
SECONDARY_ORDER_TERMS = ("repair_cost", "decision_points", "runtime_ms",
                         "rollback_steps", "new_source_lines")

# --------------------------------------------------------------------------
# 6. Authority invariants and continuity hashes
# --------------------------------------------------------------------------

#: Byte-identical before disable, after disable, after install, after rollback.
CONTINUITY_ARTIFACT_SHA256 = {
    "constitution/constitution.ucl":
        "5c269850d8da799db66030103c52a175596d9c5f3bb61d25f54d7da9dde2ecd0",
    "constitution/sovereignty.ucl":
        "dc44c1f4304d42791a9db634796584531d40ba6b46191f2cba3877e48ee7fbcc",
    "constitution/shutdown-policy.ucl":
        "e3b443663cc5ed81a8b8827d8feb49962f82f262e85c282113f534c2afab2e54",
    "constitution/amendment-policy.ucl":
        "0132d53ec1e770a526f0e57888235a0b0bac4ed14b443782da537fb70b2ac01f",
    "constitution/participant-rights.ucl":
        "feba5d83800cd5d04702087473eea4d38290950097072efc578cfd498d631687",
    "authority/authority-matrix.yaml":
        "bd763098ecbbfd6ea7e8c9d80b83ed329fefd4766e53ed9b11006719fc671a45",
    "authority/legal-principals.yaml":
        "bdbe881c32353ec3546c459f7250f2bc34b40b014e7fe661f36281c7b9af5061",
    "authority/reserved-matters.yaml":
        "f185e0d11dec25e2bc3dbb73ce92bbb5d276358d1ac8abcaca7526a2805eb924",
    "identity/organ-registry.yaml":
        "7a78955247df0d8204959d0cbb38b05d6e49578e3c0a9f3f0f7d0c916fcebb40",
    "identity/agent-registry.yaml":
        "5c8b7b4775299c2c3943a4e3432798b1f864fada0070f4a5f3699400d95cd7fd",
    "identity/service-identities.yaml":
        "cd8c2c493b22a25926bbcedb049ebe28d86bd6e087ab920c0bbe2bae08cceac0",
    "policy/consequence_gate.py":
        "0b133b57eea1e349db63c8edf3ad9514d934e7b0b11f67cad0c9adc4b78a63ce",
}
#: sha256 over the concatenated bytes of the artifacts above, in that order.
CONTINUITY_COMBINED_SHA256 = \
    "c1d621a80671d1f39f75e3d525561b45795a978d7d15b1eee7d43546140e63aa"

#: Absolute path to the frozen freeze-time copies of the twelve artifacts above,
#: so no caller reconstructs it by hand.
#:
#: AMENDMENT 002, 2026-08-23, under FOUNDER-RULING-2026-08-23 (CONTRADICTION-0002
#: Option A). Every hash in `CONTINUITY_ARTIFACT_SHA256` and the combined hash
#: above are **unchanged** — this amendment moves only *where the bytes are read
#: from*, never *what was expected*. That is why neither `SPEC_SHA256` nor
#: `EXPECTATIONS_SHA256` moves: this is a module-level path constant, not a
#: frozen table, exactly as `CORPUS_DIR` is for Amendment 001. The stronger
#: property Amendment 001 could not claim — the seal does not move at all — is
#: available here because the pins were always correct; only their binding to a
#: *live* tree was unsound.
#:
#: This directory answers "can the historical experiment be reproduced?" —
#: nothing else. It is NOT a tripwire on constitutional change. That duty is
#: real, and the founder ruled it must move somewhere explicit rather than
#: remain a side effect of an experiment's baseline: `governance/integrity/`.
CONTINUITY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "continuity")

AUTHORITY_INVARIANTS = (
    "no capability grant is issued to any replacement candidate",
    "no candidate may register itself as the provider of the target capability",
    "no candidate may widen its own authority or alter approval requirements",
    "RetainRegressKillDecision may recommend; it may not promote or activate",
    "the shutdown policy remains loadable and enforceable at every stage, "
    "including while the target function is absent",
    "unauthorized external effects remain exactly zero, enforced "
    "out-of-process by the Package 2 inertness harness",
    "UNIIMENTE is never the legal principal of anything in this experiment",
)

# --------------------------------------------------------------------------
# 7. Success gates, failure conditions, rollback, kill conditions
# --------------------------------------------------------------------------

#: A replacement qualifies only when EVERY gate passes. Any single failure is a
#: failed candidate, and failed candidates are preserved as evidence.
SUCCESS_GATES = (
    "all four required edge triples correct on the live corpus (4/4)",
    "all required refusal cases correct on the live corpus",
    "every held-out corpus case matches its frozen expectation exactly",
    "materially different from the original in data flow and decision structure",
    "constitution hashes unchanged",
    "identity records unchanged",
    "authority matrix unchanged",
    "legal-principal registry unchanged",
    "consequence gate unchanged",
    "institutional memory and prior evidence remain readable and verifying",
    "shutdown still succeeds",
    "the original linker remains available for rollback",
    "unauthorized external effects remain zero",
)

FAILURE_CONDITIONS = (
    "function score below 1.0 (three of four edges is a failure, not 75% credit)",
    "detection never fires on the real loss",
    "detection fires when the component is healthy",
    "detection reports recovery from incomplete output",
    "the only qualifying candidate is a reimplementation of the original",
    "any continuity artifact changes",
    "any evidence record is rewritten or deleted",
    "shutdown unenforceable at any stage",
    "any unauthorized external effect",
    "the experiment cannot be scored without changing its own thresholds",
)

ROLLBACK_PATH = (
    "the original linker package is never deleted; lifting the runtime disable "
    "restores the original import path in one step, and every stage of this "
    "package is a separate revertable commit"
)

KILL_CONDITIONS = (
    "a candidate attempts an external effect",
    "a candidate attempts to grant itself authority or self-register as provider",
    "a continuity artifact changes at any stage",
    "the shutdown policy becomes unenforceable",
    "the frozen spec hash no longer matches this module",
)

# --------------------------------------------------------------------------
# 8. Declared limitations — preserved in the result, not softened
# --------------------------------------------------------------------------

DECLARED_LIMITATIONS = (
    "All four candidates were authored in one development session by one "
    "author, so 'materially different' is bounded by one author's imagination. "
    "A stronger version of this experiment would source at least one candidate "
    "from outside the session.",
    "The replaced component is stateless. This experiment therefore answers "
    "'can function be restored' and says nothing about whether durable state "
    "survives replacement.",
    "The candidate set is fixed in advance. Nothing here generates novel "
    "implementations, so this is not unscripted morphogenesis.",
    "Detection is blind to which module failed, but the capability contract it "
    "checks against was written by the same author as the candidates.",
    "The held-out corpus is synthetic and hand-derived from the contract. It is "
    "held out in time (frozen before candidates existed) rather than held out "
    "by an independent party.",
    "No external effect, no deployment, no spending, and no real-world data "
    "are involved, so nothing here is externally verifiable evidence: the "
    "strongest verifier available is a deterministic invariant.",
)

# --------------------------------------------------------------------------
# 9. The compiled ExperimentSpec — existing machinery, not a new format
# --------------------------------------------------------------------------

EXPERIMENT = ExperimentCompiler().compile(ExperimentSpec(
    decisive_unknown=(
        "Can UNIIMENTE detect the loss of a working specialist function, rank "
        "materially different replacements with its existing machinery, install "
        "one, and preserve identity, authority, memory, evidence and shutdown "
        "throughout?"
    ),
    hypothesis=(
        "A structurally different implementation can restore the target "
        "function exactly while every continuity invariant holds, and the "
        "governed loop selects it without the author choosing the winner."
    ),
    prediction=(
        "R1 and R2 restore 4/4 and qualify; R3 is at risk on the global-negative "
        "refusal in HO-4; the B0 baseline restores 4/4 at the lowest repair cost "
        "and remains the recommended operational default."
    ),
    metric=("restored_function_score: fraction of REQUIRED_EDGE_TRIPLES resolved "
            "exactly, gated to 0.0 if any required refusal, held-out case, or "
            "continuity check fails"),
    baseline=POST_DISABLE_BASELINE,
    threshold=REQUIRED_FUNCTION_THRESHOLD,
    direction="gte",
    workflow="package3.governed_functional_replacement",
    required_capabilities=[
        "evolution.comparison", "evolution.experiment", "evolution.capsule",
        "capabilities.genome", "provenance.ledger", "memory.causal",
        "closure.framework", "compiler.ucl_compiler",
    ],
    authority_requirements=["founder_ratification"],
    budget_usd=0.0,
    reversible=True,
    rollback_path=ROLLBACK_PATH,
    kill_condition="; ".join(KILL_CONDITIONS),
    # The function measurement is a deterministic invariant, so formal_proof is
    # honest for the restoration claim. The separate judgement about which
    # method should be the operational default rests on same_model_critique,
    # which is hypothesis-only and may never authorize promotion.
    verification="formal_proof",
    experiment_id="package3-governed-functional-replacement-v1",
))

OPERATIONAL_DEFAULT_VERIFIER_LEVEL = "same_model_critique"

# --------------------------------------------------------------------------
# 10. Self-seal
# --------------------------------------------------------------------------

_FROZEN_TABLES = {
    "baseline_branch": BASELINE_BRANCH,
    "baseline_commit": BASELINE_COMMIT,
    "subject_package": SUBJECT_PACKAGE,
    "subject_files": SUBJECT_FILES,
    "original_linker_file_sha256": ORIGINAL_LINKER_FILE_SHA256,
    "original_linker_package_sha256": ORIGINAL_LINKER_PACKAGE_SHA256,
    "target_capability": TARGET_CAPABILITY,
    "target_function_contract": TARGET_FUNCTION_CONTRACT,
    "required_edge_triples": REQUIRED_EDGE_TRIPLES,
    "required_refusals": REQUIRED_REFUSALS,
    "required_function_threshold": REQUIRED_FUNCTION_THRESHOLD,
    "post_disable_baseline": POST_DISABLE_BASELINE,
    "measurement_corpus": MEASUREMENT_CORPUS,
    "held_out_corpus": HELD_OUT_CORPUS,
    "candidate_ids": CANDIDATE_IDS,
    "baseline_candidate_id": BASELINE_CANDIDATE_ID,
    "expected_results": EXPECTED_RESULTS,
    "material_difference_claims": MATERIAL_DIFFERENCE_CLAIMS,
    "r3_round_budget": R3_ROUND_BUDGET,
    "repair_cost_weights": REPAIR_COST_WEIGHTS,
    "secondary_order_terms": SECONDARY_ORDER_TERMS,
    "continuity_artifact_sha256": CONTINUITY_ARTIFACT_SHA256,
    "continuity_combined_sha256": CONTINUITY_COMBINED_SHA256,
    "authority_invariants": AUTHORITY_INVARIANTS,
    "success_gates": SUCCESS_GATES,
    "failure_conditions": FAILURE_CONDITIONS,
    "rollback_path": ROLLBACK_PATH,
    "kill_conditions": KILL_CONDITIONS,
    "declared_limitations": DECLARED_LIMITATIONS,
    "experiment": EXPERIMENT.to_dict(),
    "operational_default_verifier_level": OPERATIONAL_DEFAULT_VERIFIER_LEVEL,
}


def canonical_json() -> str:
    """Deterministic serialisation of every frozen table. Tuples become lists,
    keys are sorted; the same spec always produces the same bytes."""
    return json.dumps(_FROZEN_TABLES, sort_keys=True, separators=(",", ":"),
                      default=list)


def spec_hash() -> str:
    return hashlib.sha256(canonical_json().encode()).hexdigest()


def expectations_hash() -> str:
    """Seal every frozen table EXCEPT the corpus binding.

    The amendment below repoints which input the experiment reads. The whole
    claim it rests on is that it changes *what is measured against*, never *what
    was expected*. A sentence in a docstring cannot carry that claim, because
    the reader would have to trust it. This hash can: it is computed over every
    expectation table with `measurement_corpus` removed, so it is invariant
    under a corpus repoint and moves the moment any threshold, edge triple,
    refusal count or result expectation is touched.

    `EXPECTATIONS_SHA256` below is the value computed from the spec **as it
    stood before the amendment**, at seal `6f6d7dab…c4ab7f4a`. Its equality with
    this function today is the proof, not the promise, that no expectation value
    moved.
    """
    tables = {k: v for k, v in _FROZEN_TABLES.items() if k != "measurement_corpus"}
    return hashlib.sha256(
        json.dumps(tables, sort_keys=True, separators=(",", ":"),
                   default=list).encode()).hexdigest()


#: Computed from the PRE-amendment spec (seal `6f6d7dab…c4ab7f4a`) and pinned
#: here unchanged. Deliberately not in `_FROZEN_TABLES`: a value that sealed
#: itself would prove nothing.
EXPECTATIONS_SHA256 = "8720b0b1c94ceba58ef2babfb0adef3466b85e72c8c5e0a8d4d069d7b3cd746a"


#: The seal. Computed from the tables above at the moment of freezing. A test
#: asserts equality, so any later edit to this module fails the build instead
#: of quietly moving the goalposts.
#:
#: AMENDED once, 2026-08-22, under FOUNDER-RULING-2026-08-22 (DEC-OM-002 Option
#: A). The prior seal was `6f6d7dab40cf023dd69995511a3db298482c31b0bb39675d4a5c47f7c4ab7f4a`
#: and covered a MEASUREMENT_CORPUS bound to a live glob. The amendment repoints
#: that binding at the frozen corpus and changes no expectation value. Rationale
#: and full diff of intent: `docs/release/package-3/AMENDMENT-001-frozen-corpus.md`.
#: The superseded seal is retained here rather than deleted, so the amendment is
#: visible in the file and not only in git history.
SPEC_SHA256_ORIGINAL = "6f6d7dab40cf023dd69995511a3db298482c31b0bb39675d4a5c47f7c4ab7f4a"
SPEC_SHA256 = "c02e634203e2dd2e4689cc90548a917eadaadfcdc324350ac086ed937b0a6fc8"
