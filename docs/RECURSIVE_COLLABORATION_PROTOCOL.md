# Recursive Collaboration Protocol

This protocol turns collaboration, dissent, and founder-intent preservation into an auditable institutional process.

## 1. Required review roles

Every material architectural change must receive explicit analysis from five roles. One person may perform multiple roles, but each perspective must be recorded separately.

1. **Builder** - strongest implementation case.
2. **Adversary** - strongest failure, abuse, drift, and counterexample case.
3. **Operator** - deployment, maintenance, observability, recovery, and cost.
4. **Beneficiary Representative** - participant welfare, accessibility, dignity, and externalities.
5. **Constitutional Reviewer** - authority, evidence, legality, reversibility, and shutdown integrity.

Disagreement is preserved. Consensus is not manufactured.

## 2. Mandatory alternatives

Every proposal must compare at least:

- proposed design;
- simplest viable design;
- strongest competing design;
- do-nothing / preserve-current-state option;
- staged or reversible experiment.

Each alternative records benefits, liabilities, evidence, dependencies, migration cost, rollback path, and kill criteria.

## 3. Two upward passes

A proposal cannot be marked ready until it completes exactly two strengthening passes.

### Pass 1 - structural inversion

For every advantage:

- identify how it can become a moat, default pathway, interoperability advantage, proof advantage, cost advantage, or participant-welfare flywheel;
- identify the condition under which the advantage reverses into a liability.

For every disadvantage:

- remove it;
- bound it;
- make it observable;
- make it reversible;
- or convert it into a useful constraint, test, modular boundary, market signal, or governance advantage.

### Pass 2 - adversarial compounding

Re-attack the strengthened design as though Pass 1 were already deployed.

- Find new concentration, complexity, incentive, authority, security, maintenance, adoption, and evidence risks.
- Strengthen the design again.
- A Pass-1 downside may not disappear from the record. It must be resolved, accepted with a named owner and threshold, or converted into a kill condition.

## 4. Merge proof

A material change is mergeable only when the record contains:

- founder-intent references;
- system boundary affected;
- all alternatives;
- five-role debate;
- Pass 1 and Pass 2 maps;
- explicit unresolved dissent;
- evidence and counterevidence;
- tests and verifier strength;
- migration and rollback plan;
- operational owner;
- kill criteria;
- decision: `retain`, `regress`, `kill`, `defer`, or `experiment`.

No document, model output, majority vote, reputation score, or reviewer enthusiasm authorizes production effects. The Consequence Gate and human constitutional authority remain final.

## 5. Collaboration norms

- Critique claims and mechanisms, not people.
- Steelman before rejecting.
- Preserve contributor lineage and rejected branches.
- Prefer narrow contracts over duplicated implementations.
- Prefer reversible experiments over argument when the decisive uncertainty is testable.
- Escalate irreducible value conflicts to the founder.
- Record negative and zero results.
- Never hide scope, assumptions, unresolved risk, or contradictory evidence.
- Optimize for shared capability and market health, not collaborator dependence.

## 6. Recursive application

This protocol applies to itself. At each major release, audit whether it improves decision quality, contributor comprehension, cycle time, defect escape rate, duplicated work, and founder-intent fidelity. Retain, revise, or regress it based on measured outcomes.

## 7. Machine-readable records

Sections 1-5 define the process. The record of a decision that has followed it lives in `docs/deliberations/D-NNN-*.json`, and the founder intentions it serves live in `docs/intent/ledger.json`. Both are checked by `tests/unit/test_governance_records.py` in the ordinary suite, so an omitted role, a silently dropped Pass-1 downside, erased dissent, or a decision that contradicts its own second pass fails the build rather than passing review.

The five roles in section 1 are canonical and unchanged. Records use those names.

### 7.1 One addition: `NEEDS_FOUNDER_DECISION`

Section 4 lists five decisions: `retain`, `regress`, `kill`, `defer`, `experiment`. A sixth is added:

- `NEEDS_FOUNDER_DECISION` - the deliberation is complete and its recommendation is clear, but the change is constitutional or authority-changing and no authorized human has approved it.

Section 4 already says that no document, model output, majority vote, reputation score, or reviewer enthusiasm authorizes production effects. That principle previously had no way to be recorded as an outcome, so a constitutional proposal with unanimous support had to be written down as `retain` and wait. Now it is recorded as what it is.

A constitutional or authority-changing record may not resolve to anything else until a named human has actually approved it. Writing `approved` without an approval is fabricated authorization. `tests/unit/test_governance_records.py::TestConstitutionalDecisionsCannotSelfApprove` enforces this, and the first record it stopped was the one installing this section.

### 7.2 Relationship to the external protocol skill

The machine-readable format was adapted from an external founder-intent collaboration protocol. Its record structure and the `NEEDS_FOUNDER_DECISION` state were adopted. Its role vocabulary was **not**: this repository already had five roles, `.github/pull_request_template.md` already uses them, and replacing a working vocabulary to match an imported template would destroy institutional memory for no control advantage.

The external validators therefore do not run clean against these records, by design. They expect their own role names. The authoritative checks are in `tests/`, take no dependency on any file outside this repository, and are the ones that gate the build.