# Append-only witness — evidence (2026-10-14)

Mechanism card: `docs/mechanisms/MC-0001-append-only-witness.md`.

| File | What it shows | Reproduce |
|---|---|---|
| `rea/rea-sigstore-verify.json.gz` | Complete REA evidence for `@sigstore/verify@4.1.2` (ev_8c44d082…34af) | `npm pack @sigstore/verify@4.1.2`, extract, `npx -y rea-agents@6.1.0 analyze-javascript-application $PWD/package --json` |
| `rea/tlog-extract.json` | The `dist/tlog/*` subgraph (30 nodes, import/export edges) | filter of the bundle above |
| `rea/rea-progress.log` | REA progress stream for the run | — |
| `sigstore-oracle-result.json` | Sigstore's shipped verifier accepts 8385/8385 Kernel inclusion proofs, rejects 8385/8385 tampered leaves | see header of `scripts/sigstore_inclusion_oracle.cjs` |
| `comparison.json` | Detection / cost vs three baselines, seed 20261014 | `python scripts/experiment_append_only_witness.py` |

Tier: internal deterministic tests + one independent implementation (Sigstore, Node) as oracle for inclusion-proof compatibility. No live witness, no external acceptance.
