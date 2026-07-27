# Gate B — the 65-test delta, explained

**`UNEXPLAINED_TEST_COLLECTION_DELTA = 0`. Gate B is closed.**

The merge loses nothing. 495 tests on `origin/main` + 184 tests arriving from
`phase7/fast-capability-evolution` = 679 in the merged tree, and the three node-ID
sets are byte-for-byte identical under union. The merged suite runs **679 passed in
12.60s**.

Machine-readable evidence, including SHA256 of every node-ID file:
[`TEST_INVENTORY_RECONCILIATION.json`](TEST_INVENTORY_RECONCILIATION.json).

---

## The delta was my measurement error, not a property of the merge

The arithmetic that raised the alarm was `560 + 184 = 744` against a merged
collection of `679` — an unexplained 65.

**`560` was never `origin/main`.** I collected it from `/home/user/uniimente-kernel`,
whose checked-out branch is `claude/integration-canonicalization-audit`, which is
built on top of `claude/uniimente-system-design-hczheq`. That working tree carries
this session's own unmerged test files. A clean detached worktree at `origin/main`
collects **495**.

The 65 account for themselves exactly:

| File | Tests | Provenance |
|---|---:|---|
| `tests/unit/test_traceability.py` | 33 | absent on `origin/main`; written this session (PR #54) |
| `tests/unit/test_governance_records.py` | 29 | absent on `origin/main`; written this session (PR #54) |
| `tests/unit/test_repair_spec_frozen.py` | 2 | file exists on main; 2 cases added this session (baseline corpus) |
| `tests/integration/test_phase_zero_connection.py` | 1 | file exists on main; 1 case added this session (PumpStation manifest) |

Every one is mine. None belongs to `origin/main`, and none was ever supposed to be in
the phase7 merge — PR #54 is a different branch and a separate landing decision.

## The hypothesis I was testing is refuted

I suspected the SDK was **displacing** main's tests through path or name collisions —
that the merge would silently trade 65 kernel tests for 184 SDK tests, losing coverage
while the headline number went up. That would have materially changed the
recommendation to land PR #21 first.

It is not happening. The signal that looked like displacement — `sdk.ids ∩ merged.ids
= 0` — was a rootdir artifact. The SDK subtree was collected with `rootdir=sdk-python/`,
so its node IDs read `tests/test_gate.py::…` while the merged tree reads
`sdk-python/tests/test_gate.py::…`. Re-rooted, the 184 match the 184 gained exactly,
byte-for-byte. Zero collisions. **The merge is purely additive.**

## Why the SDK tests were missing from main

`sdk-python/` **exists** on `origin/main`. It contains exactly one file:

> `sdk-python/README.md` — "Python SDK for organ integration: contracts, event
> emission, gateway client, identity helpers. DALEOBANKS and WealthMachineIntelligence
> migrate onto this in Phases 2-3. Publish target: Phase 10."

32 files and 14 test files on `phase7`; 1 file and 0 test files on `main`. There is no
`pytest.ini`, `setup.cfg`, `pyproject.toml` or `tox.ini` anywhere on main, so no
`norecursedirs` or `testpaths` rule is involved. The absence is missing code.

Worth naming plainly: the canonical branch ships a directory whose README describes an
SDK that two other repositories are said to migrate onto, and the implementation lives
only on an unmerged branch. That is the institution's central pathology reproduced at
the scale of a single directory — a documented capability that the canonical branch
does not contain.

## What this does and does not establish

**Establishes.** No test is lost by merging phase7. The 184 SDK tests are new code, not
a collection-config change. The merged tree is green.

**Does not establish.** Node-ID identity proves the *inventory* is additive; the green
run proves the merged tree *passes*. Neither proves the 495 main tests still exercise
the same **mechanisms** — a test can pass against a changed implementation, and 127
commits of divergence sit under this merge. That is the objection recorded against
Decision A, and Gate B does not answer it. **Gate A does.**

Two standing caveats. The merge is staged and uncommitted, so these numbers describe a
working tree and must be re-measured before any tag. And Gate B is inventory only — it
is not evidence about authority semantics.

## Method

Every collection was run, saved, and hashed. Nothing was inferred.

```bash
# clean origin/main — the collection that should have been used from the start
git worktree add --detach $W/cleanmain origin/main
( cd $W/cleanmain && python -m pytest --collect-only -q | grep '::' | sort -u ) > cleanmain.sorted   # 495

# merged tree (phase7 merged onto main, 4 conflicts resolved --ours, staged, NOT committed)
( cd $W/merged   && python -m pytest --collect-only -q | grep '::' | sort -u ) > merged.sorted       # 679

# SDK subtree alone — note the rootdir, and therefore the prefix
( cd $W/merged/sdk-python && python -m pytest --collect-only -q | grep '::' | sort -u ) > sdk.sorted # 184

sed 's|^|sdk-python/|' sdk.sorted | sort -u > sdk_rerooted.sorted
cat cleanmain.sorted sdk_rerooted.sorted | sort -u > union.ids
diff -q union.ids merged.sorted    # identical -> delta = 0
```

The invalid 560-test collection is retained in the JSON under `contaminated_main`, with
its true ref recorded. It is preserved rather than discarded: a measurement error that
nearly reversed a merge recommendation is institutional evidence about the method, and
the rule that caught it — *collect from an explicit ref, never from the working tree* —
is worth more than the number it corrected.
