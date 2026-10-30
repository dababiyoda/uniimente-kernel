# Digest-rule consolidation — 2026-10-30

Session `session_01KucyfmCJx5if8GZ8bFqy1R`. Base: #196 head `f65638b3`. Scope: maintenance on
the integration line; no authority, evidence or mission semantics change.

## What was measured

An organization audit of the #196 tree (972 Python files outside the lineage archive, 266k lines):

| Finding | Count | Disposition |
| --- | --- | --- |
| Byte-identical tracked files | 37 groups, 65 extra copies, 2.9 MB of ~98 MB | **Kept.** 2.5 MB is the deliberate Track A/B lineage archive (`docs/collaboration/lineage-archive/`); the rest are content-addressed continuity objects and dated evidence copies. Removing them would break the lineage they exist to prove. |
| Private `_canon` / `_sha` / `_digest` / `_hash` / `_now` helpers | ~60 definitions in ~45 files | **Consolidated where safe** (below). |
| Copies of the exact one-sided sign test | 8 | **Kept.** Every copy is in a frozen evaluation runner or a module whose source hash an admission freeze pins. |
| Re-implementations of `egregore.contracts.canonical_json` | 2 (`cortex/contracts.py`, `governance/integrity/__init__.py`) | **Kept.** Both are deliberately import-independent: the integrity check must not import what it guards, and the cortex seed is a separable package. Their rule is identical and tested in place. |

## The defect behind the duplication

The private helpers looked alike but did not share a rule. Some escape non-ASCII, some write it
raw; some refuse NaN, some emit `NaN`; some stringify unknown objects (`default=str`); two use
spaced separators. Each difference changes the hashed bytes, so two modules can give one value two
digests. That is invisible while each module only compares against itself, and becomes a
false mismatch the first time a record crosses between them.

Swapping every copy for the strict rule would have "fixed" the look-alikes by changing digests that
persisted records already carry. So the consolidation keeps every rule and makes it visible.

## What changed

- `provenance/digests.py` (stdlib only): `compact_json_bytes(value, *, ensure_ascii, allow_nan,
  default, separators)`, `sha256_tagged`, `sha256_file`, `sha256_json(value, **rule)`, `utc_now`,
  `utc_now_z`. Defaults reproduce the most common rule; a call site that differs says so in keyword
  arguments.
- 21 modules import it instead of carrying a copy: 15 under `foundry/systems/`, `foundry/completion.py`,
  `greg/institution.py`, and the four `_now` copies in `evolution/`. One dead helper
  (`company_loop._canon`, never called) is gone. Net: 24 lines added, 110 removed in those modules.
- `tests/unit/test_provenance_digests.py`: every migrated helper is checked against the exact
  expression it carried before, on ASCII, non-ASCII, nested and empty values; the rules are shown to
  differ (so none may be swapped for another); the strict rule equals `egregore.contracts.canonical_json`;
  and `foundry/systems/` may not grow a new private copy. It fails on `f65638b3` (module absent).

## What was deliberately not touched, and why

A file was eligible only if no committed artifact pins its current hash, no mutant gate patches its
text, it is not a protected surface, and no open PR edits it (checked against 24 open PR heads).

| Excluded | Reason |
| --- | --- |
| `policy/consequence_gate.py` | Integrity-protected artifact; changes need a founder-signed `INTEGRITY_AUTHORIZE`. |
| `events/spine.py`, `identity/machine_passport.py`, `provenance/commit_witness.py`, `loom/ratify.py`, `business/*`, `foundry/territory.py`, `adapters/daleobanks_opportunity.py` | Source hash pinned by evolution specs, freezes or evidence. |
| `greg/cognition/**`, `cortex/evaluation/**` | Pinned by admission freezes; evaluation runners are frozen instruments. |
| `greg/workers.py`, `greg/missions.py` | Protected surfaces: changes need founder or authorized review (`acceptance/missions.json`). |
| `greg/licensing.py` | 30 mutant gates patch its text; open PR #230 rewrites it. |
| `capabilities/router.py` | Labelled non-canonical; low value. |

## Next candidates

1. `greg/licensing.py._digest` (`default=str` rule) once #230 lands.
2. Pinned modules at their next deliberate version bump: adopt `provenance.digests` in the same
   commit that re-freezes them, so no extra freeze is spent.
3. One `stats.sign_test` for new evaluation code; the eight frozen copies stay as written.

## Product delta

None. This is maintenance: no digest changes, so no existing disagreement is resolved. What it
buys is that each rule difference is now stated at its call site and tested, and the Foundry systems
cannot grow another private copy. GREG can do nothing new because of it.
