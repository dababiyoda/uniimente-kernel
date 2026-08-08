# P3 inspection and Route B resolution

## Current disposition

`P3_COMPLETE_CANONICAL_CI_GREEN`

The consequence-inert local and Canonical CI counterfactuals prove the narrow
routing claim at the two manifest-pinned organ revisions. They do not prove
deployment, external verifier acceptance, settlement, a commercial result, or a
developmental closure. `VERIFIED_DEVELOPMENTAL_CLOSURES` remains `0`.

## Initial measured inspection

Before construction, repository inspection found two real absences:

1. Organ manifests named contracts while `EventSpine` routed event-type
   prefixes. No canonical contract-to-event binding existed.
2. The kernel contained no legitimate consumer for the selected contract.
   The real implementation lived in WealthMachineIntelligence.

The EventSpine also had no non-test subscriber. These observations made the
initial disposition `P3_PARTIAL`; they did not falsify the geometry.

## Route adjudication

Route A, a kernel-resident consumer, was rejected. The only in-kernel use of
`LinkReport` was a health check. Disabling the edge changed the check's
verdict, not a distinct institutional function.

Route B was selected because both sides are legitimate organ functions:

| Role | Revision | Symbol | Function |
| --- | --- | --- | --- |
| Producer | DALEOBANKS `829c5f2810776bef65d6ea108800a3516c9f4c2b` | `IdeaRefinery._opportunity_from` plus `packet_to_wire` | Produces a canonical OpportunityPacket wire object |
| Consumer | WealthMachineIntelligence `6549984a22a171f68b268b775f19192aee599609` | `OpportunityIntakeService.evaluate_packet` | Produces a schema-valid assessment with human approval required |

A decisive adversarial finding changed the design: DALEOBANKS
`WealthMachineClient` defaults to a local mock when no URL is configured. It
can create a valid-looking assessment without invoking WMI. The client is
therefore excluded from the decisive path and used only as a hostile bypass
control.

## Selected seam

`runtime/contract_events.py` adds one generic routing seam:

- it consumes the existing `LinkReport`; it does not implement a second linker;
- it emits `contract.delivery` and `contract.delivery_completed` on the
  existing `EventSpine`; it does not create a second bus;
- it requires one exact producer-contract-consumer edge;
- it requires the real stable consumer method reference;
- it refuses any consequence classification other than `INERT`;
- it records both source revisions, a checkout-independent schema locator, and
  the schema SHA-256;
- it records the result as a causal child of the request;
- it grants no capability and cannot flush an external outbox.

Contract names remain data. No event name is derived from contract spelling.

## Four-state counterfactual

The probe ran the two exact git checkouts with network denied:

| State | Controlled change | Required observation | Local result |
| --- | --- | --- | --- |
| A healthy | Exact edge present | Real WMI assessment exists | PASS |
| B disabled | Remove only the target edge | Binding refused; no assessment | PASS |
| C bypass | Offer real DALEOBANKS local mock as WMI | Lookalike exists; binding refused | PASS |
| D restored | Restore exact edge | Assessment and causal result receipt return | PASS |

Additional assertions passed:

- both checkout HEADs equal the manifest pins;
- packet ids match across the route;
- `requires_human_approval` is true;
- the evidence chain verifies;
- external effects equal zero;
- closure-count delta equals zero;
- a non-inert binding classification is refused;
- schema provenance is
  `contracts/wire-opportunity-packet.schema.json` plus
  SHA-256 `487a28729bb856f239cd2d90c12b43f8088db4b625123750f8887e56c8ba7352`.

## Evidence boundary and dissent

This is `SANDBOX_EXECUTION_CONSEQUENCE_INERT`. It establishes that, at the
pinned revisions, the existing linker can control delivery of a real packet to a
real consumer through the existing EventSpine. It does not establish that the
same code is deployed as separate services or accepted by an external verifier.

The Evidence and Welfare Guardian's dissent is binding: P3 must not be described
as a closure, deployment, commercial result, or proof-to-settlement outcome.

## Canonical CI evidence

Commit `af827176763bd86ec2851fef272c369678c34da1` passed Canonical CI run
`31282596092` (`run_number: 134`) on 2026-08-08. The remote evidence was:

- complete kernel suite: 512 passed, 15 skipped;
- institutional verifier V2 unit evidence: 491 passed, 14 skipped;
- contract schema references: pass;
- authority singleton: pass;
- sealed developmental boundary and TARGET_FORM_001: pass;
- pinned DALEOBANKS and WMI checkouts: pass;
- named Route B counterfactual: 1 passed.

The skips are preserved as skips, not counted as passes. The dedicated Route B
step did run after both exact checkouts and passed.

## Next gate

P4 may inspect and freeze the held-out evaluator and candidate-builder boundary.
No candidate generation or closure claim is authorized by this P3 result.
