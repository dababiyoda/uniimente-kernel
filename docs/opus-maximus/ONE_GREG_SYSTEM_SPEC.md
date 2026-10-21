# One GREG System Specification

Deliverable D. This describes the machine as it runs on this branch, not as any document wishes it. Every interface names the file that implements it. Where a part is missing it says so. Reality labels follow the cognition SOP: IMPLEMENTED, INTEGRATED, TESTED, SANDBOXED. Nothing here is MAC-VERIFIED, REBOOT-VERIFIED, EXTERNALLY-VERIFIED or PRODUCTION-AUTHORIZED, and VEPMC is 0.

## 1. One authority path

```text
founder (Ed25519 key, offline)
  -> signed command envelope (kind, body, body_id, nonce, issued/expires, signature)
  -> Body.apply                  verify key, body binding, TTL, unused nonce; journal command.accepted
  -> MissionEngine / Genesis / Goal Gravity binding / LIFECYCLE / STOP
  -> AuthorityOffice.act         one short-lived grant per action, inside the signed light cone
  -> ConsequenceGate             dispatch claim -> adapter -> receipt (or UNCERTAIN)
  -> retained ledger             EvidenceLedger under one EventSpine (greg/journal.py)
  -> separate-process appraiser  python -m greg.appraisal re-derives the closure
```

There is one ledger per body and one mission engine. No organ, worker, model, phone or console holds signing authority. Implementation: `greg/founder.py`, `greg/body.py`, `greg/authority.py`, `policy/consequence_gate.py`, `greg/journal.py`, `greg/appraisal.py`. Reality: INTEGRATED, TESTED.

## 2. Founder commands

`greg/founder.py` `COMMAND_KINDS`:

| Kind | Effect | Who may sign |
|---|---|---|
| `MISSION` | Register a persistent mission; its body carries the light cone | Founder key |
| `DECISION` | Answer one pending request, bound to its exact scope digest | Founder or an enrolled device |
| `LIFECYCLE` | Pause, resume, supersede or abandon one mission | Founder or device |
| `CRITIQUE` | Morning-tribunal critique of retained evidence | Founder or device |
| `CAPABILITY_ATTACH` / `CAPABILITY_DETACH` | Attach a verified capability under a ceiling, or detach it | Founder key |
| `BODY_PAUSE` / `BODY_RESUME` / `BODY_STOP` | Body-wide pause, resume and stop | Founder or device |
| `BODY_DESIGNATE` | Name this body as the intended first execution body | Founder key |
| `NODE_ENROLL` | Admit another compute node with its own bounded identity | Founder key |
| `SOP_RATIFY` | Promote an observed procedure into a reusable capability | Founder key |
| `MODEL_ROUTE_SET` | Replace cognition routes, never authority | Founder key |
| `ROTATE_FOUNDER_KEY`, `DEVICE_ENROLL`, `DEVICE_REVOKE`, `ANCHOR_CONFIGURE` | Key and anchoring administration | Founder key |
| `GOAL` | Authorize a persistent Goal Gravity goal bound to signed missions (#175) | Founder key |
| `GOAL_CONTROL` | Narrow, stop, resume or revoke one admitted goal | Founder; a device only narrows |

Replay rule: the inbox is idempotent on the envelope digest, and a different envelope that reuses a nonce is refused ("replayed command nonce"). A rejected GOAL or GOAL_CONTROL still consumes its nonce (`NONCE_CONSUMED_ON_REJECT`).

## 3. Missions

A mission spec (`greg/templates.py` builds them; `greg/missions.py` runs them) holds:

| Field | Meaning |
|---|---|
| `mission_id`, `founder_expression`, `intended_effect`, `priority`, `closure` | Identity and what counts as done |
| `success_checks[]` | `check_id`, a read-only `sensor` (capability, params, target) and a `predicate` over the sensor's output |
| `strategies[]` | `action_id`, `capability` or `function`, `params`, `target`, `cost_usd`, `advances[]`, optional `bind[]` edges from earlier receipts |
| `light_cone` | `capabilities`, `targets`, `max_consequence_class`, `budget_usd`, `horizon`: the authority envelope |
| `auto_attach` (optional) | `{"max_consequence_class": "read_only"}`: Genesis may attach a qualified read-only construction without asking |
| `standing_reconciliation` (optional, this branch) | `{"consequence_inert": true}`: an interrupted, provably consequence-inert action is settled without asking (section 7) |

The engine is a feedback loop: observe every check, pick the next strategy whose `advances` covers a failing check, act through the Authority Office, re-observe, and close when the checks pass. A missing function opens a `CapabilityDeficit` and routes to Genesis. An action outside the cone or above the ceiling becomes one founder APPROVAL request. An interrupted non-read-only action becomes UNCERTAIN and is never retried blindly. Ordering across missions comes from #178's `greg.gravity.select`; waking and preparing comes from #175's persistent-goal binding (`greg/goal_gravity.py`). Neither adds, drops or widens a mission.

## 4. Capability broker and the Mind

`greg/capabilities.py` registers 105 built-in capabilities. Each manifest declares route, consequence class, credentials, binaries, retry safety and the Spider-Web control points it strengthens; registration refuses one that strengthens none. Lifecycle states: `DISCOVERED`, `VERIFIED`, `ATTACHED`, `DETACHED`, `QUARANTINED`.

`InvocationContext` is the only thing an adapter receives: workspace, read roots, secret broker, manifest, deliver root, artifact root, mission id, authority reference, grant id, policy version, stop check, a read-only capability registry for cognition, the founder-selected model route, the cognition budget, the #26 egress relay when the body confines egress, and the body's worker confinement setting.

The Mind is `greg/cognition/`: the Competency Compiler classifies a bounded problem's geometry, chooses the cheapest competent method (exact solvers, CP-SAT, Z3, LP, Bayesian and causal estimators, collective and basal methods, models last), and returns a typed receipt (SAT/UNSAT/UNKNOWN, FEASIBLE/OPTIMAL/UNVERIFIED, calibrated intervals, or an abstention). A model never confers proof. Reality: INTEGRATED, TESTED; Verified Polyintelligence Lift is 3 of 4 families (`FOUNDER_INTENT_LEDGER.md`, 2026-10-08).

## 5. Capability Genesis (functional morphogenesis)

`greg/genesis.py` and `greg/recombine.py`. Order: attached capability, verified capability attached in signed scope, catalog acquisition of an installed open-source engine, construction by certified reduction onto a qualified engine, then a builder (coding worker). Every candidate is qualified against a frozen oracle in the sandbox before it is VERIFIED. Attachment needs a founder command or a signed read-only `auto_attach`. Faults are repaired by a two-strike rule; a lying engine is quarantined and the construction re-formed over another; recovery restores eligibility, never authority. Reality: INTEGRATED, TESTED (ten-step proof step 5; #178 test stage 3).

## 6. Hands: workers

`greg/workers.py`. One `worker.commission` action is one WorkOrder: objective, acceptance, a private clone, tools, spend cap, timeout. GREG collects the diff, checks scope and protected surfaces, re-runs acceptance with no network, commits on a `greg/` branch inside the private clone, and never pushes. `worker.appraise` re-checks in a fresh clone.

Confinement is the founder's body setting `worker_confinement`:

| Setting | Worker the envelope can confine | Worker it cannot (unreviewed provider, or no bubblewrap) | Acceptance tests |
|---|---|---|---|
| `required` (default) | #157 bubblewrap envelope | Refused before dispatch | Envelope, else refused |
| `supervised` (founder opt-in at `greg init`) | #157 bubblewrap envelope | #178 process supervision; the report says filesystem and network were NOT confined | Envelope, else network denied by seccomp or sandbox-exec with the filesystem not confined |

The script worker never falls back, and a body that confines egress refuses supervision rather than give a worker direct network. A supervised worker runs as the body's user and can read whatever that user can, including a founder key kept on the body; #169's newest commit (`dcb9cd7`) closes that read for confined programs, which is one more reason the default is `required`. Reality: INTEGRATED, TESTED (`tests/unit/test_greg_worker_confinement_setting.py`; ten-step proof uses `required`; #178's whole-machine test uses `supervised`).

## 7. Recovery

Dispatch claims without receipts become UNCERTAIN on restart. The founder answers `reconcile_executed` (DONE, with the signed cap booked when spend is unknown) or `reconcile_not_executed` (one retry). Routing and resilience count one outcome per attempt.

Standing reconciliation (this branch, the selected invention in `INVENTION_LEDGER.md`): when the founder signed `standing_reconciliation.consequence_inert` into the mission, an UNCERTAIN `worker.commission` whose provider is consequence-inert (network namespace closed, no credentials, no paid route, writes only inside a private clone discarded before any retry), whose order left no completed evidence, and which has had fewer than two standing reconciliations, is settled as RECONCILED_NOT_EXECUTED with a recorded proof and retried once. The signed cap held for the interrupted attempt is released, since nothing could be charged. Anything else still asks the founder, and the request lists the predicates that failed.

## 8. Organs

| Path | Contract | Reality |
|---|---|---|
| `organ.exchange` / `organ.status` (#178, `greg/organs.py`) | DALEOBANKS produces an OpportunityPacket and WealthMachine an assessment, each in its own interpreter under Landlock with network denial, signed with the pinned `uniimente-kernel-boundaries` 0.1.2; the kernel verifies both on one mission trace; a second WMI process reproduces the assessment | INTEGRATED, TESTED against real DALEOBANKS `667439f` and WMI `ec82b80` |
| `organs.exchange` / `organs.exchange_status` (this branch, `greg/organ_exchange.py`) | Alternate exchange with replay-protected bridge state and the DALEOBANKS ledger acceptance record | Registered alternate; TESTED against the same heads |
| `venture.assess` (`greg/ventures.py`) | RailScout appraisal to WMI assessment (Bridge A) | TESTED against RailScout PR #9 branch |

Organs never sign as the Kernel and never hold founder authority. Upgrading their pin to per-organ keys is a founder decision.

## 9. Founder surfaces

`greg/console.py` (owner-session console; signs only for its owner), `greg/mission_control.py` (five-question Mission Control rendered from retained events), `greg/remote.py` and `greg/phone/` (device-key channel), `greg/cli.py`. The ten-step proof renders Mission Control at 1920, 1366 and 390 pixels wide in Playwright. Install, STOP, rollback and local-model instructions: `MISSION_CONTROL_OPERATIONS.md`.

## 10. Resource flows

| Flow | Rule | File |
|---|---|---|
| Money | Every priced action is inside the signed `budget_usd`; unknown spend books the signed cap; money is kept in separate columns; no payment rail is called | `greg/missions.py` (`metered_spend`), `greg/workers.py` (`worker_spend`) |
| Models | Local and open-source first; a paid route only by founder `MODEL_ROUTE_SET`; no silent substitution; substitution only from a priced allowlist | `greg/models.py` |
| Compute | Measure and recommend, never self-provision | `greg/compute.py` |
| Founder attention | One ask path with evidence, alternatives, costs and uncertainty; no manufactured urgency | `greg/asks.py` |

## 11. Governance overlays

The Golden 5 are domain evaluations, not a second Kernel: Performance (checks close), Money (budget and booked spend), Floor (Gate refusals, protected surfaces, confinement), Proof (separate-process appraisal), Future (repair, held-out learning, reproducibility). Maturity Gates A-H and the distinction between machine authorization and civic or public governance are preserved unchanged from the founder's sources (`FOUNDER_INTENT_COVERAGE_MATRIX.md`).

## 12. Known gaps

- VEPMC is 0: no run on a founder-designated device with Alfonso's own key.
- Real external transactions: none. The venture loop is a FIXTURE.
- Per-organ keys are not in the organs' pin.
- `browser.session`, paid model routes, anchoring and the DALEOBANKS bridge remain outside the #26 relay; confinement of egress is opt-in.
- `MissionBook` still folds an unsigned `mission.registered` (#175's ADR, P2 second half). The `decision.answered` half closed in next-wave item 7 (2026-10-16): an answer counts only as the record re-derived from a founder-signed DECISION at its own acceptance; any other row stays in `MissionBook.unverified`, moves nothing, and `ledger_closure` reports it. Residuals: a genuine never-applied DECISION smuggled for a request still open, and unsigned `decision.requested`.
