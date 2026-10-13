# RECOMBINE: Capability Genesis constructs new capabilities (2026-10-13)

Invention and integration record for `INTENT-20261013-FRONTIER-LEAP-RECOMBINE`
(directive section 16). One agent wrote, attacked and reviewed this change. That is not
independent peer review.

## Original deficit

Capability Genesis had two ways to supply a missing function:

- **acquire** it: an installed tool, or an open-source package already catalogued with a frozen oracle (DEPEND);
- **commission** it: a builder working against a founder-signed contract.

The rung `RECOMBINE` was named in the reuse ladder but never implemented. A mission that needed staffing with skills, a
one-to-one matching or a cheapest on-time project plan therefore ended at founder
escalation, even though GREG already held certified engines (maximum flow, LP) that
can answer each of these. GREG could swap parts. It could not build a new
function out of the competence it already had.

## Source mechanisms (inspected)

| Source | What was taken |
|---|---|
| `greg/genesis.py`, `greg/mechanisms.py`, `greg/cognition/network.py`, `greg/cognition/linear.py` (this lineage) | The ladder, Mechanism Cards, frozen oracles, and the max-flow and LP certificates. Reused, not copied. |
| Ford and Fulkerson, *Canadian J. Math.* 8 (1956); P. Hall, *J. London Math. Soc.* 10 (1935); Koenig and Egervary (1931) | Max-flow/min-cut duality, and deficiency sets as witnesses of a shortage. |
| J.E. Kelley, *Operations Research* 9(3) (1961); D.R. Fulkerson, *Operations Research* 9(2) (1961) | Time-cost trade-off as a difference-constraint LP. |
| McConnell, Mehlhorn, Naeher and Schweitzer, "Certifying algorithms", *Computer Science Review* 5(2) (2011) | Every answer ships with a witness that a simple checker verifies. |
| NetworkX and SciPy as installed (the versions are recorded in `results.json`) | The engines, through GREG's existing no-network runner. |

## REA observations

REA (`dababiyoda/REA-Reverse-Engineering-Anything`, head `0c6852b`, `rea-agents` 6.1.0,
MIT licence) was inspected:

- **Distribution.** A TypeScript CLI and MCP server. Its binaries are `rea` and `rea-agents`.
- **Providers.** Hopper, Ghidra and IDA are bring-your-own. JavaScript static analysis needs no provider.
- **Runtime.** It requires Node 22.19+. This host has v22.22.2.

REA was **not built or run**. Its dependencies are not installed, and installing them means running a third-party
npm tree. For this leap REA could add nothing that source inspection did not already
give. The mechanisms are published mathematics, the engines' Python source is installed
locally, and the directive itself prefers source over binary reconstruction when source is available. REA established
nothing here. A real REA investigation remains a continuation item. The directive's own example is
a lawful static analysis of how an open-source application recovers from component failure.

## Mechanism extraction

The primitives kept:

- a bipartite transportation network: source → worker (capacity) → order (an uncuttable arc) → sink (demand);
- unit capacities and unit demands;
- start and finish variables with duration bounds and precedence differences;
- certificate checking in exact integers;
- content-addressed identity of executable code.

## Mutation

The mutation is **certificate transport**. An engine's certificate is not just checked
on the engine's own terms and thrown away. It is carried back through each reduction and
re-expressed as a witness about the *original* problem:

- **Staffing.** A residual minimum cut becomes a set of orders together with the only workers able to serve them. Staffed equals demand outside that set plus those workers' capacity, which proves the assignment optimal by weak duality.
- **Matching.** The same witness becomes a Hall violator.
- **Project crashing.** The LP duality certificate on GREG's own encoding is combined with an exact feasibility and cost check against the project. An impossible deadline is proved by a shortest-duration chain with no engine call at all.

## Recombination: why this is new behaviour

1. **One engine serves a growing family of functions.** Each new function costs one reviewed set of reduction functions, plus a brute-force oracle, plus a card. It never costs a new solver.
2. **Reductions chain.** Matching reduces to staffing, which reduces to max-flow. The chain compiler stops at a catalogued engine, at most 3 levels deep, and refuses cycles.
3. **Self-repair works across levels.** An engine that lies is caught *through* the construction. Both are quarantined with the same evidence, the engine is re-acquired from a different package, and the construction is re-formed over it.
4. **Answers are decision-ready.** "8 of 9 units; Dock1 and Dock2 can only be served by Ana and Ben, who are one unit short" is a statement a person can act on, and it is proved, not estimated.

## Implementation

| File | Content |
|---|---|
| `greg/recombine.py` | `Reduction`; staffing, matching and crash reductions; `chain`, `library`, `source_digest`, `chain_digest`, `composed_adapter`, `qualify`; `CARD_FIELDS` (the 20 directive fields) |
| `greg/genesis.py` | `constructed` rung (`_recombine_route`, `_composed_manifest`), `_restore_composed`, engine quarantine in `repair` for faults raised through a construction, `composed:` in `FORMED` and in the fault markers |
| `greg/templates.py` | `constructed_question` (`constructed-question`) |
| `scripts/qualify_recombine.py` | Reproducible stress and reuse measurement, which writes `results.json` |
| `tests/unit/test_greg_recombine.py` | Certificates, chain compiler, end-to-end missions on a real body, lying engine, restart, founder detach, engine detach, card completeness |

The interface is a mission step `{"function": "assignment.staffing", "params": {...}}`, the
same as any other function. Constructed capability ids are
`composed.<function>.<engine provider>.<chain digest>`.

## Authority

**Permitted:**

- a read-only construction, registered VERIFIED only after its own frozen oracle passes through the real engine;
- attachment only by a founder `CAPABILITY_ATTACH`, or by a founder-signed mission `auto_attach` limited to read-only and inside the light cone, which must name both `composed.<function>.*` and `acquired.<engine>.*`.

**Enforced:**

- A construction runs only while its pinned engine is ATTACHED. If the founder detaches the engine, every construction built on it stops.
- A founder-detached construction is never re-attached automatically.
- If the reduction code changes, the construction is quarantined at restart.
- Constructions over non-read-only engines are refused.
- Every answer carries `authority_created: false`.

**Prohibited, unchanged:** spending, publishing, contacting anyone, automatic promotion,
production activation. Who can ratify: Alfonso.

## Evidence

Tests and mutation checks:

- `tests/unit/test_greg_recombine.py`: 16 passed.
- Five targeted mutants were each killed by a test:
  - the engine quarantine in `repair` removed;
  - the founder-detach check removed;
  - the restart digest check removed;
  - the deficiency bound removed;
  - the engine-usable check removed.
- The engine-usable mutant first survived. A test was added for it.

Stress and reuse measurement (`results.json`, from `python scripts/qualify_recombine.py`, 60 seeds).
The environment was Python 3.11.15 on Linux, with NetworkX 3.6.1, SciPy 1.17.1 and NumPy 2.4.6. OR-Tools is
not installed.

| Function | Engine | Cases | Proved without engine | Engine cases | Wrong | Refused |
|---|---|---|---|---|---|---|
| assignment.staffing | NetworkX max-flow | 600 | 0 | 600 | 0 | 0 |
| assignment.staffing | SciPy max-flow | 600 | 0 | 600 | 0 | 0 |
| project.crash | SciPy LP (HiGHS) | 600 | 184 | 416 | 0 | 0 |
| project.crash | OR-Tools LP (GLOP) | not installed | | | | |

Reuse, measured on one engine (`results.json`):

- Qualifying the max-flow engine took 0.23 s: 12 oracle cases plus a scale probe of 300 nodes and 2,942 arcs, in one isolated batch.
- Constructing staffing over that attached engine took 0.22 s for 10 cases. Constructing matching took 0.23 s for 9 cases.
- Neither construction re-qualified the engine. Neither added solver code.

**Negative result, then fixed.** The first version (`results-v1-per-call.json`) took 2.09 s and
1.94 s, so reuse saved re-qualification and solver code but not wall time: each composed
oracle case started its own isolated interpreter. Engine adapters for installed packages now offer
`batch`, which runs one isolated batch under the same pin check and certifies every answer separately.
Composed adapters use it, both in qualification and in service, so a batch of one is the
single call. A test pins qualification to one engine run, and a malformed request in a batch is
refused alone.

Negative results (kept):

- Two hand-made fixtures were wrong:
  - a staffing example that had no shortage;
  - a crash plan costing 12 where 10 is optimal.

  GREG's certificates refused both, and the fixtures were corrected.
- OR-Tools is not installed here, so the GLOP route for `project.crash` is untested.
- No founder use, no external outcome. VEPMC is still 0.

## System impact

The Body, Organs and Mind path now gains a capability without a new engine. Before
this change, an uncatalogued function, a missing contract, or missing founder words for a builder all
ended at escalation. Now any function with a reduction to an engine GREG already trusts closes
the mission with a certified answer. Founder control is unchanged: one signature
pre-authorizes the attach.

## Reconciliation (no duplicate genesis)

Kernel PR #129 (`egregore/genesis.py`, on main's lineage) is a capability-formation loop for
**standing-cognition slots**: proposer and evaluator parts, shadow trials and ratification. `greg/genesis.py` is the
**mission-capability** genesis, and RECOMBINE extends only it. Both share the doctrine
(INTENT-0030) and the ladder. Neither is deleted.

The convergence seam is to let the kernel loop's discovery read `greg/genesis.py`'s registry
and reduction library as a rung once the greg lineage lands on main. That is open work, not done here.

## Continuation (buildable next)

1. ~~Batch composed qualification~~ (done; see above).
2. Let the Competency Compiler's `CAPABILITY_DEFICIT` name a constructible function, so reductions are found from problem geometry and not only from a mission's explicit function.
3. Add reductions that pay for themselves on real missions. Candidates: interval scheduling via LP; minimum-cost assignment via min-cost flow, which first needs a qualified min-cost-flow engine; project selection via min-cut (Picard and Queyranne).
4. Write words templates for staffing and crashing, like `network-in-words`.
5. Run a lawful REA static investigation of a recovery mechanism (directive section 5).
6. Measure Verified Polyintelligence Lift (VPL) on a family that only construction serves.
