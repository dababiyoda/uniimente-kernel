# ADR: Fifth increment of the Goal Gravity loop — explicit, evidence-preserving torn-tail recovery of the Evidence Ledger

- Decision ID: ADR-GOAL-GRAVITY-004
- Status: proposed (draft PR #160, fifth increment; adoption into `main` is a founder decision)
- Date: 2026-11-13
- Decision owner: Alfonso Lopez
- Deliberation level: Standard (one additive module in the `provenance` boundary package and its tests; no change to
  `EvidenceLedger`, the Gate, any contract, any authority or any organ). Wiring it into a supervisor (G5) or into an
  organ's restart path would touch evidence retention on a live ledger and is a separate, constitutional decision.
- Founder intent references: `INTENT-20261013-GOAL-GRAVITY` (§25 "Restart continuity"), `SR001-FOUNDER-LOOP-ENTRY`
  (proof P2), `INTENT-20261014-minimum-viable-continuous-loop`, `INTENT-0030`
- Deliberation record: `docs/collaboration/deliberation-goal-gravity-fifth-increment-2026-11-13.json` (validator exit 0)
- Review record: `tests/evidence/goal-gravity-20261013/review-increment-5.json`
- Supersedes: none (additive to ADR-GOAL-GRAVITY-001 to -003)
- Superseded by: none

## Problem

**Observations.**

- The founder-loop entry gate's proof P2 requires that after an interruption the process "reopen canonical history,
  retain stable identity, reject transport replay, recover retained result or preserve uncertainty; no duplicate
  consequence" (`docs/founder-loop-entry-gate.json`).
- `EvidenceLedger._append` writes a record, flushes and fsyncs it, and only then returns. A process killed during
  that write leaves a partial last line. `EvidenceLedger._load` refuses partial lines, which is correct: history
  fails closed.
- The result was a liveness gap. The first through fourth increments characterized it by test and listed it as
  unrepaired (`docs/GOAL_GRAVITY.md`, row 11 and the blocked table). A SIGKILL inside the Gate's `grant_dispatch`
  append left a ledger that could not be reopened.
- No repair existed. The only way forward was a person editing the canonical ledger by hand. That is unaccountable
  and can silently drop an acknowledged record, so P2 could not pass with any supervisor.

**Inference.** The residual CapabilityDeficit is narrow: an explicit, accountable repair that makes a torn ledger
reopenable without losing evidence, without admitting the torn bytes and without hiding the ambiguity a byte-level
check cannot resolve. The supervisor that would call it on restart is G5 and is not built here.

## Decision

Add `provenance/recovery.py` with
`recover_torn_tail(path, constitution_hash, *, recovered_by, reason, expected_head=None, acknowledged_risks=())`.
Holding the ledger's single-writer lock for the whole procedure, it:

1. **Refuses unsafe entry conditions.** It refuses a symlinked path or a file with more than one hard link, because
   the lock is keyed on the path string, and resolves the directories in the path physically, as the operating
   system does. It refuses a live writer (`WriterConflict`). An empty file and a torn or zero-filled genesis line are
   refused on purpose: nothing distinguishes them from an acknowledged history truncated to nothing, so a person
   decides.
2. **Verifies history in memory.** Every complete line must verify as a chain anchored to the expected constitution,
   parsed with the same checks `EvidenceLedger._load` applies; no copy of history is written. A supplied
   `expected_head` must equal the head before the torn line.
3. **Accepts only what one interrupted append can leave.** That is a byte prefix of the next record's line exactly
   as the writer serializes it, optionally NUL-padded, or a run of NULs. The checks run as far as the bytes go:
   - the header `{"seq": <n>, "ts_utc": "<time>", "record_type": "<type>", "payload": {`;
   - after the payload's closing brace (found by a string-aware scan), exactly `, "prev_hash": `, and the fields
     before it re-serialize to exactly the visible bytes;
   - a `prev_hash` equal to this chain's head;
   - hash digits that begin the hash these fields give, with `corrects` null or a hash of this chain; otherwise the
     tail is `partial_unverified`;
   - once the hash is complete, the record's own closing fields and `hash_version` 2.

   The tail is classified `partial`, `partial_unverified`, `zero_fill`, `content_complete`,
   `content_complete_unverified` or `complete_unterminated`. Anything else is refused, even with every risk
   acknowledged:
   - a fork, a foreign or misplaced field, other separators, control bytes, a mismatched hash, or a complete object
     followed by more bytes;
   - a NUL hole inside the content, which a reordering storage stack and the zeroing of an acknowledged record can
     both leave.

   Damage inside a field still being written, before any hash digit is visible, cannot be seen in the bytes; that is
   the residual `unanchored` names.
4. **Requires named acknowledgment of the risks a byte check cannot exclude:**
   - `unanchored`: no `expected_head` was given.
   - `complete_record`: the record's 64-digit hash was written, so its identity is fixed, or its visible hash digits
     match no record this chain can hold. This applies with or without `expected_head` (R1b) and for records with
     `corrects` set (second review, classifier:0).
   - `stop_record`: the torn bytes show a stop that never took effect. Record and event types are judged against
     explicit registries, and tests require every type the code writes to be in one; names are never searched for
     stop words. The stops are:
     - a seal, a suspension, a founder preference or answer, a capability detach;
     - a goal revocation or supersession, including the replacement's authorization, which is supersede's first
       append;
     - an evolution capsule deciding kill or regress;
     - an action revoked, an autonomy regression, a business termination, a provider withdrawn, a component
       disabled, or a node or organ retired.

     An unknown record or event type, or a cut before the deciding field, is warned about without a required
     acknowledgment.
5. **Writes the plan before touching the ledger.**
   - The torn bytes are copied byte for byte to `<ledger>.torn-<16 hex of the prior head>-<sha256>` (temporary
     file, fsync, link).
   - A `.json` sidecar is written by temporary file, fsync and replace. It records what was found, who is recovering
     it, and the plan: the exact `ledger.torn_tail_quarantined` event line, the offset, and the digest of the
     verified prefix bytes.
6. **Applies the plan in place, so the ledger never opens before its repair is recorded.**
   - The event line is written over the torn bytes; every byte is written, and checked by reading it back.
   - The file is cut to the event's length, then the newline is written, with an fsync after each step.
   - Until the newline the file never ends with a newline, so `EvidenceLedger` keeps refusing to open it and no
     restarting writer can append.
   - The plan is then marked applied, and quarantine files this chain does not record are reported, never chained.
   - A call that finds a plan part-way applied completes it. The plan must be unapplied and written for exactly
     these prefix bytes and offset. The tail must show at least one of its event bytes in place of a torn byte;
     every other byte must be the event's, the torn byte, the newline or a zero.
   - The completing caller is written to the sidecar first. The plan's caller remains `recovered_by` and the new
     caller is returned as `completed_by`.
   - A plan whose application never began is replaced by the new caller's own.
   - On a clean ledger, a last record that is a recovery event is returned as `last_recovery`, so its stop warning
     reaches a caller whose first call was cut off.

The torn record is never re-admitted: an append that never returned took no effect. Opening a torn ledger still
fails closed. Nothing calls recovery automatically.

The integration test `test_sigkill_inside_the_dispatch_claim_append_is_recovered_without_loss_or_redispatch` kills a
real child halfway through writing `grant_dispatch`. It then checks the following:

- the ledger refuses to open;
- recovery classifies the tail `partial` with type `grant_dispatch` and quarantines exactly the torn bytes;
- the reopened chain verifies and carries one recovery event;
- no `grant_dispatch` survives and the intervention stays `attempted`;
- a fresh grant does not cause a second dispatch, and reconciliation reports the route unresolved.

## Effect compilation

- **Founder expression.** The founder wrote "maintain them across sessions and interruptions" and, in §25, "Restart
  continuity — Interruption occurs during mission → resume without duplicate consequential action." The directive's
  opening adds "functional survival mechanisms preserve continuity". Proof P2 states the same requirement.
- **Intended effect.** A crash at the worst moment, inside the append that claims a dispatch, does not end the
  institution's history. The history can be reopened, its uncertainty is preserved rather than guessed away, and the
  same consequence is never produced twice.
- **Literal requirements.** Reopen canonical history; no duplicate consequence; preserve uncertainty; accountable
  recovery.
- **Metaphor and aspiration.** "Survival" and "continuity" compile to recoverability with preserved evidence (the
  Effect Compiler's "heal yourself" and "immortal" examples). No self-healing simulation is implied, and recovery
  itself is not autonomous until a supervisor exists.
- **Simplest viable mechanism.** Tail truncation as practiced by mature write-ahead logs:
  - etcd's `wal.Repair` truncates a last WAL file ending in `ErrUnexpectedEOF`, and older releases copied it to a
    `.broken` file first. Its stated rationale is ours: raft sends nothing until an entry is durable, so a torn final
    entry was never relied on.
  - RocksDB's `kTolerateCorruptedTailRecords` tolerates incomplete trailing records. Its own source notes that it
    cannot tell a torn tail from real corruption, which is why its default moved to point-in-time recovery.

  Sources: [etcd wal package](https://pkg.go.dev/go.etcd.io/etcd/server/v3/wal),
  [etcd v3.2.7 repair.go](https://chromium.googlesource.com/external/github.com/coreos/etcd/+/v3.2.7/wal/repair.go),
  [RocksDB WAL recovery consistency levels](https://git.nextgraph.org/NextGraph/rocksdb/commit/de85e4cadfd3bd9ea5d3e148868f70cfab5c91d4),
  [RocksDB `WALRecoveryMode`](https://javadoc.io/static/org.rocksdb/rocksdbjni/7.9.2/org/rocksdb/WALRecoveryMode.html).
- **What differs, and why.** This ledger is evidence, not a cache, so silent tolerance is wrong for it. The adopted
  mechanism keeps etcd's backup-first discipline but replaces the torn bytes with a record of the repair. It applies
  that record in place, behind a durable plan, the write-ahead-intent pattern of redo logs. It turns RocksDB's
  documented ambiguity into named risks that an accountable caller must acknowledge, instead of a mode that hides
  them.
- **Existing mechanisms searched.**
  - `EvidenceLedger`'s fail-closed load, single-writer lock, `corrects` field and seal.
  - The kill tests of the first through fourth increments.
  - `docs/GOAL_GRAVITY.md`'s blocked table.
  - etcd, RocksDB and LevelDB WAL recovery, above.
- **Residual deficit.** This module. A supervisor that calls it (G5) remains blocked, as does an isolated verification
  facility (SR001).
- **Falsification.** Any one of these would falsify the effect:
  - an acknowledged record dropped without the caller naming a risk that admits it;
  - a ledger that opens with its torn bytes removed but no recovery event;
  - a completed or foreign plan replayed on a later tear;
  - a torn record admitted to the chain;
  - a tail accepted that one interrupted append cannot produce;
  - a second dispatch after recovery;
  - a recovery event that claims more than was proven.

## Alternatives

| Alternative | Benefits | Liabilities | Disposition |
|---|---|---|---|
| Explicit recovery module with named risks (selected) | evidence preserved and chained; ambiguity explicit; no change to the ledger contract | needs a caller (G5); an operator can still acknowledge a risk carelessly | EXPERIMENT |
| Do nothing (fail closed forever) | no new code on evidence | P2 cannot pass; hand edits of the canonical ledger become the de facto repair | rejected |
| Tolerant load inside `EvidenceLedger` (RocksDB-style mode) | restarts need no extra call | silent loss in every organ that pins the boundary package; contract change; the ambiguity RocksDB documents | rejected; revive only with a founder ruling on silent tolerance |
| Self-delimiting framing (length and checksum prefix, `hash_version` 3) | torn writes detectable by construction | shared-contract migration for every organ; does not remove the acknowledged-then-damaged ambiguity | deferred; revive if torn tails recur in a live deployment |
| Atomic per-record writes (temp plus rename, or one file per record) | no torn lines | O(n) rewrite per append or a new storage layout; fsync cost | rejected |
| Truncate in place, then append the event (first design, `54fd20cc` and `2f79683`) | simple | a crash between the two leaves an openable ledger with no record of the truncation (second review, crash:0) | superseded by the in-place plan |
| Atomic replace (write the prefix and the event to a scratch file, rename it over the ledger) | textbook atomicity | needs free space equal to the ledger at the moment a full disk is the classic cause of a torn append; changes the inode; leaves full copies of history when killed | rejected in favour of the in-place plan |

## Adversarial review of this increment

An independent review workflow (`wf_4100bf3c-3ab`) ran three finders (evidence integrity, crash and concurrency,
semantics and honesty), each followed by an independent verifier. The verifiers re-ran or rewrote every reproduction
against a clean extraction of the pre-review commit `54fd20cc`. Fourteen findings were raised; 13 were confirmed real
and one was judged not a defect. They reduce to ten distinct issues. Replaying the probes against the first fixed tree
surfaced one more (R1b). The full record, with verbatim verdicts, is
`tests/evidence/goal-gravity-20261013/review-increment-5.json`.

| Finding(s) | Issue at `54fd20cc` | Disposition |
|---|---|---|
| EI-0, SH-0 (major) | any damage that made the tail unparseable was "partial" and dropped without proof, so cutting 2–40 bytes from an acknowledged `grant_dispatch` dropped it and the event said "never returned" | strict classifier (prefix of the next record or NULs; anything else refused); `unanchored` must be named without `expected_head`; disposition states what cannot be excluded |
| EI-1, CC-3, SH-3 (minor) | quarantines keyed on the torn bytes' digest alone: a second identical tear was truncated with no event, and the sidecar was reused with stale metadata | names carry the prior head; recording deduplicates by file name |
| EI-2 (minor) | path-keyed lock: through a symlink, recovery ran under a live writer and forked the ledger | symlinks and hard-linked files refused; root cause referred to the ledger owner (below) |
| EI-3 (minor) | any `<ledger>.torn-*` file, such as a `.json.bak`, was taken for a quarantine and chained | whole-name match `<base>.torn-<16 hex>-<64 hex>`; bytes must match the digest in the name |
| CC-0, SH-1 (major) | the lock was released between truncation and the event; a restarting writer won that window every time, and the truncation went unrecorded | lock held through the chained event |
| CC-1 (major) | a crash during the quarantine copy left an empty file that blocked every later recovery | temporary file, fsync, link |
| CC-2 (major) | a crash during the sidecar write left an empty `.json` that later broke recording, including for unrelated recoveries | atomic replace on every truncating attempt; unreadable or contradictory sidecars are not trusted, and the event says so |
| CC-4 (minor) | a retry chained an earlier attempt's proof | the truncating attempt writes its own sidecar |
| SH-4 (minor) | a completed crash attributed the truncation to the later caller | `recovered_by`/`reason` from the sidecar; the later caller is `recorded_by` |
| SH-2 (major claimed; verifier: not a defect) | a torn suspension is quarantined and the body restarts unsuspended | not a defect: `suspend` sets its flag only after `append` returns. Hardened: torn type named, `stop_record` required for stop types, stop warning when the type is a stop or unreadable |
| R1b (found by the replay) | a checkpoint one append stale matches the head before the torn line, so `expected_head` alone let a complete, acknowledged record be dropped with "never returned" | `complete_record` required whenever the tail is complete; anchored disposition is conditional ("if that was the writer's last acknowledged head") |

Every disposition has a regression test in `tests/unit/test_ledger_recovery.py`. The second review below replaced the
mechanism behind CC-0/SH-1, CC-2 and SH-4 (truncate under the lock, then record from the sidecar) with the in-place
plan, which keeps their effect: no writer appends before the repair is recorded, and a crash never chains another
attempt's proof or identity.

`tests/evidence/goal-gravity-20261013/review-probes-increment-5.log` replays all 26 probes against the fixed tree:

- 19 complete with no finding reproducing;
- 7 end in a deliberate refusal.

The log lists each mechanical adaptation the old API required.

### Second adversarial review (of `2f79683`)

A second review workflow (`wf_6a3dd129-b42`: classifier, crash and honesty finders, one independent verifier per
finding) raised 18 findings. Fifteen were confirmed real and three were judged not defects. Records:
`tests/evidence/goal-gravity-20261013/review-increment-5.json` (`second_review`) and
`review2-probes-increment-5.log`.

| Finding(s) | Issue at `2f79683` | Disposition |
|---|---|---|
| crash:0 (major) | a recovery killed after truncating and before its event left an openable ledger; a restarting body appended onto the unrecorded truncation (about half of a long call is in that window) | the in-place plan: the ledger never ends with a newline until the event is durable; real-SIGKILL test at each apply step |
| crash:1, honesty:2 (major) | an altered, unrecorded quarantine made recovery refuse after it had truncated, and blocked recording | quarantines without an event in this chain are reported, never chained, so nothing can fail after a change |
| classifier:1, honesty:0 (major) | a torn goal revocation, supersession or capability detach was recovered as "not a stop" and the revoked goal acted again | detach added to the stop types; goal transitions and events are stops when their visible payload shows one; wake/sleep reasons exclude a stop; unknown types warned (completed in the third round: registries, not stop words, and tests covering every egregore record type and every event type the code writes) |
| classifier:0 (major claimed; verifier: minor) | a cut just before the hash's closing quote, or inside a correction record's closing fields, was `partial`, so `complete_record` was not demanded | complete once the 64-digit hash is written; `corrects` rebuilt and the hash recomputed; every-offset sweep of six record kinds |
| classifier:2 (minor) | tails the writer cannot produce (a fork, control bytes, a foreign field) were accepted as `partial` | refused |
| crash:2, honesty:1 (minor) | quarantines from an earlier ledger at the same path were chained as recoveries of this one | reported, never chained |
| crash:3, honesty:4 (minor) | after a crash, a byte-identical re-tear at the same head gave two truncations and one event | the precondition (a truncation without an event) no longer exists |
| crash:4, honesty:5 (minor) | verification wrote a full copy of history: recovery needed free space equal to the ledger, and killed attempts left copies | verification in memory, with a parity test against `_load` |
| crash:5 (minor) | `..` through a symlinked directory made recovery act on a different file | directories resolved physically |
| honesty:6 (nit) | a fallback attribution text named the wrong cause | moot: events are never built from a sidecar now |
| classifier:3, classifier:4, honesty:3 (verifier: not defects) | a NUL hole inside a record and a torn genesis line are refused; sidecar fields could reach the event | the refusals are deliberate and now documented, and a person decides; the sidecar path is gone |

### Third verification round (of `621d2de`)

A third workflow (`wf_67cbe503-425`) ran four fix-checkers and two fresh adversaries, with one skeptic per finding. The
fix-checkers re-ran the second review's own probes on `621d2de`. All second-review dispositions held except three that
were partly fixed (classifier:2, honesty:0, crash:2/honesty:1). Those three are completed below. Twenty-two findings were
raised: 18 confirmed, 4 judged not defects. Records: `review-increment-5.json` (`third_review`),
`review2-probes-increment-5.log` (fix-checks) and `review3-probes-increment-5.log` (the round's probes replayed against
the fixed tree).

| Finding(s) | Issue at `621d2de` | Disposition |
|---|---|---|
| fix-apply:0, fix-space:1, adv-protocol:1 (major) | a completed plan, or one left by another ledger at the same path, was resumed on a later tear at the same prior head and offset; a zero-filled tail matched any plan | plans are marked applied; a plan must be written for exactly these prefix bytes; the tail must show positive evidence of its application; the resumed line must chain |
| fix-space:0, adv-protocol:2, adv-semantics:4 (major) | a short `pwrite` was ignored, so a newline could terminate a damaged event, and every later call refused | every byte is written and read back before the newline; a mismatch rolls the file back to the resumable state |
| adv-protocol:0, fix-apply:1 (major, minor) | a lost final newline (the event plus a NUL) was not recognized as a plan in progress | that state is resumed; a recovery event whose plan is missing is refused, never quarantined as a record |
| fix-stops:0 (major) | a torn first append of a supersede (the replacement's `goal_authorized`) was not a stop, and the restarted loop acted on the goal the founder had superseded | `goal_authorized` naming a goal it supersedes is a stop; `GoalRegistry.supersede` now writes the old goal's superseded transition first, so a crash between its two appends leaves the old goal stopped |
| fix-stops:1, adv-semantics:0 (minor, major) | stops written as events whose names avoid the stop words (autonomy regression, business termination, provider withdrawal, organ retirement, kill capsules) were not stops | explicit stop and non-stop registries, enforced by a test that scans every event type the code writes |
| fix-classifier:0, adv-semantics:1, adv-semantics:2 (minor) | tails outside the writer's template were accepted before their hash was visible, and one flipped delimiter byte hid a complete record | header template, payload-end scan, exact re-serialization, hash digits checked against the recomputed hash, and `hash_version` 2 |
| fix-space:2, fix-space:3, adv-protocol:5, adv-semantics:5 (nits) | a failed copy left its `.tmp-` file; one refusal named the wrong file; repeated full-chain hashing; stale doc statements | removed on failure; distinct messages; lazy candidates and no post-apply reload; docs corrected |
| fix-stops:2, adv-semantics:3, adv-protocol:3, adv-protocol:4 (verifier: not defects) | over-refusal by stop words; no channel for a cut-off caller; completing caller not durable | improved anyway: registries replace stop words; `last_recovery`; completions written to the sidecar |

**Root cause referred to the ledger owner.** `EvidenceLedger` keys its single-writer lock on `<path>.lock`. A
symlink, hard link or bind mount of the ledger file therefore has its own lock file, and two writers can append to the
same bytes. Recovery now refuses the first two aliases it can detect. The ledger itself does not. Locking the ledger
file's own descriptor, or refusing `st_nlink > 1` and symlinks at open, would close it at the source. That changes
the boundary package all organs pin, so it is left as a proposal for the ledger owner.

## P2 status

P2 is not complete. It requires "the chosen supervisor restarts the process without a human advancing the harness".
G5 is `DECISION_REQUIRED_BEFORE_NEW_ARCHITECTURE`, and nothing calls `recover_torn_tail` on restart. What this
increment proves is narrower. History torn at the worst moment can be reopened by an accountable call, with
uncertainty preserved and no duplicate consequence: the route stays `attempted`, and reconciliation reports it
unresolved instead of re-dispatching. A supervisor that passes `acknowledged_risks=("unanchored",)` unattended would
be making a standing acknowledgment on the founder's behalf. That choice belongs to the G5 decision, not to this
module.

## Evidence tier

IMPLEMENTED, UNIT-TESTED and INTEGRATION-TESTED on synthetic JSONL ledgers, with a real SIGKILL inside the dispatch-claim
append and inside each step of applying a recovery. Not SANDBOX-VERIFIED, not EXTERNALLY VERIFIED, not FOUNDER-ACCEPTED. No supervisor has called recovery, and CMC,
VDM and VEPMC remain 0.

## Not achievable in this increment (preserved targets with blocking dependency)

- Autonomous restart (P2 in full) is blocked on the founder's selection of a supervisor or trigger (G5).
- Independent verification of recovery in an isolated facility is blocked on SR001's isolated verification facility.
- Alias-proof locking inside `EvidenceLedger` is blocked on a ledger-owner change to the boundary package, which
  organs must re-pin.
- An empty file, a torn or zero-filled genesis line, and a NUL hole inside a record are refused by design, so a
  person decides. Tolerating them is a ledger-recreation decision, best taken with G5 or with self-delimiting
  framing.
- Recovery of a torn line in an organ's own ledger (WMI, DALEOBANKS) is blocked on organ adoption. The organs pin the
  boundary archive at `4999acff`, so this module reaches them only when they re-pin.

## Rollback and kill criteria

**Rollback.** Revert the fifth-increment commits. The module is additive and nothing imports it outside its tests.
Quarantine files and chained recovery events produced by any run remain as evidence. A quarantined line can be inspected
from its file and never needs to be restored.

**Kill criteria.** Kill the mechanism if any of these occurs:

- any recovery drops an acknowledged record without a named risk that admits it;
- a ledger ever opens with its torn bytes removed and no recovery event;
- a completed or foreign plan is ever replayed;
- a torn record is ever admitted;
- recovery is ever cited as authority to act;
- the founder rules that ledger repair must be impossible rather than explicit.
