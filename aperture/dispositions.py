"""Machine-readable disposition of every authority implementation.

Gate A is not a claim in a document. It is this registry plus the tests in
tests/unit/test_no_parallel_authority.py, which fail the build if a second
implementation is ever marked CANONICAL_ACTIVE or if canonical organ code
imports a superseded engine.

Nothing here deletes anything. The Final Build Order forbids destroying
institutional memory, and a superseded engine remains valuable as a regression
oracle and as a counterfactual twin. SUPERSEDED means "a stronger default
exists", not "removed".
"""
from __future__ import annotations

from dataclasses import dataclass, field

CANONICAL_ACTIVE = "CANONICAL_ACTIVE"
THIN_CLIENT = "THIN_CLIENT"
VERIFICATION_HELPER = "VERIFICATION_HELPER"
COMPATIBILITY_ADAPTER = "COMPATIBILITY_ADAPTER"
CONFORMANCE_FIXTURE = "CONFORMANCE_FIXTURE"
EXPERIMENTAL = "EXPERIMENTAL"
HISTORICAL = "HISTORICAL"
QUARANTINED = "QUARANTINED"
SUPERSEDED = "SUPERSEDED"

CLASSIFICATIONS = (CANONICAL_ACTIVE, THIN_CLIENT, VERIFICATION_HELPER,
                   COMPATIBILITY_ADAPTER, CONFORMANCE_FIXTURE, EXPERIMENTAL,
                   HISTORICAL, QUARANTINED, SUPERSEDED)

# Read from the canonical manifest. NOT a second hardcoded list - that
# duplication is exactly what let Gate A close dishonestly.
from . import manifest as _manifest


def FORBIDDEN_ON_CANONICAL_PATH() -> tuple[str, ...]:  # noqa: N802
    return _manifest.forbidden_on_canonical_path()


@dataclass(frozen=True)
class Disposition:
    implementation: str
    module: str
    classification: str
    may_issue_authority: bool
    rationale: str
    retained_because: str = ""
    revival_conditions: str = ""


DISPOSITIONS: tuple[Disposition, ...] = (
    Disposition(
        implementation="Reality Aperture (proof-carrying authorization)",
        module="aperture.issuer",
        classification=CANONICAL_ACTIVE,
        may_issue_authority=True,
        rationale=(
            "The single canonical issuance mechanism. One signer, twenty bound "
            "fields, verification distributed everywhere as public keys only."),
    ),
    Disposition(
        implementation="Aperture effector boundary",
        module="aperture.effector",
        classification=VERIFICATION_HELPER,
        may_issue_authority=False,
        rationale=(
            "Verifies and refuses. Holds a VerificationRegistry, which has no "
            "signing method and cannot mint authority."),
    ),
    Disposition(
        implementation="main root Consequence Gate",
        module="policy.consequence_gate",
        classification=SUPERSEDED,
        may_issue_authority=False,
        rationale=(
            "Three verified authority defects: capability not bound to the "
            "passport, commit-time REQUIRE_HUMAN discarded, and a grant "
            "redeemable by a different actor. Its effect hash bound three "
            "fields; the aperture binds twenty. Its HMAC trust root cannot "
            "support independent verification."),
        retained_because=(
            "regression oracle and counterfactual twin. Its 13 tests still run "
            "and still pass; they document what the previous engine did."),
        revival_conditions=(
            "if asymmetric signing proves operationally impossible in some "
            "deployment, this engine documents the symmetric fallback that "
            "would have to be re-argued from scratch."),
    ),
    Disposition(
        implementation="phase7 SDK ConsequenceGate",
        module="uniimente_kernel.gate",
        classification=SUPERSEDED,
        may_issue_authority=False,
        rationale=(
            "Embedded its own in-process authority objects while named "
            "uniimente_kernel - the second-government hazard. Its KillSwitch "
            "was written to but never read, so it vetoed nothing."),
        retained_because=(
            "its named_targets and permitted_actions grant scoping was the "
            "strongest scope control found in any engine and is promoted into "
            "aperture.issuer as known_targets / declared_capabilities."),
        revival_conditions="none foreseen; the scoping idea already moved.",
    ),
    Disposition(
        implementation="PR #21 kernel.gate pipeline",
        module="kernel.gate.pipeline",
        classification=CONFORMANCE_FIXTURE,
        may_issue_authority=False,
        rationale=(
            "Earned 24 of 30 refusals in the differential corpus - the best of "
            "the three prior engines. Its fingerprint breadth, staged fail-closed "
            "discipline and Ed25519 trust root are promoted into the aperture."),
        retained_because=(
            "its 12-case hostile suite is the strongest adversarial corpus in "
            "the repository and becomes a conformance opponent."),
        revival_conditions=(
            "if the aperture's certificate model proves unable to express a "
            "staged pipeline requirement, PR #21 holds the worked example."),
    ),
    Disposition(
        implementation="legacy HMAC witness records",
        module="provenance.commit_witness",
        classification=HISTORICAL,
        may_issue_authority=False,
        rationale=(
            "Symmetric HMAC: verification capability implies forging capability, "
            "so these records can establish consistency but never attribution."),
        retained_because="institutional memory; preserved and readable.",
        revival_conditions="never as authority. See aperture.legacy.",
    ),
)


def canonical_active() -> tuple[Disposition, ...]:
    return tuple(d for d in DISPOSITIONS if d.classification == CANONICAL_ACTIVE)


def active_authority_count() -> int:
    """The Gate A metric, read from the manifest rather than from this file."""
    return _manifest.active_issuer_count()


def agrees_with_manifest() -> list[str]:
    """Every disagreement between this registry and the canonical manifest.

    Empty means the two agree. Non-empty is the drift condition that
    invalidated the previous Gate A closure, now detectable.
    """
    problems: list[str] = []
    for d in DISPOSITIONS:
        try:
            m = _manifest.implementation(d.module)
        except _manifest.ManifestError:
            problems.append(f"{d.module} has a disposition but no manifest entry")
            continue
        if bool(m.get("may_issue_authority")) != d.may_issue_authority:
            problems.append(
                f"{d.module}: manifest may_issue_authority="
                f"{m.get('may_issue_authority')} vs registry {d.may_issue_authority}")
        if m.get("classification") != d.classification:
            problems.append(
                f"{d.module}: manifest classification={m.get('classification')!r} "
                f"vs registry {d.classification!r}")
    declared = {d.module for d in DISPOSITIONS}
    for m in _manifest.implementations():
        if m["module"] not in declared:
            problems.append(f"{m['module']} is in the manifest but has no disposition")
    return problems
