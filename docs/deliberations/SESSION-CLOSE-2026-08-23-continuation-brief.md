# Session close — 2026-08-23 continuation brief

**Session:** Claude, Opus Maximus continuation under `FOUNDER-RULING-2026-08-23`.
**Branch:** `claude/uniimente-infinite-goal-chase-rjxvzo` (kernel, DALEOBANKS, WMI).
**Base:** stacked on `claude/opus-maximus-audit-eay0ek` (PR #71).

**Note on this file.** The founder's instruction listed this path as something
to inspect. It did not exist in any branch at session start — a previous session
either never wrote it or never pushed it. Created here so the reference resolves,
and flagged rather than quietly filled in, because a brief that appeared without
explanation would be indistinguishable from one that was always there.

---

## 1. Ruling discharged, in the founder's order

| Step | State | Where |
|---|---|---|
| CONTRADICTION-0002 (Option A) | **done** | kernel PR #87 |
| CONTRADICTION-0003 (A + B) | **done** | kernel PR #87 |
| Witness v2 live emission | **done** | kernel PR #87 |
| Workload-identity adoption | **1/6 edges** | kernel PR #87 |
| Peer parity | **proposed** | DALEOBANKS PR #74, WMI PR #32 |
| Internal Alpha | **bottleneck named** | see §4 |
| Recompute the goal chase | **done** | `docs/INFINITE_GOAL_CHASE_RECOMPUTE-2026-08-23.md` |
| CANARY-0001 GO/NO-GO | **awaiting founder** | §5 |

---

## 2. Verification at session close

```
python -m pytest                  1236 passed        (1169 at PR #71 head)
scripts/ci/*.py                   all three PASS, including check 3
python -m governance.integrity    12 artifacts, all as authorised, 1 amendment
python -m governance.gap_audit    14 checked, 14 verified open, 0 stale, 0 anchor lost
python verifier/v2/verify.py      PASS (V1–V5)
python -m governance.decisions    AWAITING_FOUNDER=0  AUTHORIZED=4
python -m bridges.closure_verdict FALSELY_CLOSED (all 7 loops)
```

`CVO = 0`. `HARDENED = 0`. Both unchanged, deliberately.

**Environment gotcha that will cost the next session an hour if unstated:** the
suite needs `cryptography>=42` per `requirements-dev.txt`. This container ships
a Debian-owned 41.0.7 that `pip install -r` cannot replace ("Cannot uninstall
… RECORD file not found"), and the failure mode is 22 PKI tests failing on
`not_valid_before_utc`. `pip install --ignore-installed "cryptography>=42"`
fixes it. `jsonschema` is also absent until installed.

The peer repositories have pre-existing collection errors from absent
`fastapi` / `sqlalchemy` / `apscheduler` / `tweepy`. Verified identical with the
session's changes stashed. Not caused by this work, and not fixed by it.

---

## 3. Five defects found by the mechanisms, not by inspection

Recorded because *how* they were found is the reusable part.

1. **The Gate issued its own capability grant** for external actions. Reachable
   only after CONTRADICTION-0003 removed the confidence conflation — the
   evidence floor had been refusing those proposals earlier in the pipeline, so
   the missing authorization check had never executed. A floor was doing an
   authorization check's job and the two failures looked identical from outside.
   Now refused for any class that reaches outside; internal effects may still be
   self-granted.

2. **Amendment 002 missed two call sites** still comparing live bytes against
   the freeze-time constant. Invisible until the live gate actually diverged.
   Fixed as Amendment 003.

3. **The amendment scope-guard pattern was wrong** — each guard compared against
   the *current* pins, so the third amendment broke the first two. Each now
   compares its own frozen before/after pair. Documented in
   `tests/unit/test_repair_frozen_corpus.py` for whoever writes Amendment 004.

4. **Replay protection did not survive a restart.** `EventSpine._seen_ids`
   started empty at construction, so a reloaded ledger came back with a spine
   that had never seen anything: a byte-identical peer event was accepted and
   ledgered a second time, and the hash chain over the duplicate verifies
   exactly as well as the chain over the original. Found by testing a claim
   this brief had asserted without checking. Fixed by deriving the inbox from
   the ledger, like every other view; pinned by
   `tests/unit/test_restart_resume.py`.

5. **The frozen corpus was an importable second Consequence Gate.** Storing the
   freeze-time artifacts under their real names made
   `evolution/repair/continuity/policy/consequence_gate.py` importable — PEP 420
   namespace packages need no `__init__.py` — so the remedy for
   CONTRADICTION-0002 had created a genuine second path to external effect under
   a reassuring directory name. **CI check 3 ("one source of authority") caught
   it within minutes of the push and was right.** Fixed by suffixing every
   frozen artifact `.frozen` (Amendment 004), *not* by excluding the directory
   from that check — an exclusion would have let the check pass while the
   importable duplicate stayed on disk. No pinned hash changed; only filenames
   moved.

A sixth, smaller: I asserted in-session that the `authorized` criterion was
"already enforced by the grant and identity checks". Wrong, and falsified within
the hour by a test written to protect the canary. The correction is kept visible
in `tests/unit/test_two_confidences.py` rather than tidied away.

---

## 4. The bottleneck, for whoever picks this up

**Composing a durable runtime.** Not the Founder Cockpit, and not a reasoning
organ.

This brief's first draft said "persistent state is absent". Checking that claim
against the code corrected it and found the real defect — see §3, item 4. The
ledger already persists and reverifies on reload, and causal memory and
`replay()` are views over it, so they rebuild for free.

What is missing is that **nothing boots the institution from a state
directory**. Every entry point still constructs a fresh in-memory
`EvidenceLedger("sha256:" + "0" * 64)`. A standing mandate has nothing to stand
in; a cockpit would command a body that forgets between commands.

**Smallest falsifiable step:** an `InstitutionalRuntime.boot(state_dir)` that
composes a durable ledger with the gate, spine and causal memory, plus a test
that runs a governed action, discards every object, boots again from the same
directory, and finds the witness, the chain and the inbox intact.

**Do not write a third implementation.** PR #78 (WP-04) built a Postgres spine
backend and a rebuild-from-spine drill, and DUP-2 in the Kimi reconciliation
recommends porting it behind main's existing spine interface. The JSONL path
already satisfies the Alpha requirement; Postgres is the scale-up, not the
prerequisite.

---

## 5. What is waiting on the founder

1. **CANARY-0001 GO/NO-GO.** Both internal blockers are closed and neither was
   removed by relaxing anything — the 0.70 floor and the sealed 0.55 prediction
   are both unchanged and simply no longer compared to each other. The Gate now
   admits the *consequence-inert rehearsal*; it does not authorise the canary.
   `authorized_by` is `None` with no code path that sets it. Run
   `python -m graduation.packet` for the one-screen decision.

2. **PR #87** (this session), **PR #71** (its base), **PR #86** (ChatGPT's
   Infinite Goal Chase backlog), **PR #74** and **PR #32** (peer parity). All
   draft, all unmerged.

3. **The pre-existing open decisions are unchanged** and were not touched:
   issue #80 convergence ruling (A/B/D), PR #54 ADR-001/D-001, kernel issue #1
   ratification, DUP-3/DUP-4 consumption mechanism.

---

## 6. The stale check-in

The founder's ruling superseded a routine instructing future sessions to expect
or restore 20 failing tests, to avoid technology #31, and to treat
CONTRADICTION-0001 and the settled bridge gaps as unresolved.

**That routine is wrong on every count and must never be treated as authority.**
The 20 failures were fixed by PR #71's Amendment 001; #31 shipped its inert
half; CONTRADICTION-0001 is closed. Current truth comes from current repository
evidence, the Founder Intent Ledger, and the standing ruling.

No scheduled trigger was found in this repository to disable. If one exists in
the session scheduler rather than in the repo, it is outside what this session
can reach, and disabling it is a founder or operator action.

---

## 7. Standing constraints honoured

No merge to main. No deployment. No publication. No external contact. No
spending. No asset movement. No physical actuation. No canary execution. No
network surface opened — `mutual_tls` runs over `ssl.MemoryBIO`, a real TLS 1.3
handshake with real chain validation and no socket.

No authority was created. The one authority-shaped change **removed** an ability
the institution had: the Gate can no longer authorise its own external acts.
