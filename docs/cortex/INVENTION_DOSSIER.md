# Invention dossier: Proof-Carrying, Gate-First Polyintelligence Router

Mechanism Recombination Foundry output for the GREG Polyintelligence Cortex seed. Machine-readable record:
[`invention.json`](invention.json) (passes the Foundry's `validate_invention.py`). Patent or legal novelty is not
claimed; this is an invention analysis, not legal advice.

## The invention

A router that answers each question from the mechanism with **legitimate epistemic jurisdiction** over it, makes
that mechanism **prove its answer in that jurisdiction's terms**, **refuses or hands off** with a named missing fact
when no mechanism may answer, sends **human-led protective actions to humans**, and lets its record of which
mechanism works where **learn only from verified reality** — with no path by which competence, proof or
confidence becomes authority.

## 1. Why it is different

| Existing system | What it does | What it cannot do that this does |
| --- | --- | --- |
| LLM routers (RouterBench, LLMRouterBench) | pick the model with the best expected quality per cost | refuse with jurisdiction; check gates before ranking; emit class-specific proof; keep learning away from permission |
| Algorithm portfolios (SATzilla) | pick the fastest solver for an instance of one problem class | span classes (formal, estimation, causal, semantic); select *nobody* as a correct outcome |
| LLM + solver (Logic-LM, SymbolLKG) | translate to a solver and refine on errors | verify the translation against obligations and requester witnesses; mark unverified premises; certify optimality independently |
| Proof-carrying code (Necula 1997) | ships a machine-checked safety proof with code | carry proof for *cognitive claims*, split formal, empirical and authority validity, and refuse to let proof authorize |
| Signed agent receipts (IETF/SCITT drafts, 2026) | attest that an agent did something | attest what cognition could *not* establish: falsifiers, missing information, strongest counterargument |

## 2. Mechanism anatomy

Mechanism cards (source → extracted causal machinery, branding discarded):

- **Portfolio selection** — state: instance features; transition: features → predicted performance → choice; invariant
  kept: per-instance choice. Discarded: single problem class, runtime as the only objective.
- **Router settlement** — state: per-model quality/cost estimates; feedback: observed results update estimates.
  Kept: better methods earn more work. Discarded: self-reported or benchmark-only settlement.
- **Proof-carrying** — producer ships evidence; consumer checks before relying. Kept: check, do not trust.
  Discarded: proof implies permission to run.
- **Translate–solve–refine** — model formalizes; solver decides. Kept: exact reasoning delegated to solvers.
  Discarded: trust in the model's formalization.
- **Model–identify–estimate–refute** — causal claims need identification and refutation. Kept entirely; mutated so a
  model-generated diagram can never be the identification basis.
- **Receipts** — canonical, content-addressed records. Kept; purpose inverted from attesting actions to attesting
  limits.
- **Constitutional separation** — models propose, the Kernel authorizes. Kept as the hard outer boundary.

## 3. Mutation lineage

| Source | Operator | New behavior | Invariant kept | New failure introduced |
| --- | --- | --- | --- | --- |
| Portfolio | constraint inversion + role widening | selection across epistemic classes; abstention and handoff are first-class, credited outcomes | per-instance selection | a payload can mimic a geometry |
| Proof-carrying code | authority decoupling | typed proof per epistemic class; formal / empirical / authority truth split; `authority_created: false` enforced by schema | consumer checks evidence | valid proof of an unfaithful encoding (mitigated by reverse translation, witnesses, `WORLD_UNVERIFIED`) |
| LLM routers | incentive mutation | settlement only by verified, provenance-weighted outcomes; learning permutes eligible routes only | better methods get more work | slow learning when outcomes are rare |
| Hard constraints | sequencing inversion | gates over provenance-checked permission records before any ranking; Pareto front, not a scalar | best among feasible | over-blocking, surfaced as `UNRESOLVED` with a named resolution |
| Signed receipts | purpose inversion | receipts publish falsifiers, missing information, strongest counterargument; never identities | canonical auditable records | prose falsifiers are only as precise as their templates |
| Translate–solve–refine | verification insertion | reverse translation, obligation coverage, witnesses, counterexample search; undecided witness stops; optimality certificate | solver does exact reasoning | structural coverage cannot prove completeness |

Every mutation that matters changes authority, incentives or consequences, not only implementation. None reduces
to "use X with Y".

## 4. System topology

```
question + structured facts
  → geometry (epistemic class, consequence vector, reversibility, unknowns explicit)
  → eligibility (Capability Genome may_instantiate, contraindications, light-cone ceiling)
  → hard gates over permission-bearing records (when options exist)  ── fail → never ranked
  → budget
  → route or bounded composition (Semantic | Fermi | Formal/Optimization | Evidence/Causal)
  → typed proof artifact
  → model-free adversarial verifier (can only lower)
  → recommend | bounded test | abstain | handoff  (human-led protection forces handoff)
  → receipt (truth split, accountability, authority_created=false)
  → Kernel policy engine → capability grant → Consequence Gate   (outside the cortex)
  → outcome → competence ledger (verified only; permute eligible only; rollback)
```

## 5. Emergent behavior

The interaction produces capabilities no source has alone:

- **Jurisdictional refusal**: the system can say "no mechanism here may answer this; this is what is missing", and
  that answer scores as correct.
- **Disputes narrowed by construction**: every answer names the assumption, premise or observation that would
  falsify it, so disagreement attacks evidence rather than the AI.
- **Competence without sovereignty**: the routing record compounds from reality while being structurally unable to
  widen permissions, ceilings or evaluators.
- **Protection without exposure**: protective actions are ordered and handed to humans, and the audit trail proves
  the handling without ever naming the person or channel.

## 6. Incentive and authority design

- Methods earn default routing per method × geometry × conditions × version, only from settled outcomes weighted by
  validation status; predictions and self-assessments are refused as outcomes.
- The scoring rule credits correct abstention (1.0) and penalizes confident error (0.0), with over-caution at 0.25,
  so neither withholding nor bluffing wins.
- Permission comes only from records whose kind and origin are verified (Kernel policy decision, founder-signed
  mandate, Kernel grant, consent capture, qualified human legal opinion). Forged origins are rejected.
- The cortex cannot import the Consequence Gate, adapters or any actuator; a static test enforces it.

## 7. Omnidirectional effects

| Party | Beneficial | Harmful or ambiguous | Redesign applied |
| --- | --- | --- | --- |
| Founder | auditable answers; fewer opaque assertions; clear handoffs | more handoffs than a bluffing system | handoffs name the next step and missing fact |
| Affected third parties / victims | protection routed to humans; identities never in receipts | cognition cannot act fast on their behalf | protection is ordered "protect now" first; human-led by design |
| Operators | explicit states for every failure; reproducible freezes | more machinery than a single model | mutation check and traceability tests keep it honest |
| Adversaries / counterparties | must attack named assumptions | a published falsifier is also a map of weak points | falsifiers name evidence to bring, which strengthens legitimate challenge |
| Model vendors | swappable organs | lose lock-in | intended |
| Future versions | contracts and reserved families give extension points | reserved names can look like capability | registry marks them disabled; register says "reserved" |
| Second/third order | institutions can rely on bounded, falsifiable AI claims | over-trust in "proof" | truth split: formal ≠ empirical ≠ authority, on every receipt |

## 8. Adversarial failure analysis

- **Prompt injection in sources** → flagged by the verifier; the exact-quote check means injected text cannot
  manufacture support.
- **Forged permission records** → origin check per kind; mutation test proves a forged origin cannot grant.
- **Evaluator gaming** → frozen suites by hash; held-out refuses changed inputs; evaluator-gaming items in the suite.
- **Lying optimizer** → independent UNSAT optimality certificate; a test swaps in an optimizer that misreports.
- **Unfaithful formalization** → obligation coverage, requester witnesses, counterexample search,
  `FORMALIZATION_INCOMPLETE`, `WORLD_UNVERIFIED`.
- **Competence gaming** → only provenance-weighted verified outcomes settle; learning cannot touch the registry.
- **Correlated agreement** → shared dependencies recorded; the verifier shares no model with any route.

## 9. Novelty and precedent ledger

| Element | Classification | Nearest precedent |
| --- | --- | --- |
| Per-instance routing | known primitive | SATzilla; RouterBench |
| LLM-to-solver translation | known combination | Logic-LM; SymbolLKG Logic Router |
| Proof shipped with output | known primitive (code) → mutated mechanism (cognition) | Necula 1997 |
| Model → identify → estimate → refute | known implementation | DoWhy |
| Signed canonical receipts | known implementation | IETF/SCITT agent-receipt drafts (2026) |
| Abstention as a scored outcome | known primitive (selective prediction) | abstention surveys; AbstentionBench |
| Gates over provenance-checked permission records *before* ranking, with Pareto tradeoffs | mutated mechanism | constrained optimization |
| Epistemic-class-typed proof with formal / empirical / authority split | new proof relationship (likely) | none located combining all three |
| Outcome-only settlement that can permute eligible routes but never permissions | new authority relationship (likely) | routers learn routing; none located that structurally fences learning from authority |
| Receipts publishing falsifiers, missing information, strongest counterargument, `authority_created=false` | new proof/consequence chain (likely) | receipts attest actions, not limits |
| Victim-protection-aware dispositions with identity-free receipts | mutated mechanism | none located in routing systems |

Claim discipline: components are known; the mutated interaction appears structurally distinct from located
precedents; the likely novelty lies in the authority and proof relationships above. Strongest counterexample to the
*value* claim: LLMRouterBench reports several routers, including a commercial one, failing to beat the best single
model — so routing gain must be demonstrated, not assumed.

## 10. Scores (0–10) and fatal gates

| Criterion | Score | Note |
| --- | --- | --- |
| Mechanism novelty | 7 | interaction-level; components known |
| Emergent capability | 8 | jurisdictional refusal, falsifier receipts, fenced learning |
| Causal coherence | 8 | every stage tested; 26/26 mutants caught |
| Incentive coherence | 8 | settlement only by reality; abstention credited |
| Omnidirectional net benefit | 8 | protection and accountability improve without new authority |
| Feasibility | 9 | built and running |
| Capital efficiency | 9 | one optional dependency (z3-solver), local execution |
| Defensibility through accepted state | 6 | grows only with real outcomes, which do not exist yet |
| Modularity and replaceability | 9 | organs swap behind one contract |
| Developmental potential | 7 | reserved families and genesis path; unproven |
| User legibility | 7 | receipts are long; README and examples help |
| Graceful failure and recovery | 9 | explicit states, rollback, freeze refusal |

Fatal gates: no real emergent capability — passes; unchanged repository integration — passes (mutations above);
hidden dependence on nonexistent technology — passes at the seed tier; ungoverned irreversible harm — passes
(handoff by rule); authority without accountability — passes (no authority created); incentives rewarding
degradation — passes; no path to first experiment — passes; novelty contradicted by direct precedent — not found
for the interaction; components are disclosed as known.

## 11. Cumulative ascent

| Level | Stage | Tier |
| --- | --- | --- |
| Seed invention | this router (N1) | BUILDABLE (built) |
| Compound invention | Composer + metaconsensus (N3) | EXPERIMENTAL |
| Platform / substrate | Cortex on independent problems with shadow use (N2) | EXPERIMENTAL |
| Developmental system | deficit-driven capability genesis (N4) | EXPERIMENTAL |
| Cyber-physical institution | Polyintelligent GREG on real missions (N5) | EXPERIMENTAL |
| Frontier architecture | frontier capability discovery (N6) | FRONTIER |
| Science-fiction descendant | substrate-plural, poly-embodied GREG | SCIENCE-FICTION |

Each level inherits the gates, receipts and outcome-only settlement of the one before; see
[`BACKCAST_GPS_CORTEX.md`](BACKCAST_GPS_CORTEX.md).

## 12. Build path and kill test

- **Minimum experiment:** the frozen held-out run (freeze v0.1.5) with both declared baselines under the
  pre-registered exit rule.
- **30 days:** baselines run (local model, then a strong model under founder authorization); verdict recorded.
- **90 days (only after `GAIN_VERIFIED` and VEPMC ≥ 1):** externally authored free-text suite; shadow receipts on
  real GREG missions.
- **Kill test:** `GAIN_ABSENT` against strong baselines on two frozen versions with no critical-error advantage →
  retire the performance claim; keep gates and receipts only if they still reduce critical errors.

## Decision: EXPERIMENT

- **Next concrete action:** obtain a reachable model and run the frozen held-out partition with all arms.
- **Measurable result:** exit verdict `GAIN_VERIFIED` or `GAIN_ABSENT`, with per-geometry paired gains.
- **Evidence required:** both declared baselines `RUN` against the committed freeze.
- **Stage gate:** Node 1 of the backcast.
- **Termination condition:** the kill test above.
