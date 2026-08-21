# Phase 2 Decision — Governed Functional Regeneration

**Field B (Function Continuity Contract) + Field E (Obligation-Preserving Succession).**
Not Field A. The provisional name *Proof-Carrying Organogenesis* was challenged and **rejected**.

## The hidden assumption, found by inspection not by reasoning

I expected the gap to be organ birth. It is not. Inspecting the corpus first:

| Already implemented | Where | Evidence |
|---|---|---|
| Deficit detection | `evolution/repair/detector.py` | `FunctionLossDetector` — "observes a capability and reports whether the institution still has it" |
| Function contracts independent of implementation | `evolution/repair/` | `DeclaredContract`, required edges/properties |
| Candidate generation + **blind held-out evaluation** | `evolution/repair/candidate.py` | `CapabilityProviderRegistry`, `ResolverCandidate`, `HeldOutCorpora` ("how the detector stays blind") |
| Organ admission with human ratification | `omnimorph/engine.py` | `compose → simulate → propose_activation → record_gate_activation → retire` |
| Set-point error fields | `morphogenesis/` | `MorphogeneticSetPoint`, `Direction`, `rank_actions` |
| Portable exact authority | `aperture/` | Gate D closed |

118 repair tests pass. **Organogenesis is largely solved.** So Field A would have been re-inventing what exists — the exact "integration dressed as invention" this project keeps correcting.

**What is actually missing**, three findings from reading the source:

1. `OrganManifest.objective` is a bare `str`. An organ *names* its purpose; it does not reference anything that outlives it. Retire the organ and the purpose retires with it.
2. **`grep aperture|certificate` across `evolution/repair/` returns nothing.** Repair swaps a replacement provider in with *no organ identity and no certificate*. Regeneration today is invisible to the authority system.
3. `OmnimorphEngine.retire()` takes a `reconciliation_ref` **hash**. Nothing holds unresolved duties, so nothing can carry them across a replacement. Obligations are referenced, never transferred.

**The gap is that nothing persists at the function level.** The institution can notice a loss and build a replacement, but has no object saying *"this duty is still owed, by whoever now performs it."*

## The invention

`regeneration/` adds the missing state and makes five separations executable:

```
function identity      is not  organ identity
organ identity         is not  workload identity
workload identity      is not  authority
authority              is not  obligation
obligation continuity  is not  permission inheritance
```

The last is load-bearing. **A successor inherits duties and evidence. It never inherits identity or permission.**

Refused by construction, not by policy: self-ratified admission; reusing a retired organ identity; a successor whose topology is not materially different in ≥2 dimensions (compared on *values*, so renaming changes nothing); a successor handed its predecessor's authority record; retiring an organ that still owes open obligations; discharging an obligation without evidence.

Three powers, three components: `CandidateFormer` proposes and cannot admit or authorize · `FunctionRegistry` admits and cannot authorize · `AuthorityIssuer` authorizes and does not choose topologies.

## Result

10/10 recoveries, 3/3 held-out, 10 distinct replacement forms, 60 candidates formed and 5 rejected, 0 inherited-authority events, 0 unauthorized external effects. Predecessor certificate refused every time (`certificate_revoked`); predecessor identity refused every time (`actor_mismatch`); a valid successor certificate with the local veto engaged still yields `local_veto` and 0 external writes.

| Strategy | Recoveries / 10 |
|---|---:|
| do nothing | 0 |
| restart same implementation | 1 |
| identical replica | 1 |
| hardcoded backup | 7 |
| conventional orchestration | 8 |
| **centralized planner (upper bound)** | **10** |
| **the invention** | **10** |

**Read this honestly.** The invention *matches* the planner ceiling; it does not beat it, and cannot — the ceiling is set by the capability pool. It beats conventional orchestration 10 vs 8. What it adds over a planner is **governance**, which a planner does not provide at all.

## Surviving attacks

- **Bounded local knowledge is unproven.** §11 was not implemented; the former sees the whole pool. The *morphogenetic* claim of local competency is not demonstrated — only governed succession is.
- **"Held-out" means an unused former seed schedule, not an unseen capability vocabulary.** Weaker than it sounds.
- **Damage is harness-injected.** Detection is not wired to `FunctionLossDetector`; that connection is conceptual so far.
- **The function contract may favour decomposable topologies.** A function with one viable body would show nothing.
- **Complexity over baseline is real:** +2 vs conventional orchestration, for ~600 lines plus governance the baseline lacks.
