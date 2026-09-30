# Independent Verification — main @ 8cb3074a (canonical-v1 merge)

**Auditor:** Kimi (independent session; no shared state with the releasing session)
**Date:** 2026-08-22 (run timestamps UTC 2026-08-21T18:53–19:01Z)
**Subject:** `main @ 8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1` — the canonical-v1 merge commit
**Method:** byte-exact mirror reconstruction, then independent execution of the full test suite, both verifiers, all three CI scripts, the developmental module, and both evolution experiment harnesses.
**Governing rule for this audit:** never allow the system's opinion of itself to serve as sufficient proof. Every number below comes from an independent run against bytes proven identical to the release, not from the release's own records.

---

## 1. Mirror reconstruction — the foundation claim

**291/291 files.** Every local file's git blob SHA-1 (`sha1("blob {len}\0" + bytes)`) equals the remote tree's blob SHA at `8cb3074a`. Zero missing, zero extra, zero mismatched.

- Fetch channel: GitHub API file contents (repository is private; no git protocol available).
- Encoding edge cases were resolved by SHA arbitration, never by assumption: most remote markdown/JSON blobs carry a trailing newline (applied where the SHA required it), and the two `docs/release/package-{3,4}/EVIDENCE_RECORD.json` blobs store em-dashes as literal `\u2014` 6-byte ASCII sequences (restored by byte replacement, then SHA-verified).
- Record: `docs/audit/runs-8cb3074a/mirror-verification.json`.

Why this matters: every execution result in §2 ran against bytes proven identical to the release — not against a partial or assumed tree. The historical record contains verifier runs executed against partial mirrors (their own `skips` fields say so); this audit's first act was to make that confusion impossible for its own runs.

## 2. Execution results

All records preserved under `docs/audit/runs-8cb3074a/`, including the failing one. Environment: Python 3.12.12, pytest 9.1.1, pyyaml 6.0.2, jsonschema 4.25.1, Linux.

| Command | Result | Exit |
|---|---|---|
| `python3 -m pytest -q` (full suite) | **493 passed, 2 skipped, 0 failed** in 9.45s | 0 |
| `python3 -m pytest tests/unit -q -rs` | **472 passed, 2 skipped** in 13.87s | 0 |
| `python3 verifier/verify.py` (v1, standalone) | **FAIL C2** — see Finding 1 | **1** |
| `python3 verifier/v2/verify.py` (V1–V5 harness) | **PASS all five stages** | 0 |
| `python3 scripts/ci/check_schema_refs.py` | PASS — 13 schemas, 12 local refs resolve | 0 |
| `python3 scripts/ci/check_authority_singleton.py` | PASS — exactly one source of authority per governed artifact | 0 |
| `python3 scripts/ci/check_sealed_developmental.py` | PASS — external_effects=0, SIMULATED_NOT_AUTHORIZED, verdict intact | 0 |
| `python3 -m developmental` | runs to completion; verdict `MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED` | 0 |
| `python3 -m evolution.repair` (Package 3 reproduction) | **REPRODUCED** — §2.1 | 0 |
| `python3 -m evolution.migration` (Package 4 reproduction) | **REPRODUCED** — §2.2 | 0 |
| Wave-0 exact-duplicate scan at the full 291-file tree | 0 duplicate groups, 0 undeclared | 0 |

The v2 harness detail: V1 45/45 canonical artifacts present; V2 472 passed + 2 skipped; V3 all 20 modules closed; V4 false closure → FALSELY_CLOSED, gate loops → CLOSED; V5 18 module READMEs declare the buildability standard. The verifiers' own self-records from these exact runs are committed to `verifier/runs/` in this PR — including the v1 FAILURE record, which is evidence, not debris.

### 2.1 Package 3 (`evolution.repair`) reproduction

Compared field-by-field against the committed `docs/release/package-3/EVIDENCE_RECORD.json`. **Matched:** spec seal `6f6d7dab…c4ab7f4a`, baseline commit, decision (`regress`), all four trial scores (1.0), qualification flags, selection (B0 cheapest / R1 best structural), secondary ranking order (B0 < R1 < R3 < R2), prediction summary (2 of 4 fully held — the R3 failure reproduces), continuity unchanged, capsule measured value 1.0. **Differed:** only the experiment-local ledger head — by design, since the ledger is rebuilt per run and its records carry timestamps; 31 records and `chain_verifies: true` in both runs. Record: `evolution-repair-comparison.json`.

### 2.2 Package 4 (`evolution.migration`) reproduction

Compared against `docs/release/package-4/EVIDENCE_RECORD.json`. **Matched on every compared field:** spec seal `24643845…df44b`, decision (`regress`), trial scores (W0/W1/W2 = 1.0; **W3-journal = 0.0 with `state_survives_migration: false` — the "usefully wrong" prediction reproduces exactly**), selection (W1-projection), the malformed-checkpoint control (refused **before** append, 0 malformed in ledger, the same five violations named), rollback triple, continuity, prediction summary (3/4 held), 38 ledger records. Record: `evolution-migration-comparison.json`.

## 3. The 172 / 305 / 474 / 495 question — resolved by measurement

| Number | What it actually is | Evidence |
|---|---|---|
| 172 | tests/unit on **archived main @ 3d9b577** (2026-07-19 era) | in-repo v2 records 19:31/19:32 |
| 305 | canonical-v1 **candidate baseline CI** @ 8b55efa | release docs (not re-run here) |
| 474 | tests/unit **with git history** (v2 record 2026-07-26T17:57) | independently reproduced as **472 passed + 2 environmental skips** |
| 495 | full suite **with git history** | independently reproduced as **493 passed + 2 environmental skips, 0 failed** |

The two skips are `test_migration_spec_frozen.py:62` and `test_repair_spec_frozen.py:84` — `git merge-base --is-ancestor` assertions that skip when no git object store is present (this mirror is API-fetched, so it has no `.git`). The merge commit's own wording — "493 passed / 2 skipped under CI (495 passed locally; the 2 skips are git-ancestry assertions that skip under CI's shallow checkout)" — is **confirmed in every particular**. All *other* frozen-spec checks in those same files (byte-identity hashes of `linker/` and of the `DurableWorkflow`/`WorkflowStep` classes, canonical-construction-site AST assertions) **ran and passed** on this mirror.

## 4. Findings

### Finding 1 — DEFECT, survives on current main (@ 542c8f57): `verifier/verify.py` C2 stale schema count

`verifier/verify.py` line: `check("C2", not bad and len(schemas) == 9, ...)`. The tree contains **13** `contracts/*.schema.json`, all individually valid draft 2020-12 (the check's own defect list is empty; it fails on count alone). Result: the standalone v1 verifier **exits 1 on a healthy canonical tree**. Reproduced twice; the failing self-record is committed in this PR. Verified still present on `main @ 542c8f57` (blob `2db96527…`).

The v2 harness (what canonical CI actually runs) is unaffected — its V1 stage checks artifact presence, not schema count — which is why the release's "V1–V5 PASS" claim is simultaneously true (v2 stages) and incomplete (the standalone v1 script is red).

History: `== 9` dates from 2026-07-19, when 9 schemas existed. The Phase-Zero `$defs` repair and canonical-v1 grew the set to 13 without updating the canary.

**Proposed repair** (separable final commit of this PR): `== 9` → `== 13`. Kept strict deliberately: the hard-coded count functions as a *deliberate-addition canary* — any new schema must consciously update the verifier. Loosening to `>=` would silently retire that property. The larger option — formally deprecating standalone v1 as superseded by the v2 harness — is a founder decision and is presented in the companion issue, not decided here.

### Finding 2 — prior audit defect C: survives, narrowed

`provenance/ledger.py` `EvidenceLedger` exposes `append` and `verify_chain` only — **no `replay` method** — while `provenance/README.md` still promises "Recovery path: rebuild by replay". No caller invokes `ledger.replay()` (replay lives on the event spine: `closure/kernel_registry.py:319,377–378`), and the full suite passes. Status: **documentation-vs-code mismatch, not runtime-breaking.** Defects A, B, D, E, F, G of the prior audit were confirmed fixed in earlier segments of this audit trail.

### Finding 3 — trail hygiene: main tip 542c8f57 is a verifier record from a stale partial mirror

The single commit atop the canonical-v1 merge adds `verifier/runs/v2-2026-08-21T14-36-39…json` reporting **172 tests / 13 modules / a V1 partial-mirror skip** — the pre-canonical signature. The record is honest (its own `skips` field discloses the partial mirror), so this is not falsification. But run records do not bind to the commit they measured, so main's newest evidence describes a tree main does not contain. **Recommendation (proposal only, no code in this PR):** verifier run records should embed the HEAD commit when a git object store is available, and `MIRROR_UNKNOWN` when not.

## 5. Release-claim scoreboard

| canonical-v1 claim | Independent measurement | Verdict |
|---|---|---|
| V1–V5 PASS (v2 harness) | V1 45/45, V2 472+2skip, V3 20 modules, V4 false-closure detected, V5 18 READMEs | **CONFIRMED** |
| 13 schemas / 12 local refs resolve | identical output | **CONFIRMED** |
| authority singleton | identical output | **CONFIRMED** |
| sealed developmental, external_effects=0 | identical output | **CONFIRMED** |
| Package 3 evidence record | reproduced on every substantive field | **CONFIRMED** |
| Package 4 evidence record | reproduced on every compared field | **CONFIRMED** |
| "495 passed" (merge claim, local) | 493 passed + 2 git-ancestry skips, 0 failed | **CONFIRMED, with the claim's own caveat reproduced** |
| continuity fingerprint `c1d621a8…` unchanged | unchanged in both reproduced experiments | **CONFIRMED** |
| "verifier V1–V5 PASS" read as covering standalone `verify.py` | standalone v1 **FAILS C2** (Finding 1) | **CLAIM SCOPE NARROWER THAN A READER WOULD ASSUME** |

## 6. What was NOT inspected (fail-closed: no unperformed inspection is claimed)

- The two git-ancestry tests could not execute (no git object store over API access); only their skip conditions were verified.
- GitHub Actions runs (e.g. 30214050333) were read from records, not re-run.
- The release manifest self-hash, the archive tag `main-pre-canonical-v1-2026-07-19`, and release id 360089207 were not re-fetched this round; the merge commit's description of them is accepted as a record, not independently confirmed here.
- DALEOBANKS and WealthMachineIntelligence were out of scope for this slice.
- This audit ran on main @ 8cb3074a. Current main is 542c8f57 (+1 verifier-record commit, Finding 3); Finding 1 was re-confirmed against 542c8f57 directly.

## 7. Cross-model handoff envelope

```yaml
handoff:
  from: kimi-independent-verification (this session)
  to: [founder, claude-sessions, chatgpt-sessions, kimi-reconciliation-session]
  date: 2026-08-22
  canonical_owner_of_reconciliation_trail: PR #82 (kimi/collaboration-reconciliation-2026-08-22) — Wave-0 inventory of main @ 542c8f57
  this_work:
    type: independent_verification
    subject: main @ 8cb3074a (canonical-v1 merge)
    relation_to_pr82: complements, does not duplicate — #82 inventories paths; this audit byte-verifies content and executes the tree
  artifacts:
    mirror: 291/291 blob-SHA-verified
    evidence_pr: this PR
    decision_record: companion founder issue (cross-linked)
  open_questions_for_founder:
    - v1 C2 repair: bump to 13 (proposed here) vs deprecate standalone v1 vs leave
    - EvidenceLedger.replay: implement vs correct the README promise
    - run-record commit binding (Finding 3 recommendation)
    - archive tag/branch protection (both exist; both unprotected per merge-commit record)
    - boundary L1-L4 (carried from docs/release/canonical-v1/03-core-venture-boundary.md)
  constraints_respected:
    - no default-branch modification; merge authority remains the founder's
    - failing run records preserved, not curated
    - no inspection claimed that did not happen (§6)
    - no parallel canonical governance created; this trail attaches to the existing one
```
