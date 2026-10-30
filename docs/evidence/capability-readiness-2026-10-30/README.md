# Capability readiness ladder — 2026-10-30 (MU-B)

Directive sections 32, 26 and 70: distinguish KNOWN, INSTALLED, CREDENTIALLED, GRANTED, EXERCISED and VERIFIED for
every capability, and do not count raw tools as success. Base `b1950be2` (#196 head). Branch
`claude/capability-readiness-ladder-20261030`.

## What changed

- `greg/readiness.py` (new, read-only). For every capability in the registry the body uses (the 163 built-ins and
  every capability Genesis registered on the journal), the rungs it has reached, each with evidence references, and
  the first missing rung with its reason. It writes, grants and attaches nothing.
- `greg/cli.py`: `greg readiness [--capability ID]` prints it as JSON, like `greg routing`. There is no
  `greg capabilities` subcommand, so the scope's fallback name is used.
- `tests/unit/test_greg_readiness.py`: 26 tests (14 in the first round, 12 added after review).
- `scripts/ci/check_capability_readiness_mutants.py`: 38 mutants (19 in the first round, 19 added after review).

| Rung | Read from (existing reader) |
| --- | --- |
| KNOWN | `BUILTINS`; `capability.registered` events whose provider Genesis forms (`built:`, `installed:`, `composed:`; the ones `Genesis.restore` re-registers) |
| INSTALLED | `CapabilityManifest.available()` (platforms, exact binaries: the `AuthorityOffice.precheck` test); for `installed:python:` providers, the pinned distribution version via `importlib.metadata` (nothing imported) |
| CREDENTIALLED | every declared handle is in `SecretBroker.names()`; not applicable when none is declared; no value is resolved. A store the broker refuses or that is not a mapping of names reads missing, with the error's type |
| GRANTED | an ACTIVE, unpaused `MissionBook` mission whose founder-signed cone admits it (pattern, ceiling, targets, horizon), or which pre-approves a step that `greg.missions.pre_approved` admits (the engine's own test), and the capability is ATTACHED. Spent single-action Kernel grants are shown as lineage only |
| EXERCISED | a positive Gate receipt whose witness names it; refused receipts are counted, never as exercise |
| VERIFIED | a `mission.appraised` VERIFIED of a closure that judged one of its receipts (the mission's completed actions before the closure, and this mission's observation receipts the closure cites), with no later REFUTED appraisal of such a closure (a failure closure's included) and no later `routing.outcome` ineffective verdict. A receipt the body blamed (routing ruled it ineffective, or `MissionBook` blamed its action for breaking a passing check) is never credited by a VERIFIED closure. VERIFIED_UNMET and UNAVAILABLE verify nothing |

Each row also carries Mission Control's class (`mission_control.classify_capability`) and routing's track record
(`routing.track_record`, `routing.reliability`).

## Review round 1 (two independent reviewers), dispositions

| Finding | Disposition | Regression test (fails at `3f0d54d3`, passes now) |
| --- | --- | --- |
| F1: a capability whose only receipt routing ruled ineffective read VERIFIED through a sibling strategy's verified closure | fixed: blamed receipts are not credited; the class includes receipts `MissionBook` blames for breaking a passing check | `test_a_strategy_routing_ruled_ineffective_is_not_verified_by_a_sibling_s_success` (real engine, real appraiser); `test_a_strategy_blamed_for_breaking_a_passing_check_is_not_credited_by_the_closure` |
| F2 / MUB-F1: GRANTED read any pre-approved step naming the capability, without the engine's `pre_approved` test | fixed: decided through `greg.missions.pre_approved` for the step's own strategy, target under the prefix | `test_a_pre_approved_step_grants_only_what_the_engine_runs_as_pre_approved[read_only]`; the `[internal_write]` case shows the engine runs the matching step and readiness grants it |
| F3: a REFUTED of a failure closure demoted VERIFIED while a comment called such verdicts neutral | fixed in favour of the binding scope ("a REFUTED latest outcome never reads VERIFIED"; routing counts it refuted too): any REFUTED demotes, the comment is corrected, and the reason now names a failure closure | `test_a_refuted_failure_closure_drops_verified_and_is_named_a_failure_closure` (REFUTED from the real appraiser) |
| F4: a secret store holding `null` or a non-name list crashed the command | fixed: TypeError and non-string names read as an unreadable store | `test_an_unreadable_secret_store_is_reported_not_guessed[null-384]`, `[[1, 2]-384]` |
| F5: Mission Control does not show the same counts | deferred: open PR #178 (draft, head `e410977d`) still edits `greg/mission_control.py`, and the scope allows the change only when no open PR does | none |
| MUB-F2: nine safeguards survived mutation | fixed: tests pin each (standing hold window, another mission's cited receipt, non-formed provider, both target directions, unreadable store, all three track-record disagreements, the verdict filter) and the mutants are in the script | see the mutant list |
| MUB-F3: the test docstring and this README under-listed the facts tests record directly | fixed: both list all seven kinds | n/a (documentation) |
| MUB-F4: `browser.render` was said to lack Chromium | fixed below: its manifest names the macOS Chrome app path, so it can never be INSTALLED on Linux | n/a (documentation) |

## Disagreements between readers, reported by the ladder

1. `mission_control.classify_capability` reads every capability that declares a credential BLOCKED ("needs
   credentials"), even when the secret store holds every declared handle (shown for `github.pulls` in the tests).
2. `body.status`, and so Mission Control's capability list, holds only built-ins. Capabilities Genesis registered,
   which the running body re-registers, are absent from it.
3. `routing.track_record` reads completed actions only, so a capability verified only as a closure's sensor
   (`fs.read` in the tests; `foundry.query`, `institution.appraise` on the rehearsal body) has no verified count
   there. It also drops a refutation whose effect checks held: an act no strategy names, slipped into a mission the
   engine then closes, is refuted by the appraiser on its approval boundary, and routing still counts the capability
   verified with no refutation (tested).
4. `routing.track_record` credits every completed action of a verified mission, including one whose receipt routing
   itself ruled ineffective (F1); the ladder does not, and says so.

## Commands and results

All with `/home/user/venv311/bin/python`, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`.

| Command | Result |
| --- | --- |
| Fail-before (command absent): `pytest tests/unit/test_greg_readiness.py` in a detached worktree of `b1950be2` with the final test file copied in | 26 failed: 21 on `cannot import name 'readiness'`, 5 CLI tests on `invalid choice: 'readiness'` |
| Fail-before (review fixes): the same file in a detached worktree of `3f0d54d3` (the first-round head) | 6 failed, 20 passed. Failed: the two unreadable-store cases (`null` crashed with `TypeError: 'NoneType' object is not iterable`; `[1, 2]` was read as names), the mismatched pre-approval (GRANTED `reached`), F1 (`fs.list` VERIFIED `reached`), the regressed receipts (3 credited instead of 1), F3 (the reason did not name a failure closure). The 20 that passed are the 14 first-round tests and 6 that pin safeguards which already held, to catch their mutants |
| Pass-after: `pytest tests/unit/test_greg_readiness.py` | 26 passed |
| Related suites: `pytest tests/unit/test_greg_readiness.py tests/unit/test_greg_platform.py tests/unit/test_greg_founder_asks.py tests/unit/test_greg_mission_control_costs.py tests/unit/test_greg_runbook_commands.py tests/unit/test_greg_capabilities.py tests/unit/test_greg_routing_integrity.py tests/unit/test_greg_evolution_routing.py tests/integration/test_greg_credentials_view.py` | 165 passed (26 new, 139 existing) at `d4302f0e` |
| `python -B scripts/ci/check_capability_readiness_mutants.py` | baseline passes; 38/38 mutants caught at `d4302f0e` (19 first-round mutants, refreshed where the code moved, and 19 for the review round); scratch copy, `python -B`, no bytecode, `__pycache__` purged before each run |
| The credential-leak mutant against the planted-value test alone (first round) | caught (`assert PLANTED not in out`) |
| `python -m greg rehearse --dir <scratch>/run`, then `python -m greg --home <scratch>/run/body readiness` | rehearsal exit 0 (118 s); readout in `rehearsal-readout.json`. Re-read after the review fixes: summary, rows and disagreements identical (no receipt there is blamed) |

Rehearsal readout (throwaway body, REHEARSAL key, no network, models or money): of 163 capabilities, 8 reach
EXERCISED and VERIFIED (`artifact.store`, `cognition.dp_knapsack`, `foundry.apply`, `foundry.query`,
`institution.appraise`, `institution.compose`, `institution.dossier`, `institution.survey`). Their first missing rung
is GRANTED, because every rehearsal mission closed: the next use needs a new signed mission. 4 are not installed on
this host: three `mac.*` require darwin, and `browser.render`'s manifest declares linux and darwin but names one
binary, the macOS path `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, so it cannot be INSTALLED on
any Linux body whatever browser is present. 2 lack their `github_token`; 157 have no live grant.

## Limitations and negatives

- Mission Control parity is a carried field, not a view (F5, deferred): each row carries Mission Control's own class,
  and a test checks it equals the class Mission Control gives the `body.status` row. A readiness panel in Mission
  Control waits until #178 no longer edits `greg/mission_control.py`. The scope's parity item is not complete.
- GRANTED does not read the body-wide PAUSE or STOP, the cone's remaining budget, its data classes, or the
  constitution's policy (a step the cone or a pre-approval admits still waits for a founder DECISION where policy
  requires a human).
- CREDENTIALLED reads names in the body's file store; a macOS Keychain item reads missing until a capability resolves
  it. A store that is a JSON list of strings is read as names, as the broker reads it.
- INSTALLED does not run the capability; a built capability's source integrity is Genesis's check at restore.
- EXERCISED needs a positive receipt; the scope's wording was "a receipt of its invocation". Refused receipts are
  shown, not counted.
- VERIFIED is more conservative than routing: a REFUTED closure, a failure closure's included, demotes every
  capability whose receipts it judged, even when the refutation was not about that capability's effect; a VERIFIED
  closure credits no receipt the body blamed. VERIFIED_UNMET is neutral.
- Seven kinds of fact are recorded directly in tests, in their writers' fields, instead of being produced by the
  engine's tick: `mission.action` DONE records (written by the `_act_through_gate` helper after a real Gate act),
  `mission.achieved` and `mission.unmet` closure claims, VERIFIED_UNMET and UNAVAILABLE appraisals, `routing.outcome`
  rows (one with a verdict no writer gives), `capability.registered` and `capability.state`. Every VERIFIED and
  REFUTED verdict in the tests comes from the body's separate appraiser, sometimes judging such a recorded claim.
- Not run: the full suite, macOS, a founder body.

## Reality level

INTEGRATION-TESTED on local test bodies (a real Ed25519 test key, receipts from the real Kernel Gate, appraisals from
the body's separate appraiser process) and on a credential-free rehearsal body. Not LOCAL-REAL on a founder body; no
founder device; VEPMC unchanged.
