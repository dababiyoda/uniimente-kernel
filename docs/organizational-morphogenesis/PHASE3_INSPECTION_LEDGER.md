# Phase-3 Organization-Compiler Inspection Ledger

Status: **FROZEN BEFORE PHASE-3 CODE**  
Decision class: **CONSTITUTIONAL**  
Inspection date: **2026-09-04 UTC**  
Posture: **EXPERIMENT / PROPOSAL ONLY**  
Stack base: draft PR #90 at `8c01c800978ca1dde8352359607546b3638e2cf6`

This addendum continues the Phase-0 ledger without rewriting its frozen record.
It records the current repositories, open lines, security primitives, and
counterevidence inspected before the organization compiler is implemented.

## Repository truth

| Repository | Default branch inspected | Material additional line | Disposition |
|---|---|---|---|
| `dababiyoda/uniimente-kernel` | `bcbb1ab4a0c42cda4a97aec42a11125753962762` | Draft PRs #35, #56, #70, #87, #88, #90 and new unrelated #91 | INSPECTED; CANONICAL constitutional owner; experimental lines preserved |
| `dababiyoda/DALEOBANKS` | `ed5e95d7f48e006d180b972efe138179325c31d2` | Open PRs through #75, including bridge/transport and current scheduler surfaces | INSPECTED; CANONICAL organ; no Phase-3 write |
| `dababiyoda/WealthMachineIntelligence` | `ec84b6a2eec4efbc07bed7f167da81f5e25d890c` | Open PRs through #32, including fail-closed intake and transport parity | INSPECTED; CANONICAL organ; no Phase-3 write |
| `dababiyoda/PumpStation` | `df6a732f44412c626098ee9591b9d19f420d02dd` | Open PRs #13, #15 and #16 | INSPECTED; experimental organizational evidence; no Phase-3 write |
| `dababiyoda/RAILSCOUT` | `c255ff323aa889ec198962a7bac47d21b6074422` | Draft PRs #2-#5 | INSPECTED; runtime UNAVAILABLE; no Phase-3 write |

Draft PR #90 remains open, draft, mergeable, unmerged, and green at the
inspected head. It adds contracts and a replay-derived task reducer beneath the
competing PR #70/#87 runtime lines. Those runtime candidates remain UNRESOLVED;
Phase 3 does not select either.

## Canonical and experimental surfaces

| Surface | Finding | Classification |
|---|---|---|
| `contracts/mission-contract.schema.json` | Owns bounded mission, ProblemGeometry, resources, authority refs and organization policy. | CANONICAL |
| `contracts/orchestration-genome.schema.json` | Owns non-authorizing organizational design; v1.0 has no integrated zero-trust profile. | CANONICAL; compatible extension candidate |
| `events/EventSpine` and `DurableWorkflow` | Existing append-only transition truth, replay and strongest conventional baseline. | CANONICAL; protected competitor |
| `events/task_fabric.py` on PR #90 | Replay-derived Phase-2 task state; no scheduler, executor or topology selector. | EXPERIMENTAL; canonical seam candidate |
| `identity/mesh.py` and `identity/pki/` on the stacked line | SPIFFE-named, short-lived asymmetric workload identities and mutual TLS exist for an in-process bridge. Identity explicitly is not authority. | EXPERIMENTAL; key custody/network/revocation gaps UNRESOLVED |
| `authority/authority-matrix.yaml` | Child grants must be strict subsets; expiry, revocation and commit-time revalidation are canonical invariants. | CANONICAL |
| `provenance/proof.py` | Merkle inclusion proofs and checkpoints already exist. | CANONICAL; no external witness or anti-equivocation guarantee |
| `adapters/bridge_transport.py` | Nonce, skew and idempotency protections exist with no signature downgrade. | EXPERIMENTAL on stacked line; in-memory nonce scope is limited |
| `omnimorph/engine.py` | Composes and retires bounded organs; cannot self-ratify, execute or mint authority. | CANONICAL composition owner |
| `morphogenesis/engine.py` | Deterministic target/setpoint evaluation, distinct from organization compilation. | CANONICAL; DUPLICATION PROHIBITED |
| PR #35 trust rail | Generic proof/settlement extensions are explicitly inactive until reuse is earned. | EXPERIMENTAL; whole subsystem not imported |
| PR #56 authority line | Rich proof-carrying authorization/revocation semantics. | EXPERIMENTAL competing implementation; not silently canonicalized |

## External primary sources inspected

| Source | Primitive retained | Counterevidence retained |
|---|---|---|
| NIST SP 800-207 | Verify subject/resource each session/request, least privilege, dynamic policy, no network-location trust. | Zero trust reduces uncertainty; it does not eliminate threats or make a component truthful. |
| RFC 8785 | Deterministic I-JSON canonicalization before hashing/signing. | A digest binds bytes/content, not correctness or authority. |
| RFC 9334 RATS | Separate Attester, Verifier and Relying Party; freshness through nonce/time/epoch. | Attestation evidence and appraisal results do not themselves authorize action; verifier loss must be explicit. |
| RFC 9943 SCITT | Signed statement, registration policy, append-only verifiable structure, receipt and independent audit. | Transparency holds issuers accountable but does not prevent dishonest or compromised issuers; ordering and key management require care. |
| SPIFFE specifications | Structured workload identity and cryptographically verifiable SVID. | A SPIFFE name has no inherent legal identity or action authority. |
| in-toto design | Expected step layout, functionary separation, signed link evidence and threshold verification. | Supply-chain metadata cannot prove mission outcome quality by itself. |

## Founder sources re-opened

- `DOCTRINE.txt`: the durable advantage is proof, trust, eligibility, routing,
  settlement, and regenerative participant improvement—not agent count.
- Existing founder architecture sources: one Kernel, one consequence path,
  typed boundaries, human sovereignty, and deliberately boring execution.
- New directive: preserve a Jarvis-level capability horizon while using
  blockchain and zero-trust mechanisms to constrain agents.

The Jarvis/infinite-improvement language is classified as **ASPIRATION**. The
zero-trust organizational profile is an **ACTIVE REQUIREMENT**. Neither is an
authority grant or evidence of safe autonomous self-improvement.

## Ownership disposition

| Semantic | Owner | Phase-3 permission | Prohibition |
|---|---|---|---|
| Mission authority | existing `governance/` and legal-principal mechanisms | Read and copy refs | Mint, widen or reinterpret |
| Organization design | `omnimorph/organization_compiler.py` | Deterministically emit hypotheses and score traces | Execute, spawn, activate or self-select as authority |
| Shared genome/decision semantics | `contracts/` | Compatible v1.1 genome profile and one TopologyDecision schema | Duplicate identity, grant, receipt or runtime contracts |
| Durable execution | existing `events/` plus unresolved runtime composition | Reference canonical seams | Add a second Event Spine, ledger or workflow engine |
| Identity/authentication | existing `identity/` | Require/refuse based on policy refs | Treat identity as authority or add an issuer |
| Authorization | existing `authority/`, capabilities and governance | Require strict attenuation and commit-time recheck | Let topology or coordinator grant power |
| Evidence/integrity | existing `provenance/` and Event Spine | Content-bind outputs and require receipts/checkpoints | Claim truth, public-chain finality or anti-equivocation not proved |
| Consequence | existing Consequence Gate/legal principal | Reference sole path | Execute or bypass |

## Negative evidence and unresolved items

- **CANONICAL:** static `DurableWorkflow` stays default, fallback, protected
  baseline, and tie winner.
- **EXPERIMENTAL:** organization scoring is a deterministic hypothesis, not
  organizational knowledge.
- **UNRESOLVED:** PR #70 versus PR #87 runtime composition ownership.
- **UNAVAILABLE:** independently verified production key custody, distributed
  revocation, hardware-backed workload attestation, external transparency
  witness, and cross-organ VDM closure.
- **DUPLICATE CANDIDATE:** a new blockchain ledger, token, DAO, consensus
  authority, identity issuer, policy engine, Event Spine, workflow engine,
  Consequence Gate, or `orchestration/` package.
- **SUPERSEDED/PROHIBITED:** self-preservation, self-ratification, authority
  inheritance, live recursive self-rewrite, and claims that security prevents
  all rogue or harmful behavior.

## Phase-3 entry gate

The ledger permits only a deterministic, consequence-inert compiler and its
contracts/tests. It must preserve static and do-not-instantiate, defer
decentralized/developmental candidates absent executed evidence, copy the
mission envelope and authority refs exactly, expose score components and
security gaps, and emit no runtime event. `Verified Durable Mission Closures`
remains **0**.
