# Backcast GPS: GREG's certified mind on Body 1

2026-10-01 · founder corrections on #143 (draft #144) · subordinate to `greg/path.json` · authority change none

Status: a plan for founder review. It changes no node order on `greg/path.json` and grants nothing.
Node N1 (VEPMC) stays the one operationally primary project node.

## Reasoning summary

**Current reality.** In the tested container, GREG solves inside signed missions through one entry
(`cognition.solve`): Z3 and CP-SAT on formal models, schedules in words, estimates, causal questions.
It also forms three functions from open-source engines it did not write (`graph.shortest_path`,
`graph.max_flow`, `lp.optimize`). It accepts their answers only on its own certificate. All of this is
verified in a Linux container. None of it is verified on the founder's machine.

**Control layer.** The engines are commodities: a plain-Python Dijkstra matched NetworkX on the probe.
GREG owns two things:
- **the certificate**, which makes every engine replaceable;
- **the body**, which decides whether any of this exists where Alfonso works.

The second is the gate. `greg/chromebook/install.sh` installs `requirements-dev.txt` only, so a clean
Body 1 carries none of the five engines (Z3, OR-Tools, SciPy, NetworkX, SymPy). Every certified family
verified here is absent on Body 1 by construction.

**Strongest counterexample.** "Keep adding families; Body 1 can catch up later."
- Each family adds tests and records, but no founder-reachable capability until the engines ship.
- VEPMC is still 0, and no real mission has used any geometry.
- Breadth without a body is the cathedral the founder has named twice.

**Selected route.** Make the certified mind installable on Body 1 first; it strengthens N1 directly.
Then finish the proof layer of the families that already exist (prove "no plan exists"). Add new
families only when a real mission asks.

## GPS Lock

| Field | Value |
| --- | --- |
| Destination | Body 1 runs GREG as a supervised service. VEPMC ≥ 1. On that body GREG closes founder-signed missions across the certified geometries, using engines it did not write and certificates it checks itself. Each engine is pinned, and attached and detached only by the founder. |
| Current position | Verified in the tested environment only; VEPMC 0; installer carries 0 of 5 engines. |
| Project-primary node | N1, VEPMC 0 → 1 (Alfonso enables ChromeOS Linux, runs the installer and the runbook mission). |
| Agent command node | A: a clean Body 1 can carry the certified mind. It strengthens N1's gate and competes for no founder time. |
| Active gate (A) | The founder-run installer does not install the engines, and nothing tells the founder which engines are present. |
| Gate-crossing evidence | On a clean install, `greg doctor --chromebook` lists each engine with version, license and the functions it serves. A failed engine install never blocks Body 1. Tested in the container; ARM unverified. |
| Active SBM | Certified engines a clean Body 1 install carries (of 5) |
| Baseline → target | 0 → 5 in the container; Body 1 itself measured at N1 |
| Resource budget | One working session; no new authority, no service, no download by GREG (the founder's installer run downloads) |
| Three-step system | Select one gap between "verified here" and "present on Body 1" → close it with a test → record it in `greg doctor` |
| Review cadence | Every push; again at the founder's first Body 1 run |

## Critical assumption register

| Assumption | Why it matters | Confidence | Cheapest decisive test | Consequence if false |
| --- | --- | --- | --- | --- |
| ChromeOS Linux is available on Alfonso's Chromebook | N1 needs it | Unknown (recorded "Unavailable/unsure" 2026-09-26) | Settings → Advanced → Developers → Linux development environment | Body 1 must change; a founder decision (no Mac owned) |
| Binary wheels exist for Body 1's CPU | Engines install without compiling | Medium (x86_64 yes; ARM likely, unverified) | Installer engine step with binary wheels only, on Body 1 | Those families abstain and GREG asks; N1 unaffected |
| The certificate, not the engine, is the defensible layer | Decides where effort goes | High: local implementations matched the packages; a lying engine was caught | Keep every certificate mutation-tested | None for safety; effort shifts to engines |
| Real missions will need these geometries | Otherwise breadth is waste | Unknown: no real mission yet | Geometry mix of the first 10 real missions | Stop adding families; follow demand |
| One attach per engine is acceptable founder friction | Attach stays with the founder | Unknown | First attach on Body 1 | Signed read-only pre-authorization per mission already exists |

## Route tournament (agent work, 1–10)

| Criterion | Fast: more families | Resilient: Body 1 readiness | Leverage: proof completion |
| --- | --- | --- | --- |
| Probability of success | 9 | 9 | 8 |
| Time to proof | 8 | 9 | 7 |
| Moves N1 or founder use | 2 | 8 | 4 |
| Reversibility | 9 | 9 | 9 |
| Downside exposure | 6 (cathedral) | 8 (install size, ARM) | 9 |
| Optionality created | 6 | 8 | 8 |
| Durability | 5 | 8 | 9 |

**Chosen: Resilient, then Leverage.**
- **Fast loses:** it scores on counts the Spider-Web rule refuses to optimize.
- **Resilient first:** it is the only route that changes what exists on the founder's machine.
- **Leverage second:** it turns each family's "no answer" into a proved answer, which a real mission can settle.

## G — Backcasted success state

**Final state.** All of these hold:
- Alfonso's Chromebook runs GREG as a supervised user service.
- VEPMC has reached 1: a mission closed on Body 1, and Alfonso accepted it.
- The founder-run installer has put the engines on Body 1, and `greg doctor` shows each one with its
  card.
- At least one real founder mission in a certified geometry has closed on Body 1, with its competence
  settled once.
- Any engine can be detached, and its function re-forms from another engine or abstains.

**Time horizon.**
- Agent-side nodes: days.
- N1: gated by the founder's hardware check and one runbook session.
- No date is promised.

**Constraints.**
- No authority is created.
- GREG installs and downloads nothing at runtime.
- Attach stays with the founder.
- Shutdown wins.
- Licenses come from metadata and are shown before attach.

**Superiority.** One certified geometry used on the founder's machine is worth more than ten verified only
in a container. The certificate makes the engine set replaceable, so the asset compounds as engines
improve.

**Entrenchment.**
- Every closed mission leaves a settled competence record.
- Every engine leaves a pinned card.
- Every certificate leaves a mutation-tested proof check.
- All three survive a change of engine or model.

**Warnings.**
- Counting families is not progress.
- A green container is not Body 1.
- Do not add a model route or a paid service to fill a gap.

**Falsification.** Any of these makes G irrational or demands a re-backcast:
- ChromeOS Linux is unavailable and no other founder-owned body exists;
- certified geometries never appear in real missions;
- engine installs repeatedly break Body 1.

## P — Stage-gated plan

Six nodes. Each is a distinct permission, proof standard or owner transition; none merges.

| # | Node | Owner | Gate | SBM | Exit evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| A | Body 1 carries the certified mind | agent | installer omits engines; no engine report | engines carried (of 5) | doctor lists 5 engines on a clean container install; engine failure non-fatal | next |
| N1 | VEPMC 0 → 1 | Alfonso | ChromeOS Linux, installer, runbook mission | VEPMC | founder-accepted closure on Body 1 | primary; founder-held |
| C | Proved negatives | agent | an engine's "infeasible" is relayed, not proved | uncertified-claim share in qualification | elastic-program certificate proves infeasibility and names conflicting limits; a false "infeasible" is refuted | after A |
| D | First real certified mission on Body 1 | Alfonso + agent | N1 | settled real outcomes per geometry | one founder mission closed in a certified geometry; competence settled once | after N1 |
| E | Model baselines | Alfonso | no founder-selected local model | model arms run (of 2) | frozen v0.3 `always_llm`, `tool_llm` arms run | founder-held |
| F | Builder route for cognition (P7 second route) | Alfonso + agent | no builder attached | deficits closed by a builder | one cognition function built against a founder-frozen contract and the same certificate | founder-held |

**Thresholds.**
- **A:** continue while each step is testable in the container. Pivot to `--no-engines` as the
  default if Body 1 storage or ARM wheels fail at N1. Kill if the engine step ever blocks Body 1
  creation.
- **C:** kill if the elastic proof needs a model or a paid service.
- **D:** escalate if the first ten real missions use no certified geometry.

## S — Active node execution card (A)

**1. Select.**
- **Tiny Yes:** the installer installs the engines from binary wheels, best-effort, and `greg doctor`
  reports each engine.
- **Target:** `greg/chromebook/install.sh`, `greg/doctor.py`.
- **Evidence:** tests, plus a doctor report that names engine, version, license and functions.
- **Ceiling:** one session.

**2. Execute.**
- **Trigger:** the current push is green.
- **Action:** add a `--no-engines` opt-out. Install `requirements-cognition.txt` with binary wheels
  only, so a failure warns and Body 1 continues. Add the engine report to the doctor, outside
  `missing`, because engines are not N1 prerequisites.
- **Quality:**
  - the existing installer tests still pass;
  - a new test shows the opt-out parses;
  - the report never makes an engine a prerequisite.
- **Stop:** if the installer change would need sudo or block designation.

**3. Evidence.**
- **Record:** the doctor output in the test, plus a line in the runbook.
- **Decision:** repeat for the next gap between "verified here" and "present on Body 1"; otherwise
  move to node C.

**Operating range.**
- Bad day: the doctor engine report only.
- Standard: report and installer step.
- Maximum: both, plus a runbook line telling Alfonso what to expect.

**Measurement.**
- **Leading:** installer tests green; doctor engine count in the container.
- **Lagging:** doctor engine count on Body 1 at N1.
- **Failure signals:** engine step time over 10 minutes; a source build attempted; designation
  blocked.

## Adversarial defense

- **Attack: a poisoned or changed engine.**
  - Pinned digest; quarantine at restart; certificate on every call.
  - Detach and re-form from the other engine (tested).
- **Concentration: SciPy and NumPy shared by two engines.**
  - The cards disclose it.
  - The certificate shares no code with either.
- **Hardest to reverse: none.** Engines live in the founder's venv and `--no-engines` removes the step.
- **Success creates a new failure:** a larger install on a small Chromebook disk. The doctor reports
  it, and the opt-out exists.

## Probability update

- **Node A clearance (container):** high. The work is local and testable.
- **Total path to G:** unknown, dominated by ChromeOS Linux availability on Alfonso's machine, which no
  agent action changes.
- **Timing:** agent nodes in days; N1 on the founder's schedule.
- **What moved the estimate:** the finding that Body 1 installs no engine. It lowered the value of
  further breadth and raised the value of node A.

## Exact next actions

1. **Agent, now.** Push the verified commits (open-source route, LP, #140 fix) and answer the founder
   comment on #143.
2. **Agent, next.** Node A: installer engine step and doctor engine report, with tests.
3. **Agent, then.** Node C: prove "no plan exists" with the elastic program and refute a false
   "infeasible".
4. **Alfonso, when ready.** Check ChromeOS Linux availability, run `bash greg/chromebook/install.sh`,
   follow `greg/CHROMEBOOK_FIRST_MISSION.md` (N1).
5. **Alfonso, optional.** `greg model set --route ollama --local-model <name> --key …` unlocks node E.

## Process quality gate

**90 / 100.** Nine categories pass. Reality grounding falls short of 100 for one reason: there is no
evidence yet that ChromeOS Linux runs on Alfonso's Chromebook, or of the geometry mix of real missions.
Both arrive only with the founder's first Body 1 session.
