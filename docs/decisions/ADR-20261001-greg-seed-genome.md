# ADR: Converge the cortex onto GREG's mission path as the seed Competency Compiler, as an experiment

- Decision ID: DEL-20261001-greg-seed-genome
- Status: proposed (draft branch `claude/greg-seed-genome-build-y43kmg`)
- Date: 2026-10-01
- Decision owner: Alfonso Lopez
- Founder intent: [`INTENT-20261001-greg-seed-genome`](../intent/INTENT-20261001-greg-seed-genome.json);
  SG-001 to SG-012 in [`intents-greg-seed-genome-20261001.json`](../collaboration/intents-greg-seed-genome-20261001.json);
  verbatim source [`GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md`](../intent/sources/GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md)
- Requirement map: [`requirements-greg-seed-genome-20261001.json`](../collaboration/requirements-greg-seed-genome-20261001.json)
  (122 crosswalk rows, 8 ambiguities, 11 completion conditions; 18 fields each)
- Deliberation: [`deliberation-greg-seed-genome-20261001.json`](../collaboration/deliberation-greg-seed-genome-20261001.json)
  (passes the protocol's `validate_deliberation.py`; one agent performed all five roles, which is a limitation)

## Decisions

| Decision | State | Who decides |
| --- | --- | --- |
| Build the reversible seed on a draft branch and test its claimed advantage | `EXPERIMENT` | authorized by the directive; this record |
| Merge to main or promote any organ beyond SANDBOXED (changes shared contracts on main) | `NEEDS_FOUNDER_DECISION` | Alfonso |
| External advancement of the cognitive substrate (Spider-Web gate) | **Stage-gate** | Alfonso, on an external actor's acceptance |
| Hard-gate high privacy harm (SG-012) | `NEEDS_FOUNDER_DECISION` | Alfonso |

## Problem

GREG had two cognition lineages that did not meet: #140's operations inside signed missions and #141's
cortex as a separate package with its own registry, receipts and evaluation. A third (#139) sat on a
branch. The directive asks for one Competency Compiler on the real GREG path, with its advantage proven
by a frozen comparison against GREG's own baselines, and no growth in authority.

## Decision

Converge through a bridge: `cognition.solve` dispatches the cortex dialect to a bounded worker; the
cortex organs are ordinary GREG manifests the founder can detach; the GREG receipt wraps the cortex
receipt; competence settles once through the existing appraisal. #139 is placed on the path, not
merged (a second package would be a second registry). Keep the decision `EXPERIMENT`.

## Evidence

| Claim | Tier | Location | Finding |
| --- | --- | --- | --- |
| Integrated and durable | sandbox execution | `tests/evidence/greg-cortex-rehearsal/rehearsal-summary.json` | kill -9 while waiting, restart, approve: 1 write, 2 VERIFIED appraisals, 1 settlement per mission; detach survives restart; stop stays stopped |
| Safeguards load-bearing | unit test | `tests/evidence/cortex-mutants-2026-10-01/run3-v0.2.1.log` | 41 mutants, 0 survived (first run: 2 survived; both now pinned) |
| First frozen comparison | deterministic fixture | `tests/evidence/greg-crossgeo-v0.2/results.json` | `GAIN_ABSENT`: one hard failure, a misclassified high-consequence problem recommended (static router too) |
| Second frozen comparison, fresh samples | deterministic fixture | `tests/evidence/greg-crossgeo-v0.3/results.json` | `GAIN_VERIFIED_AGAINST_RUN_BASELINES`: gain 0.0064 (0.0044–0.0084) over the static router, 25.6% relative, 0 hard failures |
| What the gain is | post-hoc decomposition | same file | about all of it is incomparable trade-offs handed to the founder; elsewhere ties or trails by worker latency |
| Model baselines | — | same file | `NOT_RUN`: no founder-selected loopback model; downloads egress-blocked |
| Routing is not new | primary source | SATzilla (arXiv 1111.2249) | per-instance algorithm portfolios are direct precedent |

## Consequences

- GREG can now take a bounded problem (a formal model, an estimate, a causal question, evidence for a
  claim, options, or a schedule in controlled words) inside a signed mission and return typed,
  independently checked computation with a receipt that settles competence once across restarts.
- The cortex is not shown to beat a model. Against a static table with the same organs it wins only by
  escalating incomparable trade-offs; that is a disposition rule, cheap to copy into the static table.
- Each problem costs a worker process (median 0.22 s).

## Correction, 2026-10-01: open-source supply on the genesis path

Alfonso's comment on this PR (draft #144) made open-source mechanisms construction supply and ended
VEPMC's use as a stopping condition. Decision record:
[`deliberation-greg-open-source-genesis-20261001.json`](../collaboration/deliberation-greg-open-source-genesis-20261001.json),
decision `EXPERIMENT`, authority change none.

- Genesis now forms `graph.shortest_path` and `graph.max_flow` from installed NetworkX or SciPy, and
  `lp.optimize` from SciPy's HiGHS or OR-Tools GLOP (DEPEND).
  GREG installs nothing. Attach stays with the founder (console button or `greg attach`) unless a signed
  mission pre-authorizes a read-only attach.
- Every answer passes a GREG certificate that shares no code with the engine. A lying engine is
  quarantined and replaced by a different package; it is not re-admitted without the founder.
- Kill if an uncertified answer is ever accepted, if GREG installs or downloads a package, or if a
  quarantined package returns without the founder.

## Rollback

`greg detach cognition.cortex` (founder-signed) withholds the router at once; reverting the branch
removes it. #140 operation requests and retained receipts stay valid without it (tested).

## Kill criteria

- The routed system loses to the strongest run baseline beyond the predeclared margin on two
  consecutive frozen comparisons.
- Any receipt that creates authority, or any duplicate settlement after restart.

## Review trigger

A founder-selected local model on Body 1 (the model arms run on the frozen v0.3 suite), the founder's
N1 Chromebook run, or a P4 learned-routing comparison.
