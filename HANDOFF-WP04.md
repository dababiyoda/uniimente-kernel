# HANDOFF-WP04: Postgres Spine Backend + Rebuild-From-Spine Drill

Status: COMPLETE. Branch: `build/pg-spine` (stacked on `build/real-adapter-loop`).
Spec: `SPEC-WP04.md` v1.0 — implemented faithfully; **no deviations**.

## What was built

- `kernel/spine/pg.py` — `PostgresSpine`, a drop-in for the WP-01 file `Spine`
  (`append`, `get`, `iter`, `verify_chain`, `next_seq`), plus the clearly-marked
  REBUILD-ONLY `append_record(record)` used by the drill. Frozen WP-01 hash
  formula replicated exactly; lazy psycopg v3 import; idempotent DDL; advisory
  `pg_advisory_xact_lock(hashtext(table))` writer serialization; strict table
  identifier validation (`^[a-z_][a-z0-9_]*$`, <= 63 chars); all values
  parameterized; Python-side `verify_chain` (fails closed, False on connection
  failure); fake-connection injection via the `connect` parameter.
- `kernel/spine/__init__.py` — exports `Spine`, `SpineError`, `GENESIS_HASH`,
  and `PostgresSpine` via a module `__getattr__` lazy guard: importing without
  psycopg installed works; only instantiation raises `SpineError` with guidance.
- `scripts/rebuild_drill.py` — the Continuity proof. Reads the DSN from
  `UNIIMENTE_SPINE_DSN` only (exit 2 + instructions if absent). Drops/recreates
  the drill-owned tables `wp04_origin` / `wp04_rebuilt` / `wp04_tampered`, runs
  the full gate loop (compiled constitution + echo adapter, no external
  network) into origin, replays origin into rebuilt via `append_record`
  (re-validating every record's hash before accepting), runs the SQL tamper
  negative control, writes `proof/wp04_rebuild_capsule.json` (refuses to write
  if the DSN would appear in it), prints a one-line verdict, exit 0 only if
  all proofs hold.
- `tests/spine_pg/` — 19 tests (SPEC section 4 items 1–10; item 4 split into
  its four anomaly sub-cases, item 7 parametrized, plus an `append_record`
  rebuild-path test) over an in-memory `FakeConnection`/`FakeCursor` DBAPI
  stub. No live database in the suite.
- `proof/wp04_rebuild_capsule.json` — live-drill evidence (no credentials).

## Verification evidence

- Full suite: **177 passed, rc=0** (158 pre-existing + 19 new).
- Hash-parity vector: `tests/spine_pg/test_pg_spine.py::test_01_...` appends a
  fully pinned model to the file `Spine` and to `PostgresSpine`-with-fake and
  asserts the sealed records are byte-identical (and equal to the hand-computed
  frozen formula).
- Live drill against Neon (`python scripts/rebuild_drill.py`, DSN from env):
  `ok=True origin_records=10 rebuilt_records=10 hash_parity=True
  verify_origin=True verify_rebuilt=True verify_tampered=False
  tamper_control=PASS
  head=d0a05131e09782da327b8f8bd7e327a7102cbf0fd8914beb6a43ac3dee79ba13` — rc=0.
  (Independently re-run by the verifier after the build; same verdict. The
  capsule in `proof/` is the verifier's run — head hashes differ between runs
  because gate-loop records carry wall-clock timestamps; the proven property
  is origin/rebuilt byte-parity, not a pinned head.)
- Capsule credential check: `grep -c "npg_"` = 0, `grep -c "neon.tech"` = 0,
  `grep -ci "postgresql://"` = 0 on `proof/wp04_rebuild_capsule.json`; the
  script additionally refuses to write the capsule if the DSN appears in it.

## ADRs (confirmed, per SPEC section 6)

1. Python-side hash verification only — the database is storage, never a
   trusted verifier; `verify_chain` re-reads and re-hashes every row.
2. Advisory xact lock serializes writers on the single-chain table.
3. JSONB for payload/refs: JSONB round-trips values, not key order;
   `canonical_json` re-sorts keys, so record hashes are stable. Reads accept
   both decoded objects (real psycopg) and JSON strings (fake layer).
4. psycopg lazy import + `connect` injection: no new hard dependency for
   non-Postgres users; the test suite never imports the driver.
5. `append_record` is REBUILD-ONLY: re-validates key set, record_hash against
   the frozen formula, seq continuity, and prev_hash linkage before accepting
   a replayed record. Faithful replay reproduces identical hashes.
6. Credentials only ever via the DSN env var — never in code, tests, or proof.

## Limitations (honest, per SPEC section 7)

- Single-chain table; no sharding or multi-tenant namespacing beyond the
  `table` parameter.
- The advisory lock serializes writers on ONE database; cross-database
  federation is a later organ.
- File spine remains the dev/capsule backend; a file -> pg migration tool is
  future work (the drill's replay path demonstrates the mechanism).
- `PostgresSpine` holds one persistent connection per instance; callers doing
  their own process forking should construct per-process instances.

## Resume steps for the next agent

1. Read `SPEC-WP04.md`, this file, and `kernel/spine/pg.py`.
2. Re-run the suite: `python -m pytest tests/spine_pg -q` (no DB needed).
3. Re-run the live drill (needs the DSN env var; never commit it):
   `UNIIMENTE_SPINE_DSN=... python scripts/rebuild_drill.py` — expect rc=0 and
   a fresh `proof/wp04_rebuild_capsule.json`.
4. Next work package per the locked build order: Phase 2 — the First
   Evolution Cycle (ClosureLoop, StrategyTree, StrategyBranch, SpiderWebAudit,
   ExperimentSpec, EvolutionCapsule, VerifierRecord, RetainRegressKillDecision).
