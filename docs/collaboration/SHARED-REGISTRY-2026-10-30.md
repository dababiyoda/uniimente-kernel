# Shared claims across separate worker containers

Intent lineage: INTENT-20261030-MANDATORY-COLLABORATION; Alfonso explicitly
requests mandatory SOP discovery and parallel teamwork, then says to continue
when Claude browser sign-in is unavailable. The prior local gate decision is
[MANDATORY-GATE-2026-10-30.md](MANDATORY-GATE-2026-10-30.md). This is a linked new
decision for its observed cross-container gap, not a third strengthening pass.
Constitutional scope: shared contributor obligations and cross-repository
coordination. Current instruction authorizes reversible development/testing.
Default-branch adoption, protected merges and managed-client settings retain
their existing authority requirements. No GREG runtime authority is added.

## Mechanism and boundary

Optional remote mode uses one GitHub Contents file on one explicitly selected
`coordination/` branch. A SHA-conditional replacement serializes admissions;
409 causes a fresh read and full conflict re-evaluation, at most four attempts.
Other failures refuse admission. Every covered write checks its current remote
claim as well as the existing local HEAD, source digests and path scope. There
is no fallback to local-only mode when remote mode is configured.

GitHub origin `https://github.com/owner/repo[.git]` or
`git@github.com:owner/repo[.git]` supplies the normalized repository identity.
Different clones/branches of that repository share path exclusions. Named
interfaces exclude conflicts across different repositories. Repository renames,
mirrors and enterprise hosts require explicit migration; they are not guessed.

The remote file publishes session, repo, HEAD, paths, interfaces, expiry, work
item, source references/digests and state. Absolute local paths, snapshot content
and credentials are omitted. Do not place secrets in work-item URLs or scope
labels. Git history retains changes; the JSON audit is not silently truncated.
Decoded state is limited to512KiB, after which writes refuse until a reviewed
migration. Remote operations use existing `gh api --hostname github.com` auth;
this package does not obtain credentials or change their permissions.

This is cooperative coordination among enrolled trusted clients. Anyone who can
rewrite the registry, gate or client settings can bypass it. Session IDs identify
claims; they do not authenticate separate humans. Checks do not fence an
already-running tool. Finish writes before releasing; never release another
worker's active claim merely to unblock a queue. Expiry blocks writes but never
steals ownership. The local OS, uncovered tools and unenrolled clients remain
outside this gate. Remote availability/rate limits add latency and can stop
covered writes. Broad Bash still requires an exclusive whole-repository claim.

## Installation and recovery

The development registry was initialized explicitly at:

- Repository: `dababiyoda/uniimente-kernel`
- Branch: `coordination/worker-claims-20261030`
- File: `collaboration/claims.json`
- Initial schema: `{"version":1,"claims":{},"audit":[]}`

No workers were enrolled by initialization or by the isolated live SHA probe.
The module refuses missing state and refuses the repository's actual default
branch, even if that default happens to begin with `coordination/`.

On an actual reviewed checkout with existing authorized GitHub access:

```sh
python scripts/install_collaboration_gate.py --workspace /shared \
  --remote-registry dababiyoda/uniimente-kernel \
  --remote-branch coordination/worker-claims-20261030 \
  install --repo /shared/organ
python scripts/install_collaboration_gate.py --workspace /shared \
  --remote-registry dababiyoda/uniimente-kernel \
  --remote-branch coordination/worker-claims-20261030 \
  start --manifest /shared/claim.json --prompt 'Perform the claimed task'
```

Options precede the action. Use the same remote arguments for `check`, and for
direct `collaboration_gate.py` commands. Existing gate rules with different
arguments are deliberately refused: review/remove only the old matching gate
entry before reinstalling, preserving all other settings and backups. Never
delete the settings file. A changed setting is not evidence that the running
client has loaded it; test an actual refused and admitted tool invocation.

Headless mode preserves existing Claude permissions. The gate never grants tool
permissions: configure any needed permissions separately under existing authority.
The integrator's real launcher test had a scoped write denied by Claude's own
permission prompt, while the out-of-scope write was refused by this gate. Do
not use a blanket permission bypass to turn that test green.

For a remote handoff, the sender uses `handoff --session A --receiver B
--reference https://...`. Receiver B prepares fresh local HEAD/source snapshots
with exactly the transferred repository, paths, interfaces and work item, then
uses `accept --session B --from-session A --reference https://...
--manifest receiver.json`. Receiver expiry/head/source digests can be fresh.
Sender `finish` preserves the pending reservation. The receiver may use a
different clone, container and local DB.

After a timeout/unknown response, inspect the exact remote claim before retrying.
Do not reset state. If reserve succeeded remotely but local setup failed,
re-enroll the exact manifest or explicitly release your own reservation. If
accept succeeded remotely but its response/local setup failed, reconcile the
active receiver record and enroll the identical receiver manifest; blindly
repeating accept may correctly refuse because the sender is already released.
A local conflict after remote success keeps the remote exclusion reserved until
reconciliation. If cleanup cannot reach GitHub, it leaves the claim reserved.

## Deliberation: exactly two strengthening passes

Five parent self-review perspectives, complemented by a separate code reviewer:

| Perspective | Requirement |
| --- | --- |
| Founder-Intent Steward | Make independent containers share exclusions without another SOP or narrowing the complete machine. |
| Systems Architect | Reuse GitHub and the existing gate; local evidence plus one shared admission record. |
| Adversarial Reviewer | Conditional writes, explicit identity, uncertainty refusal, corruption refusal and no default-branch writes. |
| Operator and Maintainer | Existing authentication, bounded retries, explicit recovery and preserving installation. |
| Evidence and Welfare Guardian | Separate fixture, connector API, actual CLI and live-client evidence; measure serialization cost. |

**Pass1.** Baseline local SQLite cannot coordinate separate containers. Doing
nothing retains that failure; board acknowledgments are the simplest alternative
but not atomic. A hosted authenticated coordinator is the strongest competitor,
with service deployment/identity/availability costs. A reversible GitHub Contents
experiment reuses the already-connected collaboration substrate and server-side
SHA conflict refusal. Advantages are durable shared state and auditable changes.

- D1: network outages and rate limits interrupt tools. Refuse writes, bound
  requests/retries, retain reservations; no offline permission fallback.
- D2: shared writers can spoof a session or edit state. Keep a trusted-client
  boundary and existing access controls; no hostile-writer security claim.
- D3: unknown outcomes can lose a handoff or strand ownership. Preserve explicit
  states, reconcile current records, and document recovery without automatic theft.
- D4: GitHub commits/latency may cost more than collisions prevented. Read-only
  checks do not commit; measure five-task pilot before mandatory broad adoption.
- D5: identity/config drift can split the registry. Normalize actual origin,
  configure one branch/file, bind hooks/launcher and refuse mismatched settings.

**Pass2.** Attack the strengthened design. A client-side ref lease is insufficient;
use Contents' server-enforced blob SHA and verify the returned blob identity.
Re-evaluate all conflicts after409. A `coordination/` prefix alone could name the
default branch; inspect actual repository metadata before reads/mutations. An API
envelope is larger than decoded state; bound each separately. Separate local DBs
need a fresh receiver manifest, while same-DB acceptance must release only the
matching local pending sender. Preserve all discovered failures and prior claims.

| Downside | Final disposition and review trigger |
| --- | --- |
| D1 | Accepted fail-closed availability cost; operator measures tool failures and latency. |
| D2 | Explicit trusted-client limit; revisit if authenticated per-worker isolation becomes required. |
| D3 | Preserved states/recovery; halt rollout on silent loss or takeover. |
| D4 | Five-task measured pilot; simplify if coordination cost exceeds rework saved. |
| D5 | Explicit config/origin verification; new container, renamed repo or source change triggers re-enrollment. |

Dissent: this still cannot force a client that never loads the hook to comply;
nor can it safely treat every shell command as a scoped write. Those concerns
remain valid and managed startup/client enrollment remains necessary. Decision:
EXPERIMENT, with independent review and a staged rollout, not universal completion.

## Evidence, rollout and rollback

102 distinct local tests pass:25 existing gate/installer/launcher,19 remote
registry,4 local/remote integration,5 workspace and49 receipt. Separate reviewer
reran19 remote and25 original tests and independently probed a two-workspace
handoff. Fixtures cover stale CAS, response loss, branch refusal and outages.

The coordinator's real GitHub connector probe on the isolated registry committed
`861cecb9f6b22fd15e43fd380fd52fa585642870`, then retried the prior blob SHA
`6c2cf1caff88a43ca097cf4443daae14065247aa`. GitHub returned409; newer state was
preserved. Final probe receipt commit is
`338743afbc63eee90132b7fac2a7e9f0e4f0610c`, with zero active claims. This is real
API conditional-update evidence, not a simultaneous two-client or actual `gh`
transport test. Official reference inspected2026-10-30:
https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents .

The integrator reports real Claude2.1.314 testing of the preceding launcher pin
`803b8960` (PR196 comment6525582491): root pytest collection passes; headless
launch exits0, outside Write is refused and finish releases. All live cloud
sessions remain unenrolled at that report. New remote-mode `gh` transport and
two real containers still need their actual client's tests. Never relabel these
fixtures or the connector probe as those tests.

Rollout: publish the reviewed extension on existing PR206, notify its integrator
and board96, run two remote client claims against this same branch, then record
actual hook refusal/admission and receiver acknowledgment. Workers retain board
claims while unenrolled. Stop/simplify on lost claims, bypassed conflicts, erased
settings/evidence, or excess pilot cost. Rollback stops new entrants, finishes
in-flight tools, releases owned reservations with evidence, then removes only
matching remote-hook settings. Preserve registry branch/history. Never silently
downgrade an active remote client to local-only coordination.
