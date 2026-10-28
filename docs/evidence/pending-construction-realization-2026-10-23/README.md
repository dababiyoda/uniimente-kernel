# Pending construction feedback

GREG's body already accepts scalar outcomes for constructed plans. The operator path was incomplete: the pending view listed forecasts only and the realize CLI always sent a list.

This change lists accepted constructed objectives and adds `greg realize RECEIPT --objective-value NUMBER --key KEY`. Forecast `--value` remains a list, including one-step forecasts. The forms are mutually exclusive; nonfinite scalars are refused before signing. Reading the pending view writes no events and creates no authority.

The view reuses the existing construction-registration, receipt and objective predicates. It names the objective, promise, sense, tolerance, method/version and reporting command. Its verification ceiling is explicit: the world outcome is not independently verified by the view. Existing signing, source labels, accepted-realization rules, conflict handling, tolerance and settlement remain unchanged.

## Evidence

- `before.txt`: two failures before production edits, including an actual portfolio construction missing from the CLI view.
- `before-cli.txt`: scalar reporting unavailable before the change.
- `after.txt`: **73 passed in 201.40s**, Python 3.12.14, across pending construction intake, forecast outcome calibration, construction realization/settlement, Goal Gravity and founder-tier controls.
- `ablation.txt`: restoring only the exact baseline projection gives one expected failure and one pass; scalar CLI remains functional. Production hashes remain unchanged.
- New tests pass Ruff; neither edited production file adds diagnostics relative to its base. Diff whitespace check passes.

The body test executes a portfolio construction, reads its pending row without appending history, submits the scalar through the test-key-signed CLI/inbox and observes the existing world settlement and pending removal. All reported outcomes are synthetic and all keys are generated test keys. No real-world learning dividend, buyer outcome or founder-device closure is claimed.

Exact scoped command:

```sh
python -m pytest -q tests/unit/test_greg_pending_construction_realization.py tests/unit/test_greg_outcome_calibration.py tests/unit/test_greg_construction_realization.py tests/unit/test_greg_construction_settlement.py tests/unit/test_greg_gravity.py tests/unit/test_greg_founder_tier.py --tb=short --show-capture=no
```

An initial environment collection error was missing the repository-declared rfc3161-client dependency. After installation, the unchanged existing construction-realization baseline passed before new tests/source edits. No dependency pin changed.

## Coordination and adoption

Implementer: Codex `/root`, workspace `a60f90b8f5e5`, task `construction-realization-intake`. [Claim](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6366693337); [CLI scope refinement](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6366744166).

Tested parent: `a1c6dbcb2d5b4f1647b0f3569dbbbdf0aae558d3`. On resume October 25, #196 advanced to `fa80ace79eb1ac2cc4bf745918baf5587e1ae3f6`: only a lineage map, data-exposure ledger and stochastic-genome tests changed. Neither edited source file changed upstream. The child retains its tested parent; combined integration checks remain separate.

Integration owner: `session_01FBS4KNJR59nSbdGbxo8Mbx`. Independent review unassigned and receiver acknowledgment pending. The owner's branch is untouched. The five-role, exactly-two-pass deliberation is explicit self-review by one worker; decision **EXPERIMENT**. No merge or activation authority is granted.

Next action: exact-head review and intake into #196, then combined-machine checks. The first separately authorized real constructed plan can use the displayed scalar route to supply observed evidence to the existing learning experiment. Keep its dividend unmeasured until real evidence exists. Repeated receipt observations may produce multiple pending rows; row count is not independent outcome evidence.

BODY + ORGANS + MIND remains the completion boundary. WMI #45 is separately handed off; this change does not close its pin adoption, asymmetric transport, combined license qualification, local-model comparisons, device acceptance or real outcomes.

Rollback: revert this component commit. The existing body/API still understands retained scalar and forecast realization facts. Preserve the failed-before evidence in history.
