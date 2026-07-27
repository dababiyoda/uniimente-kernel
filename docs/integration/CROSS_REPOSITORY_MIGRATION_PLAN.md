# Cross-Repository Migration Plan — from branch pin to version

## The pin, exactly as it exists

`DALEOBANKS@phase5/consequence-gate-adoption/requirements.txt`:

```
# Pinned to the Phase 5 stack tip until kernel PRs #11-#22 merge; switch to @main then.
uniimente-kernel @ git+https://github.com/dababiyoda/uniimente-kernel.git@phase5/consequence-gate#subdirectory=sdk-python
```

The comment names the stall in its own words. The pin waits on PRs that never merged; the PRs cannot merge without breaking the pin.

## DALEOBANKS

| | Current | Target |
|---|---|---|
| Dependency | `git+...@phase5/consequence-gate#subdirectory=sdk-python` | `uniimente-kernel-sdk==0.1.0` |
| Gate | `services/gate.py` (branch-local) | thin adapter over SDK client |
| Grants | `services/capability.py` (286 lines, canonical locally) | SDK grants canonical; local module becomes a **verifier of Kernel grants**, retained |
| Ledger | `services/ledger.py` hash chain | **local operational journal**, explicitly non-canonical |
| KillSwitch | `services/ledger.py` | **unchanged, stays local** — network-dependent kill fails open |
| ConstitutionGuard | `services/constitution.py` | **unchanged, stays local** |
| `evidence_policy.py` | local | **candidate for promotion into the Kernel** — the anti-cathedral rule has no Kernel equivalent |
| X credentials | 5 env vars in-process | out of the reasoning process (Decision B, later pass) |
| Tests | `tests/test_gate_publishing.py` on `phase5` | preserved, re-cut against the versioned SDK |

**Re-cut, do not merge.** `phase5/consequence-gate-adoption` is 9 files against a branch-tip pin. Re-cutting it against `==0.1.0` is cheaper than rebasing it and keeps the pin from reappearing.

## WealthMachineIntelligence

Two branches reference the kernel: `agent/foundry-underwriting-envelope` (5 files), `phase3/protocol-swap` (2 files). Neither inspected in detail. Same target: `uniimente-kernel-sdk==0.1.0`, re-cut rather than rebased.

`bridge_security.py` exists in **three** copies — DALEOBANKS, WMI, and the kernel's `adapters/bridge_transport.py`. One canonical owner (kernel), two thin consumers. Not on the critical path for the first transaction; scheduled after it.

## PumpStation

No kernel imports, no branch pins, no SDK dependency. `governance/admission.js` is JavaScript and shares no contract with the Python SDK. **Unaffected.** No action this pass.

## build-your-own-x

4 files, no code, no dependency, on no runtime path. The selected architecture does not place it on one. **Unaffected.**

## Removal date for branch pins

No organ may remain on an unmerged development branch past the `v0.1.0` tag. The pin comment's own instruction — *"switch to @main then"* — is superseded: switch to a **version**, not to `@main`, because `@main` is another moving target.
