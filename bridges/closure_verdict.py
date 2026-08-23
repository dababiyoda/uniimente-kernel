"""The whole-body verdict on the bridge chain, including against its author.

`closure/whole_body.py` defines FALSELY_CLOSED as the dangerous case: an
internal metric moved and the external consequence stayed flat. Its canonical
signatures are blunt — *"code coverage increased but bypasses remained"*, *"a
model rated itself higher but external performance did not improve"*.

Bridges A through E all run. They emit events, cross the Consequence Gate, take
witnesses, write receipts and reconcile. Every one of those is an internal
metric. `assurance.side_effects` measures this institution at zero
network-egress sites, and `bridges.reality_to_learning.clean_verified_outcomes`
reads the Single Bottleneck Metric at 0. So the external consequence is flat.

Internal up, external flat. By the institution's own definition that is not
success — it is the failure mode with a name. This module says so in the
controller's own vocabulary rather than leaving the chain to be described by
whoever built it.

## Why the evidence is derived and not passed in

`LoopEvidence` takes two booleans. A caller who supplies them decides the
verdict, and a builder grading their own work would supply `external_ok=True`
by the same optimism that produces false closure in the first place. So
`assess()` takes a ledger and computes both from it:

- `internal_ok` — did the chain actually run? Read from receipts and witnesses.
- `external_ok` — did anything outside say so? Read from the SBM, which
  requires an observer distinct from the actor.

The consequence is that this verdict **changes itself**. Nothing here needs
editing when a real counterparty finally speaks: Bridge D records the
observation, the SBM moves, and the loops close on their own. Until then it
reports FALSELY_CLOSED, and the required actions the controller returns are
`investigate_false_closure` and `regress_change` — aimed at this session's work.
"""
from __future__ import annotations

from bridges.reality_to_learning import clean_verified_outcomes
from closure.whole_body import Loop, LoopEvidence, WholeBodyClosureController

#: The loops the bridge chain actually touches. Everything else is reported
#: open-by-omission and does not block, which is `applicable`'s contract —
#: claiming loops the chain never touches would be its own kind of inflation.
BRIDGE_LOOPS = {
    Loop.STRATEGIC,        # Bridge B: eleven branches, losers preserved
    Loop.ARCHITECTURAL,    # Bridge B: the Spider-Web audit gates
    Loop.AUTHORITY,        # Bridge C: narrowing, grants, commit-time recheck
    Loop.EXECUTION,        # Bridge C: witness, receipt, reconciliation
    Loop.EPISTEMIC,        # Bridge D: validation status and weight
    Loop.REALITY,          # Bridge D: an outside party, or nobody
    Loop.META_IMPROVEMENT,  # Bridge E: retain / regress / kill, governed
}


def _ran(ledger, record_type: str) -> bool:
    return len(ledger.by_type(record_type)) > 0


def assess(ledger, *, change_id: str = "bridge-chain") -> dict:
    """Evaluate the bridge chain against the whole-body controller.

    Both halves of every `LoopEvidence` are derived from `ledger`. There is no
    parameter by which a caller can assert that an external consequence
    occurred — that fact has exactly one source, and it is the Single
    Bottleneck Metric.
    """
    receipts = _ran(ledger, "receipt")
    witnesses = _ran(ledger, "witness")
    outcomes = _ran(ledger, "outcome")
    events = _ran(ledger, "event")

    # One source for every external claim in this function.
    external = clean_verified_outcomes(ledger) > 0

    evidence = {
        Loop.STRATEGIC: LoopEvidence(
            internal_ok=events, external_ok=external,
            detail="branches generated and losers preserved; no external party has "
                   "acted on the selection"),
        Loop.ARCHITECTURAL: LoopEvidence(
            internal_ok=events, external_ok=external,
            detail="the spider-web audit gates the experiment; no external system "
                   "depends on the result yet"),
        Loop.AUTHORITY: LoopEvidence(
            internal_ok=witnesses, external_ok=external,
            detail="narrowing, grant issuance and commit-time revalidation all ran"),
        Loop.EXECUTION: LoopEvidence(
            internal_ok=receipts, external_ok=external,
            detail="actions committed and receipted against a sandbox target; the "
                   "institution holds zero egress sites"),
        Loop.EPISTEMIC: LoopEvidence(
            internal_ok=outcomes, external_ok=external,
            detail="outcomes recorded with an explicit validation status; "
                   "calibration is blocked by GAP-BRIDGE-D-001"),
        Loop.REALITY: LoopEvidence(
            internal_ok=outcomes, external_ok=external,
            detail=f"clean verified outcomes: {clean_verified_outcomes(ledger)}"),
        Loop.META_IMPROVEMENT: LoopEvidence(
            internal_ok=events, external_ok=external,
            detail="retain/regress/kill can now be reached only through the gate"),
    }

    result = WholeBodyClosureController().applicable(
        change_id, evidence, BRIDGE_LOOPS)
    return result.to_dict()


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI entry
    """`python -m bridges.closure_verdict` — the verdict, printed plainly.

    The chain is RUN first, then assessed. An earlier version assessed an empty
    ledger and printed OPEN, which understates the finding in the flattering
    direction: OPEN means nothing ran, and the point of this module is that
    something ran and still did not close.
    """
    import os

    from bridges import experiment_to_reality as bridge_c
    from compiler.ucl_compiler import compile_constitution
    from evolution.experiment import ExperimentSpec
    from identity.machine_passport import PassportRegistry
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner
    from provenance.ledger import EvidenceLedger

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    compiled = compile_constitution(root)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["experiment.run"],
        budget_ceiling_usd=5.0, consequence_class="internal_write")
    run = bridge_c.run(
        ExperimentSpec(
            decisive_unknown="is the chain externally closed",
            hypothesis="it is not", prediction="the sandbox run records a value",
            metric="verified_outcomes", baseline=0.0, threshold=1.0,
            direction="gte", workflow="experiment.run",
            required_capabilities=["experiment.run"],
            authority_requirements=["kernel.grant"], budget_usd=0.0,
            reversible=True, rollback_path="discard the sandbox record",
            kill_condition="measured exceeds 100",
            verification="cryptographic_receipt"),
        gate=gate, passports=passports, actor=actor.passport_id,
        measure=lambda s: 2.0, ledger=ledger)

    verdict = assess(ledger)

    print("=" * 74)
    print("WHOLE-BODY VERDICT ON THE BRIDGE CHAIN")
    print("=" * 74)
    print(f"chain ran : completed={run.completed} receipt={run.receipt_hash is not None}")
    print(f"overall   : {verdict['overall']}")
    for loop, v in sorted(verdict["verdicts"].items()):
        if loop in {l.value for l in BRIDGE_LOOPS}:
            print(f"  {loop:<18} {v}")
    if verdict["falsely_closed"]:
        print(f"\nfalsely closed: {verdict['falsely_closed']}")
    if verdict["required_actions"]:
        print(f"required:       {verdict['required_actions']}")
    print("\nInternal metrics moved; the external consequence is flat. That is the")
    print("institution's own name for this, and it applies to the work that built it.")
    print("Derived from the ledger: it changes when an outside party speaks, and")
    print("not because anyone edited this file.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
