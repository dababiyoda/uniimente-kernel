"""Explicit SR-001 continuation subject, not an amendment to frozen experiments.

Owner: evolution (developmental evaluation). No runtime grant/identity/policy.
Package3/4 corpora, thresholds, predictions and seals remain in their original
spec modules. These pre-measurement hashes bind the separately authorized shared
repair, so a passing continuation cannot rewrite a historical result.
Unknown future changes fail the same equality gate; never learn expected hashes
from the files being evaluated at runtime.
"""
from evolution.repair import spec as repair_spec

PROFILE_ID = "sr-001-shared-repair-continuation-2026-09-09"
SUBJECT_COMMIT = "3e059c20331d96e05a44daac1b097896aaabde93"
CONTINUITY_ARTIFACT_SHA256 = {
    **repair_spec.CONTINUITY_ARTIFACT_SHA256,
    "policy/consequence_gate.py":
        "1c189be5af884932ed2115557b5a285883a2c6045af183c7f6f65a0815a06f2e",
}
CONTINUITY_COMBINED_SHA256 = \
    "5594003e1f691bb4a20220505c932b69332c83743ece43a3325f5bbe89a19d70"
WORKFLOW_CLASS_SHA256 = {
    "DurableWorkflow": "7b303f6e5d268722221b6063b540ee0786fbe2675ab062c8c7b81e50b82220bb",
    "WorkflowStep": "ed63561261f29e9869f0626ec7fdd7bb505c21f1d8e9231c349753873310bbec",
}


def subject_record():
    return {
        "profile_id": PROFILE_ID,
        "subject_commit": SUBJECT_COMMIT,
        "historical_continuity_sha256": repair_spec.CONTINUITY_COMBINED_SHA256,
        "continuation_continuity_sha256": CONTINUITY_COMBINED_SHA256,
        "historical_spec_unchanged": repair_spec.spec_hash() == repair_spec.SPEC_SHA256,
        "authority_created": False,
        "historical_outcomes_replaced": False,
    }
