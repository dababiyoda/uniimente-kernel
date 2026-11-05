# Contributing to the UNIIMENTE Kernel

This file covers how to work in the repository. *What* to build and *why* is
governed by the founder documents. Read them before material work. This page
links to them rather than restating them:

- `AGENTS.md`: entry contract for AI agents (humans should read it too)
- `docs/FOUNDER_EFFECT_COMPILER.md`: preserve the intended effect; do not literalize the metaphor
- `docs/RECURSIVE_COLLABORATION_PROTOCOL.md`: review roles, alternatives, merge proof
- `docs/README.md`: index of every document and which one wins on conflict

## Set up

```bash
git clone https://github.com/dababiyoda/uniimente-kernel
cd uniimente-kernel
git fetch --unshallow 2>/dev/null || true   # frozen-experiment tests need full history
make install                                 # pip install -r requirements-dev.txt
make ci                                      # everything CI jobs 1-4 run
```

Python 3.11+. `make help` lists every target.

| Command | What it runs |
|---|---|
| `make test` | `python -m pytest -q` (unit + integration) |
| `make unit` | `tests/unit` only |
| `make verify` | institutional verifier V1–V5; writes a run record to `verifier/runs/` |
| `make contracts` / `authority` / `sealed` | CI guard jobs 2 / 3 / 4 |
| `make lint` | ruff correctness checks (config in `pyproject.toml`) |

## Where things go

Start from `docs/ARCHITECTURE.md` (codemap) and the root `README.md` (layout).
Before adding a module, check `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`:
each concern has one canonical owner, and a second active owner is a defect.

- A new top-level directory needs a `README.md` and a row in the root
  `README.md` Layout table. `tests/unit/test_repository_map.py` enforces both.
- Shared mechanics (hashing, clock) come from `common/`. Do not add another
  local `_now()` or `json.dumps(..., sort_keys=True)` digest.
- A cross-organ shape is a schema in `contracts/`, not a Python dict convention.
- External effects go through `policy/consequence_gate.py` and nowhere else.

## Things you must not change casually

**Sealed artifacts.** These are listed in `docs/ARCHITECTURE.md` under "Sealed
artifacts": the Constitution, authority and identity registries, the
Consequence Gate, the pinned `events.spine` classes, and the frozen
`evolution/repair/` and `evolution/migration/` experiments. The continuity
tests will fail. That failure is intended: such a change needs a founder
decision and a new reviewed binding, not a test update.

**The boundary distribution.** `adapters/`, `contracts/`, `events/` and
`provenance/` ship as `uniimente-kernel-boundaries` (`pyproject.toml`).
WealthMachineIntelligence and DALEOBANKS pin this distribution. Keep its
imports inside those four packages, and version any change to it.

**Records.** `tests/evidence/`, `verifier/runs/`, `docs/release/`,
`docs/decisions/` and dated reports are evidence. Append new records. Do not
edit old ones.

## Preservation rule

Delete nothing of institutional value (`docs/UNIIMENTE_FINAL_BUILD_ORDER.md`
§2, §12). Superseded code can be wrapped, registered as a fallback, marked
historical or turned into a test oracle, but it stays in the repository. A
CI workflow that is no longer used is reduced to `workflow_dispatch` rather
than removed (see `.github/workflows/tests.yml`).

## Pull requests

Use `.github/pull_request_template.md`. A material change records the intent
it advances (`docs/FOUNDER_INTENT_LEDGER.md`, "Mandatory Traceability"). A
change with no traceable intent is labelled *maintenance*. Open material PRs
as drafts. A green CI run is evidence for review. It does not authorize
merging, deployment or activation.
