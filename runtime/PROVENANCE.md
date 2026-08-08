# Track-A runtime — lineage and authority

This branch carries the UNIIMENTE Track-A runtime implementation. It is based on
canonical `main` and is **separate from the planning lineage by design**.

## Why this branch exists

The super-planning round produced its decision record on branch
`claude/super-planning-prompt-h8l0oj` (draft PR #68), whose declared scope was
**planning-only**: no runtime change, and deleting the planning trees would leave
the kernel byte-identical to `main`.

Commit `d8c921552660675485f347637f8be08d6880f7cc` on that branch landed
`runtime/contract.py` and its guard tests under the founder's P0/P1
authorization. That work was authorized — but it crossed the branch's own stated
boundary. The PR description still claimed planning-only while the head contained
runtime implementation.

**That is scope drift, and the institution detected it in itself.** It is
preserved, not erased:

- No Git history was rewritten.
- `d8c9215` remains in PR #68's history as evidence that bounded implementation
  briefly entered the planning branch and was separated.
- PR #68 was corrected by an ordinary forward commit removing the runtime files,
  so its final diff again satisfies planning-only scope.
- The runtime work was transferred here byte-identically, with its frozen
  semantics unchanged.

## Lineage

| | |
|---|---|
| Base | `main` @ `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1` |
| Transferred from | `d8c921552660675485f347637f8be08d6880f7cc` |
| Planning authority | Draft PR #68 |
| Continuation ledger | Issue #69 |
| Founder authorization | `authorization.p0_p1` (planning graph node) |
| Frozen contract hash | `408b197e73240c2c16cc805d495a1a0f5ed4ec9f6994299b49d1e14a509ea30c` |

`runtime/contract.py` was copied without modification. Its sha256 is
`e052a3c85f3233ada8c804abadbfe54d46592bf5c61bad79fcd6b02e2b0c55ec` on both
branches, and `CONTRACT_SHA256` still matches its own recomputed digest — the
transfer did not alter what was frozen.

## The two lineages

```
PR #68  —  planning truth, decision genome, founder intent, evidence architecture
   |
   |  authorizes
   v
Track-A PR  —  runtime spine, evaluator, candidate development, closure experiment
```

One canonical decision record → separate bounded implementation → evidence →
promotion only after proof. This is the same doctrine UNIIMENTE applies to its
organs, applied to its own development.

## Standing constraints on this branch

- PR #66 is immutable Track B research at `a6f14d3`. Do not touch it.
- No merge, no deploy, no publication, no production credentials, no money
  movement, no external effect of any kind.
- Everything here is `CONSEQUENCE_CLASS = INERT`.
- `VERIFIED_DEVELOPMENTAL_CLOSURES` may move `0 → 1` only when **all twelve**
  frozen conditions in `runtime/contract.py` hold independently. No rounding, no
  "essentially passed", no fixture standing in for runtime consumption.
- Reimplementing the linker, closure controller, registries or adapters is a
  contract violation. The measured defect was disconnection, not absence.

## P3 Route B evidence, 2026-08-08

### Supplied source classification

| Source | SHA-256 | Classification | Executable authority |
|---|---|---|---|
| `01-DOCTRINE.txt` | `be509f5718de7471809aaf287e9763412316c7003dc29157d5c44b94e94cde4f` | canonical founder requirement | active requirement |
| `02-Proof-to-Settlement-Egregore.pdf` | `c5a4dba7528968f6e557a1e92602c6a66d2002d8a5301f12be18e2a152f7ab26` | model-output design synthesis | advisory; needs external evidence |
| `03-UNIIMENTE-Reality-Compiler-Blueprint.pdf` | `f53a255529ee97859980b51d39672c5450505439b0d3dc141ef1d555417521f8` | model-output design synthesis | advisory; needs external evidence |
| `04-Be-accumulative-and-repeat-what-you-just-did___htt....pdf` | `d6b2eafc0b537781fc0890a6e3fafe9047f49f3f2b31c94eb6f59d6958df39e6` | historical exploratory expression | sovereign intent and self-preservation prohibited |
| `05-Https___youtu.be_t6EFV2gSSmg_is-9qFWlmdavuhdaGCf__....pdf` | `10e4a7126b3b73c06e9fb25ba67d86dda20098e23177da5b2a8843c5e6c44ef3` | historical exploratory expression | autonomous treasury and unrestricted self-modification prohibited |

The machine-readable dispositions are in
`runtime/P3_SOURCE_INTENT_LEDGER.json`. The material architecture choice has
exactly two strengthening passes in
`runtime/P3_ROUTE_B_DELIBERATION.json` and a human-readable record in
`runtime/ADR-P3-ROUTE-B.md`.

### Pinned organ evidence

| Role | Repository | Revision | Decisive symbol |
|---|---|---|---|
| producer | `dababiyoda/DALEOBANKS` | `829c5f2810776bef65d6ea108800a3516c9f4c2b` | `IdeaRefinery._opportunity_from` and `packet_to_wire` |
| consumer | `dababiyoda/WealthMachineIntelligence` | `6549984a22a171f68b268b775f19192aee599609` | `OpportunityIntakeService.evaluate_packet` |

Both local checkout HEADs were compared to the manifest pins before execution.
The linked schema was
`contracts/wire-opportunity-packet.schema.json`, SHA-256
`487a28729bb856f239cd2d90c12b43f8088db4b625123750f8887e56c8ba7352`.

### Reproduction

```bash
PYTHONDONTWRITEBYTECODE=1 \
python3 runtime/probes/route_b_counterfactual.py \
  --kernel . \
  --daleobanks /path/to/DALEOBANKS@829c5f2 \
  --wealthmachine /path/to/WealthMachineIntelligence@6549984

PYTHONDONTWRITEBYTECODE=1 \
TRACK_A_DALEOBANKS_DIR=/path/to/DALEOBANKS@829c5f2 \
TRACK_A_WMI_DIR=/path/to/WealthMachineIntelligence@6549984 \
python3 -m pytest -q tests/integration/test_track_a_route_b.py
```

Observed locally: `1 passed`. State A delivered the real packet to the real WMI
consumer. State B removed the target edge and refused the binding. State C
created a real local-mock lookalike and rejected it as the WMI implementation.
State D restored the edge and restored a causally linked result. Network was
denied, non-inert binding classification was refused, external effects were
`0`, and closure-count delta was `0`.

### Claim boundary

Evidence tier: `sandbox_execution`.

The result proves only the P3 internal routing geometry at the pinned revisions.
It is not a deployment, independently verified outcome, settlement, commercial
result, or developmental closure. Canonical CI on the complete repository is
the remaining P3 gate.
