# linker — the Institutional Linker

Resolves typed edges between organs from their manifests (`organs/*.manifest.yaml`),
using the contract schemas in `contracts/` as the only source of contract truth.

- An edge exists only when a producer's contract name matches a consumer's AND a
  schema file for that contract exists. No schema file → the reference is reported
  as **untyped**, never silently accepted.
- Contracts consumed with no producer are **unproduced** (a disconnected edge — the
  integration gap the build order targets). Produced with no consumer:
  **unconsumed** (dormant capability, preserved and visible).
- Manifests' `unresolved` lists surface as open questions; `SPECIALIZED`
  capabilities surface as **overlapping authority** (organ-local implementations of
  something the kernel owns canonically — preserved, flagged, governed).
- The linker never invents an edge, an identity, or an authority. Fails closed.

Entry points: `linker.manifest.load_all()` → `linker.linker.InstitutionalLinker(...).link()`.
