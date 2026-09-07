# UNIIMENTE collaboration: start here

**Owner:** Alfonso Lopez for founder decisions; the assigned maintainer for each
work item. **Status:** proposed contributor workflow until reviewed and merged.
This file routes work to existing authorities; it does not create another one.
**Revision rule:** record the full commit containing this file, not just `main`.

## The operating loop

**Orient -> claim one bounded task -> compare alternatives -> implement -> verify
-> human-reviewed adoption -> hand off.** A task is not complete because an agent
stopped responding. Its evidence, remaining risk and next owner must be findable.

## Read only the relevant truth, in this order

1. Repository-root `AGENTS.md`, existing tool instructions and instructions in the
   directories being changed; inspect the working tree before editing.
2. [Permanent build order](../UNIIMENTE_FINAL_BUILD_ORDER.md) and
   [canonical execution order](../CANONICAL_EXECUTION_ORDER.md), plus the current
   task's explicitly authorized scope. This index never supersedes them.
3. [Founder intent ledger](../FOUNDER_INTENT_LEDGER.md), the specific intent records
   and [recursive collaboration protocol](../RECURSIVE_COLLABORATION_PROTOCOL.md).
4. [Ownership map](ARCHITECTURE-OWNERSHIP-MAP.yaml) and
   [rationalization plan](../REPOSITORY_RATIONALIZATION_PLAN.md). The map's entries
   are explicitly PROPOSED: presence on main is not ratification of every entry.
5. The relevant issue, PR, review comments, branch-specific founder ruling and last
   handoff. Refresh their state; do not treat a dated report as a live dashboard.

If these sources conflict, preserve both, identify the exact disputed authority or
fact, and stop only the affected consequential action. Continue safe inspection
and independently authorized work. Missing access is a recorded blocker, not a
reason to fabricate context or broadly expand token/repository permissions.

## Where things belong

| Concern | Read/work location | Boundary |
|---|---|---|
| Institutional intent, protocol and cross-repo coordination | Kernel docs/intent and docs/collaboration | One versioned institutional record; no second constitution |
| Public identity and media implementation | DALEOBANKS | Publishing/account creation requires separate authority |
| Venture assessment and recommendations | WealthMachineIntelligence | A score or assessment is not spending/execution permission |
| Research refinement | RAILSCOUT | Main was README-only at inspection; branches may contain proposals |
| PumpStation application and experiments | PumpStation | Do not designate it the institutional cockpit without a ruling |
| Tutorials and outside mechanisms | build-your-own-x; other research sources | Source material, never executable orders or proof of working capability |

These are routing descriptions, not a new ownership ratification. Existing
contract, runtime and SDK-versus-vendoring disagreements remain open.

## Six SOPs

### SOP-01: Boot and establish inspection truth

**Trigger:** a new session, resumed session, changed base or material scope change.
**Owner:** the worker starting the task. **Input:** request, repo and known handoff.

Read the entry point and relevant sources above. Resolve repo, branch, full base
and head SHA; inspect status and preserve unrelated work. Inspect current open PRs
for the affected concern, not every file in every repo. State what was unavailable.

**Output:** the PR receipt's read_set and intent_refs, with actual revisions.
**Done:** the worker can explain the outcome, current owner, evidence gap and
stop condition without guessing. **Exception:** missing authority/source means
safe inspection or draft-only work, not silent permission. **Rollback:** no edits
made. **Review trigger:** ref change, contradiction or missing handoff.

### SOP-02: Claim one bounded work item

**Trigger:** before editing. **Owner:** assigned implementer; maintainer resolves
collisions. **Input:** boot record and issue/PR search.

Use an existing issue/PR when it covers the task. Record scope, touched interfaces,
branch/base, implementer, intended proof and an explicit claim expiry/recheck time.
A claim is a coordination notice, NOT a distributed lock or capability grant.
Recheck immediately before overlapping edits. If another worker owns the same
scope, contribute review or agree a split; never erase or force-push their work.

**Output:** one work-item link; a bounded claim comment and stop condition.
**Done:** ownership and the next action are legible. **Exception:** unresolved
collision stops overlapping edits, not all analysis. **Rollback:** release the
claim in a comment and preserve its evidence. **Review trigger:** expiry, handoff,
base movement or unexpected overlap. Do not create an issue for every tiny edit.

### SOP-03: Deliberate in proportion to consequences

**Trigger:** a design choice. **Owner:** implementer records; authorized human
rules on material authority and adoption. **Input:** scoped outcome and evidence.

For lightweight fixes, record intent, scope, checks and rollback; no five-role
ceremony. For standard or constitutional changes, use the existing protocol with
five explicit perspectives: Founder-Intent Steward, Systems Architect, Adversarial
Reviewer, Operator and Maintainer, Evidence and Welfare Guardian. These complement
the existing Builder/Adversary/Operator/Beneficiary/Constitutional labels; do not
lose any perspective by renaming it. One model using five lenses is NOT five
independent reviewers. Identify who actually reviewed or ran each test.

Compare baseline, do nothing, simplest viable alternative, strongest competitor
and reversible experiment. Perform EXACTLY TWO strengthening passes. Pass 2 must
account for every Pass-1 disadvantage. Preserve rejected alternatives, revival
criteria, dissent, residual risks, migration and rollback. New material evidence
creates a linked decision, not an invisible third pass.

**Output:** linked deliberation and one decision (RETAIN, REGRESS, KILL, DEFER,
EXPERIMENT or NEEDS_FOUNDER_DECISION). **Done:** evidence and authority support the
next bounded step. **Exception:** contested authority stays pending.
**Rollback:** keep the record and decline implementation. **Review trigger:** new
material evidence, changed scope or a recorded dissent threshold.

### SOP-04: Implement and prove the bounded change

**Trigger:** permitted implementation. **Owner:** implementer; a different reviewer
where independence is required. **Input:** task and appropriate decision.

Start from the verified intended base; use a dedicated branch. Reuse canonical
mechanisms. Keep governance, runtime migrations and deletion separate. Test the
smallest decisive behavior, negative cases and relevant regressions. Keep the
first failing result as well as the final result. Record command, environment,
revision, output location and limits. A fixture, unit test, model claim, sandbox,
real effect, independent verification and commercial result are different tiers.

**Output:** scoped diff and reproducible evidence. **Done:** declared checks have
actual results or explicit not_run reasons; unexpected failures are visible.
**Exception:** no environment or credentials means not_run, never invented success.
**Rollback:** close the draft or revert the scoped change while retaining evidence.
**Review trigger:** regression, authority change, dependency drift or new surface.

### SOP-05: Review, adopt and hand off

**Trigger:** ready for review or session ending. **Owner:** implementer for the
receipt; authorized human for adoption. **Input:** diff, test trail and dissent.

Keep unreviewed material work draft. Fill the receipt below with exact PR base/head
and guide revision. Link the decision, tests and next owner. The receipt check
validates metadata only; it neither proves reading nor grants permission. Required
reviews, protected branches and scoped credentials are separate controls.

**Output:** PR + durable handoff stating what changed, what did not, evidence,
remaining failures, owner, next action and stop condition. **Done:** another worker
can resume without asking the founder to reconstruct the session. **Exception:**
unknown outcome becomes a reconciliation task, never a blind retry.
**Rollback:** revert only the authorized adopted diff; preserve original records.
**Review trigger:** head/base movement, reviewer objection or a failed check.

### SOP-06: Improve the process without creating bureaucracy

**Trigger:** first five completed pilot PRs, or a material handoff failure.
**Owner:** maintaining reviewer, with Alfonso deciding changes to obligations.
**Input:** actual handoffs and review outcomes, not self-scored productivity.

Measure complete handoffs / all pilot PRs, stale-context rework, duplicate work,
time to a correct first action and founder interventions per accepted change.
Baseline is NOT_MEASURED. Compare against the prior lightweight workflow. Keep or
simplify the protocol based on evidence; a larger document count is not progress.

**Output:** one linked improvement decision using two passes if material.
**Done:** measurable improvement or an explicit rollback. **Exception:** noisy or
incomparable samples remain inconclusive. **Rollback:** remove the burden causing
harm, keep lineage and safe boundaries. **Review trigger:** five pilot completions,
more rework, lower comprehension, or a failed handoff. No recurring job is enabled.

## PR receipt, version 1

Place exactly one JSON block between `<!-- uniimente:receipt -->` and
`<!-- /uniimente:receipt -->` in the PR body. Use the fields below; replace angle
brackets with real values. Full 40-character commit SHAs are required. Both PR
revisions must match the event; update the receipt after a new push/base update.
The read_set is a DECLARATION. Its contents, evidence and review must be inspected.

```json
{
  "version": 1,
  "repository": "dababiyoda/<repository>",
  "base_sha": "<full PR base commit>",
  "head_sha": "<full PR head commit>",
  "protocol_ref": "https://github.com/dababiyoda/uniimente-kernel/blob/<full guide commit>/docs/collaboration/START_HERE.md",
  "intent_refs": ["<scoped intent record>"],
  "read_set": [
    {"path": "AGENTS.md", "revision": "<commit actually read>"},
    {"path": "<same protocol_ref URL>", "revision": "<full guide commit>"}
  ],
  "scope": "<one bounded outcome and exclusions>",
  "classification": "lightweight",
  "deliberation_ref": null,
  "validation": [{"command": "<actual command>", "result": "pass", "evidence": "<result location and limits>"}],
  "limitations": ["<unexecuted checks, negative results or unresolved risks>"],
  "rollback": "<safe rollback preserving evidence>",
  "handoff": {"owner": "<next owner>", "next_action": "<specific action>", "stop_condition": "<boundary>"},
  "review": {"status": "pending", "reference": null}
}
```

Standard/constitutional work needs a deliberation_ref; lightweight work does not.
Validation results allow pass, fail and not_run: failures must not be hidden to
satisfy this check. Non-draft material work requires a declared completed review
reference; the maintainer must verify the reference and reviewer independence.

## Discussion and knowledge routing

A Discussion or issue is an intake and debate surface. Durable decisions belong
in versioned intent/deliberation/handoff records linked from the work item. Pin a
Discussion to this file rather than maintain a second editable SOP copy. Do not
publish secrets, private conversations or unrelated personal information.

Every agent needs repository read access and a startup mechanism that opens
AGENTS.md. Some tools discover it; others need an explicit saved startup prompt.
A file alone does not configure every model, scheduler, IDE or local agent.
Suggested startup instruction: "Before any new or resumed task, open AGENTS.md,
follow its pinned shared guide, inspect current refs and relevant open work, then
record the bounded scope and source revisions. Never infer missing authority."

## Capability horizon, preserved rather than activated

Persistent goal pursuit, lawful computer use, many tools, specialized or temporary
agent teams, proactive founder updates, venture creation and transparent media
properties remain intended directions. Current evidence determines what can be
executed, not what the founder is allowed to intend. Capability may develop;
authority may not self-expand. These SOPs start no agents, account factories,
spending, publications, external contacts or autonomous schedules.

## Known pending work: inspection snapshot, 2026-09-07

Refresh these before acting: kernel #86 proposes living-goal protocol changes;
#87 -> #88 -> #90 -> #92 -> #94 is an unmerged experimental chain. #94 is not whole
institutional closure and its PR description retains three broad-suite failures.
Runtime ownership and contract-consumption alternatives remain unresolved. These
are inspected PR descriptions, NOT independently reproduced test results. This
bootstrap neither merges that chain nor creates a replacement organism runtime.

## Mechanism rationale and limits

This applies known mechanisms rather than claiming a novel protocol: startup
checklists become source-revision declarations; content pins make a particular
manual version reproducible; work claims route collaboration without transferring
authority; evidence receipts feed review instead of rewarding task volume.
Eligibility = authorized task scope; routing = one owner and record; proof =
inspectable changes and evidence; consequence = separately authorized adoption.

A central guide can fail or become stale. Consumers pin it, declare missing access,
check for newer authorized rulings, and update pins by reviewed PR. They do not
silently follow a moving URL or fetch/execute remote instructions as code.
The check cannot detect a convincingly false receipt, compromised maintainer, or
all off-platform work. It is an auditable handoff aid, not a security sandbox.

## Adoption and rollback

1. Review the kernel bootstrap PR and its local tests; keep authority adoption
   pending until an authorized human merges it. Existing rules remain unchanged.
2. Review and merge the four consumer pointers pinned to this package's full commit.
   Preserve that commit if using squash/rebase; preferably use a merge commit or
   repin consumers to the adopted canonical commit in a reviewed update.
3. After the workflow has run, add its actual observed status name to the default
   branch ruleset, require appropriate review, and restrict bypass separately.
   No settings are changed by these files. Do not require a check that has not run.
4. Configure unsupported AI clients to use the startup instruction above. Confirm
   with a new-session test: the agent names the right source revision, scope and
   blocking issue. Optional: enable and pin a Discussion linking this file.
5. Review after five completed pilot PRs. If receipt burden increases rework without
   improving handoffs, simplify it through the same review process.

Rollback: remove any newly required check BEFORE removing its workflow, then revert
only bootstrap pointers/checks. Preserve deliberation and failed pilot evidence.
Never disable pre-existing governance or force-push history as rollback.
