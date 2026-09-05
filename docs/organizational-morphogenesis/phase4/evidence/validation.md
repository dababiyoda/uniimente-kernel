# CMC-002 validation record

All results below are observations, not cryptographic founder authentication.
Working tree: dedicated Phase-4 branch based on cbb1d277ec9082acecb82d8529f816bc17f70784.
Python: 3.12.13. No dependencies installed during this slice.

Unless noted, commands ran from the Phase-4 repository with:
`PYTHONPATH=/workspace/scratch/c1c408c41c36/tmp/phase3-venv/lib/python3.12/site-packages`.

| Command | Actual result |
|---|---|
| Default `python -m pytest tests/unit/test_founder_authentication_gap.py -q` without PYTHONPATH | Failed: No module named pytest |
| Existing `tmp/phase3-venv/bin/python` launcher | Failed: missing interpreter target; not repaired |
| `python -m pytest tests/unit/test_founder_authentication_gap.py -q` with PYTHONPATH | 6 passed in 0.06s |
| First `python -m pytest tests/unit/test_cathedral_metabolism.py -q` | 8 failed, 28 passed in 2.87s; preserved raw output |
| Corrected focused command, same selection | 36 passed in 5.31s |
| First broad `python -m pytest tests/unit -q` | Final result unavailable after session handoff; UNKNOWN, not pass |
| Logged repeat `python -m pytest tests/unit -q` | **3 failed, 1256 passed in 158.45s** |
| Frozen pre-implementation archive: `python -m pytest tests/unit/test_seams.py -q` | **Same three test IDs failed, 15 passed in 0.25s** |
| `python verifier/v2/verify.py` | **FAIL**, V2 reports 3 failed, 1256 passed in 159.24s; V1/V3/V4/V5 passed their existing checks |
| `python scripts/ci/check_schema_refs.py` | 22 schemas, 34 local refs; all resolve |
| `python scripts/ci/check_authority_singleton.py` | Exactly one of each of six governed artifacts |
| Skill `validate_intent_ledger.py docs/intent/INTENT-CMC-2026-09-04.json` | VALID: 1 record |
| Skill `validate_deliberation.py`, each CMC-001 and CMC-002 record | Both VALID: five-role review, exactly two passes each |
| `git diff --check` | Passed before final evidence commit |

The protocol validator scripts are under
`/root/.codex/skills/remote-skills/skill-6a654f0761e48191bffab56314edeae7/scripts/`.

## Negative evidence and baseline isolation

The broader failures are the three parametrizations of
`test_every_seam_is_satisfied_by_a_real_kernel_class` for
CapabilityAdvertisementLike, RoutingDecisionLike and ProvenanceNodeLike.
The same test IDs fail in an untouched archive of cbb1d277; this reproduces
pre-existing failures under the same Python environment. It does not establish
their behavior in Python 3.11 CI. Protocol member iteration order differs, so
the first reported missing field may differ. No seam implementation or seam
test was changed.

Archive creation was `git archive cbb1d277ec9082acecb82d8529f816bc17f70784 | tar -x -C /workspace/scratch/c1c408c41c36/tmp/cmc-baseline.ix4ixS`.
This created no branch and changed no repository source.

The original focused failure was an incorrect positional argument to existing
StandingCognitionRuntime; corrected to keyword `ledger=`.
An earlier clean OMNIMORPH import failed with the existing Foundry package
cycle involving GateActivationReceipt. A narrow lazy facade repaired that
cycle; both cold import orders are exercised by the passing focused suite.
The full original import traceback was not separately saved; this entry
records the observed failure without inventing raw output.

Raw broad logs: `full-unit-regression.txt`, `baseline-seams.txt`.
Verifier receipt:
`verifier/runs/v2-2026-09-05T08-55-39.095044+00-00.json`.
V3's existing structural closure label is not actual founder mission closure,
production readiness, or external outcome evidence.

## Executed episode evidence

`comparison.json` preserves six exact subprocess commands, exit codes,
stdout and shell elapsed times. Direct/static each run:
deliberate exit 75 → separate recovery process → synthetic test continuation.
Both complete one read-only audit invocation. Full evidence chains are
`direct-simulation.jsonl` and `static-simulation.jsonl`.

All episodes are SIMULATION. No actual model calls, authenticated founder
commands, actual organ execution, actual mission closures or external effects.
ResourceGovernor reserves three conservative cognition-call slots even though
the deterministic test callables do not call a model provider.

No held-out efficacy evaluation, full integration suite, sealed-developmental
CI job or remote PR CI success is claimed here. Remote CI status belongs to
the draft PR and may remain pending or fail. The full unit suite is **not green**.
