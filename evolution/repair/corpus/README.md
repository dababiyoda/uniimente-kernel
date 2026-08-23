# Frozen measurement corpus for the Package 3 repair experiment

Three organ manifests, byte-identical to their content at `627ec48` — the commit
that froze `evolution/repair/spec.py`. Verify with `git hash-object`:

    kernel        7b894e47f2c70c2a28bb8f26b6b8ae1ec56ea7b6
    daleobanks    533c55ee9ddd2683ce94eadb93a0e8bfc73e3545
    wealthmachine 3c649b1042df90b1a441da9d74bfd3b637481ee7

## Why this exists

`spec.MEASUREMENT_CORPUS` declares `"manifests": "organs/*.manifest.yaml"` — a
**live glob**. A sealed experiment whose inputs are a mutable directory cannot be
reproduced, and the recorded Package 3 run therefore cannot be re-executed today
and get its recorded answer. That is CONTRADICTION-0001.

This is not hypothetical drift. `organs/kernel.manifest.yaml` **already changed**
after the freeze (`7b894e47` → `303ee198`) in a way that happened not to move the
unresolved count. The next change was not so lucky: publishing the PumpStation
and RESEARCH-IN manifests took the live corpus from 7 unresolved rows to 17, and
20 tests went red on `assert 17 == 7`.

## What this corpus does and does not change

Pointing the experiment here reproduces **every sealed expectation, unchanged**:

    unresolved       7  ==  REQUIRED_REFUSALS["unresolved_count"]
    edges            4  ==  len(REQUIRED_EDGE_TRIPLES)
    edge triples        exact match, sorted

That is the important property. The expectations were always correct. Only the
*binding* from experiment to input was unsound. No expectation value is touched
by this remedy, and `tests/unit/test_repair_frozen_corpus.py` proves it.

## What has NOT been done, and why

Nothing under `evolution/repair/` or `tests/unit/test_repair*.py` has been
modified. Applying the remedy means repointing five call sites at this directory:

    evolution/repair/harness.py:152        load_all(os.path.join(self.root, "organs"))
    tests/unit/test_repair_adapters.py:40  load_all()
    tests/unit/test_repair_candidates.py:47 load_all()
    tests/unit/test_repair_inertness.py:99 load_all(__REPO_ROOT__ + "/organs")
    tests/unit/test_repair_spec_frozen.py:126 load_all()

plus `MEASUREMENT_CORPUS` and a recomputed `SPEC_SHA256`. That is six files of
another session's sealed proof record. The seal's own test documents the
procedure — *"If this is a deliberate amendment, say so explicitly in the commit
message and in docs/release/package-3/ — do not just update the hash"* — so the
amendment is sanctioned, not forbidden. It was still left unapplied: the founder
has DEC-OM-002 on record and Kimi independently classified the same item as
founder-blocked, and no urgency outweighed two engines reading it the same way.

The remedy is built and proven so that applying it is a five-line change against
executable evidence rather than a judgement call against prose.
