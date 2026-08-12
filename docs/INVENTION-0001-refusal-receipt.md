# INVENTION-0001 — The Refusal Receipt

Produced with the `mechanism-recombination-foundry` skill on 2026-08-12, against the
capability set this repository can actually prove it has.

**Invention dossier, not authorization.** Nothing here is built, activated, sold, or
shown to anyone. Buildability is asserted; a build is a separate founder decision.

---

## 1. Invention field

**Intended transformation.** Turn the thing UNIIMENTE is uniquely good at into
something a stranger will accept.

**Present constraint, measured.** `docs/SPIDER_WEB_FIRST_OUTCOME_AUDIT.md` scores
side 3 (accepted artifact) at **1/5** and side 4 (downstream consequence) at **0/5**.
No external party has ever accepted a UNIIMENTE receipt and nothing turns on one.
Meanwhile side 2 (control point) scores 3/5 on genuinely strong machinery. The
institution's proof layer is far ahead of its market contact.

**Assets already available and PROVEN in this repository:** hash-chained evidence
ledger with Merkle inclusion proofs; a Consequence Gate that revalidates at commit
time with 12 passing adversarial cases; a UCL compiler whose constitution compiles
deterministically to a stable hash; capability grants bound to nine dimensions and
single-use; causal memory that reconstructs outcome → receipt → witness.

**Minimum impressive result.** One external party states that a UNIIMENTE artifact
would change a decision they actually make.

**Unacceptable harms.** Any artifact that could be used to claim safety that was not
achieved. Any receipt that is easier to forge than to earn.

---

## 2. The tension worth inventing through

**Proving a positive is easy. Proving a negative is not, and the negative is what
everyone actually needs to know about an autonomous agent.**

Every audit system in existence records what happened. None can distinguish, to a
third party, between:

1. the agent never attempted the harmful action;
2. the agent attempted it and the attempt was not logged;
3. the agent did it and the log was edited afterward.

Absence of a log entry is not evidence of absence. This is the single hardest claim
to make credibly about a deployed AI system, and it is the claim that insurers,
auditors, procurement officers and counterparties most need.

---

## 3. Mechanism cards and their mutations

| Source mechanism | Source behaviour | Operator | Mutated behaviour | Invariant preserved | New failure introduced |
|---|---|---|---|---|---|
| **Consequence Gate** (`policy/consequence_gate.py`) | Decides whether an action may execute; refusal is a control outcome and a dead end. | **Role inversion** — the by-product becomes the product | The **refusal** is the emitted artifact. The gate stops being only a gatekeeper and becomes an evidence manufacturer. | Fail-closed. Nine conditions unchanged. | An operator gains an incentive to generate refusals for their evidentiary value. Addressed in §7. |
| **UCL compiler** (`compiler/`) | Compiles doctrine to policy deterministically, anchored by `constitution_hash`. | **Externalisation** — the hash leaves the building | A third party can **recompile the same constitution and re-derive the same refusal**. Verification stops requiring trust in the log. | Deterministic recompilation, already tested. | The constitution becomes partly public, which is a disclosure decision, not a technical one. |
| **Evidence ledger + Merkle proofs** (`provenance/`) | Proves a record exists and was not altered. | **Polarity flip** — prove non-issuance | Proves **no capability grant was ever minted** for the refused action, via inclusion proof over the grant chain. | Append-only, tamper-evident, O(log n) verification. | Absence proofs are only as strong as the checkpoint cadence. |
| **Capability grants** (9 dimensions, single-use) | Narrow permission to act. | **Negative space** | The *absence* of a grant, provable rather than merely unlogged, becomes the load-bearing fact. | Grants remain unforgeable and expiring. | Requires the grant chain be complete — a gap is indistinguishable from a refusal. |
| **Causal memory** (`memory/causal.py`) | Reconstructs why an outcome occurred. | **Counterfactual extension** | Reconstructs **why an action did not occur** — which policy clause, which missing evidence, which absent grant. | Ancestry over a verifiable chain. | Explanations of refusals may leak policy internals to a probing adversary. |

Each mutation changes role, authority or consequence — not just implementation. None
of these is "use X with Y."

---

## 4. The invention

> **A Refusal Receipt is a portable, independently re-derivable proof that a specific
> action was requested of an autonomous system and refused, by a policy the verifier
> can recompile themselves, at a moment the verifier can place in a tamper-evident
> chain, with cryptographic evidence that no permission for it was ever issued.**

A receipt carries five bindings, each already producible by a PROVEN component:

1. **The request**, hashed — what was actually asked for, including target and consequence class.
2. **The policy in force**, as `constitution_hash` — recompilable by the verifier to the same value, or the receipt is void.
3. **The refusal and its reason**, naming the clause that fired.
4. **A Merkle inclusion proof** placing the refusal in the append-only chain at a checkpointed position, so it cannot be back-dated or removed.
5. **A non-issuance proof** that the grant chain contains no grant matching that request — the negative, made positive.

**Emergent capability:** a counterparty can verify a negative about an autonomous
system *without trusting its operator*. No component does this alone. The gate
decides but does not prove to outsiders. The ledger proves existence but not
authorisation. The compiler is deterministic but reaches nobody. Combined and
mutated, they answer a question nobody can currently answer.

---

## 5. Novelty boundary, stated honestly

**Not novel.** Merkle transparency logs and absence proofs (Certificate Transparency
does exactly this for certificates). Deterministic policy engines (OPA, Cedar).
Hash-chained audit logs. Remote attestation. All mature, all prior art.

**Plausibly novel — the topology.** Binding a *refusal* to a *recompilable policy
hash* and a *proof of non-issuance* in one portable artifact, so the verifier
re-derives the decision instead of trusting the record. Certificate Transparency
proves a certificate was issued; this proves a permission was **not** issued and that
the refusal was **compelled** by a policy the verifier can run.

**Plausibly novel — the incentive geometry.** The operator's interest points toward
producing refusal evidence, because refusals are what reduce their liability. Most
audit systems fight operator incentives; this one rides them. That alignment is the
part I would defend as genuinely unusual.

**Uncertain.** Whether any AI-governance or assurance vendor already ships an
equivalent. I have not run a formal prior-art or patent search and **make no patent
novelty claim.** The nearest analogues above should be checked properly before any
originality is asserted publicly.

---

## 6. Why this attacks exactly the measured constraint

| Spider-Web side | Before | With this invention |
|---|---|---|
| 3 — accepted artifact | 1/5: a receipt format exists, nobody has accepted one | A receipt that answers a question the recipient cannot otherwise answer. Acceptance becomes testable in one conversation. |
| 4 — downstream consequence | 0/5: nothing turns on the artifact | Candidate consequences that already exist in the world: an underwriting decision, a procurement condition, a liability allocation, a post-incident finding. |
| 2 — control point | 3/5 | Unchanged and now load-bearing: Proof/Truth is exactly the super-node this occupies. |

It also converts the ladder's own weakness into a use. The blueprint records that
**HARDENED is unreachable because no reconciled external outcome exists.** A refusal
accepted by an external party *is* an external consequence — the first one available
that requires no payment rail, no entity formation and no money movement.

---

## 7. Omnidirectional consequences, including the ones against it

**Direct beneficiary:** whoever bears downside when an agent acts wrongly — insurer, deploying enterprise, the vendor's customer.

**Silent stakeholder:** the person the refused action would have affected. They never learn they were protected. The receipt is evidence for the operator, not for them. **This is the design's clearest ethical gap and it is not solved here.**

**Adversary — and this is the serious one:** an operator could manufacture refusals to build a reputation for restraint, refusing things it was never going to do. The receipt proves refusal; it does not prove the refusal was *hard*. **Redesign, not a risk note:** a receipt must carry the request's provenance — who or what generated it — so a self-generated request is distinguishable from an externally originated one. Without that field the artifact is theatre, and it should not be built without it.

**Second adversary:** an operator could refuse loudly and act quietly through an unlogged path. The receipt proves nothing about actions that never reached the gate. **Bound honestly:** the artifact's scope is "actions that reached the gate," and it must say so on its face. It is not a proof of total containment, and any marketing that implies otherwise is the harm named in §1.

**Regulator:** likely favourable, but a novel artifact with no standing carries no weight until someone with standing says it does. That is side 4 and it is unsolved.

**Incumbent self-harm:** an AI vendor issuing governance proofs about its own agents is marking its own homework. A third party whose only business is the proof does not have that conflict. That is the counter-position, and it is real.

---

## 8. Cumulative ascent

| Level | Name | Tier | What it adds |
|---|---|---|---|
| 1 **Seed** | Refusal Receipt | `BUILDABLE` today from PROVEN components | Proof of a specific compelled refusal. |
| 2 **Compound** | Refusal Ledger | `BUILDABLE` | A population of refusals over time, from which a *rate* is derivable — the first thing an underwriter can price. |
| 3 **Substrate** | Cross-operator refusal transparency log | `EXPERIMENTAL` | Multiple operators publish to one Merkle log; comparison across operators becomes possible, and gossip makes suppression detectable. Needs a second operator, which does not exist. |
| 4 **Developmental** | Policy evolution under refusal evidence | `EXPERIMENTAL` | The existing evolution loop tunes policy against measured refusal outcomes rather than fixtures. Machinery exists; real outcomes do not. |
| 5 **Cyber-physical institution** | Refusal-conditioned insurance | `FRONTIER` | A premium that moves with verified refusal behaviour. Requires an insurer, an actuarial basis and a regulator. None exist. |
| 6 **Frontier** | Refusal as an interoperability standard | `FRONTIER` | Agents from different vendors exchange refusal proofs as a condition of interaction. Every component exists; the authority to standardise does not. |
| 7 **Science-fiction descendant** | Mutual non-action proof between autonomous institutions | `SCIENCE-FICTION` | Two institutions continuously prove to each other what they are not doing. Depends on capabilities that do not exist at required reliability. Labelled, not smuggled in. |

Levels 1 and 2 are buildable from what this repository already proves. Everything
from 3 onward waits on parties who do not yet exist.

---

## 9. Scoring, with fatal gates applied first

**Fatal gates:** no real emergent capability — *passes*, it verifies a negative
without operator trust. Unchanged repository integration — *passes*, five mechanisms
mutated in role. Dependence on nonexistent technology at the buildable tier —
*passes* at levels 1–2. Authority without accountability — *passes*, it creates no
authority. Incentives rewarding degradation — **conditionally fails** without the
request-provenance field from §7, which is therefore mandatory rather than optional.
Credible path to first experiment — *passes*, one conversation.

| Criterion | Score |
|---|---|
| Mechanism novelty | 6 — components old, topology and incentive geometry plausibly new |
| Emergent capability | 9 — verifying a negative without trusting the operator |
| Causal coherence | 8 |
| Incentive coherence | 8, and only with the §7 provenance field; 4 without it |
| Omnidirectional net benefit | 6 — the silent-stakeholder gap is unresolved |
| Feasibility | 9 — every level-1 component is PROVEN in-repo |
| Capital efficiency | 10 — no new infrastructure, no spend |
| Defensibility | 5 — the mechanism is copyable; the accumulated ledger is not |
| Modularity | 8 |
| Developmental potential | 8 |
| User legibility | 7 — "proof it refused" is explainable in one sentence |
| Graceful failure | 7 — a void receipt is detectably void |

**Average 7.6.** The two lowest scores are the honest ones: defensibility, because
anyone with a policy engine and a Merkle log could copy the mechanism; and
omnidirectional benefit, because the person actually protected never sees the proof.

---

## 10. Minimum experiment

Identical to the Spider-Web decisive test, arrived at independently — which is the
strongest signal in this document.

1. Take a **real refusal that already exists** in the adversarial gate suite — a revoked grant, an effect mismatch, a weak-evidence external-contact refusal.
2. Render it as a Refusal Receipt with all five bindings, including the §7 request-provenance field.
3. Show it to **one** person who underwrites, audits or procures AI systems.
4. Ask one question: *"Would this change a decision you actually make?"*

**Cost:** hours of work and one conversation. **Evidence produced:** the first data
point ever on side 3. **Falsification:** three qualified reviewers say it changes no
decision → side 4 is empty by evidence rather than by absence, and this invention
dies with a recorded reason.

**30 days:** receipt schema drafted, one real refusal rendered, three reviewers
approached. **90 days:** if any reviewer says yes, level 2 (refusal rate) becomes the
next artifact, because a rate is what an underwriter can price.

---

## 11. Decision

**EXPERIMENT.**

Not `BUILD`: the request-provenance field is mandatory and the silent-stakeholder gap
is unresolved, so building the full artifact before one reviewer has seen a draft
would be building on an untested side 3.

Not `RESEARCH`: the components are PROVEN and the experiment costs one conversation.
Further study would be avoidance.

Not `PARK` or `KILL`: this is the only design found that attacks the two measured
zeroes directly, using only what the institution can already prove it has.

**Preserved dissent.** The strongest objection is that this invents a product for the
capability the institution happens to have, rather than for a need someone expressed
— the classic solution-first error, and the fact that it emerged from an asset
inventory is exactly the shape that error takes. The counter is that step 10 tests
demand before anything is built, and the test is cheap enough that being wrong costs
one conversation. That counter is adequate for an experiment and would not be
adequate for a build.
