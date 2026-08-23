"""Where the institution's decision records live, and which ones this ref can see.

Four contributors now keep decision records in four places, in four ID
namespaces, on four unmerged refs. Nobody can answer "what is waiting on the
founder?" from any single checkout, and the failure mode KIMI named in
`docs/collaboration/RECONCILIATION-2026-08-22-KIMI.md` — *artifacts that exist
only locally are lost* — is one step worse than described: an artifact can also
be durable, committed, and still invisible to every other contributor because it
sits on a branch nobody merged.

This module is a **register of registries**. It records where each decision
record lives and what it is canonical for. It deliberately does NOT copy their
contents: a fifth copy of the same open questions is the disease, not the cure.
`test_the_register_holds_pointers_not_content` enforces that by AST.

Three readings it produces that no single registry can:

**Unreachable registries.** A registry declared here whose path is absent from
this checkout is reported, never dropped. That is the honest state — "KIMI's
cross-repository catalogue exists and this ref cannot see it" is a fact worth
printing, and a silent omission would reproduce the exact failure the register
was built to expose.

**Contested concerns.** KIMI's ownership map states the rule plainly: *one
canonical owner per concern; two active owners is a defect.* Two registries
claiming the same concern is therefore a defect by the institution's own
standard, and it is computed here rather than asserted. There is one such
overlap today, it is pinned by a test, and resolving it is a founder decision —
not something this module may settle by declaring a winner.

**Namespace collisions.** Four ID schemes (`INTENT-00NN`, `INT-OM-0NN`,
`DEC-OM-00N`, `DELIB-KIMI-*`) address overlapping subject matter. Recorded as a
conflict rather than reconciled, per the protocol's rule that conflicting
sources are both preserved and neither is resolved by guess.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Owner(Enum):
    """Who authors and maintains a registry. Not who has authority over it."""

    CLAUDE = "CLAUDE"
    CHATGPT = "CHATGPT"
    KIMI = "KIMI"
    FOUNDER = "FOUNDER"


@dataclass(frozen=True)
class Registry:
    """One place decision or intent records live.

    `path` is relative to the kernel root for kernel registries, and is the
    reason reachability is checkable at all: a registry that cannot name a path
    cannot be verified to exist.
    """

    registry_id: str
    owner: Owner
    #: The institutional concern this registry claims to be canonical for.
    #: Two registries sharing one concern is a defect by KIMI's ownership rule.
    canonical_for: str
    repository: str
    path: str
    #: The ref the records live on. `main` means merged; anything else means
    #: this registry is invisible to contributors who have not fetched it.
    ref: str
    #: The ID scheme its records use.
    id_namespace: str
    #: A specific artifact whose presence proves this registry's RECORDS are
    #: here — not merely its folder. Directory existence is not enough and the
    #: distinction is not hypothetical: writing one CLAUDE record into KIMI's
    #: `docs/collaboration/` made that directory exist on this branch while
    #: containing none of KIMI's records, and a directory probe reported the
    #: catalogue reachable. Sharing the directory was correct; the probe was
    #: wrong. Defaults to `path` when the path is itself the artifact.
    marker: str = ""
    note: str = ""

    @property
    def probe(self) -> str:
        return self.marker or self.path

    @property
    def merged(self) -> bool:
        return self.ref == "main"

    def reachable(self, root: str = ROOT) -> bool:
        """Does this registry's path exist in the checkout being read?

        Only meaningful for kernel registries; a peer-repository registry is
        reported unreachable from here, which is accurate rather than a defect.
        """
        return os.path.exists(os.path.join(root, self.probe))


#: Every decision or intent registry known to exist across the organism, whether
#: or not this ref can see it. Adding a row is how a contributor becomes visible
#: to the others; the register is useless if it only lists what is convenient.
KNOWN_REGISTRIES: tuple[Registry, ...] = (
    Registry(
        registry_id="REG-INTENT-MD",
        owner=Owner.FOUNDER,
        canonical_for="founder intent, human-readable",
        repository="dababiyoda/uniimente-kernel",
        path="docs/intent",
        ref="main",
        id_namespace="INTENT-00NN",
        marker="docs/intent/INTENT-0001-uniimente-as-legal-principal.md",
        note="One Markdown file per intent. Merged, so every contributor sees it. "
             "KIMI extends this namespace (INTENT-0027, INTENT-0028).",
    ),
    Registry(
        registry_id="REG-INTENT-JSON",
        owner=Owner.CLAUDE,
        canonical_for="founder intent, machine-readable",
        repository="dababiyoda/uniimente-kernel",
        path="governance/intents.json",
        ref="claude/opus-maximus-audit-eay0ek",
        id_namespace="INT-OM-0NN",
        note="Machine-readable ledger the FOUNDER_INTENT_LEDGER asked for. "
             "Unmerged, and its namespace does not align with REG-INTENT-MD.",
    ),
    Registry(
        registry_id="REG-DELIB-KERNEL",
        owner=Owner.CLAUDE,
        canonical_for="open founder decisions",
        repository="dababiyoda/uniimente-kernel",
        path="docs/deliberations",
        ref="claude/opus-maximus-audit-eay0ek",
        id_namespace="DEC-OM-00N",
        marker="docs/deliberations/DEC-OM-001-canonical-selector.json",
        note="Full five-role, two-pass records for decisions raised on PR #71. "
             "Read executably by governance/decisions.py.",
    ),
    Registry(
        registry_id="REG-COLLAB-KIMI",
        owner=Owner.KIMI,
        canonical_for="open founder decisions",
        repository="dababiyoda/uniimente-kernel",
        path="docs/collaboration",
        ref="main",
        id_namespace="DELIB-KIMI-*",
        marker="docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml",
        note="Cross-repository catalogue spanning all three organs, plus the "
             "architecture ownership map. MERGED to main via PR #82 on "
             "2026-08-21; this row previously pinned the branch and went stale "
             "the moment it landed, which its own test caught.",
    ),
)

#: The one contested concern on record, and the registries contesting it.
#: Pinned so a NEW contest breaks a test rather than passing unnoticed.
#:
#: SETTLED IN POSTURE, NOT IN OWNERSHIP. The founder's ruling on issue #80
#: (2026-08-21T19:49Z) directs every engine not to optimize for preserving any
#: model's architecture or ownership. So this row is no longer an escalation
#: waiting on a winner — it records that two registries cover one concern at
#: different scopes, which is a fact to work with rather than a contest to win.
#: It stays measured because a THIRD claimant would still be a defect.
KNOWN_CONTESTED: tuple[str, ...] = ("open founder decisions",)


def contested_concerns(registries: tuple[Registry, ...] = KNOWN_REGISTRIES
                       ) -> dict[str, tuple[Registry, ...]]:
    """Concerns claimed by more than one registry.

    KIMI's ownership map states the standard this implements: one canonical
    owner per concern, two active owners is a defect. Computed from the rows
    rather than asserted, so it stays true as rows change.
    """
    by_concern: dict[str, list[Registry]] = {}
    for registry in registries:
        by_concern.setdefault(registry.canonical_for, []).append(registry)
    return {
        concern: tuple(rows)
        for concern, rows in sorted(by_concern.items())
        if len(rows) > 1
    }


def namespace_conflicts(registries: tuple[Registry, ...] = KNOWN_REGISTRIES
                        ) -> tuple[tuple[str, str], ...]:
    """Distinct ID schemes addressing one concern.

    Not a defect on its own — two namespaces can coexist. It becomes one when
    the same decision acquires two IDs, which is why the pairs are reported for
    a human to read rather than scored.
    """
    out: list[tuple[str, str]] = []
    for concern, rows in contested_concerns(registries).items():
        namespaces = sorted({r.id_namespace for r in rows})
        if len(namespaces) > 1:
            out.append((concern, " vs ".join(namespaces)))
    return tuple(out)


def unreachable(registries: tuple[Registry, ...] = KNOWN_REGISTRIES,
                root: str = ROOT) -> tuple[Registry, ...]:
    """Registries this checkout cannot read.

    The point of the whole module. A registry can be durable, committed and
    still invisible, and that is worth printing every time.
    """
    return tuple(r for r in registries if not r.reachable(root))


def unmerged(registries: tuple[Registry, ...] = KNOWN_REGISTRIES
             ) -> tuple[Registry, ...]:
    """Registries no other contributor sees without fetching a branch."""
    return tuple(r for r in registries if not r.merged)


def render(root: str = ROOT) -> str:
    lines = [f"decision registries known : {len(KNOWN_REGISTRIES)}"]
    for registry in KNOWN_REGISTRIES:
        mark = "  " if registry.reachable(root) else "!!"
        state = "merged" if registry.merged else f"on {registry.ref}"
        lines.append(f"{mark} {registry.registry_id:<18} {registry.owner.value:<8} "
                     f"{registry.path:<24} {state}")
        lines.append(f"     canonical for: {registry.canonical_for}  "
                     f"[{registry.id_namespace}]")

    missing = unreachable(KNOWN_REGISTRIES, root)
    lines.append("")
    if missing:
        lines.append(f"{len(missing)} registry(ies) this ref cannot read:")
        for registry in missing:
            lines.append(f"  {registry.registry_id} — {registry.repository} "
                         f"{registry.path} on {registry.ref}")
        lines.append("  Durable, committed, and invisible from here. Fetch the ref "
                     "or merge it; do not re-derive its contents.")
    else:
        lines.append("every known registry is readable from this ref")

    contested = contested_concerns()
    if contested:
        lines.append("")
        lines.append(f"{len(contested)} contested concern(s) — one canonical owner "
                     "per concern is the standard:")
        for concern, rows in contested.items():
            owners = ", ".join(f"{r.registry_id}({r.owner.value})" for r in rows)
            lines.append(f"  {concern}: {owners}")
        for concern, namespaces in namespace_conflicts():
            lines.append(f"    ID schemes in conflict: {namespaces}")
        lines.append("  Resolving an ownership contest is a founder decision.")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(render())
