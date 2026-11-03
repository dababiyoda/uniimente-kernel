# Audit of the One Mind reconciliation (#154) — 2026-10-07

Tree audited: `kimi/one-mind-surface-20261003` @ `d282d2e` (tree `af30b369`, matching #154's claim).
Run in a clean venv with that tree's own pins (`requirements-dev.txt`, `requirements-cognition.txt`;
mcp 2.3.0, Z3, OR-Tools, SciPy, NetworkX, SymPy present). Nothing here was pushed to that branch;
`patch-for-d282d2e.diff` is offered for whoever drives #154/#148.

| Run | Passed | Failed | Errors |
| --- | --- | --- | --- |
| isolation tests, unpatched (`isolation-tests-unpatched-venv.txt`) | 96 | 4 | 0 |
| isolation tests, patched | 100 | 0 | 0 |
| full unit suite, isolation patch only (`full-suite-isolation-patch-only.txt`) | 1865 | 28 | 2 |
| full unit suite, both fixes (`full-suite-both-fixes.txt`) | 1883 | 10 | 2 |

## Defects with a verified fix (in the patch)

1. **Confined workers cannot start inside a venv.** `greg/isolation.py` grants `sys.prefix/lib` but not
   `sys.prefix/pyvenv.cfg`, which every child interpreter reads at startup. The Chromebook installer makes a
   venv, so on Body 1 every Landlock-confined worker (foundry DSL verifier, MCP tools) dies before its first
   line. Same class: on Debian-style Pythons the system site-packages sit outside `sys.prefix/lib`
   (Permission denied on `dist-packages/mcp`), and on CI's setup-python glibc's `librt.so.1` is outside every
   grant (#154's run #415). The patch grants `pyvenv.cfg`, the interpreter's system site-packages (never user
   site) and glibc's companion libraries beside the loaded libc. The librt part is inferred from the CI log,
   not reproduced here.
2. **The preserved selector points one directory too high.** `greg/cognition/selector.py` was moved
   byte-for-byte from `greg/cognition.py`, so `ROOT = parents[1]` now resolves to `greg/` and every
   selector call fails on `greg/cortex/seed/verify.py`. One line (`parents[2]`) restores 17 of 21 tests.

## Capability lost in the reconciliation (no patch; a merge decision)

- `greg/templates.py` and `greg/planner.py` are #148's, so schedule, network and plan in words are gone: the
  console no longer turns "Shift: 10 hours. Job J takes 3 hours..." into a mission (5 schedule-words tests), and
  `test_greg_open_source_genesis.py` / `test_greg_linear_genesis.py` fail at import.
- `greg cognition inventory|knowledge|mission` (#140's CLI, including the competence readout) is absent.
- #154's own kill criterion names "loss of a line-unique capability without explicit supersession".

## Named dissent, now evidenced

Four selector mission-path tests fail because `cognition.solve` now resolves to the compiler. #154 recorded this
as material dissent; it is a founder decision, not a defect.
