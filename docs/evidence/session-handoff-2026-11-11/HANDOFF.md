# Session handoff, 2026-11-11 (session `session_01Kucyfm9exT5imDVYvHTYSv`)

Saved because the session ran out of budget mid-work. This branch is evidence only: **not for merge**. It holds
the connected staffing proof, the raw results of two review workflows, and the exact continuation steps.

Reality status of everything below: sandbox, test keys, a cloud container. No founder-device run. VEPMC 0.
No merge, deployment, spending, publication or outside contact happened.

## 1. State of each branch

| Branch | Head | State |
|---|---|---|
| `egregore/fervent-mayer-syy5d6` (PR #291, child of #290) | `7245fa5d` | Pushed. Reviewed adversarially; fixes below are owed |
| `claude/directive-map-s69a6-20261111` | `252be328` | Pushed, no PR yet. Reviewed: sound with fixes; fixes owed |
| `claude/revoked-device-authority-20261111` | `d7c43ce5` | Pushed, no PR yet. **WIP: builder was stopped mid-build, tests unconfirmed, unreviewed** |
| `integration-rehearsal-20261111` | `b8d95167` | Local only, not pushed (no new trunk). Recipe in section 3 |
| `claude/session-evidence-20261111` | this branch | Evidence only |

All are based on #196 `8d20532464b1533b28d71d8331ca3412a90dbb11` except #291, which is based on #290 `facea170`.

## 2. PR #291: what is done, what the review found

Done at `7245fa5d`: the office refuses an adapter, manifest or context that is not the registered one; a
caller's `around` runs only inside the Gate's dispatch; `registry` is required and a `None` registry refuses
every act. 29 tests pass across both authority files; mutation gates 11/11 and 5/5.

Hosted CI: the full suite on the second commit `3325f8e0` gave 11,441 passed, 9 failed; the nine are the
stand-in tests fixed in `9039eec0`. On `7245fa5d` Canonical CI run 43029662008 was still running; its job 6
died in `apt-get` (DNS failure) before any test. **Owed: re-run that job once when the run completes.**

Independent adversarial review of `7245fa5d` (three lenses, each finding re-run by a skeptic; raw results in
`workflow-journals/wf_a16f6b74-f43-journal.jsonl`). Both named concerns hold at this head: no caller code
before authorization, no execution without a registry. Confirmed findings, in priority order:

1. **Test gaps (in model, medium).** 11 of 16 new mutants of `greg/authority.py` survive both authority test
   files. The important ones: no test fails when a detached write adapter runs under an attached read-only
   manifest *with a matching context* (my test also mismatches the context, so the adapter check alone is
   unpinned); the context check has no test for an edited manifest of the same id or a missing one; nothing
   pins that a wrapped adapter runs exactly once inside the dispatch; the two ratchet tests
   (`AROUND_CALLERS`, `OFFICE_BUILDERS`) miss some spellings of a caller or builder. **Owed: add those tests
   and mutants to the gate.**
2. **`adapter=None` or `ctx=None` (low).** `attach_refusal` skips the identity checks for a `None` adapter or
   context, and `act` then issues a grant and records an UNCERTAIN dispatch. **Owed: `act` refuses a `None`
   adapter or context before any grant.**
3. **Manifest identity trusts the presented object's own `digest()` (low, needs hostile in-process code).**
   Consider computing the digest with the registered manifest's class, or comparing `to_dict()`.
4. **Pre-existing, not caused by #291, separate units:**
   - *Retained negative receipt reused as DONE (medium).* In `AuthorityOffice.act`, the retained-receipt
     branch returns DONE without checking `result_class`; a refused compensation is recorded DONE after a kill
     and the founder is never asked. The legacy-scope branch a few lines above does check `positive`.
   - *The appraiser runs a founder-DETACHED sensor's adapter directly (low, in model).* Path:
     `Body.tick -> _close_out -> _appraise_closure -> Body.appraise`. No office, grant, receipt or attach check.
5. **Composition (confirmed).** A clean merge of #273 onto #291 refuses every off-turn worker until #273's
   one call site in `greg/missions.py` passes `adapter=adapter, around=wrap`.

## 3. Combined tree: #196 + #290 + #291 + #273 + #278

Local branch `integration-rehearsal-20261111` at `b8d95167`: start at #196 `8d205324`; merge #290
`facea170`, #291 `7245fa5d`, #273 `331de165`, #278 `a639add7`; then change the one call site
(`adapter=wrap(adapter)` to `adapter=adapter, around=wrap`). Result reported by the composing reviewer: every
listed test file passes except the failures this container already has on #196 itself; no other composition
defect found. The per-file table and conflict notes are in the `attack:compose` result in the journal.

## 4. Connected staffing proof (verification only)

Kernel #196 `8d205324` against the real organs at the commits the kernel's CI pins:
`tests/integration/test_organ_staffing_figures.py` 7 passed, 0 failed, 0 skipped;
`tests/unit/test_greg_organs.py` 43 passed, 0 skipped, the five live exchanges included. The 8-of-8 and
4-of-8 packets come back with different assessments. Full record, commits, environment and the captured
assessment fields: `staffing-proof/EVIDENCE.md` (checksums in `SHA256SUMS`). This dependency is **built and
reproduced**; it needs no further build, only the organ `main` merges that are the founder's.

## 5. Completion map, S69.A6

`claude/directive-map-s69a6-20261111` `252be328`: the entry now cites five passing tests, tier UNIT_VERIFIED,
coverage "partial", still open under unit S69-A. No count moves: 82/272 met, 125 buildable, before and after.
Independent review: sound with fixes. **Owed before a PR:**
- the commit message says a surviving mutant's safeguard has no failing test; another test does fail without it;
- the note's stale-anchor sentence holds for 15 of 27 gates, not all;
- `check_seed_mutants.py` catches 6 of 7 with requirements installed, where the tree's text says 7 of 7;
- no test pins what a gate counts as "caught" (the cited runner test passes with the rule removed);
- the reviewer lists other asks that still record gated, passing behaviour as nonexistent (journal:
  `review:map`). They are not edited on this branch.

## 6. Revoked-device approvals (WIP)

Founder policy, verbatim, is in `docs/intent/sources/REVOKED-DEVICE-AUTHORITY-2026-11-11-source.md` on the WIP
branch. The builder added `greg/revocation.py`, changes in `greg/body.py`, `missions.py`, `asks.py`,
`appraisal.py`, `cli.py`, `goal_gravity.py`, `remote.py`, a test file, a mutant gate, an ADR and a
deliberation record (17 files, about 2,200 lines). It was stopped before reporting. **Nothing on that branch
is verified.** Owed: run its tests, read the whole diff, run the adversarial review written for it (prompt in
`workflow-journals`, unit `device`), fix, then open a draft PR. It also edits `foundry/owned-source.json` and
`docs/FOUNDER_INTENT_LEDGER.md`; check both edits are warranted.

## 7. Next steps, in order

1. Re-run CI job 6 on #291 once; confirm Canonical CI on the head.
2. #291: fix findings 1 and 2 of section 2 (tests and mutants first), push, update the PR receipt.
3. New small PR off #196: the retained negative receipt reused as DONE (reproduce, fix, test).
4. S69.A6 branch: apply the owed corrections, open a draft PR.
5. Revoked-device branch: verify, review, fix, open a draft PR.
6. New small PR: the appraiser runs a detached sensor's adapter.
7. Then choose the next capability unit from the open directive units (`python -m acceptance directive`):
   candidates read so far are S40-A (a ratified procedure answers the founder's words with zero model calls),
   S40-C (a compounding SOP becomes a callable capability), S50-A (qualify a newly selected model route) and
   S51-A (organ consequence seams verify a Kernel gate decision). Check the board and open PRs for claims first.

## 8. Founder decisions still open

- Intake of #290 then #291 into #196, with the one-line #273 change.
- #291 reverses #290's choice that an office without a registry "keeps its earlier behaviour".
- Whether an unconsumed device approval is voided on revocation (your stated preference: yes; being built).
- `check_seed_mutants.py` in CI (S-3).
