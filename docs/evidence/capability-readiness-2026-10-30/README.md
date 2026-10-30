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
- `tests/unit/test_greg_readiness.py`: 14 tests.
- `scripts/ci/check_capability_readiness_mutants.py`: 19 mutants.

| Rung | Read from (existing reader) |
| --- | --- |
| KNOWN | `BUILTINS`; `capability.registered` events Genesis wrote (the providers `Genesis.restore` re-registers) |
| INSTALLED | `CapabilityManifest.available()` (platforms, exact binaries: the `AuthorityOffice.precheck` test); for `installed:python:` providers, the pinned distribution version via `importlib.metadata` (nothing imported) |
| CREDENTIALLED | every declared handle is in `SecretBroker.names()`; not applicable when none is declared; no value is resolved |
| GRANTED | an ACTIVE, unpaused `MissionBook` mission whose founder-signed cone admits it (pattern, ceiling, targets, horizon) or pre-approves a step naming it, and the capability is ATTACHED. Spent single-action Kernel grants are shown as lineage only |
| EXERCISED | a positive Gate receipt whose witness names it; refused receipts are counted, never as exercise |
| VERIFIED | a `mission.appraised` VERIFIED of a closure that judged one of its receipts (the mission's completed actions before the closure, and the observation receipts the closure cites), with no later REFUTED appraisal of such a closure and no later `routing.outcome` ineffective verdict. VERIFIED_UNMET and UNAVAILABLE verify nothing |

Each row also carries Mission Control's class (`mission_control.classify_capability`) and routing's track record
(`routing.track_record`, `routing.reliability`).

## Disagreements between readers, reported by the ladder

1. `mission_control.classify_capability` reads every capability that declares a credential BLOCKED ("needs
   credentials"), even when the secret store holds every declared handle (shown for `github.pulls` in the tests).
2. `body.status`, and so Mission Control's capability list, holds only built-ins. Capabilities Genesis registered,
   which the running body re-registers, are absent from it.
3. `routing.track_record` reads completed actions only, so a capability verified only as a closure's sensor
   (`foundry.query`, `institution.appraise` on the rehearsal body) has no verified count there. It also drops a
   refutation whose effect checks held; the ladder drops VERIFIED on any later REFUTED of a closure that judged the
   capability's receipts.

## Commands and results

All with `/home/user/venv311/bin/python`, `PYTHONDONTWRITEBYTECODE=1`, `-B`, `-p no:cacheprovider`.

| Command | Result |
| --- | --- |
| Fail-before: `pytest tests/unit/test_greg_readiness.py` in a detached worktree of `b1950be2` with the new test file copied in | 14 failed: 2 on `invalid choice: 'readiness'` (the CLI tests), 12 on `cannot import name 'readiness'` |
| Pass-after: `pytest tests/unit/test_greg_readiness.py` | 14 passed |
| Related suites: `pytest tests/unit/test_greg_readiness.py tests/unit/test_greg_platform.py tests/unit/test_greg_founder_asks.py tests/unit/test_greg_mission_control_costs.py tests/unit/test_greg_runbook_commands.py tests/unit/test_greg_capabilities.py tests/unit/test_greg_routing_integrity.py tests/unit/test_greg_evolution_routing.py tests/integration/test_greg_credentials_view.py` | 153 passed (14 new, 139 existing) |
| `python -B scripts/ci/check_capability_readiness_mutants.py` | baseline passes; 19/19 mutants caught (run at `2dafddff`) |
| The credential-leak mutant against the planted-value test alone | caught (`assert PLANTED not in out`) |
| `python -m greg rehearse --dir <scratch>/run`, then `python -m greg --home <scratch>/run/body readiness` | rehearsal exit 0 (118 s); readout in `rehearsal-readout.json` |

Rehearsal readout (throwaway body, REHEARSAL key, no network, models or money): of 163 capabilities, 8 reach
EXERCISED and VERIFIED (`artifact.store`, `cognition.dp_knapsack`, `foundry.apply`, `foundry.query`,
`institution.appraise`, `institution.compose`, `institution.dossier`, `institution.survey`). Their first missing rung
is GRANTED, because every rehearsal mission closed: the next use needs a new signed mission. 4 are not installed on
this host (`browser.render`: no Chromium; three `mac.*`: Linux), 2 lack their `github_token`, 157 have no live grant.

## Limitations and negatives

- Mission Control parity is a carried field, not a view: `greg/mission_control.py` is edited by open PR #178, so it
  was not changed. Each row carries Mission Control's own class, and a test checks it equals the class Mission
  Control gives the `body.status` row. A readiness panel in Mission Control remains to be done.
- GRANTED does not read the body-wide PAUSE or STOP, the cone's remaining budget, or its data classes.
- CREDENTIALLED reads names in the body's file store; a macOS Keychain item reads missing until a capability resolves
  it.
- INSTALLED does not run the capability; a built capability's source integrity is Genesis's check at restore.
- EXERCISED needs a positive receipt; the scope's wording was "a receipt of its invocation". Refused receipts are
  shown, not counted.
- VERIFIED is more conservative than routing: a REFUTED closure demotes every capability whose receipts it judged,
  even when the refutation was not about that capability's effect. VERIFIED_UNMET is neutral.
- Four kinds of fact are recorded directly in tests, in their writers' shape, instead of being produced end to end:
  an ineffective `routing.outcome`, `capability.registered`, a `mission.unmet` closure, and VERIFIED_UNMET and
  UNAVAILABLE appraisals. Every VERIFIED and REFUTED verdict in the tests comes from the body's separate appraiser.
- Not run: the full suite, macOS, a founder body.

## Reality level

INTEGRATION-TESTED on local test bodies (a real Ed25519 test key, receipts from the real Kernel Gate, appraisals from
the body's separate appraiser process) and on a credential-free rehearsal body. Not LOCAL-REAL on a founder body; no
founder device; VEPMC unchanged.
