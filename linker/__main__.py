"""`python -m linker` — print the actual link graph, unresolved rows and all.

Doctrine (LINKER): this command reports. It resolves no authority, registers
no identity and activates no organ. Three facts are deliberately kept apart
and never used as evidence for one another:

  1. linker-visible manifest      — the organ published `organs/*.manifest.yaml`
  2. canonical identity registration — the organ appears in `identity/organ-registry.yaml`
  3. runtime activation           — neither of the above; requires a grant

An organ can have any subset of the three. Printing a manifest does not
register an identity, and registering an identity does not activate anything.
Every unresolved row the linker produces is printed in full: this report is
not allowed to get shorter by hiding what did not resolve.

The manifest/identity reconciliation is delegated to
`discovery.service.CapabilityDiscoveryService.identity_reconciliation`, which
already matches a manifest's `organ_id` against the registry's SPIFFE
`identity` field. Recomputing it here with a second, naive comparison would
count `daleobanks` and `spiffe://.../organ/daleobanks` as two organs and
report numbers that disagree with the rest of the kernel.
"""
from __future__ import annotations

import sys

from discovery.service import CapabilityDiscoveryService
from linker.linker import InstitutionalLinker, known_contracts
from linker.manifest import ManifestError, load_all

RULE = "=" * 78
THIN = "-" * 78


def _rows(title: str, rows: list, render) -> None:
    print(f"\n{THIN}\n{title} — {len(rows)}\n{THIN}")
    if not rows:
        print("  (none)")
        return
    for row in rows:
        print(f"  {render(row)}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    print(RULE)
    print("UNIIMENTE INSTITUTIONAL LINKER")
    print(RULE)

    try:
        manifests = load_all()
    except ManifestError as exc:
        print(f"FAILED CLOSED: {exc}")
        return 2

    contracts = known_contracts()
    report = InstitutionalLinker(manifests).link()
    rec = CapabilityDiscoveryService().identity_reconciliation()

    print(f"\nmanifests loaded      : {rec['manifests_published']}")
    print(f"contracts typed       : {len(contracts)}  (schema files in contracts/)")
    print(f"identities registered : {rec['identity_registered']}"
          "  (identity/organ-registry.yaml)")

    print(f"\n{THIN}\nORGANS — manifest vs identity registration vs activation\n{THIN}")
    print(f"  {'ORGAN':<26} {'MANIFEST':<10} {'REGISTERED':<12} MANIFEST STATUS")
    both = set(rec["both"])
    for m in sorted(manifests, key=lambda x: x.name):
        print(f"  {m.name:<26} {'yes':<10} "
              f"{('yes' if m.name in both else 'no'):<12} {m.status}")
    for entry in rec["registered_without_manifest"]:
        print(f"  {entry['name']:<26} {'no':<10} {'yes':<12} —")
    print("\n  Neither column is activation. Activation requires a capability grant,")
    print("  which this command does not read, issue, or imply.")

    print(f"\n  in both registers                        : {len(both)}  {sorted(both)}")
    print("  manifested without identity registration : "
          f"{len(rec['manifested_without_identity_registration'])}  "
          f"{[e['name'] for e in rec['manifested_without_identity_registration']]}")
    print("  registered without manifest              : "
          f"{len(rec['registered_without_manifest'])}  "
          f"{[e['name'] for e in rec['registered_without_manifest']]}")

    _rows("RESOLVED TYPED EDGES", report.edges,
          lambda e: f"{e.producer} --[{e.contract}]--> {e.consumer}")
    _rows("UNTYPED — contract named by an organ with no schema file", report.untyped,
          lambda r: f"{r[0]:<24} {r[1]}")
    _rows("UNPRODUCED — consumed by someone, produced by no one", report.unproduced,
          lambda r: f"{r[0]:<24} {r[1]}")
    _rows("UNCONSUMED — produced by someone, consumed by no one", report.unconsumed,
          lambda r: f"{r[0]:<24} {r[1]}")
    _rows("OVERLAPPING AUTHORITY — organ-local impl of a kernel-canonical capability",
          report.overlapping_authority, lambda r: f"{r[0]:<24} {r[1]}")
    _rows("UNRESOLVED — declared open by the organ itself, never invented here",
          report.unresolved, lambda r: f"{r[0]:<24} {r[1]}")

    print(f"\n{THIN}\nVERDICT\n{THIN}")
    if report.fully_connected:
        print("  fully_connected = True   (no unproduced contract, no untyped contract)")
    else:
        print(f"  fully_connected = False  "
              f"({len(report.unproduced)} unproduced, {len(report.untyped)} untyped)")
    print("\nThis report describes a graph. It grants nothing and activates nothing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
