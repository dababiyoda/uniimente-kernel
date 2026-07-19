# HANDOFF — Work Package WP-03: Real Adapter Loop (Proof Capsule)

**Date:** 2026-07-20 · **Repo:** dababiyoda/uniimente-kernel · **Branch:** build/real-adapter-loop (stacked on build/ucl-compiler)
**Spec:** SPEC-WP03 v1.0 · **Lineage:** build/consequence-gate (WP-01) → build/ucl-compiler (WP-02)

## 1. Current state

The first verified external consequence is closed and sealed. ONE real HTTPS
GET of `https://example.com/` ran through the full 15-stage Consequence Gate
under the compiled five-file constitution (C2 → REQUIRE_HUMAN → founder
approval → one_use grant → signed CommitWitness → REAUTHORIZE → execute →
signed receipt → VERIFY → RECONCILE → OUTCOME → closed DecisionEpisode), and
the complete hash-chained artifact chain is committed at
`proof/wp03_capsule.json`.

New code:

- `kernel/adapters/http_research.py` — `HttpResearchAdapter(BoundedAdapter)`:
  the DALEOBANKS `services/websearch.py` trust model re-expressed as a kernel
  adapter. `adapter_id = "http-research"`; one action family
  (`research_fetch`); https-only; label-exact egress allowlist (fixes
  DALEOBANKS finding F1: `notgov.example` no longer matches `gov`); GET only;
  fixed User-Agent; 10 s timeout; 256 KiB body cap (reads cap+1, refuses —
  never silently truncates); ≤3 redirects, every hop re-checked against the
  allowlist; injectable `fetcher(url, timeout, max_bytes) -> FetchResult`
  (frozen: status_code/body/final_url); fail closed on every ambiguity. The
  body never leaves the adapter — only its sha256.
- `scripts/capture_proof_capsule.py` — runnable proof: builds spine (temp
  dir), fresh founder key, gate with compiled `policy_fn`, real fetcher;
  proposes the golden C2 `research_fetch` intent; founder-approves the exact
  fingerprint; runs the loop for real; writes `proof/wp03_capsule.json`;
  prints a one-line verdict; exits nonzero on any failure.
- `tests/adapters/` — 15 tests (SPEC §4), stub fetcher only, no network.
- `kernel/adapters/__init__.py` — exports `HttpResearchAdapter`, `FetchResult`
  (the only pre-existing file touched; WP-01 gate/contracts/spine untouched).

## 2. Verification evidence

- `python -m pytest -q` from the slice root: **158 passed, rc=0**
  (143 WP-01/WP-02 tests still green + 15 new WP-03 tests).
- Real proof run: `python scripts/capture_proof_capsule.py` →
  `ok=True status=200 bytes=559 body_sha256=ff67a9d7…a299d reconciled=True
  verify_chain=True records=10`, exit 0. Exactly one real GET (example.com
  answers 200 directly; the adapter never re-fetches).
- Capsule independently re-verified from the committed JSON: seq/prev_hash/
  record_hash chain re-computed over all 10 records — OK; reconciliation
  `reconciled: true`; `provider_response_hash` 64-hex; the string
  "Example Domain" (body content) appears nowhere in the capsule.
- State label: **implemented, locally tested, ONE real external loop closed
  and proven. NOT merged, NOT production-proven.**

## 3. ADRs

1. **Stdlib urllib only, no new dependencies** (kernel stays
   dependency-minimal; TLS verification is the urllib default, never
   disabled).
2. **Label-exact host matching** (`host == d or host.endswith("." + d)`,
   case-insensitive) fixes the DALEOBANKS F1 `endswith` suffix bypass.
   Exactly one trailing dot is stripped before matching
   (`example.com.` matches; `example.com..` refuses). The URL fetched is the
   original witness target; only the match uses the normalized host.
3. **Bodies hashed, never stored** — spine, receipt and capsule carry sha256
   only (copyright/size hygiene; zero attacker bytes reach the caller).
4. **`example.com` added to the default allowlist** as the canonical proof
   target (IANA-operated, content-stable). Production research targets still
   require per-target approval: the fingerprint binds the exact URL.
5. **Transport injection** (`fetcher` constructor arg) — tests stub it; the
   gate's witness path is identical either way.
6. **Receipt attestation hash (contract-shape note, per SPEC §3.3 — WP-01
   shapes NOT changed).** WP-01 RECONCILE compares
   `sha256(canonical_json(witness.expected_outcome))` with
   `provider_response_hash`. `expected_outcome` is a `str`, so its canonical
   form is a JSON-quoted string; a raw-body `sha256(body)` can therefore
   NEVER reconcile for a non-JSON body (HTML). The adapter consequently
   returns the outcome-**attestation** hash
   `sha256_hex(canonical_json(witness.expected_outcome))` — identical to
   EchoAdapter semantics — but only after cryptographically verifying the
   live response against the approved expectation: when `expected_outcome`
   parses as a JSON object carrying `status_code` / `final_url` /
   `body_sha256`, every present key must match the observed response or
   execution is refused. The raw body hash travels in the receipt's signed
   `external_id` fetch-facts (the only free result field in the WP-01 receipt
   shape) as `body_sha256`, alongside `status_code`, `bytes_fetched`,
   `final_url`, `allowlist_version`, `fetched_at`. In the unit tests the stub
   body is crafted as `canonical_json(expected_outcome)`, so
   `provider_response_hash == sha256(body)` holds there numerically and
   SPEC §4 test 1's assertion passes literally. SPEC §3.1's bullet
   "`provider_response_hash = sha256_hex(body)`" is therefore satisfied in
   tests and by `body_sha256` in the signed receipt for the real run; making
   the receipt field itself the raw-body hash would require a WP-01 contract
   change, which SPEC §3.3 defers to a separate work package.
7. **Action-family enforcement by target shape.** The WP-01 CommitWitness
   carries no `action_type` field, so the adapter cannot literally read the
   family. A witness is `research_fetch`-shaped iff its exact target is an
   allowlisted https URL; witnesses minted for other families (subprocess,
   filesystem, …) are refused at target validation (test 12). Binding the
   family string itself into the witness is a WP-01 contract change (separate
   WP).

## 4. Limitations (honest)

- Read-only GET. No POST, no auth, no cookies. Writes remain future work.
- Approval is issued by an in-process founder key for the proof run; the
  hardware-key ceremony is a later work package.
- One action family (`research_fetch`). The 100% Verified Mediated
  Side-Effect Coverage threshold applies to this family only, per the build
  order.
- The proof pins the current IANA example.com body hash
  (`ff67a9d7…a299d`, 559 bytes). If IANA ever changes the page, the adapter
  refuses to attest and the script exits 1 — fail-closed by design; re-pin
  the hash (one line in `scripts/capture_proof_capsule.py`) to renew the
  proof.
- Budget caps remain gate defaults, not constitution-derived (WP-01
  limitation, unchanged).

## 5. Resume steps for the next agent

1. WP-04: Postgres spine backend behind the same `Spine` interface;
   rebuild-from-spine drill.
2. Renew/extend the proof: additional allowlisted targets via per-target
   approval; hardware founder key ceremony.
3. Contract-shape WP: add a dedicated receipt metadata/result field (and,
   if desired, raw-body `provider_response_hash` semantics + witness
   `action_type`) as its own versioned work package — do NOT piggyback it
   onto adapter work.

## 6. Rollback

Delete branch `build/real-adapter-loop`. WP-01/WP-02 files are untouched
(except the additive adapter `__init__` export); blast radius is the new
files only.
