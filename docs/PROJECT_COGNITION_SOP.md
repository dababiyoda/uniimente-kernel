# UNIIMENTE Project Cognition and Agent Handoff SOP

Status: **mandatory collaboration procedure on this development branch**. This SOP creates no runtime authority.

## 0. Purpose

UNIIMENTE is developed across ChatGPT project conversations, Project source files, GitHub repositories, branches, pull requests, issues, experiments, failures, external research and multiple coding agents. Context loss is therefore an architectural failure mode.

The SOP makes project cognition cumulative. An agent entering any material workstream must be able to reconstruct:

- what Alfonso actually intends;
- which statements are latest and controlling;
- what has genuinely been implemented;
- what is only proposed, simulated, tested or historical;
- what previous failures taught;
- which mechanisms should survive even when an old architecture should not;
- what other agents are doing;
- which bottleneck matters now;
- what the next executable product step is.

The goal is not to make every agent read every byte before every typo. The goal is that **no material product decision may be made from a context island**.

## 1. One mind, many workers

All coding agents are temporary workers serving one persistent institutional project.

They do not own independent interpretations of UNIIMENTE.

Canonical human authority: Alfonso Lopez.

Canonical engineering posture:

> models reason -> agents propose/build within delegated development scope -> authenticated authority/policy decides consequences -> reality determines whether the result worked.

No worker may manufacture authority from intelligence, task success, test coverage, model confidence, or another worker's assertion.

## 2. Mandatory entry sequence

Before substantive work, every agent must:

1. Read `AGENTS.md`.
2. Read `CLAUDE.md` when operating as Claude/Claude Code.
3. Read `.github/copilot-instructions.md` when that surface applies.
4. Read `docs/FOUNDER_EFFECT_COMPILER.md`.
5. Read `docs/FOUNDER_INTENT_LEDGER.md`.
6. Read `docs/RECURSIVE_COLLABORATION_PROTOCOL.md`.
7. Read `docs/PROJECT_SOURCE_CENSUS_2026-09-26.md`.
8. Read `docs/intent/INTENT-2026-09-26-REAL-PRODUCT-METABOLISM.json` and its verbatim source.
9. Read the current active intent records relevant to the task.
10. Inspect current code, tests, evidence, open PRs/issues and branch ancestry for the subsystem being touched.
11. Search the Project source census for every source family materially relevant to the decision.
12. Inspect the relevant organ repositories rather than assuming Kernel summaries are current.
13. State unavailable context explicitly.

Do not claim "all project context" unless the source inventory and raw material were actually accessible and inspected.

## 3. Context reconstruction packet

Before changing architecture, canonical ownership, authority, evidence semantics, mission semantics, capability registration, persistent runtime, business routing or cross-repository contracts, write a short Context Reconstruction Packet in the PR/issue:

### Founder intent
- exact controlling founder language;
- source/intent IDs;
- intended observable effect;
- latest correction that changes older interpretations.

### Current reality
- IMPLEMENTED;
- INTEGRATED;
- TESTED;
- SANDBOXED;
- LOCAL-REAL;
- MAC-VERIFIED;
- PERSISTENT;
- REBOOT-VERIFIED;
- EXTERNALLY-VERIFIED;
- PRODUCTION-AUTHORIZED;
- PROPOSED;
- BLOCKED;
- ASPIRATIONAL.

### Source coverage
- exact GitHub files/PRs/issues/branches inspected;
- Project source families searched;
- organ repos inspected;
- unavailable sources.

### Contradictions
- old interpretation;
- newer correction;
- resolution;
- mechanism/evidence retained from the old work.

### Product delta
- capability missing before;
- capability that will exist after;
- acceptance test;
- falsifier;
- effect on the current Single Bottleneck Metric.

## 4. Source hierarchy and contradiction protocol

When sources disagree:

1. Preserve both as provenance.
2. Identify whether disagreement is factual, temporal, architectural or interpretive.
3. Latest explicit Alfonso instruction outranks older model interpretations.
4. Current executable evidence outranks prose about what is implemented.
5. Constitutional authority constraints are not weakened by aspirational autonomy language.
6. A later correction may regress an architecture without destroying useful mechanisms discovered inside it.
7. Record the reconciliation in the PR/issue and, if durable, in Founder Intent Ledger/intent records.

Never silently rewrite history to make the project appear more coherent than it was.

## 5. Project source ingestion

When Alfonso supplies a new project conversation, source, transcript, screenshot, repository, research report or correction:

1. Preserve the original source or a faithful verbatim excerpt when technically/legalistically appropriate.
2. Record date, provenance and whether it is founder language, model analysis, external research or executable evidence.
3. Extract durable founder intent separately from analysis.
4. Map it to affected systems.
5. Identify conflicts with existing intent.
6. Update the Founder Intent Ledger if durable.
7. Update the Project Source Census when a new source is exported into repository-accessible form.
8. Update the relevant issue/PR coordination surfaces.
9. If it changes another organ, propagate a concise cross-repo handoff.
10. Never turn chat text itself into runtime authority.

## 6. Repository metabolism

Every material historical implementation encountered receives one disposition:

- **PRODUCTIZE** — already belongs on the real GREG path.
- **EXTRACT** — architecture should not survive, but a mechanism should.
- **RECOMBINE** — complementary mechanisms become one stronger capability.
- **RETAIN_AS_EVIDENCE** — failure, benchmark, adversarial case or research remains useful.
- **ARCHIVE** — lineage remains but does not direct active architecture.
- **KILL_ACTIVE_COMPLEXITY** — remove from the active canonical path after proof of supersession; preserve history.

Questions for every artifact:

- What causal mechanism is actually here?
- What state transition does it implement?
- What authority does it require?
- What evidence does it create?
- What failure does it detect or recover from?
- What product capability does it strengthen?
- Does a simpler mature mechanism already exist?
- Is it duplicated elsewhere?
- Does retaining it create a second semantic/authority owner?
- Can its strongest mechanism be recombined with another implementation?

Mechanism Recombination Foundry is a method, not a reason to create another permanent framework.

## 7. Spider-Web product selection

The governing transaction is:

**Alfonso expresses an authorized intention -> GREG converts it into a verified outcome -> evidence/capability from that outcome makes the next intention easier to execute.**

Every retained capability should strengthen one or more:

1. eligibility / authority;
2. routing / coordination;
3. proof / truth;
4. settlement / outcome;
5. reliability / recovery;
6. capability formation;
7. economic / computational compounding.

Prefer capabilities that reinforce other capabilities.

Reject decorative complexity.

## 8. Product-first implementation rule

Current bottleneck until verified otherwise:

**VEPMC 0 -> 1.**

A substantial coding session is not complete merely because it created:

- architecture;
- documentation;
- tests;
- a simulation;
- a benchmark;
- an experiment;
- generated code;
- another agent;
- another framework;
- another PR.

Those may be necessary evidence.

The mandatory question is:

> **What can the actual GREG do after this work that it could not do before?**

If there is no direct product delta, identify the precise blocker the work removes and why the product cannot advance without it.

## 9. Acquire before inventing

Use this order unless evidence justifies deviation:

existing capability -> reconfigure -> compose -> commodity mechanism -> open source -> API/plugin/service -> authorized computer use -> bounded adapter -> coding agent/team -> mechanism recombination -> genuinely new architecture.

Do not rebuild commodity OS/database/browser/container/scheduler/message-bus/secret-store/authentication/networking infrastructure merely because an old source used a sovereignty metaphor.

Own the control plane and strategically differentiating mechanisms. Rent/adopt commodity mechanics when they are stronger.

## 10. Communication surfaces — keep them synchronized

Material durable corrections must propagate to the smallest sufficient set of:

- `AGENTS.md`;
- `CLAUDE.md`;
- `.github/copilot-instructions.md`;
- Founder Intent Ledger;
- active intent record + verbatim source;
- Project Source Census;
- this SOP;
- canonical coordination issue;
- affected PR conversations/reviews;
- affected organ repositories;
- PR template / issue template;
- README only when the product entry story changes;
- architecture ownership/build order only when ownership/order genuinely changes.

Do not spam every issue with identical text. Populate surfaces according to function.

## 11. Cross-agent handoff

Before ending a substantial session, leave a handoff containing:

- branch / commit / PR;
- exact product capability added;
- exact files changed;
- tests/evidence run;
- negative evidence and failed attempts;
- reality status;
- authority assumptions;
- unresolved contradictions;
- external blockers;
- current VEPMC status;
- next executable bottleneck;
- which Project sources materially influenced the work;
- which agents/workstreams should consume the result.

If another open PR now duplicates or conflicts with the work, comment there.

## 12. Pull request requirements

Every material PR must include:

- Founder-intent trace.
- Context Reconstruction Packet.
- Product delta.
- Repository-metabolism dispositions for superseded/duplicated work.
- Authority analysis.
- Reality gradient.
- Tests and independent evidence.
- Negative evidence.
- Rollback.
- Cross-repo effects.
- VEPMC impact.
- Next executable step.

For constitutional/canonical ownership changes, apply the Recursive Founder-Intent Collaboration Protocol's deliberation requirements.

## 13. Issue requirements

Agent-created implementation issues should state:

- desired product effect;
- current blocker;
- controlling founder intent;
- source coverage;
- current owner;
- dependencies;
- acceptance test;
- falsifier;
- authority ceiling;
- artifact disposition expected;
- why this is higher leverage than the strongest alternative.

## 14. Failure is institutional memory

Never hide failed tests, failed experiments, abandoned architectures, wrong interpretations or rejected approaches merely because they are embarrassing.

Extract:

- failure condition;
- detection signature;
- causal explanation;
- mechanism worth preserving;
- rule that prevents recurrence;
- whether it becomes an adversarial test, fallback, benchmark or archive.

A failed architecture can be a successful source of mechanisms.

## 15. Organs and cross-repository ownership

Kernel owns shared constitutional concerns: authority, shared evidence truth, identity/governance contracts and canonical consequence boundaries.

Organs own domain capability, not sovereignty.

Examples:

- RailScout: research/evidence capability.
- DALEOBANKS: public identity, media/community/distribution capability.
- WMI: economic/opportunity reasoning and regenerative transaction mechanisms.
- PumpStation: funded-activity/economic primitive as authorized.
- future organs: bounded reusable capability with explicit contracts/lifecycle.

If an organ recreates Kernel authority/evidence/mission truth, stop and reconcile.

## 16. Community influence

Community/public input may influence evidence, priorities, hypotheses, language and product learning.

It does not automatically become authority.

Outbound influence must preserve truth, consent, welfare and legitimate refusal. Engagement is an instrument, not a terminal objective.

## 17. Capability Genesis

A real CapabilityDeficit loop is:

active mission -> detect missing capability -> search internal registry/history -> search mature external mechanisms -> compare candidates -> acquire/adapt/compose/build residual -> test against frozen acceptance criteria -> independent verification -> register -> obtain fresh bounded authority if required -> attach -> resume the **original** mission -> measure real outcome -> retain/modify/detach/kill.

The detour is not mission completion.

## 18. Reality and evidence language

Never collapse:

- code exists;
- code is integrated;
- tests pass;
- sandbox works;
- local real effect occurred;
- founder used it;
- survives reboot;
- external outcome verified;
- production authorized.

Use the narrowest truthful label.

## 19. Developmental authority

UNIIMENTE remains in founder-guided development.

Development may include real local code, real tools, real repository reads, bounded tests and reversible integration.

It does not automatically authorize:

- production deployment;
- spending;
- customer contact;
- public publishing;
- live financial action;
- credential expansion;
- protected/default branch merge;
- removal of shutdown authority.

## 20. Definition of a good agent session

A strong session leaves:

1. more accurate institutional truth;
2. less duplicate active architecture;
3. at least one stronger real product capability or a proven blocker removal;
4. preserved negative evidence;
5. a clean handoff;
6. no unauthorized consequence;
7. a clearer next bottleneck.

A weak session leaves another impressive document, another isolated experiment, another unintegrated framework, or another interpretation future agents must rediscover.

## 21. Founder quotes that should remain visible

> "BUILD THE MACHINE ALFONSO ACTUALLY MEANS."

> "Do not return with another cathedral."

> "actually build the product, stop experimenting, stop simulating, stop doing dumb shit, and actually do the thing. Build it."

> "So if it's some random experiment, it can build it into a real tool that the egregore can use for whatever use case, right? It's gonna build it."

These quotes are preserved more fully in `docs/intent/sources/REAL-PRODUCT-METABOLISM-2026-09-26-source.md`.

## 22. Exit question

Before an agent stops, it must be able to answer:

**What did I make more real?**

If the answer is unclear, the work is not yet adequately connected to the Opus Maximus.
