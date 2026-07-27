# Package 3 baseline corpus

The three organ manifests as they stood at `BASELINE_COMMIT`
(`cb234faf932d239d79b0e7ab28e54f576b8a15bf`), extracted verbatim:

```
git show cb234fa:organs/kernel.manifest.yaml
git show cb234fa:organs/daleobanks.manifest.yaml
git show cb234fa:organs/wealthmachine.manifest.yaml
```

`SHA256SUMS` records their hashes. `tests/unit/test_repair_spec_frozen.py`
verifies both that these files match those hashes and that the hashes match the
manifests still in `organs/`, so tampering with either copy is detectable.

## Why this exists

`spec.py` freezes a measurement of the institution — four edge triples and an
exact set of linker refusals, including `unresolved_count: 7`. That measurement
was taken over these three manifests and nothing else.

The frozen-corpus test originally fed the linker from the live `organs/`
directory. That coupled a finished experiment to a growing institution: adding a
fourth organ changes `unresolved_count`, so the experiment fails — not because
the linker regressed, but because the institution acquired an organ. Registering
PumpStation as `organs/pumpstation.manifest.yaml` triggered exactly that, moving
the count from 7 to 12.

The spec's own instruction is that a change here must be re-frozen rather than
quietly re-interpreted. Re-freezing was the wrong remedy: Package 3 and Package 4
have already run and their results are recorded in `docs/release/`. Editing the
tables those results were judged against would retroactively alter a completed
experiment's baseline — the precise failure `spec.py` describes itself as
existing to prevent:

> That is the mechanism preventing candidate code from silently retuning the
> experiment it is being judged by.

So `spec.py` is unchanged and `SPEC_SHA256` still verifies. What changed is where
the test reads its corpus from: this snapshot, which is what the frozen numbers
actually describe, instead of whatever `organs/` contains today.

This is the "route for historical replay" the Absolute Preservation Rule
requires. The experiment stays reproducible at any future commit, and the
institution can register new organs without falsifying it.

## What this does not do

It does not stop a real linker regression from being caught. The linker is
unchanged and still runs against this corpus; a behavioural change in
`linker/linker.py` fails the test exactly as before. Only the *membership* of the
corpus is pinned.

Drift between these files and `organs/` is reported by
`test_baseline_corpus_still_matches_the_live_manifests`. When a live manifest is
legitimately edited, that test fails and states the choice out loud: either the
edit was unintended, or a new experiment should be frozen against the new corpus.
The old one is never silently re-pointed.
