"""Bridge G — Business-to-Capability, the half that does not need a customer.

Governed workflow -> extracted Capability Genome -> registry.

The Final Build Order draws Bridge G as: successful business workflow ->
extracted Capability Genome -> registry -> dependency resolution -> second
Venture Cell -> capability transplant -> *faster or cheaper verified outcome*.

**Only the first three arrows are built here, and the reason is not effort.**
The payoff arrow ends in a verified outcome, and
`bridges.reality_to_learning.clean_verified_outcomes` reads zero. A transplant
claiming to be faster or cheaper than a baseline that does not exist would be
measuring against nothing. So this builds extraction and registration, and says
plainly that the economic claim is unmade.

## What was actually missing

Every `CapabilityGenome` in this institution is hand-written inside a closure
probe — `closure/kernel_registry.py`, `closure/advantage_registry.py`,
`closure/commercial_registry.py`. Each is a literal, authored by whoever wrote
the probe. **Not one is extracted from a workflow that ran.** So the Capability
Genome Registry, which section 4.3 calls the institution's package manager, has
never packaged anything the institution did — only descriptions of what it
believes about itself.

That matters because the `FoundryComposer` binds registered genomes when it
composes an advantage. Feeding it only hand-written genomes means the Foundry
composes from claims. Feeding it one extracted from a receipted action means it
composes from something that happened.

## The property that makes extraction safe

**A genome may not claim authority the run did not exercise.** Packaging is the
quietest possible place to widen authority: nobody reads a registry entry as an
authority grant, and yet `GenomeRegistry.may_instantiate` checks requests
against exactly this envelope. So no caller may pass a consequence class or a
budget ceiling — there is no parameter for either, and a test asserts it.

## GAP-BRIDGE-G-001, found by trying to read the envelope off the ledger

The envelope was meant to come from the durable record. It cannot:

- `CommitWitness` carries `action_class`, `capability`, `target`,
  `budget_reservation_id` — and **no consequence class**.
- The gate writes transitions as `event` records typed `action.<state>`; there
  is no `action_state` record type, and `action.proposed` carries only actor and
  action class.
- The receipt carries `result`, `grant_id`, `witness_id` — and **no budget**.

Section 4.11 binds a permission to ten dimensions including Consequence Class
and Budget. Two of the ten did not survive to the ledger, so an action's own
durable record could not say what authority ceiling it ran under.

**Ruled on 2026-08-22.** FOUNDER-RULING-2026-08-22 approved this and
GAP-BRIDGE-D-001 as one coordinated migration, and `provenance/witness_v2.py`
now records `consequence_class` and `exposure_ceiling_usd` under the signature.
So this bridge prefers the **witness** — the action's own record of what *it*
ran under — and falls back to the **passport registry** only for v1 records.

The fallback is an over-estimate and is labelled as one. A passport states what
that actor may *ever* do; a witness states what this action was authorised to
do. `ExtractionRun.authority_source` carries which was used, because a reviewer
who cannot tell them apart will read a standing ceiling as an exercised one.

Either way the caller supplies neither, and when neither source resolves,
extraction refuses rather than defaulting: an invented ceiling is worse than no
capability.

Two more, for the same reason:

- **A refused run yields no genome.** Only a receipted action can be packaged.
  Registering a capability that never worked is the registry's worst failure.
- **The evidence provenance travels with it.** The acceptance tests cite the
  real witness and receipt, and the description records that the evidence is
  internally observed — because that is what `validation_status` said.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from provenance import witness_v2
from capabilities.genome import (CONSEQUENCE_CLASSES, AuthorityEnvelope,
                                 CapabilityGenome, GenomeError)

#: Consequence classes at or above which the envelope must demand a human.
#: `AuthorityEnvelope.validate` enforces it; named here so the extractor sets it
#: from the run rather than discovering the refusal at registration time.
HUMAN_REQUIRED_CLASSES = ("financial", "irreversible")

#: The contract every extracted genome consumes: it is packaged *from* a
#: receipted action, and `outcome` is the contract that action's record follows.
EXTRACTED_CONTRACTS = ("outcome", "evidence")


class Halt(Enum):
    """Why extraction refused. Every value is a capability not worth packaging."""

    NO_RECEIPT = "no_receipt"
    NO_WITNESS = "no_witness"
    AUTHORITY_UNREADABLE = "authority_unreadable"
    UNKNOWN_CONSEQUENCE_CLASS = "unknown_consequence_class"
    GENOME_INVALID = "genome_invalid"


@dataclass(frozen=True)
class ExtractionRun:
    """What one extraction actually did. Derived; nothing here is supplied."""

    completed: bool
    genome: CapabilityGenome | None = None
    halted_at: Halt | None = None
    reason: str = ""
    registered: bool = False
    #: The authority the run exercised, carried so a reviewer can compare it
    #: against the envelope without re-reading the ledger.
    exercised_consequence_class: str | None = None
    exercised_budget_usd: float | None = None
    #: Where the envelope above came from. `"witness"` means the action's own
    #: durable record stated it (v2). `"actor_passport"` means it was read from
    #: the acting identity's standing ceiling because the witness predates the
    #: v2 contract — which is an OVER-ESTIMATE: the passport says what that
    #: actor may ever do, not what this action was authorised to do. A reviewer
    #: must be able to tell those apart, so the source travels with the value.
    authority_source: str = "actor_passport"
    #: Stated rather than left to be assumed from a successful extraction.
    economic_claim: str = (
        "none: Bridge G's faster-or-cheaper claim needs a verified outcome, "
        "and clean_verified_outcomes reads 0"
    )


def extract(ledger, action_id: str, *, passports, version: str = "1.0.0",
            failure_modes: tuple[str, ...] = (),
            recovery_path: str = "detach the capability; the receipt stands",
            registry=None) -> ExtractionRun:
    """Package one receipted action as a Capability Genome.

    The ledger supplies what happened; `passports` supplies the authority the
    acting identity was bounded by. There is deliberately no parameter for
    consequence class or budget ceiling: a caller who could set those could
    register a capability with a wider envelope than anything the institution
    ever ran, and `may_instantiate` would honour it.

    `failure_modes` is the caller's, because the ledger cannot know how a
    capability fails — but `CapabilityGenome.validate` refuses a genome that
    declares none, so an extractor that supplies nothing is refused rather than
    quietly registering an unexamined capability.
    """
    receipts = {r.payload["action_id"]: r.payload for r in ledger.by_type("receipt")}
    receipt = receipts.get(action_id)
    if receipt is None:
        return ExtractionRun(
            completed=False, halted_at=Halt.NO_RECEIPT,
            reason=(f"no receipt for action {action_id!r}; only an action that "
                    f"reached durability may be packaged as a capability"))

    witnesses = {w.payload["witness_id"]: w.payload for w in ledger.by_type("witness")}
    witness = witnesses.get(receipt.get("witness_id"))
    if witness is None:
        return ExtractionRun(
            completed=False, halted_at=Halt.NO_WITNESS,
            reason=f"receipt {action_id!r} cites a witness the ledger does not hold")

    # --- the authority the run actually exercised ---------------------------
    outcomes = {o.payload.get("action_ref"): o.payload
                for o in ledger.by_type("outcome")}
    outcome = outcomes.get(action_id, {})
    validation = outcome.get("validation_status", "internally_observed")

    action_class = witness["action_class"]

    # Under witness contract v2 the action's own durable record states the
    # consequence class and the effective ceiling it ran under, which is the
    # right source: it describes THIS action. The passport describes what the
    # actor may ever do, so falling back to it over-estimates. Prefer the
    # witness; fall back only for v1 records, and say which was used.
    reading = witness_v2.read(witness)
    if reading.authority_reconstructable:
        consequence_class = reading.consequence_class
        budget = float(reading.exposure_ceiling_usd)
        authority_source = "witness"
    else:
        # GAP-BRIDGE-G-001 for historical records. The v1 witness never carried
        # these, and inventing them is refused — the passport is a real
        # authority source rather than a caller's assertion, and the
        # over-estimate is recorded rather than hidden.
        try:
            passport = passports.to_dict(witness["actor"])
        except Exception as exc:
            return ExtractionRun(
                completed=False, halted_at=Halt.AUTHORITY_UNREADABLE,
                reason=(f"the acting identity {witness['actor']!r} cannot be "
                        f"resolved ({exc}), and this v{reading.version} witness "
                        f"does not record a consequence class or exposure "
                        f"ceiling. Refusing to invent an authority envelope."))
        consequence_class = passport.get("consequence_class", "")
        budget = float(passport.get("budget_ceiling_usd") or 0.0)
        authority_source = "actor_passport"

    if consequence_class not in CONSEQUENCE_CLASSES:
        return ExtractionRun(
            completed=False, halted_at=Halt.UNKNOWN_CONSEQUENCE_CLASS,
            reason=(f"the run's consequence class {consequence_class!r} is not one "
                    f"of {list(CONSEQUENCE_CLASSES)}; refusing to guess an envelope"))

    envelope = AuthorityEnvelope(
        max_consequence_class=consequence_class,
        budget_ceiling_usd=budget,
        requires_human=consequence_class in HUMAN_REQUIRED_CLASSES)

    genome = CapabilityGenome(
        name=action_class,
        version=version,
        description=(
            f"Extracted from receipted action {action_id}. Evidence is "
            f"{validation}; the capability has run inside the institution and "
            f"has not been externally verified. Authority envelope read from "
            f"the acting passport, not the ledger — see GAP-BRIDGE-G-001."),
        interface={"inputs": {"proposal": "policy.engine.Proposal"},
                   "outputs": {"receipt": "provenance.ledger receipt record"}},
        contracts=list(EXTRACTED_CONTRACTS),
        authority=envelope,
        acceptance_tests=[f"witness:{witness['witness_id']}",
                          f"receipt:{action_id}"],
        failure_modes=list(failure_modes),
        recovery_path=recovery_path,
        legal_operator=witness["legal_principal"])

    problems = genome.validate()
    if problems:
        return ExtractionRun(
            completed=False, halted_at=Halt.GENOME_INVALID,
            reason=f"extracted genome does not validate: {problems}",
            exercised_consequence_class=consequence_class,
            exercised_budget_usd=budget,
            authority_source=authority_source)

    registered = False
    if registry is not None:
        try:
            registry.register(genome)
            registered = True
        except GenomeError as exc:
            return ExtractionRun(
                completed=False, halted_at=Halt.GENOME_INVALID, reason=str(exc),
                exercised_consequence_class=consequence_class,
                exercised_budget_usd=budget,
            authority_source=authority_source)

    return ExtractionRun(
        completed=True, genome=genome, registered=registered,
        exercised_consequence_class=consequence_class,
        exercised_budget_usd=budget,
            authority_source=authority_source)


#: Named so the gap travels with the code rather than living only in a commit
#: message. Both halves are dimensions section 4.11 binds a permission to.
#: AMENDED 2026-08-22 under FOUNDER-RULING-2026-08-22. The contract change was
#: ratified and made: witness v2 carries consequence_class and
#: exposure_ceiling_usd under the signature, and this bridge reads them when
#: present. The gap is rewritten rather than closed because no v2 witness has
#: been written yet — a contract nothing emits changes no reading.
GAP_BRIDGE_G_001 = (
    "Witness contract v2 records consequence_class and exposure_ceiling_usd, "
    "and extract() prefers them. But policy/consequence_gate.py is a sealed "
    "continuity artifact and still calls the v1 constructor, so every witness "
    "in the ledger is v1 and every extraction falls back to the acting "
    "identity's standing passport ceiling — an OVER-ESTIMATE, reported as "
    "authority_source='actor_passport'. Adoption is blocked on "
    "CONTRADICTION-0002; see "
    "docs/deliberations/CONTRADICTION-0002-continuity-baseline.md."
)
