# UNIIMENTE Permanent Operating Order

Read and obey:

- @docs/UNIIMENTE_FINAL_BUILD_ORDER.md
- @docs/CANONICAL_EXECUTION_ORDER.md

## Permanent rules

- Preserve every useful implementation, test, document, branch and proof record.
- Never destroy institutional memory to simplify architecture.
- Establish one canonical authority path while retaining multiple governed
  capability implementations.
- Connect disconnected systems through typed contracts, adapters, events,
  registries and capability composition.
- Build missing technology when no existing component satisfies the requirement.
- Prefer mature commodity infrastructure and build UNIIMENTE's proprietary control,
  proof, memory, composition and evolution layers above it.
- Do not claim completion without executable evidence.
- Continue until all unblocked work is implemented, tested, attacked, verified,
  documented, committed and handed off.
- Alfonso retains ultimate lawful authority.
- Intelligence never creates authority.
- No component may authorize its own promotion or expand its own sovereignty.

## Working facts

- Test suite: `python -m pytest` from the repo root (deps: `requirements-dev.txt`).
- Canonical contracts live in `contracts/*.schema.json` (JSON Schema 2020-12).
  The DALEOBANKS↔WealthMachine wire protocol v1.1 is a registered peripheral
  contract (`contracts/wire-*.schema.json`), preserved and adapted — never deleted.
- Organ manifests live in `organs/*.manifest.yaml`; the linker (`linker/`) resolves
  cross-organ edges and reports unresolved fields instead of inventing them.
- Adapters (`adapters/`) declare field mappings, information lost/added and
  assumptions explicitly. No silent translation. No fabricated fields. No authority
  inflation.
