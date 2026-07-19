# Verifier index (append-only)

## v1 — 2026-07-19T14:51:37.654209Z
Measures: presence and machine-validity of the Section XXVI canonical artifact set (C1), JSON Schema validity of the 9 shared contracts (C2), YAML parseability of policy/registry files (C3), UCL structural sanity (C4), constitutional doctrine presence (C5), doctrine test-suite coverage dirs (C6), repo docs (C7), Phase-1 module placeholders (C8).
First version; no prior baseline.

## v2 — 2026-07-20
Measures: V1 = v1 passthrough (full 45/45 in-repo; skip-missing on partial mirrors); V2 = executable unit tests green (`pytest tests/unit`); V3 = every registered module closes all five orthogonal closures (technical, authority, evidence, economic, regenerative) via `closure/kernel_registry.py`; V4 = Whole-Body Closure Controller detects FALSELY_CLOSED on a synthetic case and reports CLOSED for the Consequence Gate's applicable loops (authority, execution, continuity); V5 = module READMEs declare the 14-condition buildability standard.
Differs from v1: v1 verified that canonical artifacts exist; v2 verifies that the executable build (UCL compiler, machine passports, Consequence Gate + Commit Witness, Evidence Ledger, closure framework) runs, resists adversarial paths, and closes every orthogonal loop. Runs recorded under `verifier/runs/v2-*.json`.
