# Mandatory enrollment for enrolled worker clients

Intent INTENT-20261030-MANDATORY-COLLABORATION, active requirement. Source:
Alfonso's current instruction: “install a mandatory way for everyone to collaborate
and work in parallel”; agents must discover his SOP/Discussion on entry and work
as a professional team. This extends #193 and #206; it does not replace their SOP.

## What is enforced

The local shared-workspace registry grants one current claim per actual session.
SQLite transactions reject overlapping repository paths or shared interface names
across cooperating workers. Git common-directory identity groups git worktrees.
Claims retain exact HEAD and hashes of protocol, Discussion and board snapshots.
A changed HEAD/source, expiry, missing registry or invalid record refuses checks.
An expired claim still excludes competing work until explicitly released; time
alone never grants another worker permission to take it. Transfers require a
separate receiver acknowledgment. Source hashes record declarations, not proof
that a human or model understood the text or that a snapshot is current remotely.

Claude's PreToolUse gate rejects covered write tools without a valid claim and
rejects Write/Edit paths outside it. Arbitrary Bash requires an exclusive whole
repository claim (`paths: ["."]`), because interpreting shell text cannot prove
which paths a command writes. Bounded file edits can proceed in parallel; broad
shell activity serializes within a repository. Separate repositories can proceed
in parallel unless they claim the same shared interface. Release/re-enroll for
the next phase rather than pretending arbitrary shell has file confinement.

The installer appends this gate to existing local Claude settings, preserving
permissions and other hooks. It uses exec-form command/args, timeout and
`onFailure: block`; missing/crashing hooks must not allow writes. The checked
launcher enrolls before spawning Claude with the exact UUID session identity and
explicit settings. It releases active claims on client exit; pending transfers
remain reserved for their named receiver. Restarts enroll again.
Read tools remain available before enrollment. Notebook editing is also gated.

## Installation and operation

Use a reviewed checkout containing both scripts and the canonical guide:

```sh
python scripts/workspace_entry.py --workspace /absolute/shared --install
python scripts/install_collaboration_gate.py --workspace /absolute/shared install --repo /absolute/shared/repo
python scripts/install_collaboration_gate.py --workspace /absolute/shared check --repo /absolute/shared/repo
python scripts/install_collaboration_gate.py --workspace /absolute/shared start --manifest /absolute/claim.json
```

For a headless worker, add `--prompt 'Perform the claimed task'` to `start`.
Supplying `--prompt` selects Claude's `-p` print mode; omitting it preserves
interactive startup. Do not run interactive startup in an unattended CI job.

The source checkout may be specified with `--source /absolute/reviewed/kernel`.
Each repository/client needs installation and a startup test. Repositories are
not discovered by guessing directories; point the installer at each actual
checkout. This environment's source preparation is a partial checkout, not the
user's devices or already-running Claude sessions. Local tests do not enroll
those machines. The launcher requires an installed Claude CLI with the documented
session/settings/hook features; it does not install Claude or acquire credentials.

Manifest v1 fields:

```json
{
  "version": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "repository": "/absolute/shared/repo",
  "head_sha": "<actual full HEAD SHA>",
  "source_reads": [
    {"kind": "protocol", "path": "/absolute/reviewed/kernel/docs/collaboration/START_HERE.md", "sha256": "<actual SHA-256>", "reference": "https://github.com/dababiyoda/uniimente-kernel/pull/206", "retrieved_at": "<actual UTC retrieval time>"},
    {"kind": "discussion", "path": "/absolute/shared/snapshots/discussion89.md", "sha256": "<actual SHA-256>", "reference": "https://github.com/dababiyoda/uniimente-kernel/discussions/89", "retrieved_at": "<actual UTC retrieval time>"},
    {"kind": "board", "path": "/absolute/shared/snapshots/board96.md", "sha256": "<actual SHA-256>", "reference": "https://github.com/dababiyoda/uniimente-kernel/issues/96", "retrieved_at": "<actual UTC retrieval time>"}
  ],
  "work_item": "https://github.com/dababiyoda/uniimente-kernel/issues/96",
  "paths": ["docs/example/"],
  "interfaces": [],
  "expires_at": "<actual next UTC recheck>"
}
```

Read the current Discussion/board through an authorized connector or browser,
retain its actual content plus URL/retrieval date/revision when available, and
hash those bytes. Do not invent access or label old snapshots current. A source
access failure blocks dependent edits, while independent read-only work continues.
Post the matching bounded claim and split acknowledgment on the actual work item.
Local admission does not authenticate a GitHub claim or lock another machine.

Direct operations use `collaboration_gate.py --workspace /absolute/shared` then
`enroll --manifest`, `check --session`, `release --session`,
`handoff --session --receiver --reference`, or
`accept --session --from-session --reference`. Read the command's help for values.
Keep one shared local DB; separate DBs do not coordinate. It is not a network
service or an appropriate distributed lock on a network filesystem.

## Material decision: exactly two strengthening passes

Five parent self-review perspectives (not five independent reviewers):

| Role | Position and concern |
| --- | --- |
| Founder-Intent Steward | Enforce current enrollment before edits; preserve the user's intended outcome and one SOP. |
| Systems Architect | Extend the existing installer; use one shared registry, repository identity and explicit interfaces. |
| Adversarial Reviewer | A voluntary file is not a gate; source changes, races, corruption and missing hooks must refuse. |
| Operator and Maintainer | Preserve existing settings, provide a checked launcher, keep recovery explicit and errors actionable. |
| Evidence and Welfare Guardian | Never call snapshots comprehension, local claims global locks, or fixture tests universal client adoption. |

**Pass 1.** Baseline #206 installs pointers only. Doing nothing leaves unregistered
edits possible. The simplest alternative is reminders plus receipt CI; useful but
cannot stop local collisions. A centralized authenticated coordination service
is the strongest competitor, but adds hosting, identity and availability cost
before local enrolled-client behavior is established. Choose a reversible local
gate with actual conflict/refusal tests. Advantages: atomic local admission,
durable handoff and source drift refusal without a new runtime authority.

- D1: clients can bypass/disable local hooks. Response: define an enrollment
  boundary, explicit launcher/settings, and eventual operator-managed policy.
- D2: shell commands can write outside claimed paths. Response: require a
  repository-wide exclusive claim for arbitrary Bash; never parse shell as proof.
- D3: expired or crashed workers leave claims. Response: retain exclusions and
  evidence; explicit release/recovery instead of silent claim theft.
- D4: snapshots can be old or fabricated. Response: exact byte hashes and visible
  source provenance; workers/receivers must refresh remotely before intake.
- D5: configuration edits can destroy local rules. Response: preserve keys/hooks,
  keep original backup, refuse symlink paths and conflicting installed rules.

**Pass 2.** Attack the safeguards: a SessionStart hook cannot block writes, so use
PreToolUse instead. A missing executable can fail open by default, so set
onFailure:block. Isolated registries pretend cooperation while admitting races,
so all enrolled worktrees use the same absolute workspace DB. Broad shell claims
can destroy parallelism; restrict them to the shell phase and keep independent
bounded edits/repositories parallel. A corrupt DB/source must deny, never reset
and silently erase competing claims. Keep the original implementation receipts.

| Downside | Disposition | Owner / trigger |
| --- | --- | --- |
| D1 | Accepted local enrollment boundary; managed policy remains required for resistant clients | Client operator; installation audit |
| D2 | Accepted serialization cost for arbitrary Bash; no sandbox claim | Task coordinator; measured queue/rework |
| D3 | Accepted explicit recovery burden | Claim owner/operator; interruption or expiry |
| D4 | Accepted declaration limit; independently check source and acknowledgment | Receiver; every intake |
| D5 | Protective design with preservation/refusal tests | Installer maintainer; settings update/relocation |

Dissent retained: a local gate cannot make all remote clients mandatory, and
shell serialization may cost more than collisions saved. Revive the central
service alternative only after measured cross-machine collisions justify it;
compare against one worker/static workflow under the same budget. Decision:
EXPERIMENT, authorized by the current explicit installation instruction, with
independent code review and enrolled-client smoke tests before wider adoption.
No merge, deployment, spending, credential or runtime authority is expanded.

## Rollout, rollback and kill criteria

Stage on #206; notify the existing integrator and work board. Run actual
subprocess race, restart, drift, out-of-scope and transfer tests; separately
exercise the installed hook with real event-shaped stdin. Actual Claude launch,
managed-policy deployment, all 13 actual workspace checkouts and other clients
remain explicit per-client enrollment evidence, never inferred from PR presence.
Clients without a supported hook must use an equivalent trusted wrapper/adapter
before being counted enforced; instruction pointers alone remain advisory.

Rollback removes only this gate's matching PreToolUse entry and retains all
other settings and backups. Do not replace the whole settings file over later
edits. Release claims with an audit record and retain the DB/failed evidence.
Kill/simplify on lost local settings, silent takeover, missed conflict, fail-open
mutations, or coordination costs exceeding rework saved in the five-task pilot.
Registry access is not a hostile-host security boundary; operators must protect
the DB, source scripts and managed settings from tampering. Write-path checking
cannot stop arbitrary programs or tools outside the installed coverage.
