# UNIIMENTE: Invention from Repository Truth

**Date:** 2026-07-27 · **Scope:** the five canonical repositories · **Status:** analysis and proposal. Nothing in this document is applied. Constitutional items are marked `NEEDS_FOUNDER_DECISION`.

---

## The finding that reorganizes this document

I inspected all five repositories before writing. One measurement changes every subsequent answer:

```
$ grep -ril "uniimente" DALEOBANKS/            → 0 files
$ grep -ril "uniimente" WealthMachineIntelligence/  → 0 files
```

**No organ imports, calls, validates against, or references the Kernel.** Not once, in 21,399 lines across the two organs.

The Kernel holds 27,535 lines of constitutional machinery — Consequence Gate, capability grants, evidence ledger, authority matrix, autonomy ladder. `organs/*.manifest.yaml` describes four organs. The linker resolves four edges between them.

None of it is on any execution path. The manifests describe the organs; the organs have never heard of the manifests.

And the one typed cross-repository link that *does* exist — `contracts/wire-*.schema.json`, the DALEOBANKS↔WealthMachine protocol — routes **around** the Kernel. The founder's intended flow is `DALEOBANKS → WMI → Kernel → PumpStation`. The implemented flow is `DALEOBANKS ↔ WMI`, with the Kernel absent.

So the surface question — "what is the strongest architecture?" — is the wrong question to answer first. Every architecture scores identically while authority is unenforced. A morphogenetic runtime built on a control plane nothing calls is a simulation of governance.

**The control layer is enforcement, not design.** The rest of this document proceeds from there.

---

# Part I: Founder-Intent Reconstruction

**Known** (traceable to the founder's own words, now in `docs/intent/ledger.json`):

A persistent, nonbiological, software-engineered institution whose bounded computational mechanisms coordinate as one adaptive, developing system. Not alive, not conscious, not sovereign. The smart-vehicle analogy is exact: many bounded controllers producing apparent agency without life. It should sense, remember, specialize, coordinate, regulate, hold goals, adapt, correct errors, allocate resources, reproduce working patterns, repair, evolve under control, and interact with humans and institutions — while responsibility stays attributable and authority stays bounded (`INTENT-0003`, `INTENT-0004`).

**Inferred** (consistent with the corpus, not stated verbatim): the founder wants a *category*, not a product. The commercial thesis is persistent synthetic institutions rather than assistants. The five repositories are one body with differentiated organs.

**Uncertain:** whether the morphogenetic substrate is load-bearing or vocabulary. Whether PumpStation's memecoin surface is the business or the distribution channel for a security business. Whether household/corporate egregores (`INTENT-0008`, `INTENT-0009`, both classified `aspiration`) are direction or destination.

**Contradictory:** the founder wrote "the inevitable end is no live players remained in humanity" and then corrected it in the same message. Preserved as `INTENT-0010`, state `superseded`. The correction — that the danger is responsibility detaching from execution, not human irrelevance — became `INTENT-0003` and is the strongest organizing principle in the corpus.

**The truthful classification today:** an embryonic governed architecture with a substantial constitutional nucleus, four organs that do not consult it, and one economic cell with its first real security control. Not yet an organism. A nucleus and four cells that share a founder.

---

# Part II: Five-Repository Reality Audit

Evidence tier for every row: **direct file inspection and command execution, 2026-07-27**. No claim below rests on a README.

| Repository | Branches | Scale | Tests | Kernel coupling |
|---|---|---|---|---|
| `uniimente-kernel` | main, working branch | 165 py, **27,535 LOC**, 42 top-level dirs, 14 contracts | **560 passing** | n/a (is the kernel) |
| `DALEOBANKS` | main, working branch | 56 services, **14,054 LOC** | 56 test files | **zero references** |
| `WealthMachineIntelligence` | main, working branch | 67 py, **7,345 LOC** | 10 test files | **zero references** |
| `PumpStation` | main, working branch | client + server + governance | **55 passing** | manifest only |
| `build-your-own-x` | master, working branch | **4 files total** | none | none |

### uniimente-kernel — implemented, deep, unwired

Real and executable: UCL compiler, Consequence Gate with commit witness and budget office, hash-chained evidence ledger with Merkle proofs, event spine, machine passports, causal memory, autonomy ladder, institutional linker, developmental substrate (MICA/CDPE), evolution repair harness with a frozen experiment, Single Bottleneck Metric (added today), governance records (added today).

Twelve continuity artifacts are hash-frozen and verified. The Package 3 experiment is sealed with `SPEC_SHA256`. This is unusually disciplined work.

**Drift:** the Foundry (`foundry/`), OMNIMORPH (`omnimorph/`), and Egregore (`egregore/`) packages exist alongside `docs/FOUNDRY_OMNIMORPH_V1.md` and `docs/EGREGORE_V1_INTEGRATION_PROGRAM.md`. Whether the code implements the documents was **not verified** in this session — flagged, not asserted.

### DALEOBANKS — the largest authority conflict

56 services, 14,054 lines, 56 test files. Substantial, working, and constitutionally independent.

It runs **its own** `services/constitution.py` (83 LOC), `services/capability.py` (286 LOC), `services/ledger.py` (289 LOC), `services/evidence_policy.py` (213 LOC). The Kernel's own `organs/daleobanks.manifest.yaml` already records this as `SPECIALIZED` with unresolved fields. That was honest. It is also unchanged.

**Three competing authority implementations, zero kernel calls.** By Final Build Order §3 this is the multiple-active-authorities condition. Nothing has resolved it because nothing forces resolution.

### WealthMachineIntelligence — thin tests, real strategy code

7,345 lines. `src/services/` contains `adversarial.py`, `decision_engine.py`, `opportunity_intake.py`, `venture_protocol.py`, `risk_management.py`, `bridge_security.py`, `orchestrator.py`. **10 test files against 67 source files** — the weakest test ratio of the four operational repos. `bridge_security.py` is mirrored field-for-field in DALEOBANKS and again in the Kernel's `adapters/bridge_transport.py`: **three copies of one security mechanism**, none canonical.

### PumpStation — one real feature, now governed

Was three files. Now carries an EIP-4361 challenge/response replacing a complete authentication bypass, a bounded rate limiter, and an eleven-rule admission gate that currently **rejects** `treasury-multisig` on four rules. 55 tests. Registered as the fourth organ. Still holds no treasury, no token, no DeFi connection.

### build-your-own-x — assigned a job it cannot do

```
$ git ls-files build-your-own-x
.gitattributes
ISSUE_TEMPLATE.md
README.md              (505 lines)
codecrafters-banner.png
```

**Four files. Zero code. Zero mechanisms.**

It is an unmodified fork of the public awesome-list — a curated set of *links to third-party tutorials*. The architecture assigns it "supply mechanisms to all four operational repos." It cannot. There is nothing in it to extract. Extraction would target the linked upstream projects, not this repository.

This is not a criticism of the idea. It is a statement that the repository is currently an empty socket labelled as an organ.

---

# Part III: Canonical Repository Constitution

| Repo | Owns exclusively | May never own |
|---|---|---|
| **uniimente-kernel** | Constitution, identity root, legal principals, authority matrix, capability grants, shared contracts, event spine, evidence ledger, causal memory, Consequence Gate, egress credentials, settlement authority, shutdown, capability registry, developmental runtime, intent ledger | Domain reasoning; public voice; market analysis; token or treasury operations |
| **DALEOBANKS** | Public sensing, narrative detection, discourse analysis, public identity continuity, relationship memory, audience intelligence, content generation, distribution analytics | Constitution, capability engine, ledger-of-record, evidence policy, money, business launch, self-authorized publication |
| **WealthMachineIntelligence** | Opportunity intake, participant/buyer/budget-owner mapping, strategy generation, adversarial underwriting, economic modelling, Venture Cell *proposals*, rejected-route preservation | Venture Cell activation, capital movement, permission issuance, self-declared verification, competing governance |
| **PumpStation** | Web3 product, community, contracts, wallet UX, DAO mechanics, liquidity, treasury *operations*, scam intelligence, education, revenue, business-specific recovery | Root identity, permission ceilings, consequence classification, shutdown authority, canonical memory |
| **build-your-own-x** | Mechanism anatomy records, mutation proposals, benchmark harnesses | Anything on a runtime path. It is a library, never an organ. |

**Three prohibitions are violated today.** DALEOBANKS owns a constitution, a capability engine, and a ledger-of-record. Part VII proposes the migration; it is `NEEDS_FOUNDER_DECISION`.

---

# Part IV: Category Definition

Five candidates:

1. **Developmental Institutional Intelligence** — accurate, forgettable.
2. **Governed Synthetic Institution** — clear, understates development.
3. **Persistent Institutional Organism** — evocative, invites the life claim the founder rejected.
4. **Constitutional Runtime** — precise, sounds like middleware.
5. **Attributable Autonomy System** — names the actual differentiator.

**Selected: Attributable Autonomy System.**

Autonomy without attribution is the category everyone is already building and cannot govern. Attribution without autonomy is a workflow engine. The invention is the pair held together: the system acts, and every consequence resolves to a named human, a granted permission, and reconstructable evidence. It also states the commercial promise in three words — the thing a hospital, a grid operator, or a regulator would actually pay for.

"Egregore" stays as the founder's internal name. It should not be the category name; it imports metaphysical claims the architecture explicitly disowns.

---

# Part V: Novelty Map

| Layer | Assessment |
|---|---|
| **Existing technology** | Hash chains, Merkle proofs, SPIFFE identity, capability security, EIP-4361, JSON Schema, event sourcing, outbox/inbox, CRDTs, reaction-diffusion, actor model |
| **Existing implementation** | The Kernel's ledger, gate, passports, spine, linker are competent implementations of known patterns |
| **Novel combination** | Effect-bound single-use grants tied to a commit witness *and* a budget reservation *and* a policy version, verified again at commit time. I know of no published system binding all four to one fingerprint |
| **Potentially patentable mechanism** | The **Reality Aperture** (Part VII) — credential custody inverted so organs hold no external secrets and the only egress path is an effect-fingerprinted grant redeemed at a broker. Requires formal search and counsel; I am not qualified to assert patentability |
| **Speculative research** | Morphogenetic Virtual Machine, computational morphospace, structural regeneration through a *different* topology |
| **Unsupported claim** | That the developmental substrate outperforms conventional modular software. **No benchmark exists.** Part XV designs the experiment that would settle it |

The Single Bottleneck Metric's three refusals (no denominator → no number; no partial credit; unowned effects contaminate) are a small novel contribution: a governance metric designed so it cannot report good news it has not earned.

---

# Part VI: Seven Competing Architectures

Each differs in **mechanism**, not vocabulary.

### A1 — Contract Federation (strongest version of current design)
Organs stay independent; the Kernel publishes contracts; organs voluntarily conform.
*State:* per-organ. *Control:* none. *Authority:* advisory. *Failure geometry:* silent divergence, exactly what exists now. *Cost:* near zero. *Falsifier:* count kernel references after 90 days; if still zero, voluntary conformance is disproven. *Kill:* already effectively falsified.

### A2 — Egress Monopoly (rejects A1)
Organs hold **no** external credentials. All external effects route through a Kernel-operated broker holding the secrets. Bypass requires stealing keys that do not exist organ-side.
*State:* Kernel owns credentials + effect log. *Control:* chokepoint. *Authority:* enforced by custody. *Failure geometry:* broker outage halts all external action — a real single point of failure. *Cost:* one service, adapter rewrites. *Falsifier:* attempt an external effect without a grant; it must fail. *Kill:* if degraded-mode requirements make the broker bypassable in practice.

### A3 — Immune-System Transfer (cross-disciplinary)
No chokepoint. Kernel emits detectors that recognize *non-self* effects — external actions lacking a valid grant signature — and quarantines the emitting organ.
*State:* distributed detectors + central quarantine registry. *Control:* post-hoc. *Failure geometry:* detection latency; the effect already happened. *Cost:* moderate. *Falsifier:* time-to-detection on an injected unauthorized effect. *Kill:* if median detection exceeds the reversibility window.

### A4 — Radical Simplification
Delete the developmental substrate, the Foundry, OMNIMORPH, Egregore. Keep the Constitution, gate, ledger, contracts. Four organs, one gate, one metric.
*State:* one ledger. *Control:* one gate. *Failure geometry:* loses the category — becomes a well-governed workflow engine. *Cost:* negative. *Falsifier:* does the Single Bottleneck Metric move faster than under A2? *Kill:* if the category matters commercially, which Part XVIII argues it does.

### A5 — Maximum Capability
A2 + full morphogenetic runtime + MICA intelligence ecology + Foundry + capability transplant between Venture Cells.
*Failure geometry:* nothing is falsifiable because everything is coupled. *Cost:* years. *Kill:* it is the current trajectory and the reason nothing is wired.

### A6 — No-LLM Core
Every authority path is deterministic: policy engine, schema validation, hash verification, state machines. Models only propose and summarize, never sit on a control path.
*State:* deterministic. *Failure geometry:* brittle to novel situations; needs human escalation. *Cost:* low. *Falsifier:* what fraction of gate decisions need a model? If near zero, LLM dependence in governance is unjustified. *Kill:* only if the escalation rate is unmanageable. **This branch is stronger than it looks and is folded into the recommendation.**

### A7 — Commercial-First
Ignore the organism. Sell PumpStation's admission gate as a standalone Web3 launch-security product. Fund everything else from revenue.
*Failure geometry:* the institution never gets built; the gate becomes a feature a competitor bundles. *Cost:* lowest. *Falsifier:* one paying customer in 90 days. *Kill:* if no buyer, the security thesis is wrong and Part XVI must change.

**Null branch (do nothing):** the repositories keep diverging. Kernel reference count stays zero. The metric stays `NOT REPORTABLE`. This is the current trajectory and its cost is that the work already done becomes unverifiable.

---

# Part VII: Recommended Architecture — **A2 + A6, staged**

## The Reality Aperture

The mechanism, stated once:

> **No organ holds any credential that can affect the outside world. Every external effect is executed by a Kernel-operated egress broker that holds all secrets and will execute exactly one effect, matching one fingerprint, against one single-use grant, once.**

The Kernel already computes the fingerprint. `policy/consequence_gate.py` line ~143:

```python
"bound_effect_hash": sha256_obj({
    "payload": proposal.payload,
    "target": proposal.target,
    "action_class": proposal.action_class,
})
```

That field exists, is computed, is stored in grant metadata, and is checked at commit. It is already the hard part. What is missing is that nothing *external* consults it, because the organs hold their own API keys.

### Mutation lineage (why this is invention, not integration)

| Source mechanism | Source behavior | Mutation | New behavior |
|---|---|---|---|
| OAuth bearer token | Authorizes an *actor* for a *scope*, reusable until expiry | **Bind to effect, not actor**; single-use | Authorizes one exact consequence, once. A stolen grant buys the theft of an action the founder already approved |
| Kubernetes secrets / vault | Distributes secrets to workloads | **Invert custody** — never distribute | Organs cannot leak what they never receive |
| Payment authorization hold | Reserves funds pending capture | **Reserve authority**, not just money | Budget office already does this; extended to non-financial consequence classes |
| Content-addressed storage | Hash identifies content | **Hash identifies a permitted future** | The gate compares intent-time and commit-time fingerprints; drift between them is refused |

**Preserved invariant:** identity carries zero authority (already true in `identity/machine_passport.py`).
**New capability:** authority becomes *physically* rather than *procedurally* enforced. An organ that wants to bypass governance must first acquire credentials that do not exist in its process.
**New failure introduced:** the broker is a chokepoint and an outage stops all external action. Addressed below.

### Emergent capability

None of the source systems can do this: **the institution can prove, from its own ledger alone, that no external effect occurred outside its authority.** Not "we logged everything" — *the absence of an unauthorized effect is provable*, because unauthorized effects have no execution path. That is the difference between an audit log and a control plane, and it is what makes the Single Bottleneck Metric's contamination count meaningful rather than aspirational.

### Handling the chokepoint objection (A2's kill condition)

The broker outage risk is real and must not be waved away.

- **Degraded mode is refusal, not bypass — and the Constitution already specifies the mechanism.** `constitution/shutdown-policy.ucl` defines an eight-state safety ladder where *"movement down may be automatic; movement up requires human authority."* Its `read_only` state sets `external_effects = "none"`. A broker outage is therefore not an unhandled exception: it is an automatic descent to `read_only`, already constitutionally described and already requiring a human to climb back out. The aperture does not need a new failure policy. It needs to be the thing the existing one governs.
- **Pre-authorized envelopes** for a narrow, enumerated set of low-consequence effects (health checks, read-only fetches) with hard TTLs, so total broker loss degrades to read-only rather than dead.
- **The broker is not a single process.** It is a stateless verifier plus a secret store; it scales horizontally. The single point is the *policy*, which is the intent.

### A6 folded in

Every check on the grant path is deterministic — signature verification, fingerprint comparison, TTL, budget, single-use marking. **No model output sits on an authority path.** Models propose; the deterministic path decides. This is not a safety concession; it is what makes the path auditable and cheap.

```yaml
mechanism:
  name: Reality Aperture (egress broker + effect-bound grant)
  purpose: Make Kernel authority physically non-bypassable by inverting credential custody
  owning_repository: uniimente-kernel
  package_or_directory: policy/egress/
  interfaces_with: DALEOBANKS, WealthMachineIntelligence, PumpStation adapters
  canonical_state_owner: uniimente-kernel (credentials, grants, effect log)
  authority_owner: uniimente-kernel Consequence Gate
  deployment_boundary: separate process, separate network zone, holds all external secrets
  why_it_belongs_here: it IS the consequence boundary; §3.1 assigns consequence control to the Kernel
  why_it_does_not_belong_elsewhere: any organ holding it becomes a second authority, violating §3
```

---

# Part VIII: Cross-Repository Contract System

Fifteen objects. Common envelope on all:

```yaml
envelope:
  schema_version: semver
  content_hash: sha256 of canonical body
  actor: spiffe://uniimente.internal/...
  source_repository: enum[uniimente-kernel|DALEOBANKS|WealthMachineIntelligence|PumpStation]
  legal_principal: human or registered entity, never UNIIMENTE   # INTENT-0001
  causal_parents: [content_hash]
  evidence_refs: [content_hash]
  lifecycle_state: enum
  sensitivity: enum[public|internal|restricted|secret]
  authority_requirements: [capability_id]
  expires_at: rfc3339
  invalidation_conditions: [string]
```

| Object | Producer | Consumer | Carries |
|---|---|---|---|
| `SignalPacket` | DALEOBANKS | WMI | observation, source authority, narrative-vs-evidence classification |
| `EvidenceReference` | any | any | content hash, retrieval path, source authority tier |
| `OpportunityCase` | WMI | WMI | participant map, buyer, budget owner, recurring transaction, trapped value |
| `StrategyBranch` | WMI | WMI | route, mechanism, cost, reversibility, **revival evidence if rejected** |
| `VentureProposal` | WMI | Kernel | chosen branch, adversarial cases, requested authority, budget |
| `PolicyDecision` | Kernel | all | verdict, law applied, refusal reasons, policy version |
| `CapabilityGrant` | Kernel | broker | **bound_effect_hash**, single-use flag, TTL, budget reservation, revocation |
| `ExecutionRequest` | organ | broker | grant id + payload; broker recomputes fingerprint and compares |
| `CommitWitness` | Kernel | ledger | pre-execution attestation of identity, policy, evidence, budget |
| `ExternalReceipt` | broker | Kernel | what actually happened, transport-level proof |
| `OutcomeCredential` | Kernel | WMI | external observation, validation tier, expected-vs-actual |
| `ReconciliationRecord` | Kernel | Kernel | receipt ↔ outcome ↔ budget closure, or named discrepancy |
| `LearningUpdate` | WMI | Kernel | calibration delta with the prediction it corrects |
| `CapabilityGenome` | Kernel | registry | reusable capability + lifecycle + kill conditions |
| `ContinuityRecord` | Kernel | Kernel | identity across model/component replacement |

**Compatibility rule:** additive changes bump minor and stay backward-valid; any field removal or enum narrowing bumps major and requires an adapter in `adapters/` declaring information lost. This is already the repository's stated adapter doctrine; it is currently applied to two wire contracts and must extend to all fifteen.

**Failure handling:** idempotent inbox keyed on `content_hash`; transactional outbox per organ; dead-letter after N retries with a named owner; compensation is a *new* effect requiring a *new* grant — never a silent undo.

---

# Part IX: Kernel Developmental Runtime

Honest position first: **the developmental substrate is unproven and I am not going to assert it is superior.** `developmental/` (MICA, CDPE) exists and passes tests. No benchmark compares it to conventional modular software. Part XV is the experiment that decides.

Proposed structure, differing from the prompt's candidate in three ways:

```
uniimente-kernel/developmental/
  cell/          runtime, local state, receptors, budget
  signal/        typed diffusible signals, decay, thresholds
  field/         set-point representation and gradient computation
  topology/      neighborhood graph, attach/detach
  differentiation/  role assignment from local evidence only
  metabolism/    compute, memory, money, attention as one resource type
  repair/        damage detection, structural (not identical) restoration
  continuity/    lineage, identity across replacement
  harness/       benchmarks and adversarial baselines   ← NOT "simulation"
```

Three deliberate departures:
1. **No `morphospace/` package.** Morphospace is a *coordinate system over recorded runs*, computed from `harness/` output. Giving it a package invites a hidden global index — a central planner wearing a biological name.
2. **`harness/` replaces `simulation/`.** The name matters: simulation invites treating a passing run as validation. The prompt's own §21 forbids that. A harness is where you try to *falsify*.
3. **`metabolism/` unifies four resources.** Compute, memory, money, and attention share one accounting type with different units, so a cell cannot spend attention to evade a compute budget.

### The hard problems, answered

- **Local contribution without global visibility.** Cells read only neighbor state and local signal concentration. Global objectives enter as *set-points in a field* — a scalar target a cell compares against locally sensed value. No cell knows the goal; each knows its local error.
- **Global target without a central planner.** The field is written by a boundary condition, not a controller. This is the honest distinction: a planner *assigns roles*; a boundary condition *creates a gradient* and roles fall out of local rules. If any code path assigns a role directly, it is a planner and must be named one.
- **Distinguishing emergence from scripted orchestration.** One test: **remove the boundary condition mid-run.** Genuine local competency degrades gracefully; scripted orchestration halts or produces nonsense. Part XV includes this.
- **Restoring function through a *different* structure.** Prohibit the original topology after damage. If the system can only restore by rebuilding what was there, it is a backup system, not a developmental one.
- **Identity across component change.** `continuity/` holds lineage, not composition. Identity is the hash chain of *decisions and grants*, which survives total cell replacement. This is already how `provenance/ledger.py` works.
- **Preventing developmental systems from acquiring external authority.** They never touch the broker. Cells have no grant-request capability. A developmental result is a *proposal* that must cross the same gate as any other. `tests/unit/test_repair_inertness.py` already asserts zero external effects from the repair path.
- **When conventional modular software wins.** Whenever the problem is stationary, the failure modes are enumerable, and the topology is known. Which is most problems. The developmental substrate must earn each deployment.

---

# Part X: Intelligence Ecology

MICA's premise — distinct computational substrates forming temporary cognitive tissue — is sound. Its weakness is that "distinct substrate" is asserted, not measured. **Two substrates are only distinct if they fail differently.** Add a required field: `decorrelation_evidence` — measured disagreement on a shared benchmark. Substrates that agree everywhere are one substrate with two names, and their agreement must not be counted as corroboration.

| Intelligence | Native problem geometry | Owns | Cost | Authority ceiling | Failure mode |
|---|---|---|---|---|---|
| Deterministic policy | Enumerable rules | Kernel | negligible | **decides** | brittle to novelty |
| Schema/hash verification | Structural validity | Kernel | negligible | **decides** | validates form, not truth |
| Bayesian calibration | Repeated predictions | Kernel `memory/causal.py` | low | advises | needs volume |
| Causal graph | Intervention questions | Kernel | medium | advises | confounding |
| Evolutionary search | Rugged landscapes | Kernel `evolution/` | high | proposes | overfits the harness |
| Local cell rules | Distributed adaptation | Kernel `developmental/` | medium | proposes | **unproven** |
| Adversarial team | Failure discovery | WMI | medium | proposes | theatre if scripted |
| LLM reasoning | Ambiguous language, synthesis | all organs | high | **proposes only** | fluent fabrication |
| Immune detection | Anomaly, non-self | Kernel | low | quarantines | false positives |
| Human expertise | Everything unmodelled | outside | highest | **authorizes** | scarce, slow |

The ceiling column is the whole design. Only deterministic mechanisms decide. Only humans authorize. Everything else proposes.

---

# Part XI: DALEOBANKS Evolution

Bounded-autonomy model, in one line: **DALEOBANKS may think freely, publish narrowly, and hold nothing.**

- **Sensing and interpretation:** unrestricted. Reading public discourse creates no external consequence.
- **Interpretation is labelled:** every claim carries `observation | inference | narrative | disputed`. Ten agents citing one source is one source; `evidence_policy.py` already knows this and must be wired to the Kernel's evidence tiers instead of its own.
- **Publication is an external effect.** It goes through the aperture. DALEOBANKS holds no X credential. The broker does.
- **Migration of the three competing authorities:** `constitution.py` → Kernel compiled policy. `capability.py` → Kernel grants. `ledger.py` → retained as an organ-local *cache*, marked non-authoritative, with the Kernel chain as record. **All three preserved in `superseded/` with lineage**, per §2. This is `NEEDS_FOUNDER_DECISION`.

The metric that matters is not followers. It is **qualified signals that survive WMI intake** — the count of SignalPackets that become an OpportunityCase. Attention that produces no qualified signal is cost.

---

# Part XII: WealthMachineIntelligence Evolution — Eight-Sided Analysis

**Governing transaction:** *A memecoin launch participant must obtain confidence that a token contract will not rug them, but completion is unreliable because contract risk state is unreadable at the decisive moment — before they send funds.*

**Falsifiable thesis:** Become the accepted control layer for pre-purchase token risk by controlling the *published risk attestation* at the moment of first liquidity, issuing a signed **Launch Safety Attestation**, and tying it to listing eligibility on partner surfaces — while incumbent launchpads cannot copy it without disclosing the launches they profit from that would fail it.

That last clause is the counter-position: a launchpad earning fees per launch cannot adopt a standard that rejects launches. **Self-cannibalization is the binding constraint.**

| Side | Mechanism | Super-node | Attack | Defense |
|---|---|---|---|---|
| 1 Reality/failure | Contract analysis at first liquidity | Proof | analyzer misses novel exploit | publish coverage limits; never claim completeness |
| 2 Power/participants | Creators want distribution; buyers want safety | Eligibility | creators route around | make attested launches convert better |
| 3 Eligibility | Attestation gates partner listing | **Eligibility** | partners defect | start with own surface |
| 4 Routing | Default surfacing of attested launches | **Routing** | paid promotion outbids | disclosed promotion only |
| 5 Proof/truth | Signed attestation + public method | **Proof** | forged attestation | Kernel signs; verify offline |
| 6 Settlement | Launch fee paid on attestation | **Cashflow** | fee undercut to zero | bundle with liquidity-lock enforcement |
| 7 Distribution | DALEOBANKS + creator network | Routing | no audience | earn it before monetizing |
| 8 Reliability/governance | Incident response, restitution pool | all | one bad attestation | disclosed limits, funded reserve |

**Four super-nodes all engaged.** A proposal touching none would be decorative; this touches all four.

**Ownership split:** WMI owns the *analysis* and the *strategy routes*. The Kernel owns the *signing key and the attestation record*. PumpStation owns the *surface and the fee*. WMI must never sign — an analyst that issues its own credential is a second authority.

**Five-outcome gate (scored, and it does not pass yet):** Commercial 3 · Strategic 4 · Regenerative 4 · Institutional 3 · Capital 2. Average 3.2, below the 4.0 threshold, with Capital at 2. **Decision: Validate, not Commit.** The missing evidence is a single paying creator.

---

# Part XIII: PumpStation Evolution

The doctrine — *reproduce the economic force, remove the victim, automate the protection, outperform the exploitative model* — is sound and is not softened here.

**Sequencing, hardest constraint first:** every revenue line that touches a token requires legal review the founder has not obtained (`INTENT-0018` blocker class). So the first transaction must produce revenue **without** issuing, holding, or promoting a token.

The admission gate already refuses `treasury-multisig` on four rules. Good. That refusal is the sequencing being enforced rather than argued.

**Eight security layers, honest state:** contract ✗, treasury ✗, agent ✗, governance ✗, market ✗, information ✗, human **partial** (plain-English signing, CSP, no third-party scripts), recovery **partial** (documented, unit-exercised, no process-level rehearsal). Two of eight partially built. The other six are architecture.

---

# Part XIV: Build-Your-Own-X Mutation System

The repository is four files. Before it can supply anything it must be **populated**, and the first commit into it should be the pipeline, not a mechanism.

```yaml
mechanism_anatomy:
  source_category:      # the linked upstream project, not this repo
  primitive:
  state_model:
  communication_model:
  control_model:
  resource_model:
  useful_property:
  failure_geometry:
  proposed_mutation:    # must change incentive, authority, or consequence
  destination_repository:
  baseline:             # what it must beat
  benchmark:            # executable
  kill_condition:
```

**Gate:** a mechanism enters only with an executable benchmark and a named baseline it must beat. Sounding advanced is not a qualification. Six candidates worth the first pass: capability security (already partly adopted), workload identity, durable workflows, content addressing, CRDTs (for organ-local caches that must reconcile), reaction-diffusion (for `field/`).

**Constraint the prompt sets and I am honoring:** `build-your-own-x` supplies mechanisms; it never appears on a runtime path.

---

# Part XV: First Developmental Experiment

Lives in `uniimente-kernel/developmental/harness/`. Designed to **kill** the substrate if it does not earn its place.

**Setup:** ~100 cells, local neighborhood perception only, scarce resources, three functional regions to develop, one resource to transport across a changing environment. No cell reads global state. No controller assigns final roles.

**Perturbations, in order:** remove 20% of cells → damage one region → block the original transport path → **prohibit restoration of the original topology** → remove the boundary condition entirely.

That last one is my addition and it is the decisive test. If the system keeps functioning without the field, the field was never doing the work. If it collapses immediately, the field *was* a central planner.

**Baselines it must beat:** central planner, workflow engine, fixed modular architecture, manager-worker multi-agent, no-LLM local controller, binary vs. ternary signalling.

**Measured:** convergence time, functional recovery rate, compute, message volume, resource efficiency, **structural diversity of successful solutions**, stability, false activation, authority violations (must be **zero**), unseen-damage recovery, reproducibility across seeds, interpretability.

**Kill condition, stated in advance:** if the developmental architecture does not beat the fixed modular baseline on *unseen* damage recovery, it is demoted to `EXPERIMENTAL` and removed from the critical path. Not defended, not rationalized. Demoted.

---

# Part XVI: First Cross-Repository Commercial Experiment

**The transaction:** a memecoin creator pays **$500** for a pre-launch contract safety review that produces a signed, publicly verifiable Launch Safety Attestation.

Why this one:
- **Real buyer** with an existing budget line (creators already pay for audits).
- **Accepted artifact** — a signed attestation, publicly verifiable.
- **No token required.** PumpStation issues nothing, holds nothing, promotes nothing. Legal review is not on the critical path.
- **Exercises all four operational repos** in one loop.
- **Externally checkable** — the attestation is public, and its accuracy is falsifiable by what the contract does next.

```
DALEOBANKS   detects a creator publicly asking about launch safety
             → SignalPacket
WMI          → OpportunityCase (buyer, budget owner, recurring transaction)
             → StrategyBranch ×4, adversarial cases preserved
             → VentureProposal
Kernel       → validates identity, evidence, authority, budget, consequence class
             → CapabilityGrant, effect-bound, single-use
PumpStation  → performs the review, publishes the attestation via the aperture
             → ExternalReceipt
Kernel       → OutcomeCredential + ReconciliationRecord
WMI          → LearningUpdate (did the attestation predict the outcome?)
DALEOBANKS   → publishes result or correction, through the aperture
```

**Success is not the $500.** Success is: one payment received, one attestation published, one Single Bottleneck Metric reading that is **reportable and uncontaminated**. That last number is the first time the institution can prove it governed itself.

**Failure conditions:** no creator pays (thesis wrong — see A7); the attestation is wrong (coverage overclaimed); an effect executes without a grant (the aperture failed and everything else is void).

---

# Part XVII: Ten-Year Backcast (no AGI assumed)

- **Year 1** — Aperture enforced; kernel reference count > 0 in three organs; metric reportable; first paid attestation; developmental experiment decided either way.
- **Year 2** — Attestation accepted by one external surface that is not PumpStation. First capability transplanted between two Venture Cells. DALEOBANKS authority migration complete.
- **Year 3** — Second Venture Cell launched from registry capabilities, measurably faster than the first. Revenue covers reliability and reserves.
- **Years 4–5** — Attestation becomes a referenced standard in one narrow market. Capital layer forms *after* operating reliability is funded, never before.
- **Years 6–7** — First non-Web3 deployment. The category argument is made by a customer, not by us.
- **Years 8–10** — Institutional permanence work: succession, IP ownership, governance that survives the founder. This is the point at which "persistent institution" stops being a claim.

Each transition gated on external evidence, not elapsed time.

---

# Part XVIII: Industry Formation

The market is not "AI agents." It is **continuity of institutional competence**.

Power grids, water systems, hospitals, logistics, public records, and settlement infrastructure all depend on knowledge held by shrinking numbers of people. That knowledge leaves. Documentation rots. The systems keep running until they do not.

The buyer for an Attributable Autonomy System is whoever owns that risk: a utility with retiring operators, a hospital group with fragmented procedure knowledge, a municipality whose records systems nobody fully understands. What they will pay for is **not autonomy** — it is the ability to say, under audit, *who authorized this, on what evidence, and how to stop it*.

Household egregores (`INTENT-0008`) and corporate egregores (`INTENT-0009`) are classified `aspiration` in the ledger and stay there until a buyer exists. Infrastructure continuity is the near market. It is also the one where attributability is legally required, which converts a governance cost into a sales advantage.

---

# Part XIX: Failure and Kill Conditions

**Simplify when:** the developmental experiment loses to the fixed modular baseline; contract count grows faster than organ integrations; governance artifacts outnumber governed effects.

**Redirect when:** no creator pays for attestation within 90 days; the attestation is accepted but generates no recurring transaction; a competitor bundles equivalent safety for free without self-harm (the counter-position was wrong).

**Abandon when:** an external effect executes without a grant and the cause is architectural rather than operational; the founder cannot maintain constitutional authority in practice; the institution's governance cost exceeds the value of what it governs — the honest signal that this should have been a workflow engine.

**Already-triggered condition:** kernel reference count has been zero for the life of the project. Under A1's own falsifier, voluntary conformance is disproven. That is why A2 is recommended.

---

# Part XX: 90-Day Build Plan

**Branch strategy:** one branch per repo per package; draft PRs; kernel merges first because contracts are upstream of adapters.

| Weeks | Deliverable | Repo | Evidence |
|---|---|---|---|
| 1–2 | `policy/egress/` broker: grant redemption, fingerprint compare, single-use marking | kernel | tests incl. replay, fingerprint drift, expired grant |
| 3–4 | Fifteen contract schemas + envelope + adapter policy | kernel | schema tests; every `$ref` resolves |
| 5–6 | DALEOBANKS adapter: publication through the aperture; **X credential removed from the organ** | DALEOBANKS | integration test proving publish fails without a grant |
| 7 | WMI adapter: SignalPacket intake, OpportunityCase emit | WMI | contract parity test vs kernel schema |
| 8 | Bridge-security triplication resolved — kernel canonical, two organs consume | all three | one implementation, two thin clients |
| 9–10 | PumpStation attestation service + fee path | PumpStation | admission-gate entry passing all 11 rules |
| 11 | Developmental harness + all seven baselines | kernel | benchmark report, kill decision recorded |
| 12 | First paid attestation; full loop; metric reading | all four | reportable, uncontaminated SBM |
| 13 | Incident rehearsal: revoke a grant mid-flight; broker outage drill | kernel + PumpStation | recovery evidence, `tested: true` earned |

**Security work is not a phase.** It is weeks 1–2, because the aperture *is* the security work.

---

# Part XXI: Adversarial Final Review

Attacking this plan as though trying to stop the founder wasting ten years.

**1. "The aperture is a bottleneck you will route around the first time it is inconvenient."**
Strongest objection, and history supports it: the Kernel already exists and is already routed around. Answer: custody, not policy. If DALEOBANKS never receives the X credential, routing around requires an act of theft rather than an act of convenience. Week 5's deliverable is *credential removal*, and if that slips, the whole plan has failed and should be said so.

**2. "You are building governance for a system with no users."**
Largely fair. Mitigation: the first transaction is week 12, not year 2, and A7 (commercial-first) stays live as a fork if no creator pays.

**3. "The developmental substrate is a decade of research funded by a Web3 side business."**
Correct as stated, which is why Part XV can kill it in week 11 on a pre-declared criterion.

**4. "Attestation is a commodity; auditors already exist."**
Partly true. The differentiator is not analysis quality but *the artifact being tied to eligibility*. If no surface ever gates on it, side 3 collapses and the thesis is dead. That is the Validate decision, not a Commit.

**5. "Five repositories is a constraint you inherited, not one you chose."**
Yes. It is also correct: three of the five have real code and bounded responsibility, and a sixth repository today would add a boundary before the existing four are wired. Revisit only when the aperture is enforced.

**6. "This document is a model output describing model outputs."**
The sharpest one. Everything here is `model_output` tier except the audit, which is `primary_source` from executed commands. The 90-day plan converts exactly one claim to `real_external_effect`: a creator paying $500. Until then this is a plan, and the ledger records it as one.

### Strengthened final architecture

Unchanged in mechanism, tightened in sequence: **A2 + A6**, with credential removal as the week-5 gate rather than a later refinement, the developmental substrate placed behind a pre-declared kill criterion, and the entire commercial thesis resting on one falsifiable $500 transaction.

---

## Decision

**EXPERIMENT** on the developmental substrate (Part XV, kill criterion declared).
**VALIDATE** on the attestation business (Part XVI, five-outcome gate scored 3.2, below Commit).
**BUILD** the Reality Aperture (Part VII).

- **Next external action:** implement `policy/egress/`, then remove the X credential from DALEOBANKS.
- **External number it must change:** kernel reference count in organ code, currently **0**. Target ≥ 1 in three organs by week 8.
- **Evidence required:** an integration test proving an external publish fails without a grant; one paid attestation; one reportable, uncontaminated Single Bottleneck Metric reading.
- **Deadline:** 90 days.
- **Termination trigger:** if week 5 ends with organs still holding their own external credentials, the enforcement thesis has failed and the architecture reverts to A4 (radical simplification) — a well-governed workflow engine, honestly named.

---

## Constitutional items requiring founder decision

1. **DALEOBANKS authority migration** — retiring its constitution, capability engine, and ledger-of-record to the Kernel. Preserves all three in `superseded/`. Constitutional: changes canonical ownership across repositories.
2. **Credential custody inversion** — organs surrender external credentials to the Kernel broker. Constitutional: changes where secrets live and what an organ can do unsupervised.
3. **`build-your-own-x` role** — populate it with mechanism-anatomy records, or reassign the atlas function to a Kernel package and mark the repository historical. It cannot perform its assigned role as four files.

None is applied. Each needs a deliberation record under `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` before implementation.
