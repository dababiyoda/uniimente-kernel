"""The declared bindings for the P3 episode. Data, not mechanism.

Kept apart from ``router.py`` on purpose: the router must be judgeable without
reading these, and these must be reviewable without reading the router. Every
value below was verified by execution against the checked-out organs, and the
provenance is recorded per binding rather than in a changelog nobody reads.

The route under test:

    IdeaRefinery._opportunity_from() -> OpportunityPacket
      -> venture_protocol.packet_to_wire()
      -> [kernel: proven edge -> route -> contract-delivery event]
      -> OpportunityIntakeService.evaluate_packet() -> NetworkWealthEngine
      -> VentureAssessment(requires_human_approval=True)

``WealthMachineClient`` is deliberately absent from that chain and is named as
the forbidden bypass on both bindings. It is a transport client whose
credential-free default mode is ``mock``, in which DALEOBANKS computes the
assessment itself via ``_evaluate_mock``. Routing through it would yield a
valid-looking assessment with WealthMachineIntelligence never invoked, and the
counterfactual would be measuring nothing.
"""
from __future__ import annotations

import os

from runtime.seam.binding import ConsumerBinding, OrganEntryPoint, ProducerBinding

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKSPACE = os.path.dirname(KERNEL_ROOT)

def _organ_root(*env_names: str, default: str) -> str:
    """First environment override that is set, else the sibling checkout.

    ``TRACK_A_*`` come first because they are this branch's established
    convention: the canonical CI step checks the pinned organ revisions out to
    ``.track-a-organs/`` and exports exactly those names. Honouring them is not
    politeness — without it this episode looks for siblings that CI does not
    have, finds nothing, and **skips**. It did exactly that on the first CI run
    after the two implementations met, reporting green while never executing.
    A test that cannot run where it runs is worse than one that fails.
    """
    for name in env_names:
        value = os.environ.get(name)
        if value:
            return value
    return default


DALEOBANKS_ROOT = _organ_root(
    "TRACK_A_DALEOBANKS_DIR", "UNIIMENTE_DALEOBANKS_ROOT",
    default=os.path.join(WORKSPACE, "DALEOBANKS"),
)
WEALTHMACHINE_ROOT = _organ_root(
    "TRACK_A_WMI_DIR", "UNIIMENTE_WEALTHMACHINE_ROOT",
    default=os.path.join(WORKSPACE, "WealthMachineIntelligence"),
)

DALEOBANKS_ORGAN = "spiffe://uniimente.internal/organ/daleobanks"
WEALTHMACHINE_ORGAN = "spiffe://uniimente.internal/organ/wealthmachine"

CONTRACT = "wire-opportunity-packet"

#: The known bypass, named by file. Path fragment rather than module name
#: because the same file is importable under more than one name depending on
#: how the organ was loaded.
BYPASS = ("wealthmachine_client.py",)

_AUTHORITY = "authorization.p0_p1 (founder P3-B execution order)"


def organ_revisions() -> dict:
    """Which organ revisions this episode actually ran against.

    Recorded, not enforced. The canonical probe hard-fails when a checkout
    drifts from its manifest pin, and duplicating that check here would add a
    second authority over the same question. But an evidence record that omits
    the revision invites the reader to assume it was pinned — and on the run
    that produced ``runtime/evidence/P3_EPISODE.json`` DALEOBANKS was at main,
    not at the pinned ``829c5f28``. State it rather than let it be inferred.
    """
    import subprocess

    out = {}
    for name, root, pin in (
        ("daleobanks", DALEOBANKS_ROOT, _manifest_pin("daleobanks")),
        ("wealthmachine", WEALTHMACHINE_ROOT, _manifest_pin("wealthmachine")),
    ):
        head = None
        if os.path.isdir(root):
            try:
                head = subprocess.run(
                    ["git", "-C", root, "rev-parse", "HEAD"],
                    capture_output=True, text=True, timeout=30, check=False,
                ).stdout.strip() or None
            except (OSError, subprocess.SubprocessError):   # pragma: no cover
                head = None
        out[name] = {
            "root": root,
            "head": head,
            "manifest_pin": pin,
            "matches_manifest_pin": bool(head and pin and head == pin),
        }
    return out


def _manifest_pin(organ: str) -> str | None:
    path = os.path.join(KERNEL_ROOT, "organs", f"{organ}.manifest.yaml")
    try:
        import yaml

        with open(path, encoding="utf-8") as fh:
            return (yaml.safe_load(fh).get("source") or {}).get("commit")
    except Exception:                                        # pragma: no cover
        return None


def organs_available() -> tuple[bool, str]:
    """Whether both organ checkouts exist.

    Returned rather than raised so the episode can report UNRUNNABLE. An
    absent checkout must never be reachable as a passing result — that is the
    same dead-instrument failure the evaluator work ruled out three times.
    """
    missing = [p for p in (DALEOBANKS_ROOT, WEALTHMACHINE_ROOT) if not os.path.isdir(p)]
    if missing:
        return False, f"organ checkouts missing: {missing}"
    return True, "both organ checkouts present"


#: A realistic operator thought. Chosen so the real refinery's own offer-hint
#: and finance heuristics fire — a subject engineered to bypass its logic would
#: make the producer a formality.
SUBJECT_TEXT = (
    "People keep asking me the same question about how compound interest "
    "actually works, and why nobody ever explains it to savers in plain "
    "language. I want to build a checklist and a workshop for them."
)
SUBJECT_THESIS = "Financial systems profit from the confusion they create"


def producer_binding() -> ProducerBinding:
    return ProducerBinding(
        organ_id=DALEOBANKS_ORGAN,
        contract=CONTRACT,
        subject=OrganEntryPoint(
            organ_id=DALEOBANKS_ORGAN, repository_root=DALEOBANKS_ROOT,
            module="db.models", attribute="Idea", forbidden_fragments=BYPASS,
        ),
        subject_kwargs={"raw_text": SUBJECT_TEXT},
        entry_point=OrganEntryPoint(
            organ_id=DALEOBANKS_ORGAN, repository_root=DALEOBANKS_ROOT,
            module="services.idea_refinery", attribute="IdeaRefinery",
            forbidden_fragments=BYPASS,
        ),
        method="_opportunity_from",
        extra_args=(SUBJECT_THESIS,),
        serializer=OrganEntryPoint(
            organ_id=DALEOBANKS_ORGAN, repository_root=DALEOBANKS_ROOT,
            module="services.venture_protocol", attribute="packet_to_wire",
            forbidden_fragments=BYPASS,
        ),
        declared_by=_AUTHORITY,
        reason=(
            "IdeaRefinery is DALEOBANKS' real packet producer and packet_to_wire "
            "is its canonical serialization. Both are pure over plain dataclasses: "
            "no database session, no credentials, no network."
        ),
    )


def consumer_binding() -> ConsumerBinding:
    return ConsumerBinding(
        organ_id=WEALTHMACHINE_ORGAN,
        contract=CONTRACT,
        entry_point=OrganEntryPoint(
            organ_id=WEALTHMACHINE_ORGAN, repository_root=WEALTHMACHINE_ROOT,
            module="src.services.opportunity_intake",
            attribute="OpportunityIntakeService",
            forbidden_fragments=BYPASS,
        ),
        construct=True,
        method="evaluate_packet",
        declared_by=_AUTHORITY,
        reason=(
            "OpportunityIntakeService validates the wire packet, runs the real "
            "NetworkWealthEngine venture loop and returns a schema-validated "
            "assessment with requires_human_approval hardcoded true. It is "
            "institutional work that would belong in the organism even if this "
            "experiment were deleted — not a fixture written to be routed to."
        ),
    )


def wrong_consumer_binding() -> ConsumerBinding:
    """Negative control: a binding whose organ has no proven edge for this contract.

    DALEOBANKS produces ``wire-opportunity-packet``; it does not consume it. If
    this binding ever materialises a route, the router is matching on something
    other than the linker's proven edges and every STATE A result is void.
    """
    return ConsumerBinding(
        organ_id=DALEOBANKS_ORGAN,
        contract=CONTRACT,
        entry_point=OrganEntryPoint(
            organ_id=DALEOBANKS_ORGAN, repository_root=DALEOBANKS_ROOT,
            module="services.venture_protocol", attribute="validate_assessment_wire",
        ),
        declared_by="negative control — never a real binding",
        reason="must be refused: no proven edge delivers this contract here",
    )


def bypass_consumer_binding() -> ConsumerBinding:
    """Negative control: a binding that routes into the mock evaluator.

    This is the failure the whole P3 route was redesigned to avoid, made
    executable. It points at WealthMachineClient, whose credential-free default
    computes the assessment locally. The router must raise ``BypassDetected``.

    Without this control, "no bypass detected" in STATE B would be worthless —
    it could equally mean the detector never worked.
    """
    return ConsumerBinding(
        organ_id=WEALTHMACHINE_ORGAN,
        contract=CONTRACT,
        entry_point=OrganEntryPoint(
            organ_id=WEALTHMACHINE_ORGAN, repository_root=DALEOBANKS_ROOT,
            module="services.wealthmachine_client", attribute="WealthMachineClient",
            forbidden_fragments=BYPASS,
        ),
        construct=True,
        method="evaluate",
        declared_by="negative control — never a real binding",
        reason="must be detected as the bypass, not accepted as a consumer",
    )
