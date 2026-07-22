# Build Order: ten phases, stage-gated

Authority: canonical architecture, Section XXXII. No phase starts before the prior phase's exit evidence exists.

## Phase 1: Canonical Kernel Repository (THIS REPOSITORY)

Build: shared schemas, Constitution in UCL, authority matrix, legal principals, capability grants, event envelope, decision record, outcome record, organ registry, shutdown policy.

Exit evidence: all Section XXVI artifacts present; contracts validate; doctrine tests specified.

## Phase 2: Extract Shared Governance

Move reusable mechanisms from DALEOBANKS into Kernel modules: decision ledger, raw vault, ContextPackets, prompt firewall, operator approval, kill switch, heartbeat, identity gate, constitutional integrity verification.

Exit evidence: DALEOBANKS imports these services; no duplicated governance logic; DALEOBANKS test suite green against the shared modules.

## Phase 3: Unify Protocols

Move OpportunityPacket and VentureAssessment into this repository's versioned contract package. DALEOBANKS, RailScout, and WealthMachine import the same contract. No mirrored copies.

Exit evidence: both repositories delete their mirrored wire contracts and pass wire-parity tests against `/contracts` version 1.1.

## Phase 4: Event Spine and Workflow State

Implement typed events, durable workflows, retries, approval waits, state reconstruction, outcome capture.

Exit evidence: a workflow killed mid-execution resumes and completes with no manual restatement of state; every event carries identity, legal principal, causal parent, and policy version.

## Phase 5: Commit-Time Action Gateway

All external actions pass through: `propose()` -> `evaluate_policy()` -> `request_approval()` -> `issue_capability()` -> `reauthorize_at_commit()` -> `execute()` -> `record_outcome()`.

Exit evidence: no repository can communicate directly with production accounts; expired or revoked grants fail closed at commit time in adversarial tests.

## Phase 5B: Proof-to-Settlement Trust Rail (SANDBOX EXECUTABLE)

Turn a reconciled action into independent verifier proof, a portable outcome credential, legal-principal-signed settlement authority, an idempotent adapter receipt, reconciliation, dispute state, and scoped reputation. OpenClaw reaches it through an external MCP boundary with named executors and no payment-commit tool.

Exit evidence: 30 adversarial tests green; all five orthogonal closures green; ledger tamper, self-verification, signature mutation, amount overflow, replay, disputed proof, live/sandbox mismatch, and bad adapter receipts fail closed with zero unauthorized external effects. A live bank or blockchain adapter remains a separate legal, security, and operational gate.

## Phase 6: IVIO Closed Loop

Run one complete signal-to-buyer-response workflow for 30 consecutive days: signal -> evidence -> assessment -> approval -> action -> external response -> learning.

Exit evidence: one verified external buyer response; 100% identity, legal-principal, authorization, provenance, budget, and outcome coverage; zero unauthorized external effects; no manual reconstruction of lost context. No additional Venture Cell receives Level 3 autonomy before this loop succeeds.

## Phase 7: Causal Memory and Affect

Add decision precedent, outcome weighting, confidence calibration, Identity Homeostasis, functional affect, institutional learning.

Exit evidence: affect states have attributable triggers, ceilings, decay, and authority ceilings in `/affect`; no affect state can change facts, create evidence, increase authority, override law, resist shutdown, or authorize irreversible action; pathological-state tests pass.

## Phase 8: Agent Cell Sandboxing

Add isolated, typed, revocable capability execution environments.

Exit evidence: a research cell holding only read-packet, query-approved-sources, write-isolated-workspace, and submit-recommendation capabilities cannot reach secrets, customers, publishing, money, policy, the Constitution, or unrelated cell memory in adversarial tests.

## Phase 9: Portfolio Governor

Begin allocating attention and small experimental budgets across validated opportunities.

Exit evidence: allocation recommendations follow the constrained formula in `/capital/allocation-policy.yaml`; no score independently authorizes spending; termination discipline is exercised at least once.

## Phase 10: External Productization

Only after internal proof: publish schemas, release SDKs, create the managed control plane, package the first vertical governance product, recruit design partners.

Exit evidence: measurable internal benefit over a simpler governed workflow (authorized completion rate up, founder intervention per verified outcome down, state continuity proven).

## Global termination trigger

Suspend autonomous expansion if any component can alter its own authority, bypass the action gateway, conceal negative evidence, spend outside its grant, resist shutdown, act without a named legal principal, or generate substantial activity without changing an external outcome. Do not continue building the general platform if the Kernel adds substantial complexity without improving authorized completion, state continuity, evidence integrity, or Alfonso Sovereignty Gain over a simpler governed workflow.
