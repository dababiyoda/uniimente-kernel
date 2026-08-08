<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- source: planning/graph/nodes/ via planning/compiler/render.py -->
<!-- graph-digest: c355a9a137b04ff3b0b5aaa4df60fa574dfe0d8d49242bdf0402bcfa124f14a8 -->
<!-- projection: INSTITUTIONAL_ANATOMY_GRAPH -->


# Institutional Anatomy — Capabilities, Bridges and Authority

Produced by executing a static import analysis over all 22 kernel packages at
`8cb3074` and by running `InstitutionalLinker` across the committed organ
manifests — not by reading module docstrings.

Each capability carries a `presence` classification, which the Founder-Horizon
Override §29.4 requires before anything may be proposed for construction:

| class | meaning |
|---|---|
| `existing_and_connected` | built, and imported by non-test code |
| `existing_but_disconnected` | built and tested, but nothing imports it |
| `genuinely_absent` | earned by inspection, not assumed |

The headline result is that very little is absent. Several subsystems the brief
expected to be missing are present, well-tested, and simply unwired.

**11 nodes** projected from graph digest `c355a9a137b04ff3`. Regenerate with `python planning/compiler/render.py`.

## capability (7)

### `anatomy.closure_is_the_integration_hub` — closure/ is the one real integration hub (imports 18 of 22 packages)

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `closure/` · via `ast import analysis`

- **presence**: existing_and_connected
- **lifecycle_role**: CANONICAL
- **region**: BRIDGE
- **path**: closure/
- **files**: 8
- **imports_packages**: 18
- **imported_by**:
  - business
  - egregore
  - evolution
  - foundry
- **test_refs**: 6
- **contents**:
  - whole_body.py — the Whole-Body Closure Controller
  - framework.py
  - kernel_registry.py
  - integration_registry.py
  - developmental_registry.py
  - commercial_registry.py
  - advantage_registry.py
- **note**: Final Build Order §5.7 lists the Whole-Body Closure Controller as required nervous-system machinery. It exists, it is the most connected module in the repository, and it carries five registries. This is the single strongest counterexample to the "missing machinery" premise.

_Relates to: `discrepancy.missing_machinery_premise`_

### `capability.adapters_membrane_orphaned` — The Universal Compatibility Membrane exists and nothing imports it

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `adapters/` · via `ast reverse-import analysis: imported_by == 0`

- **presence**: existing_but_disconnected
- **lifecycle_role**: EXPERIMENTAL
- **region**: BRIDGE
- **path**: adapters/
- **files**: 4
- **imports_packages**: 0
- **imported_by**: 
- **test_refs**: 4
- **contents**:
  - bridge_transport.py — third mirror of the organs' transport security, adds the kernel identity
  - daleobanks_opportunity.py — wire→canonical opportunity packet adapter
  - wealthmachine_assessment.py — wire→canonical venture assessment adapter
- **statement**: Final Build Order §8 requires the membrane; Phase Zero built its first ring. The adapters are real, declare their field mappings and information lost, and are exercised by four test references — but zero non-test modules import them. The membrane is a shelf of correct parts that no runtime path crosses.
- **why_it_matters**: This is the difference between "we have an adapter layer" and "our organs translate through an adapter layer". Only the second is a bridge.

_Relates to: `anatomy.kernel_is_a_library_not_a_running_system`_

### `capability.developmental_mica_cdpe` — developmental/ — MICA and CDPE, reachable only from closure/ and one test

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `developmental/` · via `ast analysis; .github/workflows/canonical-ci.yml job 4`

- **presence**: existing_but_disconnected
- **lifecycle_role**: CHALLENGER
- **region**: LEFT
- **path**: developmental/
- **files**: 5
- **imported_by**: - closure
- **test_refs**: 1
- **has_entrypoint**: python -m developmental (TARGET_FORM_001 benchmark, run in CI job 4)
- **note**: Track B's flagship. It does run in CI and does emit a benchmark report, which is more than morphogenesis/ can claim, but a single test reference for a five-module package is thin coverage for something proposed as substrate.

_Relates to: `intent.track_a_track_b`_

### `capability.egregore_runtime_orphaned` — egregore/ — a runtime, closure, drift and gate adapter that nothing imports

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `egregore/` · via `ast reverse-import analysis: imported_by == 0`

- **presence**: existing_but_disconnected
- **lifecycle_role**: EXPERIMENTAL
- **region**: RIGHT
- **path**: egregore/
- **files**: 7
- **imported_by**: 
- **test_refs**: 6
- **contents**:
  - closure.py
  - contracts.py
  - drift.py
  - gate_adapter.py
  - resources.py
  - runtime.py
- **statement**: The package named for the project's own identity contains a runtime, a gate adapter and a drift detector, imports closure/ and policy/, and is imported by nothing. It is reachable only from its own tests.

_Relates to: `anatomy.kernel_is_a_library_not_a_running_system`_

### `capability.evaluator_firewall_partially_exists` — The protected evaluator firewall is half-built and its existing half is sound

**Evidence:** `verified_by_inspection`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `evolution/repair/spec.py`

- **presence**: existing_but_disconnected
- **region**: BRIDGE
- **what_exists**:
  - evolution/repair/spec.py freezes the experiment and self-seals with SPEC_SHA256
  - tests/unit/test_repair_spec_frozen.py fails the build if the hash drifts
  - ORIGINAL_LINKER_FILE_SHA256 makes 'preserved unchanged' a checkable claim rather than a promise
  - the detector is given the capability NAME and contract, never told which module provides it
  - REQUIRED_FUNCTION_THRESHOLD = 1.0 — 3 of 4 is a failure, not a 75% pass
- **what_is_missing**:
  - builder/evaluator process isolation (candidates currently run in the same interpreter)
  - candidate writable-path confinement
  - held-out cases the builder cannot read
  - a negative control proving the evaluator itself can fail
  - detection of evaluator mutation at runtime
- **statement**: Override §12 says candidate generation is not the scarce primitive; reliable judgment is. The frozen-spec mechanism is a genuine, working instance of that principle. What it lacks is isolation, not concept.

_Relates to: `intent.evaluator_sovereignty`_

### `capability.evolution_laboratory` — evolution/ — 30 modules, 44 test references, the best-covered subsystem

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `evolution/repair/spec.py` · → SPEC_SHA256, REQUIRED_FUNCTION_THRESHOLD, TARGET_CAPABILITY

- **presence**: existing_and_connected
- **lifecycle_role**: CHAMPION
- **region**: BRIDGE
- **path**: evolution/
- **files**: 30
- **test_refs**: 44
- **imported_by**: - closure
- **contents_of_note**:
  - strategy_tree.py — StrategyTree/StrategyBranch with decisive_unknown and coverage()
  - spider_web.py — SpiderWebAudit with sides, mechanism mapping, decorative removal, verdict
  - repair/ — the frozen-spec repair laboratory (spec.py self-seals via SPEC_SHA256)
  - migration/ — governed stateful replacement harness
  - experiment.py, capsule.py, comparison.py, failure_analysis.py, branch_generator.py
- **statement**: The repair laboratory already implements the hard half of a developmental closure: a frozen experiment specification whose canonical JSON is hashed into SPEC_SHA256 and guarded by a test, so candidate code cannot silently retune the experiment that judges it. That is evaluator sovereignty (Override §12) in working code.

_Relates to: `intent.evaluator_sovereignty`, `intent.first_developmental_proof`_

### `capability.morphogenesis_orphaned` — morphogenesis/ — fully isolated: imports nothing, imported by nothing

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · path `morphogenesis/` · via `ast import analysis: imports 0, imported_by 0, test_refs 2`

- **presence**: existing_but_disconnected
- **lifecycle_role**: EXPERIMENTAL
- **region**: LEFT
- **path**: morphogenesis/
- **files**: 3
- **imports_packages**: 0
- **imported_by**: 
- **test_refs**: 2
- **note**: The weakest-attached package in the repository, and a Track B artifact. Its isolation is itself evidence for the Track A / Track B decision: the morphogenetic line has not earned a connection to the canonical path.

_Relates to: `intent.track_a_track_b`_

## bridge status (3)

### `bridge.linker_measured_state` — Measured cross-organ edge state from the institutional linker

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `InstitutionalLinker(load_manifest(organs/*.manifest.yaml)).link()`

- **typed_edges_resolved**: 4
- **edges**:
  - daleobanks -> constitutional-controller : wire-opportunity-packet
  - daleobanks -> wealthmachine : wire-opportunity-packet
  - wealthmachine -> daleobanks : wire-venture-assessment
  - wealthmachine -> constitutional-controller : wire-venture-assessment
- **unconsumed_contracts**: 11
- **unconsumed_of_note**:
  - constitutional-controller produces capability-grant — consumed by no one
  - constitutional-controller produces decision — consumed by no one
  - constitutional-controller produces evidence — consumed by no one
  - constitutional-controller produces outcome — consumed by no one
  - constitutional-controller produces event — consumed by no one
- **unproduced_contracts**: 1
- **untyped_contracts**: 0
- **unresolved_fields**: 7
- **overlapping_authority**:
  - daleobanks.constitution_service
  - wealthmachine.risk_management
- **decisive_reading**: Every contract the Kernel PRODUCES is unconsumed. The organs talk to each other over the wire protocol (4 edges, all Bridge A), and nobody consumes a kernel-issued grant, decision, evidence record, outcome or event. The linker's own unresolved list states it plainly: "peer organs do not yet consume kernel-issued grants (Bridges B/C incomplete)".
- **consequence**: The Kernel is not currently in the authority path of anything. It is a constitutional government whose statutes no organ reads at runtime. Bridge A is the only bridge with typed edges; B through H have no edges at all.

_Relates to: `anatomy.kernel_is_a_library_not_a_running_system`_

### `bridge.status_a_through_h` — Bridges A–H — measured status

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `linker edge report + organ manifest inspection`

- **A_signal_to_venture**:
  - **status**: PARTIALLY_TYPED
  - **edges**: 4
  - **note**: wire protocol v1.1 typed and registered; adapters exist but are unwired; no episode ever recorded
- **B_venture_to_experiment**:
  - **status**: NO_EDGES
  - **blocker**: no organ consumes capability-grant; Venture Cell charters never requested from kernel authority envelopes
- **C_experiment_to_reality**:
  - **status**: NO_EDGES
  - **blocker**: no external-effect path has ever been exercised; 0 receipts, 0 reconciliations
- **D_reality_to_learning**:
  - **status**: NO_EDGES
  - **blocker**: depends on C; no external observation exists to learn from
- **E_learning_to_evolution**:
  - **status**: MACHINERY_PRESENT_NO_INPUT
  - **note**: evolution/ is the best-covered subsystem (44 test refs) but has no reality input to consume
- **F_audience_to_business**:
  - **status**: NO_EDGES
  - **blocker**: DALEOBANKS has zero published output; no owned audience exists yet
- **G_business_to_capability**:
  - **status**: NO_EDGES
  - **blocker**: depends on F and a completed business workflow
- **H_revenue_to_regeneration**:
  - **status**: NO_EDGES
  - **blocker**: zero revenue
- **summary**: One bridge partially typed, seven with no edges. The chain is blocked at C — the first place the institution must touch reality — and everything downstream of C is blocked by C rather than by its own difficulty.

_Relates to: `bridge.linker_measured_state`_

### `bridge.two_organs_invisible` — PumpStation and RESEARCH-IN have no organ manifests and are invisible to the linker

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `ls organs/`

- **manifests_present**:
  - kernel
  - daleobanks
  - wealthmachine
- **manifests_absent**:
  - pumpstation
  - research-in
- **consequence**: Two of six organs cannot appear in any edge, authority overlap report, or capability discovery result. Any claim about whole-system connectivity that does not say this is overstating coverage by a third.
- **note**: Writing these manifests is runtime work and is NOT authorized this round. The round records the gap and specifies the manifests; it does not create them.

_Relates to: `repo.pumpstation`, `repo.research-in`, `intent.research_in_role`_

## authority conflict (1)

### `authority.overlaps_measured` — Two organ-local authority implementations, both already flagged

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `8cb3074a4a83` · via `linker overlapping_authority; cat scripts/ci/check_authority_singleton.py`

- **overlaps**:
  - - **organ**: daleobanks
    - **capability**: daleobanks.constitution_service
    - **disposition**: SPECIALIZED beneath kernel authority — preserve, do not promote
  - - **organ**: wealthmachine
    - **capability**: wealthmachine.risk_management
    - **disposition**: SPECIALIZED beneath kernel authority — preserve, do not promote
- **third_candidate**:
  - **source**: WMI PR #30 — 'Constitutional Control Layer (Phase 0 doctrine foundation)'
  - **head**: 14e7bba896e60f31c6dc5885a477ff7e100d64c6
  - **risk**: Unmerged, so it does not yet appear in the linker's overlap report. If merged as written it would create a second constitutional control layer inside a non-Kernel organ, which Override §19 forbids. It must land as adapter, specialist, test oracle or organ-local control BENEATH kernel authority.
- **ci_guard**: scripts/ci/check_authority_singleton.py enforces no second Constitution/Gate/identity/authority registry
- **assessment**: Authority duplication is currently CONTAINED, and the containment is mechanical rather than aspirational. The live risk is PR #30, not main.

_Relates to: `pr.wmi.30`, `intent.wmi_role`_
