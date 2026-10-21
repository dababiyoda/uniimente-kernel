# Security ports — split record (2026-10-15)

Source directive: `docs/intent/sources/OPUS-MAXIMUS-MASTER-EXECUTION-DIRECTIVE-2026-10-13-source.md`
(security and resilience; preserve and port the mechanisms of open security PRs). Founder ruling:
`docs/deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md`, CONTRADICTION-0002 **Option A**.

The security line (local branch `ports-security`, 19 commits on `19bbdcb`) ports mechanisms from PRs #12,
#13, #21, #26, #55 and #87 onto the canonical paths. Every port refuses more and authorizes nothing new.
The commits split cleanly by one property: **whether they change `policy/consequence_gate.py`**, an
SR-002 founder-ratified continuity artifact (authorized digest `1c189be5…`).

## Part 1 — landed on PR #173 (no gate change)

These eleven commits were cherry-picked with `-x`, so their lineage is retained. Hashes here are the commits as they stand on PR #173 (Part 1) and PR #182 (Part 2). Each commit's `(cherry picked from commit …)` line names its original on the local security line, which was never pushed. On the resulting tree
`python -m governance.integrity --check` exits **0**: 13 protected artifacts, all as authorized, and no
founder key enrolled.

| Port | Commits | Effect | Regression |
| --- | --- | --- | --- |
| #26 egress | `5413e2b`, `0f0d548`, `69ae77f` | `greg/egress.py` is the one opener. Every redirect hop is re-checked: https only, an exact allowlist host, at most 3 hops. Credentials stay on the origin. A request with a body is never re-sent. `Location` is repaired as urllib repairs it. The OCI registry client is routed through the opener. | `tests/unit/test_greg_egress.py` plus the egress cases in the briefs, anchor and capabilities suites; on `4b0de6a` the GitHub token reached a redirect host |
| #87 autonomy | `0d35a9b`, `aa6d08e` | `issue()` above A0 needs a named human authorizer. UNIIMENTE, the subject itself, look-alike spellings and workload URIs are refused. Levels are ints from A0 to A8. The ledger is written first. Copies are handed out. | `tests/unit/test_autonomy.py`: on `4b0de6a`, A8 was minted with no authorizer |
| #13 data plane | `7daef2b`, `67aec70` | Injection is matched on every reading of the text: what a person sees and what a model may read. `identity/text.py` derives the invisible set from Unicode properties. Only instruction patterns are quarantined, or concealment together with a role marker; anything else is flagged. | `tests/unit/test_greg_dataplane_invisible.py`: on `4b0de6a`, three evasions produced 0 flags |
| Option A, historical half | `3af77fc` | `evolution/repair/continuity/` holds byte-identical, content-addressed copies of the twelve continuity artifacts per subject. SR-001, SR-002 and Package 3 read history; the live twelve must stay unchanged across a run. | `tests/unit/test_repair_continuity_history.py`: a tampered or missing copy refuses |
| Option A, live half | `a0b8c16`, `f381d4a`, `a4f13a2` | `governance/integrity`: a live check over the SR-002 baseline. A change counts as authorized only by an `INTEGRITY_AUTHORIZE` envelope signed by an enrolled founder Ed25519 key. `founder-keys.json` is committed empty (Alfonso enrolls himself by his own commit). Committed records only grow. CI job 3 runs the check with `fetch-depth: 0`. | `tests/unit/test_governance_integrity.py` |

Known trade-offs, carried with the ports:

- `authorized_by` (#87) is still a caller-supplied string. It is made explicit and attributable, but
  not unforgeable. The open step is to bind A1+ issuance to a founder-signed decision.
- Legitimate invisible characters (#13) are read as orthography and are not quarantined, but an item that
  combines concealment with a role marker is quarantined. It is retained, never deleted.
- `federation.py` and `embassy_wire.py` keep `urlopen`. They are loopback test-harness clients with no
  bearer credential.

## Part 2 — the gate hardening: draft PR #182, pending Alfonso's signature

These eight commits change `policy/consequence_gate.py` (hardened digest `732607ba97130fc9…`), or are
inseparable from commits that do:

| Port | Commits | Effect |
| --- | --- | --- |
| #55 CASE 27 | `422d131`, `60eceb7` | At commit, only ALLOW passes (REQUIRE_HUMAN passes only with this run's approval covering every reason). Authority fields are bound in the grant. The Gate executes its frozen admission copy, never the caller's mutable object. |
| #21 evidence | `f1c6c8d`, `848c805` | An optional evidence register refuses unknown, invalid or stale evidence at evaluation and at commit. It is **unarmed on every canonical path today**, and the decision record says so (an AST-checked test holds the record to the code). |
| #12 grants | `7f13f40`, `2048f7a`, `2906228` | A child grant is a strict subset of a live lineage. The issuer keeps sealed records. Spending is delegated, not copied. Revocation propagates. |
| record | `2f6a5b5` | `docs/decisions/SR002-GATE-HARDENING-01.json`: the historical tripwire is retired per Option A, and the live check carries the founder decision. |

On that branch the live check exits **1** and names only `policy/consequence_gate.py`
(authorized `1c189be5…`, observed `732607ba…`). That is correct behaviour: the hardening is not authorized
until Alfonso signs it. No digest is re-pinned and no historical hash is rewritten.

**Founder steps to authorize** (on Alfonso's own device, with his own key; no agent can perform them):

1. `python -m greg founder keygen --key <path>`: generate the Ed25519 key, if it does not already exist
   (it prints the 64-hex public key; omit `--no-passphrase` to keep the key passphrase-protected).
2. `python -m governance.integrity enroll --key <path> --label <label>`: enroll the public key, then commit
   `governance/integrity/founder-keys.json` himself (trust on first use; only possible while no key is
   enrolled).
3. `python -m governance.integrity authorize --key <path> --artifact policy/consequence_gate.py
   --sha256 <the full hardened digest> --reason "<reason>"`: append the signed envelope (it refuses any
   digest other than the bytes on disk), then commit `governance/integrity/authorizations.json`.
4. `python -m governance.integrity --check` exits 0.

To reject instead, close the draft PR. The gate stays at `1c189be5…`.

## What this record does not claim

- None of these ports has been externally attacked or independently verified. Their evidence is the
  regression tests and the bypass reviews recorded in each commit message, at the SANDBOX tier.
- Merging this record arms nothing. The evidence register stays unarmed, and the gate hardening is not
  active until it is authorized and merged.
- Chat text, a path, a hash or a caller string never authenticates Alfonso. Only his enrolled key does.
