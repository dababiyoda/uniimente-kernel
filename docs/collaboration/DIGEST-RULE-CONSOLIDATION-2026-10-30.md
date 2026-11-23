# Digest-rule consolidation — 2026-10-30

Session `session_01KucyfmCJx5if8GZ8bFqy1R`. Base: #196 head `f65638b3`, merged forward to `4dc0d581`. Scope: maintenance on
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
- 17 modules import it instead of carrying a copy: 15 under `foundry/systems/`, `foundry/completion.py`
  and `greg/institution.py`. One dead helper (`company_loop._canon`, never called) is gone. Net: 20 lines
  added, 90 removed in those modules.
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
| `evolution/capsule.py`, `evolution/migration/engines.py`, `evolution/repair/{detector,disable}.py` (four `_now` copies) | The evolution packages run sealed: `test_repair_inertness` and `test_migration_inertness` fail on any import of another kernel package. A first version of this change migrated them and `test_repair_inertness` caught it; reverted. Their stdlib-only copies are the price of that seal. |

## Next candidates

1. ~~`greg/licensing.py._digest` (`default=str` rule) once #230 lands.~~ Done in round 2.
2. Pinned modules at their next deliberate version bump: adopt `provenance.digests` in the same
   commit that re-freezes them, so no extra freeze is spent.
3. One `stats.sign_test` for new evaluation code; the eight frozen copies stay as written.

## Round 2 — 2026-11-04

Base: #196 head `d35d92a5` (123 commits after round 1 merged as #246).

**Drift measured.** The round-1 guard covered `foundry/systems/` only. In those 123 commits one new
private copy appeared outside it: `greg/backup.py::_now`, adopted from #234. Nothing pinned it.

**Migrated** (byte rules unchanged, each tested against the expression it replaced):

- `greg/licensing.py::_digest` and `capabilities/router.py::_digest` → `sha256_json(value, default=str)`.
- `provenance/ledger.py::sha256_json` (public; imported at 44 sites) now delegates to
  `provenance.digests.sha256_json(obj, default=str)`. Its name and bytes are unchanged.
- `greg/backup.py::_now` → `utc_now`; `provenance/ledger.py::_now` → `utc_now_z`. Tests that
  monkeypatch `backup._now` keep working, because the alias is still a module attribute.

**The guard became a ratchet over the whole tree.** `test_no_new_private_digest_or_timestamp_rules`
scans every tracked module outside `tests/`, `cortex/evaluation/` and the lineage archive. `KEPT`
lists the 28 copies that remain, each with its reason: pinned, sealed, protected, a different
format, or a standalone script. A new copy fails the test, and so does a `KEPT` entry whose copy is gone, so the list
can only shrink. Both directions were mutation-checked: a planted `greg/zz_probe.py::_sha` failed
the first test, and renaming `twins/tribunal.py::_now` failed the second.

**Also kept, newly found sealed:** `memory/affect.py` (the `evolution/repair` harness imports it) and
`twins/tribunal.py` (loaded by the repair adapters). Both stay stdlib-only for the same reason as the
four `evolution/` copies.

**Mutant gates checked:** the 76 `check_cortex_mutants.py` patterns on `greg/licensing.py` and
`provenance/ledger.py`, and the 55 `check_consistent_backup_mutants.py` patterns, all still apply
to the edited files exactly once.

**Not done here:** #253 records owners for eight duplicated mission-path functions; this round does
not touch that registry or its guard.

## Round 3 — 2026-11-05

Base: #254 head `c23dc2d2`. Round 2's guard matched helper *names*, so a copy under a new name
escaped it. Round 3 measured duplication by *structure* instead.

**Measured.** Every function in the 466 runtime modules (outside `tests/`, `docs/` and frozen
evaluation runners) was fingerprinted by its body: docstring dropped, every variable, argument,
handler, alias and nested definition name renamed away, at least five lines. Constants and
attribute names still count.

| Scope | Finding |
| --- | --- |
| Byte-identical files (skill `detect_exact_duplicates.py`) | Only content-addressed continuity objects, the lineage archive and dated evidence copies. All are kept. |
| Kernel, identical bodies with names as written | 7 groups, all in pinned, frozen or deliberately independent code. |
| Kernel, bodies identical once names are renamed away | 11 groups before this round, 8 after it. |
| DALEOBANKS (local checkout `667439f`) | 1 group: two 7-line `__del__` methods. Not changed here. |
| WealthMachineIntelligence (local `ec82b80`) | 0 groups. |
| RAILSCOUT, RESEARCH-IN, PumpStation | No Python at their local heads. |

The organ checkouts are their local heads, not their open PR branches.

**Consolidated.** Eleven `foundry/systems` exercises each carried the same six-line refusal probe:
run a call, then record the refusal reason or a fixed value. They differed only in three rules:
- the exception class;
- what an accepted call records (`None` or `False`);
- where the reason is cut (none, 70 or 80 characters).

`foundry/systems/refusals.py::refusal_recorder(errors, *, accepted, limit)` now holds that probe, and
each call site states its rule in one line. In the eleven modules that removes 83 lines and adds 22, plus the
33-line module.

**Verification of the consolidation.**
- Every exercise result was hashed before and after the change, deterministically across repeated
  runs, and all 11 hashes are unchanged.
- Hash sensitivity was checked by mutation. Dropping the cut-off moves 5 of the 7 hashes. The other two
  (`commissioning`, `commons`) never record a reason longer than their limit.
- Changing the accepted value moves no hash, because no exercise records an accepted call. A unit test
  covers that rule, the cut-off and the propagation of unexpected errors instead.

**Kept, with reasons:**
- `business_compiler` records `exc.problems`, `registry` prefixes the exception type, and `shell`
  calls a different function, so all three keep their own probes.
- `mcp_gateway.py` carries a twelfth copy (`GatewayError`, cut at 160 characters). It is pinned by a
  freeze, so it adopts the recorder at its next re-freeze. Its cut-off is a unique constant, so the
  structural guard does not list it.

**The guard is now structural.** `tests/unit/test_no_structural_duplicates.py` fails on any new
cross-file copy under any name, and on any `KEPT` group that has gone. `KEPT` holds the 8 remaining
groups:

| Group | Reason it stays |
| --- | --- |
| `contract_validation` / `contract_check`: `validate_*`, `formats` (2 groups) | Pinned |
| `canonical_json` ×3 | Independent on purpose (round 1 record) |
| `segmentation._load_filter` / `capabilities._network_filter` | Pinned |
| Two pairs in `greg/cognition/genomes` | Pinned |
| Two pairs in the P8 pilot scripts | Frozen instruments |

The guard was mutation-checked three ways:
1. On the round-2 foundry code it fails.
2. A planted renamed copy of `_network_filter` in a new module fails it.
3. Altering a kept pilot function fails the shrink-only check.

Building the guard exposed three blind spots, each fixed with a test:
- handler names (`except E as x`) are not name nodes;
- import aliases (`import m as x`) are not name nodes;
- nested definitions were renamed before their names were read.

**Recorded, not changed: a strictness gap.** `egregore/contract_check.py` says it enforces Goal Gravity
contracts "with the same strictness" as the boundary module. However, it loads its schemas with plain
`json.loads`, while `adapters/contract_validation.py` uses `strict_json`, which refuses duplicate keys
and non-finite numbers. The schemas are repository files, so the practical exposure is a malformed
schema committed by mistake. Both files are pinned, so the fix belongs to their next re-freeze: one
validator built from `strict_json`, used by both.

## Product delta

None. This is maintenance: no digest and no exercise result changes, so no existing disagreement is
resolved. What it buys is that each rule difference is now stated at its call site and tested.

- **Round 2:** a module anywhere in the runtime tree that adds another private helper under the usual
  names (`_canon`, `_sha`, `_digest`, `_hash`, `_now`, …) fails a unit test.
- **Round 3:** a copy of any function body of five lines or more in a second file fails a unit test
  under any name. A copy that also changes a constant or an attribute, or that sits inside one file,
  is still not caught.

GREG can do nothing new because of it.
