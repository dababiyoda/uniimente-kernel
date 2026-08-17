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
        Stage("blocked", _blocked, reads="blueprint.critical_path"),
    ),
)

EVIDENCE = Pipeline(
    "evidence",
    "what resolves, what does not, and every question the organs left open",
    (
        Stage("honesty", _honesty, reads="blueprint.registry"),
        Stage("open-questions", _open_questions, reads="linker"),
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
