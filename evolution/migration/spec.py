"""FROZEN experiment specification for Package 4. Written BEFORE any candidate.

Self-sealing, exactly as Package 3: every frozen table is hashed into
`SPEC_SHA256` and a test fails the build if it drifts. Amendment stays possible;
it stops being silent.

THE FOUNDER'S CORRECTION IS STRUCTURAL, NOT ADVISORY. A defective replacement
must not be able to append a malformed checkpoint and have it merely detected
afterwards. Validation happens BEFORE append, and it is unavoidable: the seam
hands a replacement engine a guarded ledger, so there is no unguarded path to
append through. A refused checkpoint produces a valid rejection record and
leaves the prior valid checkpoint untouched.
"""
from __future__ import annotations

import hashlib
import json

from evolution.experiment import ExperimentCompiler, ExperimentSpec

# --------------------------------------------------------------------------
# 1. Anchors
# --------------------------------------------------------------------------

BASE_BRANCH = "release/canonical-v1"
BASE_COMMIT = "5e02e47f604770fdee2c05b25418ef003f5b2b92"
APPROVED_PLAN_COMMIT = "961f6fc5798588f0aaeda039b5feee4365a7ce85"

SUBJECT = "events.spine.DurableWorkflow"

#: The class body must stay byte-identical. `events/spine.py` as a whole is
#: authorized to change (it gains the factory), so the CLASS is hashed rather
#: than the file — a file hash would either forbid the seam or prove nothing.
SUBJECT_CLASS_SHA256 = {
    "DurableWorkflow": "6ffdf672ccf426cddede1ac9e3add50ae9ea443358cf9ffb9eeced88b01dc1f8",
    "WorkflowStep": "1cc5505a28c22c1734ba0736a6e98dc3d2cd5e275d61addacd72569ca0c37067",
}

#: File hashes at the base commit, recorded for lineage. The three seam files
#: are EXPECTED to change; everything else in §9 is not.
SEAM_FILE_SHA256_AT_BASE = {
    "events/spine.py": "c87a87c034996d384356e9ddde15d895e1f1faf19d4a921b6099b4203349653c",
    "closure/kernel_registry.py": "389eb253c900601da8884b7f2b9fed2d8d87736c7f447cdcd0a8092ae7619292",
    "loom/weaver.py": "17fe2dd3187b70b77e698d67e2186eb70d81d002a8443f8897738dfe0b3fc876",
}

# --------------------------------------------------------------------------
# 2. Canonical construction sites — the boundary being exercised
# --------------------------------------------------------------------------

#: Measured on the base commit. These are the real sites; verifier V3 runs the
#: closure ones. Package 3's substitution touched none of them.
CANONICAL_CONSTRUCTION_SITES = (
    {"file": "closure/kernel_registry.py", "line": 341, "closure": "events_evidence",
     "kind": "construct", "exercised_by": "verifier V3"},
    {"file": "closure/kernel_registry.py", "line": 347, "closure": "events_evidence",
     "kind": "resume", "exercised_by": "verifier V3"},
    {"file": "closure/kernel_registry.py", "line": 370, "closure": "events_regenerative",
     "kind": "construct", "exercised_by": "verifier V3"},
    {"file": "loom/weaver.py", "line": 62, "closure": "Weaver.weave",
     "kind": "construct", "exercised_by": "loom closures + tests/unit/test_loom.py"},
)

TARGET_CAPABILITY = "institutional.durable_workflow_execution"

# --------------------------------------------------------------------------
# 3. State schemas
# --------------------------------------------------------------------------

#: The checkpoint record as it exists today, measured not assumed.
CHECKPOINT_REQUIRED_KEYS = ("workflow_id", "cursor", "status", "state", "note",
                            "actor", "legal_principal", "at")

W0_STATE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "workflow-checkpoint-w0",
    "type": "object",
    "required": list(CHECKPOINT_REQUIRED_KEYS),
    "additionalProperties": False,
    "properties": {
        "workflow_id": {"type": "string", "minLength": 1},
        "cursor": {"type": "integer", "minimum": 0},
        "status": {"enum": ["running", "completed", "interrupted", "failed",
                            "compensated"]},
        "state": {"type": "object"},
        "note": {"type": "string"},
        "actor": {"type": "string", "minLength": 1},
        "legal_principal": {"type": "string", "minLength": 1},
        "at": {"type": "string", "minLength": 1},
    },
}

#: W2 replaces positional-by-index with positional-by-name.
W2_STATE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "workflow-checkpoint-w2",
    "type": "object",
    "required": ["workflow_id", "completed_steps", "next_step", "status", "state",
                 "note", "actor", "legal_principal", "at"],
    "additionalProperties": False,
    "properties": {
        "workflow_id": {"type": "string", "minLength": 1},
        "completed_steps": {"type": "array", "items": {"type": "string"}},
        "next_step": {"type": ["string", "null"]},
        "status": {"enum": ["running", "completed", "interrupted", "failed",
                            "compensated"]},
        "state": {"type": "object"},
        "note": {"type": "string"},
        "actor": {"type": "string", "minLength": 1},
        "legal_principal": {"type": "string", "minLength": 1},
        "at": {"type": "string", "minLength": 1},
    },
}

#: Legal status transitions. A terminal status accepts no successor: that is
#: what makes HO-4 a safety property rather than a preference.
TERMINAL_STATUSES = ("completed", "failed", "compensated")
LEGAL_STATUS_TRANSITIONS = {
    "running": ("running", "completed", "interrupted", "failed", "compensated"),
    "interrupted": ("running", "interrupted", "completed", "failed", "compensated"),
    "completed": (),
    "failed": (),
    "compensated": (),
}

# --------------------------------------------------------------------------
# 4. Migration rules
# --------------------------------------------------------------------------

MIGRATION = {
    "forward": "cursor -> {completed_steps: [s.name for s in steps[:cursor]], "
               "next_step: steps[cursor].name if cursor < len(steps) else None}",
    "reverse": "next_step -> cursor = index(next_step); null -> cursor = len(steps)",
    "information_added": "step NAMES, which the W0 state does not carry; they come "
                         "from the step list, never invented",
    "information_lost": "none, when step names are unique within a workflow",
    "assumption": "step names are unique within a workflow",
    "on_ambiguity": "REFUSE. Duplicate step names make the reverse migration "
                    "ambiguous, and a migration that guesses is worse than one "
                    "that stops.",
    "failure_behavior": "fail closed — the original checkpoint is left untouched, "
                        "no malformed record is appended, and a rejection record "
                        "is appended instead",
}

# --------------------------------------------------------------------------
# 5. Behavioural corpus (LIVE) and held-out corpus
# --------------------------------------------------------------------------

#: The canonical paths that already exercise the engine.
LIVE_CORPUS = (
    {"id": "LIVE-closure-evidence",
     "source": "closure/kernel_registry.py::events_evidence",
     "asserts": "killed workflow resumes from checkpoint; finished steps never "
                "re-executed"},
    {"id": "LIVE-closure-regenerative",
     "source": "closure/kernel_registry.py::events_regenerative",
     "asserts": "failure compensated in reverse; failure and compensation kept "
                "as negative evidence"},
    {"id": "LIVE-loom-weave",
     "source": "loom/weaver.py::Weaver.weave",
     "asserts": "ratified patterns compile onto a working durable workflow"},
)

#: HELD-OUT. Inputs and expectations frozen here, in the first commit, before
#: any candidate exists. Expectations were MEASURED against the original engine
#: on the base commit and are reproduced verbatim, so a candidate that disagrees
#: is wrong about the original's behaviour, not about a guess.
HELD_OUT_CORPUS = (
    {
        "id": "HO-1",
        "purpose": "single step interrupted before it runs: cursor 0, empty "
                   "state, resume executes exactly one step",
        "steps": ("only",),
        "kill_at": "only",
        "at_interrupt": {"cursor": 0, "status": "interrupted", "state": {}},
        "after_resume": {"status": "completed", "cursor": 1, "state": {"only": 1}},
        "calls_at_interrupt": (),
        "calls_after_resume": ("only",),
    },
    {
        "id": "HO-2",
        "purpose": "interrupt at the LAST step: cursor n-1. An off-by-one in the "
                   "migration shows here or nowhere",
        "steps": ("s1", "s2", "s3"),
        "kill_at": "s3",
        "at_interrupt": {"cursor": 2, "status": "interrupted",
                         "state": {"s1": 1, "s2": 1}},
        "after_resume": {"status": "completed", "cursor": 3,
                         "state": {"s1": 1, "s2": 1, "s3": 1}},
        "calls_at_interrupt": ("s1", "s2"),
        "calls_after_resume": ("s1", "s2", "s3"),
    },
    {
        "id": "HO-3",
        "purpose": "resumed more than once — checkpoint chains, not a single hop",
        "steps": ("a1", "a2", "a3"),
        "kill_at": "a2",
        "second_kill_at": "a3",
        "after_resume": {"status": "completed", "cursor": 3,
                         "state": {"a1": 1, "a2": 1, "a3": 1}},
        "calls_after_resume": ("a1", "a2", "a3"),
    },
    {
        "id": "HO-4",
        "purpose": "failure -> compensation -> terminal `compensated`. Resume "
                   "must be REFUSED. A replacement that cheerfully resumes a "
                   "terminal workflow has lost a safety property while still "
                   "looking functional.",
        "steps": ("g1", "g2"),
        "failing_step": "g2",
        "at_terminal": {"cursor": 1, "status": "compensated", "state": {"g1": 1}},
        "calls": ("g1", "g2", "undo:g1"),
        "resume_must_refuse": True,
        "refusal_message_contains": "nothing to resume",
    },
    {
        "id": "HO-5",
        "purpose": "approval-gated step, unapproved: gate stays closed after "
                   "migration",
        "steps": ("p1", "p2"),
        "approval_step": "p2",
        "approved": False,
        "at_interrupt": {"cursor": 1, "status": "interrupted", "state": {"p1": 1}},
        "calls": ("p1",),
    },
)

# --------------------------------------------------------------------------
# 6. Candidates and pre-registered predictions
# --------------------------------------------------------------------------

CANDIDATE_IDS = ("W0-original", "W1-projection", "W2-token", "W3-journal")
BASELINE_CANDIDATE_ID = "W0-original"

#: W2 is the one that exercises the full schema-changing migration route the
#: founder named. W1 and W3 exist so W2 is not the only datapoint.
MIGRATING_CANDIDATE_ID = "W2-token"

MATERIAL_DIFFERENCE_CLAIMS = {
    "W0-original": "none — the original engine, retained as benchmark, default "
                   "and rollback target",
    "W1-projection": "stores no position at all: cursor and state are DERIVED by "
                     "folding the checkpoint stream on every resume, where the "
                     "original reads the last snapshot",
    "W2-token": "position by step NAME, not index. Different state schema, and "
                "the only candidate requiring a real migration and reverse "
                "migration",
    "W3-journal": "carries an explicit undo stack in state, which the original "
                  "recomputes from the step list at compensation time",
}

EXPECTED_RESULTS = {
    "W0-original": {
        "predicted_exactly_once": True,
        "predicted_qualifies_as_replacement": False,
        "predicted_repair_cost_rank": 1,
        "reason": "it IS the original; preserves behaviour by construction and "
                  "fails the materially-different gate by definition",
    },
    "W1-projection": {
        "predicted_exactly_once": True,
        "predicted_qualifies_as_replacement": True,
        "predicted_repair_cost_rank": 2,
        "reason": "folding the stream is sound; predicted at risk on HO-3 where "
                  "chained resumes make the fold order-sensitive",
    },
    "W2-token": {
        "predicted_exactly_once": True,
        "predicted_qualifies_as_replacement": True,
        "predicted_repair_cost_rank": 4,
        "reason": "the real migration route; predicted to be the most expensive "
                  "and the most likely to expose a genuine migration defect, "
                  "particularly at HO-2's last-step boundary",
    },
    "W3-journal": {
        "predicted_exactly_once": True,
        "predicted_qualifies_as_replacement": True,
        "predicted_repair_cost_rank": 3,
        "reason": "an explicit undo stack is redundant with the original's "
                  "reverse iteration; predicted correct but not cheaper",
    },
}

#: Package 3's R3 prediction was wrong and that was its most informative result.
#: These are recorded on the same terms: being wrong must stay visible.
PREDICTION_DISCIPLINE = ("a prediction that only survives when correct is not a "
                         "prediction; failed predictions are reported, not edited")

# --------------------------------------------------------------------------
# 7. Success and refusal thresholds
# --------------------------------------------------------------------------

#: The behavioural metric. Exactly-once is binary: a single re-executed
#: completed step is a failure, not a 95% pass. Same discipline as Package 3's
#: 4/4 — a fraction that admits "nearly" would admit duplicated work.
EXACTLY_ONCE_THRESHOLD = 1.0
POST_SUBSTITUTION_BASELINE = 0.0

SUCCESS_GATES = (
    "canonical construction sites use the selected replacement during the run",
    "every LIVE corpus behaviour matches the original",
    "every held-out case matches its frozen expectation exactly",
    "exactly-once preserved: zero completed steps re-executed, on every case",
    "all required state migrates; no required key lost or duplicated",
    "reverse migration loses no required information",
    "duplicate step names cause refusal, not a guess",
    "terminal workflows remain terminal",
    "approval gates remain closed unless properly approved",
    "no malformed checkpoint is appended — refused BEFORE append",
    "a refusal produces a valid rejection evidence record",
    "the evidence chain verifies before and after",
    "the prior valid checkpoint remains untouched and recoverable",
    "rollback restores the original provider and the last valid state",
    "the original is the default again after process restart",
    "materially different from the original in state and execution structure",
    "Constitution, identity, authority, legal principals, policy, Gate, "
    "provenance and shutdown unchanged",
    "unauthorized external effects remain zero",
)

REFUSAL_THRESHOLDS = (
    "any completed step executes twice",
    "any required state key lost or duplicated",
    "a malformed checkpoint reaches the ledger",
    "a terminal workflow becomes resumable",
    "an unapproved gate opens",
    "an ambiguous reverse migration returns a guess instead of refusing",
    "the active provider leaks outside its activation scope",
    "the original is not the default after restart",
    "any continuity artifact changes",
    "any unauthorized external effect",
)

# --------------------------------------------------------------------------
# 8. Pre-append validation — the founder's correction, as rules
# --------------------------------------------------------------------------

#: Enforced by `events/engine.py`'s guarded ledger, which is the ONLY ledger a
#: replacement engine is ever handed. There is no unguarded append path.
PRE_APPEND_VALIDATION_RULES = (
    "validate the checkpoint against the declared state schema for the active "
    "engine",
    "validate workflow identity: workflow_id non-empty and matching the engine's",
    "validate actor and legal principal are present",
    "reject UNIIMENTE as legal principal",
    "validate position: cursor within [0, len(steps)] or next_step resolvable "
    "in the declared step list",
    "validate the status transition against LEGAL_STATUS_TRANSITIONS",
    "reject any successor to a terminal status",
    "reject ambiguous or lossy migrations",
    "leave the prior valid checkpoint untouched",
)

REFUSAL_RECORD_TYPE = "event"
REFUSAL_EVENT_TYPE = "workflow.checkpoint_refused"

ON_VALIDATION_FAILURE = (
    "do not append the malformed checkpoint",
    "append only a valid rejection or migration-failure evidence record",
    "leave the original engine active, or restore it immediately",
    "resume from the last valid checkpoint",
)

# --------------------------------------------------------------------------
# 9. Isolation, continuity, authority
# --------------------------------------------------------------------------

#: Founder decision 2: the experiment uses its own ledger instance and its own
#: workflow-id namespace, so the real canonical path is exercised without
#: contaminating durable institutional history with experimental records.
EXPERIMENT_WORKFLOW_PREFIX = "p4x-"
ISOLATED_LEDGER = True
ISOLATION_RATIONALE = (
    "the canonical construction sites are real and are genuinely exercised; only "
    "the LEDGER INSTANCE and the workflow-id namespace are experiment-local. "
    "Substituting the provider is real; polluting institutional history would "
    "not have made it more real, only less reversible."
)

#: Reused unchanged from Package 3.
CONTINUITY_COMBINED_SHA256 = \
    "c1d621a80671d1f39f75e3d525561b45795a978d7d15b1eee7d43546140e63aa"
CONTINUITY_ARTIFACTS = (
    "constitution/constitution.ucl", "constitution/sovereignty.ucl",
    "constitution/shutdown-policy.ucl", "constitution/amendment-policy.ucl",
    "constitution/participant-rights.ucl", "authority/authority-matrix.yaml",
    "authority/legal-principals.yaml", "authority/reserved-matters.yaml",
    "identity/organ-registry.yaml", "identity/agent-registry.yaml",
    "identity/service-identities.yaml", "policy/consequence_gate.py",
)

AUTHORITY_INVARIANTS = (
    "the original DurableWorkflow remains available and byte-identical as the "
    "default provider",
    "direct construction of the original remains valid",
    "the provider defaults to the original after every process restart",
    "activation is scoped, temporary, allowlisted and reversible",
    "no replacement may make itself the permanent default",
    "no capability grant is issued to any candidate",
    "RetainRegressKillDecision may recommend; it may not promote or activate",
    "UNIIMENTE is never a legal principal",
    "shutdown remains enforceable at every stage, including mid-migration",
)

# --------------------------------------------------------------------------
# 10. Repair cost — Package 3's formula plus two state terms
# --------------------------------------------------------------------------

REPAIR_COST_WEIGHTS = {
    "new_source_lines": 1.0,
    "new_module_dependencies": 25.0,
    "decision_points": 4.0,
    "runtime_ms": 0.5,
    "rollback_steps": 50.0,
    # New in Package 4: state migration is work the stateless experiment had none of.
    "state_records_migrated": 2.0,
    "migration_steps": 30.0,
}
SECONDARY_ORDER_TERMS = ("repair_cost", "migration_steps", "decision_points",
                         "runtime_ms", "rollback_steps", "new_source_lines")

# --------------------------------------------------------------------------
# 11. Rollback, kill conditions, authorized files
# --------------------------------------------------------------------------

ROLLBACK_PROCEDURE = (
    "1. deactivate the replacement provider (leaving the activation scope does "
    "this automatically, and a crash does it by default)",
    "2. the original becomes the resolved engine again — it is the default, not "
    "a restored backup",
    "3. resume the workflow from the last valid checkpoint, which the "
    "append-only ledger guarantees still exists",
    "4. assert the original's behaviour is byte-identical to baseline",
)

KILL_CONDITIONS = (
    "a malformed checkpoint reaches the ledger",
    "a candidate attempts an external effect",
    "a candidate attempts to grant itself authority or become the permanent default",
    "a continuity artifact changes",
    "shutdown becomes unenforceable",
    "the frozen spec hash no longer matches this module",
)

#: Founder decision 1 authorizes exactly these three modifications, and no more.
FILES_AUTHORIZED_TO_CHANGE = (
    "events/spine.py",            # add factory; DurableWorkflow class unchanged
    "closure/kernel_registry.py",  # construction sites call the factory
    "loom/weaver.py",             # construction site calls the factory
)
FILES_FORBIDDEN_TO_CHANGE = (
    "constitution/", "authority/", "identity/", "policy/", "provenance/",
    "linker/", "ventures/", "contracts/", "autonomy/", "capital/",
)

# --------------------------------------------------------------------------
# 12. Declared limitations
# --------------------------------------------------------------------------

DECLARED_LIMITATIONS = (
    "All candidates and the seam were authored in one development session by "
    "one author. 'Materially different' is bounded by one author's imagination.",
    "State is process-local over an in-memory ledger. This is NOT a distributed "
    "or crash-consistent migration and must not be described as one.",
    "The candidate set is fixed in advance. Nothing generates novel "
    "implementations, so this is not unscripted morphogenesis or open-ended "
    "self-repair.",
    "The experiment uses an isolated ledger instance and an experiment-specific "
    "workflow-id namespace. The provider substitution at the canonical "
    "construction sites is real; the durable history it writes to is not the "
    "institution's own.",
    "No external effect, deployment, spending or real-world data. The strongest "
    "available verifier is a deterministic invariant.",
    "Activation is scoped and temporary by construction, so this demonstrates "
    "governed replacement, not sustained operation of a replacement.",
)

# --------------------------------------------------------------------------
# 13. The compiled ExperimentSpec — existing machinery
# --------------------------------------------------------------------------

EXPERIMENT = ExperimentCompiler().compile(ExperimentSpec(
    decisive_unknown=(
        "Can UNIIMENTE replace a stateful, non-authority specialist through its "
        "actual canonical runtime boundary, migrate its state into a materially "
        "different implementation, preserve exactly-once behaviour, and roll "
        "back without losing identity, authority, evidence, shutdown or prior "
        "valid state?"
    ),
    hypothesis=(
        "A materially different engine can take over at the real construction "
        "sites, carry the migrated state, preserve exactly-once execution on "
        "every corpus case, refuse malformed checkpoints before they reach the "
        "ledger, and hand control back to the original intact."
    ),
    prediction=(
        "W1, W2 and W3 all preserve exactly-once; W2 is the most expensive and "
        "the most likely to expose a genuine migration defect; W1 is at risk on "
        "HO-3; the original W0 remains the cheapest and the recommended "
        "operational default."
    ),
    metric=("exactly_once_score: 1.0 only when every corpus case matches the "
            "original's behaviour AND zero completed steps re-execute AND all "
            "required state survives migration; 0.0 otherwise"),
    baseline=POST_SUBSTITUTION_BASELINE,
    threshold=EXACTLY_ONCE_THRESHOLD,
    direction="gte",
    workflow="package4.stateful_canonical_replacement",
    required_capabilities=[
        "events.spine", "events.engine", "evolution.comparison",
        "evolution.experiment", "evolution.capsule", "capabilities.genome",
        "provenance.ledger", "memory.causal", "closure.framework", "loom.weaver",
    ],
    authority_requirements=["founder_ratification"],
    budget_usd=0.0,
    reversible=True,
    rollback_path="; ".join(ROLLBACK_PROCEDURE),
    kill_condition="; ".join(KILL_CONDITIONS),
    verification="formal_proof",
    experiment_id="package4-stateful-canonical-replacement-v1",
))

OPERATIONAL_DEFAULT_VERIFIER_LEVEL = "same_model_critique"

# --------------------------------------------------------------------------
# 14. Self-seal
# --------------------------------------------------------------------------

_FROZEN = {
    "base_branch": BASE_BRANCH, "base_commit": BASE_COMMIT,
    "approved_plan_commit": APPROVED_PLAN_COMMIT, "subject": SUBJECT,
    "subject_class_sha256": SUBJECT_CLASS_SHA256,
    "seam_file_sha256_at_base": SEAM_FILE_SHA256_AT_BASE,
    "canonical_construction_sites": CANONICAL_CONSTRUCTION_SITES,
    "target_capability": TARGET_CAPABILITY,
    "checkpoint_required_keys": CHECKPOINT_REQUIRED_KEYS,
    "w0_state_schema": W0_STATE_SCHEMA, "w2_state_schema": W2_STATE_SCHEMA,
    "terminal_statuses": TERMINAL_STATUSES,
    "legal_status_transitions": LEGAL_STATUS_TRANSITIONS,
    "migration": MIGRATION, "live_corpus": LIVE_CORPUS,
    "held_out_corpus": HELD_OUT_CORPUS, "candidate_ids": CANDIDATE_IDS,
    "baseline_candidate_id": BASELINE_CANDIDATE_ID,
    "migrating_candidate_id": MIGRATING_CANDIDATE_ID,
    "material_difference_claims": MATERIAL_DIFFERENCE_CLAIMS,
    "expected_results": EXPECTED_RESULTS,
    "prediction_discipline": PREDICTION_DISCIPLINE,
    "exactly_once_threshold": EXACTLY_ONCE_THRESHOLD,
    "post_substitution_baseline": POST_SUBSTITUTION_BASELINE,
    "success_gates": SUCCESS_GATES, "refusal_thresholds": REFUSAL_THRESHOLDS,
    "pre_append_validation_rules": PRE_APPEND_VALIDATION_RULES,
    "refusal_record_type": REFUSAL_RECORD_TYPE,
    "refusal_event_type": REFUSAL_EVENT_TYPE,
    "on_validation_failure": ON_VALIDATION_FAILURE,
    "experiment_workflow_prefix": EXPERIMENT_WORKFLOW_PREFIX,
    "isolated_ledger": ISOLATED_LEDGER, "isolation_rationale": ISOLATION_RATIONALE,
    "continuity_combined_sha256": CONTINUITY_COMBINED_SHA256,
    "continuity_artifacts": CONTINUITY_ARTIFACTS,
    "authority_invariants": AUTHORITY_INVARIANTS,
    "repair_cost_weights": REPAIR_COST_WEIGHTS,
    "secondary_order_terms": SECONDARY_ORDER_TERMS,
    "rollback_procedure": ROLLBACK_PROCEDURE, "kill_conditions": KILL_CONDITIONS,
    "files_authorized_to_change": FILES_AUTHORIZED_TO_CHANGE,
    "files_forbidden_to_change": FILES_FORBIDDEN_TO_CHANGE,
    "declared_limitations": DECLARED_LIMITATIONS,
    "experiment": EXPERIMENT.to_dict(),
    "operational_default_verifier_level": OPERATIONAL_DEFAULT_VERIFIER_LEVEL,
}


def canonical_json() -> str:
    return json.dumps(_FROZEN, sort_keys=True, separators=(",", ":"), default=list)


def spec_hash() -> str:
    return hashlib.sha256(canonical_json().encode()).hexdigest()


SPEC_SHA256 = "24643845becdcbd2cbedc192aad73bf990c28c189fb162795a0b6098ac4df44b"
