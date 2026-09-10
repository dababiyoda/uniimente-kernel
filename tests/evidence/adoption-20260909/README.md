# SR-001 adoption evidence, 2026-09-09

Read `../../../docs/SR001_ADOPTION_DECISION.md` for the decision and scope. Logs are observations at the named source/candidate, not aggregate readiness. `kernel-17-dispositions.json` binds every original failure. `wmi-ci-lint-disposition.json` retains all 2,100 historical CI observations. `conformance-map.json` maps required behavior to executed tests or explicit blocked checks.

`*-current-main-composition.patch` and `*-current-main-tree.json` bind disposable resolved overlays; they are not merges. The Kernel 556-test overlay run preceded its documentation conflict resolution; five doctrine tests were rerun afterward. WMI current-main overlay includes #33 as a prerequisite and retains the adopted doctrine pointer.

All launcher logs start with a separate native OS containment probe. Local runtime: Python 3.12.14 / pytest 8.3.3. Historical WMI CI uses Python 3.11.16 / pytest 9.1.1 / pytest-asyncio 1.4.0 / Ruff 0.16.6. Local targeted Ruff is 0.12.11. Socket/container claims remain separate. Dependencies were prepared before execution; no production credentials are supplied to the tests.

Initial failed runs are retained, including missing dependencies, invalid fixtures, the original 17 incompatibilities, incomplete DALE output, two WMI socket failures, installed-fixture development mistakes, and #94 child dependency/source mismatch. `wmi-ci-lint-complete.json` is the complete extraction; an earlier incomplete 2,082-line parser output is not used as evidence of the 2,100 total.

Remaining targeted Kernel Ruff observations are existing unused `RepairCost` / `CapabilityLossReport` imports and an unused local `sp` in a historical test. No correctness/security finding is suppressed. DALE and WMI changed-test targeted checks pass. The existing non-blocking CI lint command is unchanged.
