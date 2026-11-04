# Intent records as a contract, section 8 on every distant horizon, and an intent continuity guard (MU-F)

Directive 2026-10-28 sections 8, 11 and 54 (`docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md`).
Base `44b3df96` (#236 head). Branch `claude/intent-record-schema-20261030`, into #196.
Reality level: **UNIT-TESTED** in a container. Authority delta: none. VEPMC: 0.

## What changed

1. **`contracts/intent-record.schema.json`** (JSON Schema 2020-12). It requires the fifteen fields of the
   ledger's Required Intent Record and the five that section 11 adds: `intended_effect`, `affected_systems`,
   `authority_level`, `consequence_class` and `unresolved_questions`. Section 11's "evidence" is
   `success_evidence` plus `failure_evidence`. `state` must be one of the ledger's six states, and the older names
   `status` and `lifecycle_state`, where present, must equal it (`$defs/agreeing_lifecycle`). A superseded record
   must name its successor.
   - A field a record's source does not supply carries `{"unrecorded": "<reason>"}`.
   - `intent_id`, `statement`, `source_refs`, `owner` and `state` can never be unrecorded.
   - Text needs a visible character: whitespace or zero-width characters alone record nothing.
   - JSON Schema cannot compare two texts, so the agreement of `intended_effect` with its older names
     (`intended_outcome`, `intended_observable_effect`) is held by the repository test, and the contract says so.
   - `foundry/owned-source.json` lists the new contract (the packaging inventory test requires it).
2. **All 26 `docs/intent/*.json` records were normalized additively.** Every one is an intent record, so none is
   listed as a non-record.
   - Deleting the inserted text gives back each original file byte for byte. Every original field parses to the
     same value, in the same order.
   - 22 fields were copied from the name the same record already uses: `status` or `lifecycle_state` to `state`;
     `intended_outcome` or `intended_observable_effect` to `intended_effect`; `review_trigger` to
     `next_review_trigger`; `constraints` to `constitutional_constraints`; `source_location` to `[source_refs]`.
     For FULL-MACHINE and VERIFIED-LIFT, `exact_source_excerpt` (the founder's words) was copied to `statement`.
   - 7 fields of GOAL-GRAVITY were copied verbatim from the rows of the same name in its own Intent Record document,
     `docs/intent/INTENT-20261013-GOAL-GRAVITY.md` (review finding MUF-N1). No other record has such a document.
   - Each record's `normalization_2026_10_30` block names what was copied from where (`copied`, and
     `copied_from_document` for GOAL-GRAVITY).
   - 122 fields carry an unrecorded marker: `affected_systems` 20, `unresolved_questions` 20,
     `authority_level` 14, `consequence_class` 14, `intended_effect` 11, `success_evidence` 7,
     `failure_evidence` 7, `binding_scope` 6, `constitutional_constraints` 6, `dependencies` 5, `supersedes` 4,
     `superseded_by` 4, `conflicts` 2 and `implementation_refs` 2. A test refuses a marker on a field the
     record's own document states.
   - The test ratchets that total: a later record may close a gap, but it cannot add one without a visible edit.
   - Three of these records are #158's bytes in the Mind reconciliation map (POLYINTELLIGENCE-MIND-CONTINUATION,
     MIND-LINEAGE-CONVERGENCE, MIND-MAXIMUM-CONTINUATION). Their disposition moved from `kept` to `extended`,
     with a note, as earlier map corrections did (`d52b09d7`, `fa80ace7`).
3. **`greg/path.py` `validate()`**: every horizon whose feasibility is not CURRENTLY_BUILDABLE must carry
   `enabling_interfaces`, `feasible_when` and `falsified_by`. Each entry is `{"recorded_as": ref}`,
   `{"value": ..., "source": ...}` (verbatim) or `{"unrecorded": reason}`, and must be the horizon's own text:
   - `recorded_as` names a non-empty list of fields that record that element (`feasible_when`: `prerequisite`,
     `activation_condition`, `gate_crossing_evidence`; `falsified_by`: `nearest_falsifiable_experiment`,
     `falsification`). Each resolves to a field of the horizon, of one of its own frontier backcasts, or of a
     cognition P-node its prerequisite or activation evidence names. Another horizon's text is refused.
   - A `greg/path.json#` value must stand uncut in a field the horizon owns (not cut inside a word, at a path
     separator or at a dot inside a token), and be a phrase or a name (two or more words, or a token with a
     capital, digit or joiner), never a lone word or letter.
   - One value never mixes path and file sources. `validate()` reads no repository file (an install may ship
     without `docs/`), so a file-sourced value is checked against its file, in the section its anchor names, by
     `test_every_copied_value_is_verbatim_in_its_source`, not at load.
   - Section 8 runs after the frontier backcasts are validated.
   - `greg path` reports `horizons.section_8_unrecorded`. `build_status`, `achieved` and the primary node are
     unchanged; `greg path` still stops at N1. Every `greg/path.py` mutant text in the cortex and path-predicate
     gates still occurs exactly once (35 checked).
4. **`greg/path.json`**: all 31 non-buildable horizons were filled (sources below). Nothing else on the path
   changed; the data equals the base once the three new fields are removed.
5. **Continuity guard.** `scripts/ci/check_intent_continuity.py` checks HEAD against the committed snapshot
   `docs/collaboration/INTENT-CONTINUITY-SNAPSHOT-2026-10-30.json`.
   - The snapshot was read from `git archive` of pinned commit `44b3df9698a10d054b4ade4bb2ef77b244c3e0d9`:
     26 JSON intent records, 7 markdown intent records, 36 ids the ledger names, 40 horizons and 13 frontier
     backcasts (122 entries, 97 distinct ids). The test holds that commit, the exact per-kind counts and a sha256
     of those ids.
   - The ledger kind is every id the ledger names as a whole token. 24 of the 36 are also records. The other 12
     include `INTENT-20261001-open-source-mechanism-harvest`, an intent recorded on draft #144 that has no record
     on this tree; only the ledger's mention keeps it.
   - Each pinned id must still be present at HEAD, or a successor of its kind must name it. Succession is typed: a
     `supersedes` entry names an id only when the whole entry is that id, and intent ids are succeeded by intent
     records, horizons by horizons, frontier backcasts by frontier backcasts. Prose that mentions an id names
     nothing. A longer id does not keep a shorter one present.
   - `--write-snapshot COMMIT` only adds: it refuses while any pinned id is missing at COMMIT and appends the ids
     new there under `added` (empty today).
   - It reads no git history at test time.
6. **Mutation gate**: `scripts/ci/check_intent_record_schema_mutants.py`, 59 mutants.
7. **Evidence scripts** in this folder: `normalize_records.py` and `fill_section_8.py`. Run on a `git archive` of
   the base, they reproduce all 26 records and `greg/path.json` byte for byte (re-checked with `cmp` at the
   review-round head).

### Section 8 sources (`fill_section_8.py`)

- **`feasible_when`**: for all 31 horizons, `recorded_as: prerequisite`, the path's own prerequisite text.
- **`falsified_by`**: recorded for 16 horizons.
  - By pointer to the horizon's own text, never copied:
    - its frontier backcasts' `nearest_falsifiable_experiment`: persistent_organs, human_work_fabric,
      economic_compounding, multi_body, robotics, situational_awareness, developmental_research,
      jarvis_integration and cognitive_ecology;
    - the `falsification` of a cognition P-node the horizon names: learned_cognitive_routing (P4) and
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
  - The 12 interfaces section 31 lists for computer_use, checked inside the section its anchor names.
  - From each horizon's own fields: iPhone (`verified HTTPS path`, `Ed25519 WebCrypto`), Mac (`launchd plist`,
    `sandbox-exec`, `Keychain`), community feedback, research-in, compute growth, multi-body (`NODE_ENROLL`),
    sensors, situational awareness, Jarvis and the immune function.
  - From the horizon's own frontier backcasts: robotics (`a simulated actuator contract`), human work
    (`greg.asks`) and cognitive ecology (`contracts/cortex-receipt.schema.json`).
  - **Unrecorded for 17 horizons** (listed by `greg path`).

## Review round on `a8e40155`

Nine findings from two reviewers. Each was reproduced on a `git archive` copy of `a8e40155` before any change.

| Finding | Reproduced on `a8e40155` | Fix |
| --- | --- | --- |
| MUF-A1 empty pointer list | `{"recorded_as": []}` and `[{"recorded_as": []}]` passed `validate()` for all 3 fields and left the gap report | `c86909fe`: refused |
| MUF-A2, MUF-R1 borrowed or cut text | another horizon's backcast falsifier, `horizons/<other>/prerequisite`, any P-node, value `e` all passed | `c86909fe`: ownership and phrase rules; inferred developmental_research to P10 pointer removed |
| MUF-R2 overclaim | mixed path and file sources unchecked; file sources never read at load | `c86909fe`: mixed refused; claim narrowed (above) |
| MUF-S1 contract | status/lifecycle_state disagreeing with state and zero-width text accepted | `3fde90f6` |
| MUF-N1 false gaps | 7 GOAL-GRAVITY markers on fields its own document states | `cc695e24`: copied, 129 to 122 |
| MUF-C1 re-pin launders | `p08` deleted a ledger record and re-pinned: 0 missing, 78 passed | `a1374073`: `repin` only adds; base frozen in the test |
| MUF-C2, MUF-R3 prose succession | prose "extends INTENT-0030 ... model_plurality" and "continuity, voice or robotics" released those ids, CLI exit 0 | `a1374073`: typed whole-entry succession; the head-ids test now applies the CLI's rule |
| MUF-R4 thinned snapshot | snapshot and ledger thinned together: 55 passed, CLI exit 0 | `a1374073`: exact counts and digest |

Fail before, on a detached worktree of `a8e40155` with the new test files copied in:

- `test_intent_record_schema.py`: **10 failed**, 39 passed (contract agreement, zero-width text, the GOAL-GRAVITY
  copies and ratchet).
- `test_horizon_section_8.py`: **25 failed**, 23 passed (empty pointer lists, borrowed and cut text, mixed
  sources, zero-width reason; one case only because the refusal message changed).
- `test_intent_continuity.py`: collection error as written (`SnapshotError`, `pinned`, `repin` absent). With those
  three names stubbed: **9 failed**, 15 passed. Among them the prose test (`[] == [...]`), the horizon test
  (`[] == [...]`), and `--write-snapshot HEAD`, which rewrote `pinned_commit` to `a8e40155`.

After the fixes, each reviewer script is refused: `p11` and `p02` cases A, B, E to H raise `PathError` (C and D,
file sources, fail `test_every_copied_value_is_verbatim_in_its_source`); `p07` and the R3 copy print the ids
MISSING with exit 1; `p08` and the R4 copy fail `test_the_snapshot_is_pinned_and_covers_every_kind`.

One regression of the fix was found and fixed: run before the backcasts were validated, the ownership check
changed `test_frontier_backcasts.py`'s "unknown node or horizon" message (`7dc95349`).

## Commands and results

All runs used `/home/user/venv311/bin/python -B` with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.

- First round fail-before (base `44b3df96`): `test_intent_record_schema.py` 37 failed, 3 passed;
  `test_horizon_section_8.py` 23 failed; `test_intent_continuity.py` collection error. 0 of 26 base records
  conformed to the contract. Deleting `INTENT-20261014-competency-compiler.json` and horizon
  `selective_web3_settlement` on the base went unnoticed by all 52 base test files that read `docs/intent`,
  `greg/path.json` or `greg.path` (2626 passed, 1 Stackelberg timing failure).
- The three unit files at HEAD: **121 passed** (49 schema, 48 section 8, 24 continuity; one continuity test runs
  `git archive` and skips outside a checkout).
- `python scripts/ci/check_intent_continuity.py`: "122 ids (97 distinct) pinned at 44b3df9698a1; 0 missing at
  HEAD", exit 0.
- `python scripts/ci/check_schema_refs.py`: 28 schemas, 166 local refs, all resolve.
- `check_release_exclusions.py`, `check_authority_singleton.py`, `python -m governance.integrity --check` and
  `check_sealed_developmental.py`: all pass. `refresh_owned_source.py` changes nothing (no new file under
  `greg/` or `foundry/` in this round).
- `python scripts/ci/check_intent_record_schema_mutants.py`: **59/59 mutants caught** on the final tree (baseline
  120 passed, 1 skipped: the `git archive` test, in a copy without `.git`). Two mutants survived the first run of this round and were corrected, not hidden: a widened
  lifecycle enum is now also refused by the agreement clause, so its catcher is the contract test; and a
  "succession from any field" mutant that could never equal a whole id was replaced by one that reads every
  field's entries.
- Every test file that reads `docs/intent`, the ledger, `greg/path.json` or `greg.path`, plus the packaging,
  contract-iterating, Mind-convergence, data-exposure and frontier-backcast tests (65 files, among them
  `test_path_build_frontier.py` and `test_developmental_inheritance.py`), `-n 3`, at `c2bf31b8`: **1584 passed,
  53 skipped, 0 failed**. The phrase boundary was tightened during that run, so the 17 of those files that load
  `greg.path` were re-run on the final tree: 404 passed.
- An earlier subset run of this round found one regression of the fix (the `test_frontier_backcasts.py` message
  order, fixed in `7dc95349`).

## Limitations and negatives

- **Gaps are named, not closed.** 122 record fields, 17 horizons' enabling interfaces and 15 horizons' falsifiers
  are unrecorded. Only the founder or a record's owner can supply them; this unit invents none.
- **One source is code, not the path, a record or the directive.** Five falsifiers are copied from
  `greg/cognition/advantage.py` (PR #155's destination falsifiers, keyed by these horizon ids). A session that
  edits that file will fail `test_every_copied_value_is_verbatim_in_its_source` until the copy is updated.
- **What a check cannot judge.** The phrase rule proves a path-sourced value is the horizon's own words, uncut,
  and more than a lone word; it cannot prove the phrase names an interface. A word-bounded fragment such as
  "a running Body" still passes; review judges it.
- **File sources are checked by the test, not at load.** `greg.path.load` accepts a file-sourced value as
  written; only the unit test reads the file.
- **Same-change edits stay visible, not impossible.** Thinning the pinned ids takes an edit of both the snapshot
  and the test's frozen counts and digest. Ids added by a later re-pin are protected by `repin`, not by a frozen
  digest, so a hand edit of an `added` entry is caught only by review.
- **Markdown records.** The 7 markdown intent records and the ledger's own table records are guarded for
  continuity but are not validated against the schema. Intent JSON outside `docs/intent`
  (`docs/collaboration/...intents...json`, SG-001 to SG-012) is not covered.
- **Succession is read from the successor.** A deleted record's own `superseded_by` cannot be read at HEAD, so
  the guard accepts a missing id only when a successor of its kind lists exactly that id in `supersedes`.
- **The ledger kind pins mentions, not meanings**, including `INTENT-0029` (a collision note) and the placeholder
  `INTENT-00NN`.
- **Not in the workflow file.** The continuity check and the mutation gate are not added to
  `.github/workflows/canonical-ci.yml` (on the avoid list). The check runs through its unit test in the pytest job.
- **Not edited.** `authority_level` and `consequence_class` stay free text; enumerating them belongs to the
  founder-intent ledger unit (S11-A). `docs/FOUNDER_INTENT_LEDGER.md` was not edited (#220).

## Product delta

`greg path` names every distant capability that has no recorded way to be falsified or attached
(`horizons.section_8_unrecorded`). `greg.path.load` refuses a non-buildable horizon without section 8's three
elements, an empty pointer, a pointer or path-sourced value that is not the horizon's own uncut text, or a value
mixing path and file sources; file-sourced values are checked by the unit test. Every founder intent record is
checkable against one contract, and its missing fields are named instead of absent. A cleanup that deletes an
intent record, a markdown intent, an intent the ledger names, a horizon or a frontier backcast fails CI unless a
successor of its kind names it exactly, and a re-pin cannot drop it.
