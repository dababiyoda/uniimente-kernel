# Intent records as a contract, section 8 on every distant horizon, and an intent continuity guard (MU-F)

Directive 2026-10-28 sections 8, 11 and 54 (`docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md`).
Base `44b3df96` (#236 head). Branch `claude/intent-record-schema-20261030`, into #196.
Reality level: **UNIT-TESTED** in a container. Authority delta: none. VEPMC: 0.

## What changed

1. **`contracts/intent-record.schema.json`** (JSON Schema 2020-12). It requires the fifteen fields of the
   ledger's Required Intent Record and the five that section 11 adds: `intended_effect`, `affected_systems`,
   `authority_level`, `consequence_class` and `unresolved_questions`. Section 11's "evidence" is
   `success_evidence` plus `failure_evidence`. `state` (and the older names `status` and `lifecycle_state`)
   must be one of the ledger's six states. A superseded record must name its successor.
   - A field a record's source does not supply carries `{"unrecorded": "<reason>"}`.
   - `intent_id`, `statement`, `source_refs`, `owner` and `state` can never be unrecorded.
   - `foundry/owned-source.json` lists the new contract (the packaging inventory test requires it).
2. **All 26 `docs/intent/*.json` records were normalized additively.** Every one is an intent record, so none is
   listed as a non-record.
   - Deleting the inserted text gives back each original file byte for byte. Every original field parses to the
     same value, in the same order.
   - 22 fields were copied from the name the same record already uses: `status` or `lifecycle_state` to `state`;
     `intended_outcome` or `intended_observable_effect` to `intended_effect`; `review_trigger` to
     `next_review_trigger`; `constraints` to `constitutional_constraints`; `source_location` to `[source_refs]`.
     For FULL-MACHINE and VERIFIED-LIFT, `exact_source_excerpt` (the founder's words) was copied to `statement`.
   - Each record's `normalization_2026_10_30` block names what was copied from where.
   - 129 fields carry an unrecorded marker: `affected_systems` 20, `unresolved_questions` 20,
     `authority_level` 14, `consequence_class` 14, `intended_effect` 11, `success_evidence` 8,
     `failure_evidence` 8, `binding_scope` 7, `constitutional_constraints` 7, `dependencies` 6, `supersedes` 5,
     `superseded_by` 5, `conflicts` 2 and `implementation_refs` 2.
   - The test ratchets that total: a later record may close a gap, but it cannot add one without a visible edit.
   - Three of these records are #158's bytes in the Mind reconciliation map (POLYINTELLIGENCE-MIND-CONTINUATION,
     MIND-LINEAGE-CONVERGENCE, MIND-MAXIMUM-CONTINUATION). Their disposition moved from `kept` to `extended`,
     with a note, as earlier map corrections did (`d52b09d7`, `fa80ace7`).
     `test_the_reconciliation_map_covers_every_file_either_lineage_changed` failed on `532b8543` (full history
     present; CI's shallow clone skips it) and passes on `1c4ddaae`.
3. **`greg/path.py` `validate()`**: every horizon whose feasibility is not CURRENTLY_BUILDABLE must carry
   `enabling_interfaces`, `feasible_when` and `falsified_by`.
   - Each entry takes one of three forms: `{"recorded_as": <path field>}`, `{"value": ..., "source": ...}`
     (verbatim; a `greg/path.json#` source is checked inside `validate`) or `{"unrecorded": reason}`.
   - `recorded_as` may only name a field that records that element. `feasible_when` may name `prerequisite`,
     `activation_condition` or `gate_crossing_evidence`. `falsified_by` may name `nearest_falsifiable_experiment`
     or `falsification`.
   - `greg path` now reports `horizons.section_8_unrecorded`.
   - `build_status`, `achieved` and the primary node are unchanged; `greg path` still stops at N1. Every
     `greg/path.py` mutant text in the cortex and path-predicate gates still occurs exactly once (35 checked).
4. **`greg/path.json`**: all 31 non-buildable horizons were filled (sources below). Nothing else on the path
   changed; the data equals the base once the three new fields are removed.
5. **Continuity guard.** `scripts/ci/check_intent_continuity.py` checks HEAD against the committed snapshot
   `docs/collaboration/INTENT-CONTINUITY-SNAPSHOT-2026-10-30.json`.
   - The snapshot was read from `git archive` of pinned commit `44b3df9698a10d054b4ade4bb2ef77b244c3e0d9`:
     26 JSON intent records, 7 markdown intent records, 36 ids the ledger names, 40 horizons and 13 frontier
     backcasts (122 entries, 97 distinct ids).
   - The ledger kind is every id the ledger names as a whole token. 24 of the 36 are also records. The other 12
     include `INTENT-20261001-open-source-mechanism-harvest`, an intent recorded on draft #144 that has no record
     on this tree; only the ledger's mention keeps it.
   - Each id must still be present at HEAD, or a record present at HEAD must name it in its `supersedes`. A longer
     id does not keep a shorter one present.
   - It reads no git history at test time.
6. **Mutation gate**: `scripts/ci/check_intent_record_schema_mutants.py`, 39 mutants.
7. **Evidence scripts** in this folder: `normalize_records.py` and `fill_section_8.py`. Run on a `git archive` of
   the base, they reproduce all 26 records and `greg/path.json` byte for byte (re-checked with `cmp`).

### Section 8 sources (`fill_section_8.py`)

- **`feasible_when`**: for all 31 horizons, `recorded_as: prerequisite`, the path's own prerequisite text.
- **`falsified_by`**: recorded for 16 horizons.
  - By pointer to text already on the path, never copied:
    - frontier backcast `nearest_falsifiable_experiment`: persistent_organs, human_work_fabric,
      economic_compounding, multi_body, robotics, situational_awareness, developmental_research,
      jarvis_integration and cognitive_ecology;
    - the cognition P-node `falsification`: learned_cognitive_routing (P4), developmental_research (P10) and
      cognitive_ecology (P6, P8 to P12).
  - Copied from PR #155's destination falsifiers (`greg/cognition/advantage.py` DESTINATIONS, keyed by these
    horizon ids): decision_relevant_knowledge, continuity, persistent_organs, immune_function and
    situational_awareness.
  - Copied from directive sentences phrased as failure: agent_organizations (section 39, "If the swarm does not
    outperform the simpler form..."), business_operation and daleobanks_media_engine (section 44, "... is failure.").
  - **Unrecorded for 15 horizons**: community_feedback, compute_growth, computer_use, mac_support,
    multimodal_perception, multispecies_horizon, pumpstation_rail, regenerative_civilization,
    remote_interface_iphone, research_in_organ, scientific_embodiments, selective_web3_settlement,
    sensors_actuators, voice and workflows_and_sops.
- **`enabling_interfaces`**: recorded for 14 horizons, verbatim.
  - The 12 interfaces section 31 lists for computer_use. A directive value is checked inside the section its
    anchor names (`#31-computer-use`), and the heading must match the anchor.
  - From each horizon's own fields: iPhone (`verified HTTPS path`, `Ed25519 WebCrypto`), Mac (`launchd plist`,
    `sandbox-exec`, `Keychain`), community feedback, research-in, compute growth, multi-body (`NODE_ENROLL`),
    sensors, situational awareness, Jarvis and the immune function.
  - From frontier backcasts: robotics (`a simulated actuator contract`), human work (`greg.asks`) and cognitive
    ecology (`contracts/cortex-receipt.schema.json`).
  - **Unrecorded for 17 horizons** (listed by `greg path`).

## Commands and results

All runs used `/home/user/venv311/bin/python -B` with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.

### Fail before

The three new test files ran on a detached worktree of `44b3df96`:

| File | Result |
| --- | --- |
| `test_intent_record_schema.py` | **37 failed**, 3 passed. The contract is absent. The 3 that passed check properties the base already had: every file is a record, ids are unique, and aliases agree. |
| `test_horizon_section_8.py` | **23 failed**, 0 passed: `SECTION_8_FIELDS` is absent, the fields are missing, and `validate` accepts all 14 invented or empty entries. |
| `test_intent_continuity.py` | **collection error**: `scripts.ci.check_intent_continuity` does not exist (15 tests). |

- Validated against the new contract, **0 of the 26 base records conform** (151 missing required fields: the 22
  copies and 129 gaps above).
- `tests/unit/test_greg_packaging.py` **failed (1 of 3)** at `19db5147`, the interrupted head of this unit: the
  owned-source inventory did not list the new contract. It passes after `3ac48233`.
- Cleanup deletions on two detached worktrees of the base, each run against the 52 base test files that read
  `docs/intent`, `greg/path.json` or `greg.path` (`-n 3`):
  - Deleting `INTENT-20261014-competency-compiler.json` and horizon `selective_web3_settlement`: **2626 passed**,
    1 failed (the Stackelberg timing case described under Pass after). Nothing on the base noticed the deletion.
  - Deleting `INTENT-20260930-open-source-first.json` and horizon `voice`: 2624 passed, 3 failed. Two are
    `test_developmental_inheritance.py` (`test_every_founder_named_capability_stays_on_the_path` and
    `test_referenced_local_mechanisms_exist`), which hold a fixed list of founder phrases and local references;
    the third is the Stackelberg timing case. On the base these two ids were guarded only because that list
    happens to name them; the first pair was not guarded at all.
  - At HEAD, on a copy of the files the check reads, `check_intent_continuity.py --root <copy>` names both ids of
    each deletion "MISSING" and exits 1.

### Pass after (HEAD)

- The three new files: **78 passed** (40 schema, 23 horizon, 15 continuity).
- `python scripts/ci/check_intent_continuity.py`: "122 ids (97 distinct) pinned at 44b3df9698a1; 0 missing at
  HEAD", exit 0.
- `python scripts/ci/check_schema_refs.py`: 28 schemas, 164 local refs, all resolve.
- Every test file that reads `docs/intent`, `greg/path.json` or `greg.path`, plus the packaging test (56 files,
  among them `test_path_build_frontier.py` and `test_developmental_inheritance.py`), at `532b8543` with `-n 3`:
  2706 passed, 2 failed.
  - `test_the_reconciliation_map_covers_every_file_either_lineage_changed`: a real conflict with the
    normalization, fixed in `1c4ddaae` (above); `test_greg_mind_convergence.py` then passed 85 of 85.
  - `test_stackelberg_value_weakly_dominates_nash_and_pure_commitment[9]`: the Nash solver returned nothing under
    load; re-run alone, all 10 seeds passed. Timing, not this change.
- `tests/unit/test_data_exposure_ledger.py` (rebuilds from committed HEAD, which reads the map): 14 passed.
- `check_release_exclusions.py`, `check_authority_singleton.py`, `python -m governance.integrity --check` and
  `check_sealed_developmental.py`: all pass.
- Every test that iterates `contracts/*.schema.json` (6 files): 378 passed.
- `python scripts/ci/check_intent_record_schema_mutants.py`: **39/39 mutants caught** (baseline 78 passed). The
  mutants cover the contract (7), the records (7), `greg.path` (6), `greg/path.json` (5) and the continuity check
  and snapshot (14).

## Limitations and negatives

- **Gaps are named, not closed.** 129 record fields, 17 horizons' enabling interfaces and 15 horizons' falsifiers
  are unrecorded. Only the founder or a record's owner can supply them; this unit invents none.
- **One source is code, not the path, a record or the directive.** Five falsifiers are copied from
  `greg/cognition/advantage.py` (PR #155's destination falsifiers, keyed by these horizon ids). The scope names
  the path, intent records and the directive; these sentences are recorded repository text, checked verbatim,
  and kept because they state the falsifier for exactly these horizons. A session that edits that file (it is on
  another session's avoid list) will fail `test_every_copied_value_is_verbatim_in_its_source` until the copy is
  updated, which is the intended drift signal.
- **Choices of field, not of words.**
  - The faithful statement for two records is the founder's exact excerpt.
  - An enabling interface taken from a horizon's sentence is a verbatim fragment, such as "verified HTTPS path".
  - Path-internal values are checked as substrings, so a fragment cut at a word boundary still passes. File-sourced
    values must be a whole line, bullet or quoted string.
- **Markdown records.** The 7 markdown intent records and the ledger's own table records are guarded for
  continuity but are not validated against the schema. Intent JSON outside `docs/intent`
  (`docs/collaboration/...intents...json`, SG-001 to SG-012) is not covered.
- **Succession is read from the successor.** The scope's "a record with superseded_by names it" is implemented
  through the successor. A deleted record's own `superseded_by` cannot be read at HEAD, so the guard accepts a
  missing id only when a record present at HEAD lists it in `supersedes`. A `superseded_by` pointing at a deleted id
  is a dangling link, and the guard refuses it (tested).
- **The ledger kind pins mentions, not meanings.** Every whole-token id the ledger names is pinned, including
  `INTENT-0029` (the collision note about drafts #86 and #105) and the series placeholder `INTENT-00NN`. Removing
  such a mention later needs a successor's `supersedes` or a re-pinned snapshot.
- **The snapshot is pinned at `44b3df96`.** Ids added later are protected only after the snapshot is re-pinned
  (`--write-snapshot <commit>`).
- **Not in the workflow file.** The continuity check and the mutation gate are not added to
  `.github/workflows/canonical-ci.yml` (on the avoid list). The check runs through its unit test in the pytest job.
- **Not edited.** `authority_level` and `consequence_class` stay free text: the records use eight different
  values, and enumerating them belongs to the founder-intent ledger unit (S11-A). `docs/FOUNDER_INTENT_LEDGER.md`
  was not edited (#220).

## Product delta

`greg path` now names every distant capability that has no recorded way to be falsified or attached
(`horizons.section_8_unrecorded`). `greg.path.load` refuses a non-buildable horizon without section 8's three
elements or with a pointer or value that its source does not contain. Every founder intent record is checkable
against one contract, and its missing fields are named instead of absent. A cleanup that deletes an intent record,
a markdown intent, an intent the ledger names, a horizon or a frontier backcast fails CI unless a successor names it.
