# GoalChase sandbox host: bounded unattended wakeup

This is a **sandbox experiment** originally built on draft #97, whose parent is draft #93. The current-main integration branch combines those unmerged drafts with the shared integrity/recovery semantics merged through #98; it is not adoption of either draft or an installed Mac application. It composes the Kernel `GoalChase`, EventSpine, ledger, `DurableWorkflow`, and Consequence Gate through `open_sandbox`; it owns no authority, external adapter or independent goal state. The public synthetic demo key cannot authenticate Alfonso. This experiment implements the first-body decision recorded on `codex/intent-first-body-20260922`, without editing #93's frozen evaluator or specification.

## What can be exercised now

After registering a **synthetic** goal in a new ledger, a separate process can run:

```sh
python -m egregore.goal_chase_host /tmp/greg-sandbox.jsonl --mode once
python -m egregore.goal_chase_host /tmp/greg-sandbox.jsonl --mode report
python -m egregore.goal_chase_host /tmp/greg-sandbox.jsonl --mode loop --period-seconds 60 --cycles 2
```

Use `python -m egregore.goal_chase_demo /tmp/greg-sandbox.jsonl --phase begin` to create a demonstration goal. Its observations have a September 5 fixture clock and may be stale at wall-clock time; a waiting report is the truthful result. For a controlled fresh test, the host supports `--at` in finite `once` or `report` mode. A `<ledger>.pause` marker prevents new ticks; removing it resumes only the same sandbox process loop. The host never auto-creates a missing mission, so an empty instance cannot masquerade as progress.

The host uses one stable trigger per UTC period. The GoalChase replay and canonical ledger suppress repeated work after process replacement. A single existing-ledger writer lock is held by `open_sandbox`; an uncertain effect still follows GoalChase reconciliation and cannot be retried by this host. A JSON report exposes current goals, decisions needed, new event IDs, negative event IDs, ledger head and honest non-actions. `--mode report` appends no goal event. Stopping the host is normal; the OS does **not** restart it automatically in this experiment.

## Proof boundary and next gate

The integration test registers a synthetic mission without ticking, starts the host in another Python process, retries the same slot in a third, pauses across a later slot and resumes. It checks exactly one decision request, unchanged ledger head on replay/pause, and no real outcome. The frozen #93 evaluator, #97 attention repair and shared Kernel controls remain necessary independent checks. The initial current-main composition failed 78 of 91 focused tests: the draft wrapper acquired a second writer lock already owned by #98's canonical ledger. After removing the wrapper lock, #98's Gate refused execution without a registered pre-existing grant; the older draft had depended on implicit admission. These failed behaviors remain recorded here and in the integration PR; they must not be reclassified as a Mac or live effect. The integration now provisions a test-only grant bound to the signed synthetic goal and exact action fields, delegates the only writer lock to the ledger, and marks workflow re-entry safe solely where retained start/reconciliation events prevent unknown-result retries. The merged source has one founder-ledger textual conflict, resolved by retaining the current-main ledger and the date-based new intent record; historical draft statements remain in their PRs. The combined full Python suite passed **666 tests** after the exact-grant regression test was added. Independent review is still required before adoption. No Mac packaging, launchd/SMAppService enrollment, UI closure, reboot recovery, Keychain broker, real founder authentication, phone client, computer use, independent human appraisal, external effect or customer outcome is verified here.

Next proof: independently review the current-main composition, especially the narrow synthetic grant, interruption at each dispatch boundary and clean restart. A Mac-specific package must subsequently prove launch at login, UI closure, stop, reboot, permissions, signed/notarized install and restore. A live effect still needs separate founder authorization and Gate mediation; the synthetic fixture is never transferable to production.

Rollback: leave this draft unmerged or remove the host and its test. Preserve all ledgers and failed traces. Kill if the host grants policy, emits real effects, retries an unknown completion, changes frozen acceptance criteria, hides a failure or reports sandbox activity as an embodied closure.
