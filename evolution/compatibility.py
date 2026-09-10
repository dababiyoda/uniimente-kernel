"""Explicit SR-001 continuation subject, not an amendment to frozen experiments.

Owner: evolution (developmental evaluation). No runtime grant/identity/policy.
Package3/4 corpora, thresholds, predictions and seals remain in their original
spec modules. These pre-measurement hashes bind the separately authorized shared
repair, so a passing continuation cannot rewrite a historical result.
Unknown future changes fail the same equality gate; never learn expected hashes
from the files being evaluated at runtime.
"""
from evolution.repair import spec as repair_spec

from evolution.repair.subjects import SR001, SR001_WORKFLOW_CLASS_SHA256

# Compatibility exports delegate to one fixed subject owner. No runtime re-seal.
PROFILE_ID = "sr-001-shared-repair-continuation-2026-09-09"
SUBJECT_COMMIT = SR001.source_commit
CONTINUITY_ARTIFACT_SHA256 = dict(SR001.artifacts)
CONTINUITY_COMBINED_SHA256 = SR001.continuity_sha256
WORKFLOW_CLASS_SHA256 = SR001_WORKFLOW_CLASS_SHA256


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
