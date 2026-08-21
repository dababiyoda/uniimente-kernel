"""The named pipelines. Every number here is produced by a module that already
existed and is already separately verifiable.

Doctrine (SHELL): this file is the complete list of things the shell can do.
Pipelines are declared as data at import time and are never assembled from
caller input, so the surface is bounded and readable in one place.

Nothing in this module computes a new institutional fact. Each stage calls a
reporter that another package owns, and renders its answer. Where a reporter
cannot answer, the stage says UNRESOLVED and names the reason instead of
substituting a number.
"""
from __future__ import annotations

from shell.pipeline import Pipeline, Stage, StageResult, ok, unresolved


def _rung(status) -> str:
    """Render an awarded rung, including the absence of one.

    A technology whose evidence supports nothing carries `awarded_rung is None`
    rather than a bottom rung — the ladder refuses to round an unsupported
    claim up to BLUEPRINT. Any renderer that assumes a rung object crashes on
    exactly those rows, which is the population most worth looking at.
    """
    return status.awarded_rung.value if status.awarded_rung else "UNSUPPORTED"

# --------------------------------------------------------------------- ladder


def _ladder() -> StageResult:
    from blueprint.critical_path import compute

    report = compute()
    by_rung = report.by_rung()
    by_reality = report.by_reality()
    unsupported = by_rung.get("UNSUPPORTED", ())
    hardened = by_rung.get("HARDENED", ())

    detail = [f"{rung:<12} {len(ids):>2}" for rung, ids in by_rung.items()]
    detail.append("")
    detail += [f"{r:<15} {len(ids):>2}" for r, ids in by_reality.items()]
    if unsupported:
        detail.append("")
        detail.append(f"UNSUPPORTED: {list(unsupported)} — claimed a rung the "
                      "evidence refused")

    headline = (f"{len(report.statuses)} technologies; "
                f"{len(hardened)} HARDENED; {len(unsupported)} unsupported")
    if unsupported:
        return unresolved("ladder", headline, tuple(detail))
    return ok("ladder", headline, tuple(detail))


def _honesty() -> StageResult:
    from blueprint.registry import audit

    results = audit()
    overclaimed = [a.technology_id for a in results if a.problems]
    if overclaimed:
        detail = tuple(
            f"#{a.technology_id}: {p}" for a in results for p in a.problems
        )
        return unresolved("honesty",
                          f"{len(overclaimed)} binding(s) claim more than resolves",
                          detail)
    return ok("honesty",
              "every awarded rung is backed by a reference that resolves")


def _frontier() -> StageResult:
    from blueprint.critical_path import compute

    report = compute()
    rows = [
        f"#{s.technology_id:<3} {s.name[:38]:<38} "
        f"{_rung(s):<11} -> {s.ceiling.value:<10} "
        f"leverage={s.leverage:<3} owner={s.owner.value}"
        for s in report.frontier
    ]
    return ok("frontier",
              f"{len(report.frontier)} unblocked, {len(report.blocked)} blocked",
              tuple(rows))


def _levers() -> StageResult:
    """What would actually unstick the institution, and who owns each one."""
    from blueprint.critical_path import compute
    from blueprint.registry import Owner

    levers = compute().unlock_levers()
    if not levers:
        return unresolved("levers", "no technology can raise anyone's ceiling",
                          ("Every technology with dependents is already at its own "
                           "ceiling. Nothing internal can move the critical path.",))
    rows = ["  " + lever.headline for lever in levers]
    mine = [l for l in levers if l.owner is Owner.CLAUDE]
    buildable = [l for l in mine if not l.needs_external_reality]
    detail = tuple(rows) + (
        "",
        f"CLAUDE-owned: {[l.technology_id for l in mine]}; of those, "
        f"{[l.technology_id for l in buildable]} need only evidence that could be "
        "built, the rest need a reconciled external consequence.",
    )
    verb = "is" if len(buildable) == 1 else "are"
    headline = (f"{len(levers)} technologies could raise a ceiling; "
                f"{len(buildable)} of them {verb} CLAUDE-owned and buildable")
    if not buildable:
        return unresolved("levers", headline, detail)
    return ok("levers", headline, detail)


def _decisions() -> StageResult:
    """What is waiting on a human, and what is in force while it waits.

    Reported as UNRESOLVED whenever anything is open, because an unanswered
    constitutional question *is* an unresolved institutional state. A shell that
    rendered three pending founder decisions as OK would be describing an
    institution that had decided them.
    """
    from governance.decisions import State, load_all, open_decisions

    records = load_all()
    still_open = open_decisions(records)
    if not still_open:
        return ok("decisions",
                  f"{len(records)} deliberation record(s); none waiting on a human")

    rows: list[str] = []
    for record in still_open:
        rows.append("  " + record.headline())
        rows.append(f"    owner   : {record.owner}")
        if record.default_in_force:
            rows.append(f"    in force: {record.default_in_force}")
        if record.defect:
            rows.append(f"    DEFECT  : {record.defect}")
    unsound = [d for d in still_open if d.state is not State.AWAITING_FOUNDER]
    if unsound:
        rows.append("")
        rows.append(f"{len(unsound)} record(s) are open for a defect rather than "
                    "for a pending answer — see DEFECT lines above.")
    return unresolved("decisions",
                      f"{len(still_open)} of {len(records)} deliberation records "
                      "await an authorized human",
                      tuple(rows))


def _registries() -> StageResult:
    """Where decision records live, and which ones this ref cannot see.

    UNRESOLVED whenever a known registry is unreachable or a concern is
    contested. Both are true states of the institution rather than errors, and
    a shell that rendered them OK would be reporting a coherence the organism
    does not have.
    """
    from governance.registries import (
        KNOWN_REGISTRIES,
        contested_concerns,
        render,
        unreachable,
    )

    missing = unreachable()
    contested = contested_concerns()
    detail = tuple("  " + line for line in render().splitlines())
    if not missing and not contested:
        return ok("registries",
                  f"{len(KNOWN_REGISTRIES)} decision registries, all readable "
                  "and none contested", detail)
    parts = []
    if missing:
        parts.append(f"{len(missing)} unreadable from this ref")
    if contested:
        parts.append(f"{len(contested)} concern(s) with more than one owner")
    return unresolved("registries",
                      f"{len(KNOWN_REGISTRIES)} decision registries; "
                      + "; ".join(parts), detail)


def _side_effects() -> StageResult:
    """Can anything reach the world without crossing the gate?

    Supplies the baseline Kimi's Final Plan records as unknown, and reports
    UNRESOLVED whenever a family has unmediated sites — which is the true state,
    not an error.
    """
    from assurance.side_effects import Family, coverage, inventory, render

    sites = inventory()
    detail = tuple("  " + line for line in render().splitlines())
    open_families = [f for f in Family
                     if coverage(f, sites)[1] > coverage(f, sites)[0]]
    net_mediated, net_total = coverage(Family.NETWORK, sites)
    headline = (f"{len(sites)} side-effect site(s); network egress capability: "
                f"{'NONE' if net_total == 0 else f'{net_mediated}/{net_total} mediated'}")
    if not open_families:
        return ok("side-effects", headline, detail)
    return unresolved("side-effects",
                      f"{headline}; {len(open_families)} family(ies) with "
                      "sites that cannot be shown to cross the gate", detail)


def _blocked() -> StageResult:
    from blueprint.critical_path import compute

    report = compute()
    rows = [
        f"#{s.technology_id:<3} {s.name[:38]:<38} ceiling={s.ceiling.value:<10} "
        f"held by {list(s.blocked_by)}"
        for s in report.blocked
    ]
    return ok("blocked",
              f"{len(report.blocked)} technologies cannot advance until a "
              "dependency does",
              tuple(rows))


# --------------------------------------------------------------------- organs


def _organs() -> StageResult:
    from discovery.service import CapabilityDiscoveryService

    rec = CapabilityDiscoveryService().identity_reconciliation()
    detail = (
        f"manifests published      : {rec['manifests_published']}",
        f"identities registered    : {rec['identity_registered']}",
        f"in both registers        : {len(rec['both'])} {sorted(rec['both'])}",
        "manifested, unregistered : "
        f"{[e['name'] for e in rec['manifested_without_identity_registration']]}",
        "registered, no manifest  : "
        f"{[e['name'] for e in rec['registered_without_manifest']]}",
        "",
        "Neither register is activation. Activation requires a capability grant.",
    )
    return ok("organs",
              f"{rec['manifests_published']} manifests, "
              f"{rec['identity_registered']} identities, "
              f"{len(rec['both'])} in both",
              detail)


def _edges() -> StageResult:
    from linker.linker import InstitutionalLinker
    from linker.manifest import load_all

    report = InstitutionalLinker(load_all()).link()
    detail = tuple(
        f"{e.producer.rsplit('/', 1)[-1]} --[{e.contract}]--> "
        f"{e.consumer.rsplit('/', 1)[-1]}"
        for e in report.edges
    )
    headline = (f"{len(report.edges)} typed edges; "
                f"{len(report.unproduced)} unproduced, {len(report.untyped)} untyped")
    if not report.fully_connected:
        return unresolved("edges", headline, detail + ("", "fully_connected = False"))
    return ok("edges", headline, detail)


def _spec_anchors() -> StageResult:
    """Spec anchors that cite a phrase rather than a section."""
    from blueprint.evidence import weak_spec_anchors

    weak = weak_spec_anchors()
    if not weak:
        return ok("spec-anchors", "every spec anchor resolves to a heading")
    detail = tuple(f"#{tech_id:<3} {locator}" for tech_id, locator in weak)
    return unresolved(
        "spec-anchors",
        f"{len(weak)} spec anchor(s) appear only in prose, not as a heading",
        detail + ("",
                  "Reporting only: these still resolve. Requiring a heading would "
                  "drop these technologies to UNSUPPORTED, which is a founder-level "
                  "call about what counts as a specification."))


def _open_questions() -> StageResult:
    from linker.linker import InstitutionalLinker
    from linker.manifest import load_all

    report = InstitutionalLinker(load_all()).link()
    if not report.unresolved:
        return ok("open-questions", "no organ declares an open question")
    detail = tuple(
        f"{organ.rsplit('/', 1)[-1]}: {question}"
        for organ, question in report.unresolved
    )
    return unresolved("open-questions",
                      f"{len(report.unresolved)} question(s) declared open by the "
                      "organs themselves",
                      detail)


def _cycle_audit() -> StageResult:
    """Did the recent cycles raise rungs, or raise capability? Not the same question."""
    from blueprint.cycle import (
        Verdict,
        consecutive_ceremony,
        consecutive_without_unlock,
        history,
        kill_condition_fired,
        load_all,
        stall_condition_fired,
    )

    snapshots = load_all()
    cycles = history(snapshots)
    if not cycles:
        return unresolved("cycle-audit",
                          f"{len(snapshots)} snapshot(s) on record; a trend needs two",
                          ("Record one with: python -m blueprint.cycle take",))
    detail = tuple(c.headline for c in cycles)
    run = consecutive_ceremony(cycles)
    flagged = [c for c in cycles if c.verdict is Verdict.CEREMONY_SUSPECTED]
    regressions = [c for c in cycles if c.verdict is Verdict.REGRESSION]
    headline = (f"{len(cycles)} cycle(s); {len(flagged)} raised a rung without "
                f"unlocking anything; {len(regressions)} regression(s)")
    if stall_condition_fired(cycles):
        stalled = consecutive_without_unlock(cycles)
        return unresolved(
            "cycle-audit", f"{headline} — STALLED",
            detail + ("",
                      f"{stalled} consecutive cycles unlocked nothing downstream: no "
                      "ceiling rose, nothing entered the frontier, no external outcome "
                      "landed. Only one of those three clears it; more internal "
                      "building will not."))
    if kill_condition_fired(cycles):
        return unresolved("cycle-audit", f"{headline} — KILL CONDITION FIRED",
                          detail + ("",
                                    f"{run} consecutive ceremony cycles. Retiring the "
                                    "ladder is a founder decision, not a computation."))
    if flagged or regressions:
        return unresolved("cycle-audit", headline, detail)
    return ok("cycle-audit", headline, detail)


# ------------------------------------------------------------------- closures


#: The shell is itself a registered module, and its `technical` closure collects
#: every pipeline — including the one containing this stage. Verifying it from
#: here would recurse without terminating. It is excluded on principle as well
#: as for termination: a module cannot be its own witness. The shell's own five
#: closures are verified by the suite and by `closure/whole_body.py`, neither of
#: which the shell can influence.
SELF = "shell"


def _closures() -> StageResult:
    from closure.integration_registry import build_registry

    registry = build_registry()
    modules = [m for m in registry.modules() if m != SELF]
    reports = [registry.verify_module(m) for m in modules]
    incomplete = [r.module for r in reports if not r.complete]
    headline = (f"{len(reports)} modules under five-closure verification "
                f"({SELF} excluded — a module cannot be its own witness)")
    if incomplete:
        return unresolved("closures", f"{headline}; {len(incomplete)} incomplete",
                          tuple(incomplete))
    return ok("closures", f"{headline}; all complete")


# ------------------------------------------------------------------- outcomes


def _outcomes() -> StageResult:
    """The Single Bottleneck Metric, read off the ladder rather than asserted."""
    from blueprint.critical_path import compute

    hardened = compute().by_rung().get("HARDENED", ())
    if hardened:
        return ok("outcomes",
                  f"{len(hardened)} technology/ies carry a reconciled external "
                  f"outcome: {list(hardened)}")
    return unresolved(
        "outcomes",
        "verified external outcome count is 0",
        ("HARDENED requires a reconciled real-world consequence.",
         "No amount of further internal building changes this number."),
    )


# -------------------------------------------------------------------- handoff


def _seal() -> StageResult:
    from handoff import conform

    report = conform.run()
    detail = (
        f"contract version : {report.contract_version}",
        f"bundle digest    : {report.bundle_digest}",
        f"sealed commit    : {report.sealed_commit}",
        f"vectors passed   : {report.vectors_passed}",
    )
    if report.ok:
        return ok("seal", "CONFORMANT — integrity, seal and vectors all pass", detail)
    problems = tuple(report.integrity + report.seal + report.vectors_failed)
    return unresolved("seal", "NOT CONFORMANT", detail + ("",) + problems)


# ------------------------------------------------------------------ pipelines

STATUS = Pipeline(
    "status",
    "ladder maturity, organ connectivity and closure coverage",
    (
        Stage("ladder", _ladder, reads="blueprint.critical_path"),
        Stage("organs", _organs, reads="discovery.service"),
        Stage("edges", _edges, reads="linker"),
        Stage("closures", _closures, reads="closure.integration_registry"),
        Stage("outcomes", _outcomes, reads="blueprint.critical_path"),
    ),
)

FRONTIER = Pipeline(
    "frontier",
    "what is unblocked right now and who owns it",
    (
        Stage("frontier", _frontier, reads="blueprint.critical_path"),
        Stage("levers", _levers, reads="blueprint.critical_path"),
        Stage("blocked", _blocked, reads="blueprint.critical_path"),
        Stage("decisions", _decisions, reads="governance.decisions"),
    ),
)

EVIDENCE = Pipeline(
    "evidence",
    "what resolves, what does not, and every question the organs left open",
    (
        Stage("honesty", _honesty, reads="blueprint.registry"),
        Stage("cycle-audit", _cycle_audit, reads="blueprint.cycle"),
        Stage("spec-anchors", _spec_anchors, reads="blueprint.evidence"),
        Stage("open-questions", _open_questions, reads="linker"),
        Stage("decisions", _decisions, reads="governance.decisions"),
        Stage("registries", _registries, reads="governance.registries"),
        Stage("side-effects", _side_effects, reads="assurance.side_effects"),
        Stage("outcomes", _outcomes, reads="blueprint.critical_path"),
    ),
)

HANDOFF = Pipeline(
    "handoff",
    "integrity and seal of the frozen ChatGPT bundle",
    (Stage("seal", _seal, reads="handoff.conform"),),
)

PIPELINES: dict[str, Pipeline] = {
    p.name: p for p in (STATUS, FRONTIER, EVIDENCE, HANDOFF)
}

DEFAULT_PIPELINE = "status"
