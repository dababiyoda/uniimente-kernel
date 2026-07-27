# Differential authority conformance harness

The scripts that produced `DIFFERENTIAL_AUTHORITY_CONFORMANCE.json` and
`TEST_INVENTORY_RECONCILIATION.json`. Vendored so the results are reproducible
rather than asserted.

Each runner executes the same 30-case corpus against one authority engine, in
that engine's own git worktree. Drift is injected at the same pipeline position
in each: PR21 via its native stage interceptors at `WITNESS`, main via a wrapper
on `signer.sign`, which fires between witness creation and
`_reauthorize_at_commit`.

A case an engine cannot structurally express is recorded `ABSENT` with the
reason. No verdict is ever fabricated.

## Reproducing

```bash
# worktrees
git worktree add --detach /tmp/w/cleanmain origin/main
git worktree add --detach /tmp/w/pr21      origin/build/consequence-gate
# merged tree = origin/main with phase7 merged, 4 conflicts resolved --ours, staged

# PR21 needs three dependencies it does not declare
pip install pydantic cryptography cffi

( cd /tmp/w/cleanmain && MAIN_ROOT=$PWD PYTHONPATH=$PWD UNIIMENTE_ENV=development \
    python run_main.py > res_main.json )
( cd /tmp/w/pr21      && PYTHONPATH=$PWD python run_pr21.py > res_pr21.json )
( cd /tmp/w/merged/sdk-python && PYTHONPATH=$PWD python run_sdk.py > res_sdk.json )

python merge_conformance.py     # -> DIFFERENTIAL_AUTHORITY_CONFORMANCE.json
python gen_reconciliation.py    # -> TEST_INVENTORY_RECONCILIATION.json
```

`verify_main_holes.py` re-checks the four `PERMIT` results on `main` directly,
without the harness, so the three verified defects do not rest on harness code.
One of the four — case 2 — is confirmed **not** a defect by that script.

## Known harness limitations

- Paths are absolute to the session scratchpad; adjust before re-running.
- SDK case 6 (expired grant) is not claimed either way: driving the clock past
  the mint TTL would have required patching time, and an unclaimed result is
  better than a manufactured one.
- SDK case 30 (concurrent race) is not exercised; asserting a specific threading
  model would have tested my assumption rather than the implementation.
- The corpus tests the engines in isolation. It does not test them behind
  PR #31's merged linker, which remains unverified against these contracts.
