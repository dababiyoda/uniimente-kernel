"""Does the gap register still describe the repository?

`blueprint/registry.py` carries named hardening gaps — the institution's own
list of what is wrong with it. Ten of them belong to the founder. It is the
shortest list of things only Alfonso can unblock, which makes it the surface
where a wrong entry costs the most.

Nothing checked it. A gap is prose written at one commit and read at another,
and prose does not notice when the repository moves underneath it.

**It had already drifted.** Technology #26 carries:

    "adapters/ is imported by no non-test module: the compatibility membrane
     is built and tested but connected to nothing that runs."

That was true when it was written and is false now — `bridges/signal_to_venture`
imports `adapters` and runs it. A founder reading the gap list sees an open
problem that is closed, on the one list where his attention is scarcest.

## What this module does, and what it deliberately does not

It evaluates the gap claims that *can* be evaluated and reports three verdicts:

- `VERIFIED_OPEN` — the repository still agrees the gap is real.
- `STALE` — the gap says open; the repository says closed. A false entry on the
  founder's plate.
- `ANCHOR_LOST` — the gap text changed and this check no longer matches
  anything. **Treated as a failure, not a skip.** A check whose subject was
  reworded stops guarding silently, which is the exact failure mode that let
  the drift above survive.

Gaps with no registered check are reported as `UNCHECKED` and counted honestly.
Most gap text is prose about things no static reading can settle, and claiming
otherwise would make this instrument the thing it exists to catch.

**It reports; it does not edit.** A system that quietly rewrote its own record
of what is wrong with it would be deleting evidence, and the register's whole
value is that a human wrote each entry deliberately. Correcting a stale gap is
an authored change with the audit output as its justification.
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from blueprint.registry import BINDINGS

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Directories that are not the running institution. A gap about what "runs"
#: must not be satisfied by a test that imports the thing.
NON_INSTITUTIONAL = {".git", "__pycache__", "tests", ".venv", "scripts"}


class Verdict(str, Enum):
    VERIFIED_OPEN = "VERIFIED_OPEN"
    STALE = "STALE"
    ANCHOR_LOST = "ANCHOR_LOST"
    UNCHECKED = "UNCHECKED"


@dataclass(frozen=True)
class GapRow:
    technology_id: int
    technology: str
    gap: str
    verdict: Verdict
    evidence: str = ""

    @property
    def needs_attention(self) -> bool:
        """A stale entry misleads; a lost anchor means a check stopped running.
        Both are defects in the register, not in the institution."""
        return self.verdict in (Verdict.STALE, Verdict.ANCHOR_LOST)


# --- the checks. Each returns (still_open, evidence). --------------------------

def _non_test_importers(package: str) -> set[str]:
    """Modules outside `package` that import it, excluding tests and scripts."""
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(KERNEL_ROOT):
        dirnames[:] = [d for d in dirnames if d not in NON_INSTITUTIONAL]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, KERNEL_ROOT)
            if rel.split(os.sep)[0] == package:
                continue
            with open(path, encoding="utf-8", errors="ignore") as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                if any(m.split(".")[0] == package for m in modules):
                    found.add(rel)
    return found


def _adapters_are_disconnected() -> tuple[bool, str]:
    importers = _non_test_importers("adapters")
    if importers:
        return False, (f"adapters/ is imported by {len(importers)} non-test module(s): "
                       f"{', '.join(sorted(importers))}")
    return True, "adapters/ has no non-test importer"


def _no_external_reach() -> tuple[bool, str]:
    """Everything downstream of "this institution cannot reach anything".

    One measurement, cited by several gaps, because they are one fact: no
    payment rail, no notarization service and no publisher can be connected
    while the egress site count is zero.
    """
    from assurance.side_effects import Family, inventory

    sites = [s for s in inventory(KERNEL_ROOT) if s.family is Family.NETWORK]
    count = len(sites)
    if count == 0:
        return True, "network_egress: 0 sites — the institution cannot reach anything"
    return False, f"network_egress: {count} site(s) now exist"


def _no_verified_outcome() -> tuple[bool, str]:
    """Gaps that say nothing has been compared against reality."""
    from bridges.reality_to_learning import EXTERNALLY_VERIFIED

    # Read the contract rather than a live ledger: the claim is about the
    # institution's record as a whole, and no committed record carries one.
    import json
    import glob

    verified = 0
    for path in glob.glob(os.path.join(KERNEL_ROOT, "**", "*.json"), recursive=True):
        if any(part in path for part in NON_INSTITUTIONAL):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (ValueError, OSError):
            continue
        if isinstance(payload, dict) and payload.get("validation_status") == EXTERNALLY_VERIFIED:
            verified += 1
    if verified == 0:
        return True, "no committed record carries validation_status externally_verified"
    return False, f"{verified} externally verified outcome record(s) now exist"


#: SUPERSEDED 2026-08-22, retained as the record of a measurement that expired.
#:
#: These were the primitives whose *absence* made "HMAC over a shared secret"
#: true, and whose arrival was expected to close #7 and #26. The reasoning was
#: sound and the proxy was still wrong: `identity/pki/` imports `cryptography`,
#: so this tuple would have reported both gaps closed while the live transport
#: kept authenticating with one shared key.
#:
#: Kept rather than deleted because it is the clearest example in this file of
#: how a proxy measurement decays — it stops tracking the gap at exactly the
#: moment the work starts, and it fails toward "closed". Replaced by
#: `_asymmetric_identity_is_not_adopted`, which measures use instead of
#: presence.
_SUPERSEDED_ASYMMETRIC_PRIMITIVES = (
    "cryptography", "ecdsa", "rsa", "nacl", "OpenSSL", "jwcrypto")


#: Where the asymmetric identity mechanism lives. Its own imports of
#: `cryptography` are not evidence that anything uses it.
_PKI_PACKAGE = os.path.join("identity", "pki")


def _asymmetric_identity_is_not_adopted() -> tuple[bool, str]:
    """The shared-secret claim on #7 and #26, measured by ADOPTION.

    REPLACED 2026-08-22. This check previously asked whether any institutional
    module imported an asymmetric primitive, on the reasoning that a per-service
    identity needs one somewhere and none existed. That proxy held exactly until
    `identity/pki/` was built — at which point it would have reported the gap
    STALE, because `cryptography` was now imported.

    Which would have been wrong, and wrong in the worse direction: telling the
    founder a trust boundary had closed when the live transport was still
    authenticating with one shared key. Building a replacement is not adopting
    one.

    So the question changed to the one that is actually still open: does any
    institutional module OUTSIDE the PKI package and outside the tests actually
    use it? The PKI importing its own crypto proves nothing, and neither does a
    test — a test is how the mechanism is exercised, not how the institution
    adopts it.
    """
    users: list[str] = []
    for dirpath, dirnames, filenames in os.walk(KERNEL_ROOT):
        dirnames[:] = [d for d in dirnames if d not in NON_INSTITUTIONAL]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            relative = os.path.relpath(path, KERNEL_ROOT)
            # The mechanism does not adopt itself, and a test is not adoption.
            if relative.startswith(_PKI_PACKAGE) or relative.startswith("tests"):
                continue
            with open(path, encoding="utf-8", errors="ignore") as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                if any(m.startswith("identity.pki") for m in modules):
                    users.append(relative)
    if not users:
        return True, ("identity/pki/ exists and is tested, but no institutional "
                      "module outside it imports it; the live transport is still "
                      "HMAC over one shared key")
    return False, ("asymmetric identity is now used by "
                   f"{', '.join(sorted(set(users)))}")


def _witness_v2_is_not_emitted() -> tuple[bool, str]:
    """GAP-BRIDGE-D-001 / G-001 after the migration: is v2 actually written?

    The contract exists (`provenance/witness_v2.py`) and both bridges read it.
    Whether the institution can answer "how confident were we, under what
    exposure" depends entirely on whether the gate EMITS it — and the gate is a
    sealed continuity artifact, so it still calls the v1 constructor.

    Checked at the one place it can be settled: the `new_witness(...)` call in
    `policy/consequence_gate.py`. If its keywords carry the v2 facts, the gap is
    closed; if not, every witness in the ledger is v1 regardless of how complete
    the contract module is. Deliberately not satisfied by the contract merely
    existing — that is the proxy failure `_SUPERSEDED_ASYMMETRIC_PRIMITIVES`
    records.
    """
    gate = os.path.join(KERNEL_ROOT, "policy", "consequence_gate.py")
    try:
        with open(gate, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except OSError:
        return True, "policy/consequence_gate.py is unreadable"

    required = {"evidence_confidence", "consequence_class", "exposure_ceiling_usd"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else "")
        if name != "new_witness":
            continue
        passed = {kw.arg for kw in node.keywords if kw.arg}
        missing = sorted(required - passed)
        if not missing:
            return False, "the gate now emits witness contract v2"
        return True, (f"the gate calls new_witness without {missing}; every "
                      "witness in the ledger is v1 and reads as UNRECORDED")
    return True, "no new_witness call found in the gate"


def _routing_decision_is_untyped() -> tuple[bool, str]:
    """`RoutingDecision` has no schema in the canonical contract registry."""
    contracts = os.path.join(KERNEL_ROOT, "contracts")
    names = [n for n in os.listdir(contracts) if n.endswith(".schema.json")]
    routing = [n for n in names if "rout" in n.lower() or "decision" in n.lower()]
    # `decision.schema.json` is the constitutional decision record, not a
    # routing decision. Match the specific name a typed RoutingDecision needs.
    typed = [n for n in routing if "rout" in n.lower()]
    if not typed:
        return True, (f"contracts/ holds {len(names)} schemas, none for a routing "
                      f"decision")
    return False, f"a routing contract now exists: {', '.join(typed)}"


def _bridge_f_is_unimplemented() -> tuple[bool, str]:
    """Bridge F — audience to business — has no module under `bridges/`."""
    bridges = os.path.join(KERNEL_ROOT, "bridges")
    present = sorted(n for n in os.listdir(bridges)
                     if n.endswith(".py") and n != "__init__.py")
    f_like = [n for n in present if "audience" in n or "to_business" in n]
    if not f_like:
        return True, (f"bridges/ holds {len(present)} modules, none implementing "
                      f"audience-to-business")
    return False, f"a Bridge F module now exists: {', '.join(f_like)}"


def _commerce_dependencies_unbuilt() -> tuple[bool, str]:
    """#54 depends on payments, marketplaces and reputation. Read their REALITY.

    Reality, not rung — and the distinction is the whole reason the ladder
    carries two axes. The first draft of this check asked whether each
    dependency had climbed past BLUEPRINT and reported the gap STALE because
    payments sits at EXERCISED. But payments is EXERCISED with
    `reality=SIMULATED`: it runs inside the institution's own loop against
    fixtures, and a fixture is not a payment rail. The gap says these do not
    exist, and against the axis that means existing, it is still right.

    A false STALE costs the founder exactly what a stale gap costs — it reports
    something closed that is open — so this check reads the axis that answers
    the question actually asked.
    """
    from blueprint.critical_path import compute
    from blueprint.ladder import Reality

    report = compute()
    named = {38: "payments", 37: "marketplaces", 41: "reputation"}
    real = {label: report.statuses[tid].reality.value
            for tid, label in named.items()
            if report.statuses[tid].reality is Reality.IMPLEMENTED}
    if not real:
        states = ", ".join(
            f"{label} #{tid} {report.statuses[tid].reality.value}"
            for tid, label in named.items())
        return True, f"none is IMPLEMENTED: {states}"
    return False, f"now real: {real}"


def _no_genome_contract() -> tuple[bool, str]:
    """#12: no schema types the Capability Genome at its boundary."""
    contracts = os.path.join(KERNEL_ROOT, "contracts")
    genome = [n for n in os.listdir(contracts)
              if n.endswith(".schema.json") and "genome" in n.lower()]
    if not genome:
        return True, "contracts/ holds no capability-genome schema"
    return False, f"a genome contract now exists: {', '.join(genome)}"


def _no_module_loader() -> tuple[bool, str]:
    """#13: the governed module loader of FBO 4.4 has no implementation.

    ChatGPT owns building it. Checking whether it exists is not building it,
    and the founder's list should not carry an entry that has quietly closed.
    """
    candidates = [n for n in os.listdir(KERNEL_ROOT)
                  if os.path.isdir(os.path.join(KERNEL_ROOT, n))
                  and n.lower() in ("moduleloader", "module_loader", "loader")]
    if not candidates:
        return True, "no module-loader package exists at the repository root"
    return False, f"a module loader now exists: {', '.join(candidates)}"


def _transport_is_in_memory_only() -> tuple[bool, str]:
    """#24: the event transport has no durable implementation."""
    events = os.path.join(KERNEL_ROOT, "events")
    modules = sorted(n for n in os.listdir(events) if n.endswith(".py"))
    durable = [n for n in modules
               if any(k in n.lower() for k in ("sqlite", "postgres", "pg_", "broker"))]
    if not durable:
        return True, f"events/ holds {', '.join(modules)} — no durable backend"
    return False, f"a durable transport now exists: {', '.join(durable)}"


def _egregore_is_disconnected() -> tuple[bool, str]:
    """#48: standing cognition imported by nothing and registered nowhere.

    Both clauses. The gap is one sentence making two claims, and a check that
    answered only half of it would report the gap open on the strength of a
    condition that had already changed.
    """
    from closure.integration_registry import build_registry

    importers = _non_test_importers("egregore")
    registered = "egregore-standing-cognition" in build_registry().modules()
    if not importers and not registered:
        return True, "egregore/ has no non-test importer and is in no closure registry"
    return False, (f"imported by {', '.join(sorted(importers)) or 'nothing'}; "
                   f"registered with the closure controller: {registered}")


#:
#: The #26 adapters check was retired when the gap it watched was closed: this
#: audit reported it STALE, the register was corrected in the same change, and a
#: check with no subject would then report ANCHOR_LOST forever. The regression it
#: guarded against is still covered — Bridge A's own suite asserts that
#: `adapters/` is imported by something that is not a test.
#: (technology_id, anchor, check). The anchor is a distinctive fragment of the
#: gap text; if it stops matching, the row reports ANCHOR_LOST rather than
#: quietly dropping out of the audit.
CHECKS: tuple[tuple[int, str, Callable[[], tuple[bool, str]]], ...] = (
    (6, "No external timestamping or independent notarization", _no_external_reach),
    (38, "No payment rail is connected", _no_external_reach),
    (49, "No company has published anything", _no_external_reach),
    (25, "No live traffic has routed through either router", _no_verified_outcome),
    # Anchors re-pointed 2026-08-22 with the gap texts they track. Both rows
    # measure adoption now, not the presence of a primitive — see
    # `_asymmetric_identity_is_not_adopted`.
    (7, "The live bridge transport is still HMAC over a shared secret",
     _asymmetric_identity_is_not_adopted),
    (26, "NOT ADOPTED: no bridge, gate or organ calls `mutual_tls`",
     _asymmetric_identity_is_not_adopted),
    (30, "The Gate does not emit witness contract v2", _witness_v2_is_not_emitted),
    (25, "RoutingDecision is not a typed institutional contract",
     _routing_decision_is_untyped),
    (37, "No marketplace. Bridge F has no implementation", _bridge_f_is_unimplemented),
    (39, "No account, ledger export, or reconciliation against a real balance",
     _no_external_reach),
    (55, "No restricted fund, no real obligation, no reconciliation", _no_external_reach),
    (54, "Depends on payments (#38), marketplaces (#37) and reputation (#41)",
     _commerce_dependencies_unbuilt),
    (12, "No capability-genome contract schema types the genome", _no_genome_contract),
    (13, "The governed module loader of FBO §4.4 does not exist", _no_module_loader),
    (24, "In-memory only", _transport_is_in_memory_only),
)

#: The #48 egregore check was retired the same way #26 was: it reported the gap
#: STALE, the register was corrected in the same change, and a check whose
#: subject no longer exists would report ANCHOR_LOST forever. The connection it
#: verified is guarded by `tests/integration/test_egregore_reaches_the_gate.py`,
#: which asserts both the import and the closure registration directly.
#:
#: Deliberately NOT checked, having just shipped a false STALE on #54:
#:
#: #16 says no test node asserts the behaviour of `scripts/ci/*.py`. A test does
#: reference that path — `test_developmental_inertness` — but referencing a
#: script is not asserting its behaviour, and the two are easy to confuse from
#: the outside.
#:
#: #51 says candidate generation is registered in no closure registry. A module
#: named `evolution` is registered; whether that is the same thing as
#: `evolution/repair/candidate.py` is a judgement, not an observation.
#:
#: Both claims might be stale. Guessing would risk the failure mode with the
#: worse polarity — telling the founder something closed that is open — so they
#: stay in the honest UNCHECKED count until someone settles what they mean.


def audit() -> tuple[GapRow, ...]:
    """Every gap in the register, with a verdict where one can be earned."""
    rows: list[GapRow] = []
    checked: set[tuple[int, str]] = set()

    for technology_id, anchor, check in CHECKS:
        binding = BINDINGS.get(technology_id)
        gap = next((g for g in (binding.gaps if binding else ()) if anchor in g), None)
        if gap is None:
            rows.append(GapRow(
                technology_id=technology_id,
                technology=binding.name if binding else "unknown",
                gap=f"(anchor no longer matches any gap: {anchor!r})",
                verdict=Verdict.ANCHOR_LOST,
                evidence="the gap text changed; this check stopped guarding it"))
            continue
        checked.add((technology_id, gap))
        still_open, evidence = check()
        rows.append(GapRow(
            technology_id=technology_id, technology=binding.name, gap=gap,
            verdict=Verdict.VERIFIED_OPEN if still_open else Verdict.STALE,
            evidence=evidence))

    for technology_id, binding in sorted(BINDINGS.items()):
        for gap in binding.gaps:
            if (technology_id, gap) in checked:
                continue
            rows.append(GapRow(
                technology_id=technology_id, technology=binding.name, gap=gap,
                verdict=Verdict.UNCHECKED,
                evidence="no registered check; prose a static reading cannot settle"))

    return tuple(rows)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI entry
    rows = audit()
    stale = [r for r in rows if r.verdict is Verdict.STALE]
    lost = [r for r in rows if r.verdict is Verdict.ANCHOR_LOST]
    verified = [r for r in rows if r.verdict is Verdict.VERIFIED_OPEN]
    unchecked = [r for r in rows if r.verdict is Verdict.UNCHECKED]

    print("=" * 74)
    print("GAP REGISTER AUDIT — does the institution's own list still hold?")
    print("=" * 74)
    print(f"  gaps registered   {len(rows)}")
    print(f"  machine-checked   {len(rows) - len(unchecked)}")
    print(f"  verified open     {len(verified)}")
    print(f"  STALE             {len(stale)}")
    print(f"  ANCHOR LOST       {len(lost)}")
    print(f"  unchecked prose   {len(unchecked)}")

    for label, group in (("STALE — closed, still listed", stale),
                         ("ANCHOR LOST — a check stopped guarding", lost)):
        if not group:
            continue
        print()
        print("-" * 74)
        print(label)
        print("-" * 74)
        for row in group:
            print(f"  #{row.technology_id} {row.technology}")
            print(f"      gap : {row.gap[:100]}")
            print(f"      now : {row.evidence}")

    print()
    print("This audit reports. It does not edit the register: a system that")
    print("rewrote its own record of what is wrong with it would be deleting")
    print("evidence. Correcting a stale gap is an authored change.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
