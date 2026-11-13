# Model-weight licenses: the license an installed Ollama model carries

Offered to #201's owner with the SPDX fixes, as commits on `claude/oss-201-fix-licensing` (`greg/licensing.py`
only). The active policies do not change. Nothing here attaches, pulls or runs a model. This is not a legal review.

## The gap

The October 22 directive, section VII: "Model-weight licenses are not yet covered by the acquisition gate." #201
recorded the same limit (`docs/open-source/LICENSE-QUALIFICATION-2026-10-22.md`, open item 2;
`DOCUMENT-TEXT-2026-10-22.md`, open item 3).

GREG's local models run through Ollama (`greg/models.py` `OllamaRoute`, `docs/OPEN_SOURCE_STACK.md`). Ollama itself
is MIT whatever the weights are, so qualifying the server says nothing about the model. Before this change:

- no code read the license a pulled model carries;
- a Debian package declaring `License: Llama-2-Community` was unclassified, so under the active binary policy (P0) its
  binary kept the behaviour it had before licenses were read and attached (fail-before test below);
- the short names model cards use (`llama3.1`, `gemma`, `openrail`, `creativeml-openrail-m`, `qwen-research`) were
  unknown to every reader.

## What GREG can do now

`licensing.ollama_model("qwen3.5:4b")` reads the model's own manifest in the local Ollama store and returns an
assessment in the shape the gate already uses:

- **Where it reads.** When `OLLAMA_MODELS` is set it reads that store and no other, the value trimmed as Ollama's
  `envconfig.Var` trims it (spaces, then `"` and `'`; see
  [the review of `d1724006`](#the-review-of-d1724006-ollama_models-and-what-gos-decoder-takes)). When it is unset
  or empty once trimmed, it reads `$HOME/.ollama/models` and nothing else, as Ollama's `envconfig.Models` does; with
  `HOME` unset or empty too, Ollama panics and the model is held. The Linux service's store
  (`/usr/share/ollama/.ollama/models`) is read only when a caller passes it as `models_dir` (see
  [the review of `49aaa812`](#the-review-of-49aaa812-homes-store-alone-and-the-types-go-decodes)). There it reads the
  manifest Ollama would
  serve for the name, completed as Ollama completes names: `manifests-v2/<host>/<namespace>/<model>/<tag>` (Ollama
  0.40 and later), else `manifests/<host>/<namespace>/<model>/<tag>` (0.35 and earlier). See
  [Ollama 0.40's store](#ollama-040s-store-and-the-selection-gate).
- **What it reads.** Every layer of media type `application/vnd.ollama.image.license`, from its content-addressed
  blob. A blob whose bytes do not match its digest, a link, a FIFO, or a file over 1 MiB is not read, and the model
  is held.
- **What it binds.** The verdict is tied to the model name, the manifest's sha256 and the digest of every weight
  layer (`model`, `projector`, `adapter`). `qualify_use` takes it unchanged, so a changed weight changes the
  qualification digest.
- **How a license text is classified.** Each text is classified by what it says, not by its title:
  - **Apache-2.0** when sections 1 to 9 hash to the standard terms. Only the title header, the appendix or the
    boilerplate notice may stand beside them, and the notice's copyright field must be a copyright notice only.
  - **MIT** when the grant, the condition and the disclaimer are the standard words, after only a title and copyright
    notices.
  - **A copyright notice** is "Copyright (c) <years> <holder>", optionally ending "All rights reserved". After an
    address, a URL, an initial or a company suffix (Inc., Ltd. and similar) is set aside, the holder contains no full
    stop or other sentence mark before its end, and no normative word (shall, may, only, not, licence, use,
    research, commercial, train and similar). Anything else on that line is text beside the terms, so it is
    unclassified and held.
  - **Not open source (held)** when any restrictive wording appears in the text, as whole words. This covers the
    model families below and the existing riders (non-commercial, Commons Clause, BUSL, SSPL, Elastic, PolyForm,
    CC NC/ND).
  - **Unclassified (held)** in every other case. That includes a standard text with other terms beside it, and a
    text with one word changed.
- **Weights are never cleared by default.** No license layer, an unreadable one, a manifest that is not an Ollama
  manifest, or any unclassified text holds the model for the founder.

Model families recognised in **any** declaration (DEP-5, a package's License field, a short id, a full text):

- Llama 2 and later;
- Gemma;
- every OpenRAIL and RAIL variant;
- the Qwen research and Tongyi Qianwen license agreements;
- the DeepSeek and DeepFloyd licenses;
- Mistral's non-production and research licenses;
- research-only terms.

Each attaches conditions to the model and what is made with it, so each is not open source and is categorised
`restricted_use`. Under the draft D-LIC-1 a founder clearance of such a model needs permission evidence: the license
accepted, read against GREG's use.

## Tests and measurements

| Run | Result |
| --- | --- |
| `pytest tests/unit/test_greg_model_license.py` | 35 passed |
| The same file on the base `083c91ea` | 35 failed. The DEP-5 test fails on behaviour, not on a missing name: Llama-2 terms let the binary through. |
| The four existing licensing test files and `test_greg_document_text.py` | 1980 passed with the change; the new riders reclassify none of their fixtures |
| `model_license_tree` over every license text installed on this body (111 shipped by Python packages, 10 in `/usr/share/common-licenses`) | 46 cleared (12 Apache-2.0, 34 MIT), 74 unclassified, 1 not open |
| The 46 cleared texts, read against each package's own declaration | All are genuinely Apache-2.0 or MIT. 9 belong to packages that declare BSD or a dual license; each is a bundled third-party text or one half of a dual license. No false clear. |
| The 74 unclassified | BSD 6, GPL 8, Apache or MIT with other text beside it 12, other 48. Each is held for the founder: the cost of recognising only two texts. |
| The 1 not-open reading | `supervisor`'s LICENSES.txt, which records that Medusa "was once distributed under a 'free for non-commercial use' license". It is a false restrictive reading on an unclassified text, so the verdict (held) is unchanged. |
| Riders over the full Apache-2.0, MIT, GPL-1, GPL-2, GPL-3, LGPL-2.1 and MPL-2.0 texts | none after masking GPL-2 section 3c ("allowed only for noncommercial distribution"), which the first run read as a use restriction |
| §IX scenario 5 on the mission path (`tests/integration/test_greg_section_ix_acquisition_scenarios.py`): a signed PDF mission whose scope pre-authorizes a read-only attach, real installed `pdftotext`, its package declaring AGPL-3+, Llama-2-Community or CC-BY-NC-4.0 beside GPL-2+ | the mission waits; no attach; the reason names the license. The Llama-2 case fails on `083c91ea`: the reader attached silently |
| §IX scenario 6 (same file): a second PDF mission after the first acquired the reader | closes on the attached reader with no second deficit, qualification or attach |
| 13 mutants added to the licensing group of `scripts/ci/check_cortex_mutants.py` | 72 mutants in the group: 71 caught, 1 stale. The stale one was an existing mutant whose two anchor lines `model_assessment` had repeated. The repeat was removed and both affected mutants re-run: caught. `model-license-mutants-2026-10-30.txt` |

The script is `measure_model_texts.py` beside this file. Its output is `model-license-texts.json`.

### Copyright notices (review of #230, blocking)

The independent review at `376889d0` showed two ways to slip terms past the classification:

- a line starting "Copyright" was dropped before the MIT terms, whatever followed it;
- the Apache notice's copyright field took up to 300 characters of anything.

Llama-style terms written there ("shall not use the model to train other models", "only for research … never in
production") CLEARED the weights, with `auto_attach` true. The fix accepts only a copyright notice in either place.

| Run | Result |
| --- | --- |
| `test_greg_model_license.py` with the new tests, on `376889d0` | 5 failed. Four are the smuggled terms: the reviewer's MIT and Apache cases, a holder with no full stop ("for research use only") and one with no listed word ("Weights are for evaluation and audit purposes."). The fifth: a "©" line was held, because `©\b` never matches before a space. `copyright-notice-fail-before.txt` |
| The same file with the fix | 45 passed |
| The reviewer's licensing suites and `test_greg_section_ix_acquisition_scenarios.py` | 2032 passed, 1 xfailed |
| `model_license_tree` over the same 121 installed texts | 45 cleared, 75 unclassified, 1 not open (was 46, 74, 1). The one text no longer cleared is pluggy's MIT, whose holder line reads "holger krekel (rather uses bitbucket/hpk42)": "uses" is a normative word. It is held for the founder, a measured cost of one in 46. `copyright-notice-real-diff.json` |
| 4 mutants added to the metabolism group: notice lines dropped whatever follows; a sentence after the holder accepted; a normative word in the holder accepted; the Apache field unchecked | the whole group on `40520bcb`, 105 mutants, each in its own copy: 105 caught, 0 survived or stale. `copyright-notice-mutants-2026-10-30.txt` |

## Ollama 0.40's store, and the selection gate

### The gap

On `3358d660`, `ollama_model` read only `manifests/<host>/<namespace>/<model>/<tag>`. Ollama's own source shows that
a current Ollama keeps a pulled model elsewhere. The source read was a clone of `github.com/ollama/ollama` at `main`
`4d22e65` (2026-10-29) and the tags `v0.40.0` (`0d0720e`, 2026-10-06) and `v0.35.1` (`b0c1ca4`):

| What Ollama does | Where in its source | `v0.35.1` | `v0.40.0` and `main` |
| --- | --- | --- | --- |
| The named manifest is written as a blob of its own, `blobs/sha256-<hex>`, and named by a relative link at `manifests-v2/<host>/<namespace>/<model>/<tag>`, or by a copy where it cannot link; the legacy name is removed | `manifest/manifest.go` `WriteManifestData`, `writeManifestData`, `linkManifest`, `copyManifestFile` | no (`manifests/` only) | yes |
| After every pull, a legacy "downgrade anchor" is written at the old path: a regular file holding the pulled manifest plus a layer naming it. It is best effort, and `ollama cp` writes the v2 name without one | `server/images.go` `PullModel`, `writePullDowngradeAnchor`; `manifest/manifest.go` `WriteLegacyAnchor`; `CopyModel` | — | yes |
| The default registry is filed under `ollama.com` in `manifests-v2`; `registry.ollama.ai` and `ollama.com` are one host | `manifest/paths.go` `canonicalV2Name`, `isDefaultPublicHost` | — | yes |
| A host's `:` is written `%3A` in `manifests-v2` | `manifest/paths.go` `encodeV2ManifestHost` | — | yes |
| A requested name is matched to the stored one ignoring case, over an index of every entry four levels down `manifests-v2` and then `manifests`, a v2 entry taking the place of a legacy one of the same stored name; two stored names that differ in case are met in the order of a Go map | `manifest/manifest.go` `namedManifestRefs`, `FindName`, `FindNamedManifestForRunner`; `server/routes.go` `getExistingName` | — | yes |
| The stored name is then opened: `v0.40.0` looks at the v2 path, else the legacy path under each spelling of the default registry, so a dangling v2 link falls back to legacy; `main` opens the entry its index holds, so a dangling v2 link fails the load | `manifest/paths.go` `resolveManifestPath`, `legacyNameCandidates` (`v0.40.0`); `server/routes.go` `loadExistingModelForRunner` (`main`) | — | differs |
| A link, in either tree, is opened only when it resolves to the blob of this store its file name names, with bytes hashing to that name; a regular file only when it lies inside its tree | `manifest/manifest.go` `openManifestFileLocked` | — | yes |
| A name of 12 to 64 hex digits, or `sha256-<hex>`, is the local manifest blob it names, before any model of that name | `manifest/paths.go` `ResolveDigestReferenceName` | — | yes |
| A name may be a manifest list, one child reference per runner. Ollama runs one child: for each runner in its order (`mlx`, `llamacpp`, `ggml` on Apple-silicon macOS; `llamacpp`, `ggml`, `mlx` elsewhere), the first entry naming that runner, when its blob is local | `manifest/manifest.go` `selectManifestWithPreferences`, `runnerPreferences`; `server/images.go` `pullSelectedManifest` | — | yes |
| `/api/tags` reports the sha256 of a plain manifest's bytes; for a list, the digest of the child it selects, not the list's | `server/model_list.go` `describeModelRows` | — | yes |
| Weights are layers of type `image.model`, `image.projector`, `image.adapter`, `image.tensor` (safetensors) or `image.draft`; a model whose config names a `remote_host` and `remote_model` is a relay to that host | `manifest/layer.go`; `server/routes.go`, `types/model/config.go` | — | yes |

So on `3358d660` a model pulled by Ollama 0.40 or later was read through its downgrade anchor: the same license
layers, but bound to the anchor's digest, which is neither the manifest Ollama serves nor the one `/api/tags`
reports. A model with no anchor (after `ollama cp`, or when the best-effort write failed) was unassessed (`None`),
and a legacy manifest that differs from the v2 one (an older Ollama pulling after a downgrade) was read in place of
the one Ollama 0.40 serves. Two smaller defects: a manifest nested 100,000 deep made `ollama_model` raise
`RecursionError`, and a registry host with a port (`localhost:5000/team/coder`) was not a name the reader accepted.

### What `greg/licensing.py` does now

- **Only a manifest that Ollama `v0.40.0` and `main` both serve is read** (`_ollama_named`, `_ollama_manifest`).
  - The store's entries for the name are found as Ollama's index finds them: both trees, ignoring case, the stored
    host decoded, a directory skipped, a name that is not ASCII skipped.
  - The model is held when the two versions could serve different manifests:
    - two stored names that differ only in case;
    - two entries for the name in one tree;
    - an entry that is not where `v0.40.0` looks;
    - a v2 entry that does not open.
  - A v2 entry is read before the legacy one, so the downgrade anchor beside it is never read.
  - A link in either tree is followed only to the blob of this store that its file name names, and only when the
    bytes hash to that name. A regular file is read only inside its tree.
  - A name Ollama reads as a blob digest is held.
- **A manifest list:** every child the store holds is read once, and assessed on its own. Any held child holds the
  model. This is stricter than Ollama, which runs one child per platform, though a request naming a runner can pick
  another.
  - `subject["children"]` gives each child's digest, runners, weights and verdict.
  - `subject["api_tags_digest"]` gives the child `/api/tags` reports, which is also the child Ollama runs, under
    each runner order.
  - `manifest_sha256` is the list's own digest, the manifest the name holds. `weights` covers every child read.
  - A child whose blob is not in the store is not read. Ollama never selects it, so none of its weights can run.
    At most 8 such digests are named in `uncertainty`, and the rest are counted.
  - The model is held when:
    - a child is in the store but does not match its digest;
    - a child carries layers or a config of its own;
    - none of the children is in the store;
    - the list names more than 64 distinct manifests.
- **Weights and relays:** tensor and draft layers count as weights. These are held:
  - a manifest with no weights layer;
  - a relay to a remote host;
  - a config blob that is missing or does not match its digest.
- **A registry host may carry a port**, as Ollama's names may (`types/model/name.go` `isValidPart`).
- **A manifest too deeply nested to parse holds the model.** It no longer raises.
- **`admit_model_selection(config, models_dir=None)`.** `config` is the selection that
  `models.effective_route_config` returns.
  - **Order names `ollama`, model cleared:** the selection comes back with `license_evidence`. It carries `model`,
    `manifest_sha256`, `weights`, `verdict`, `assessment_digest` and `use_digest`, the last two from `qualify_use`
    under GREG's use. For a list it also carries `children` and `api_tags_digest`, the digests that
    `OllamaRoute` reads from `/api/tags`.
  - **Model held, unreadable, or in no store this process can read:** `ollama` leaves the order and `ollama_model`
    leaves the selection. The founder's other routes keep their order. `model_license_hold` records `model`,
    `verdict` (`UNASSESSED` when nothing was read), `reason`, `manifest_sha256` and `assessment_digest`.
  - **Order that is not a list:** every route is held.
  - Stale `license_evidence` and `model_license_hold` are removed from every result.
  - Nothing a store holds makes it raise. `None`, and anything that is not a dict, comes back unchanged.
  - It reads the store and nothing else, writes nothing and grants nothing. Nothing calls it yet.

### The review of `4f5ce7e5`

An independent review of `4f5ce7e5` reproduced ten cases (`repro.py` R1 to R10). Its findings, and what each one gives
on `2b4b0954`:

| Case | `4f5ce7e5` | `2b4b0954` |
| --- | --- | --- |
| R1, blocking: a list with an unlicensed `llamacpp` child and an Apache `mlx` child | CLEARED (the layers were pooled) | held: the `llamacpp` child declares no license; both children are recorded with their verdicts |
| R2: the digest `/api/tags` reports for a list | evidence carried the list's digest only | evidence carries `children` and `api_tags_digest`, equal to the child's digest |
| R3: a legacy link (Llama) at `registry.ollama.ai` and a regular file (Apache) at `ollama.com` | CLEARED (the link was skipped) | held: two legacy entries for the name |
| R4: `Qwen3.5:4b`, a v2 manifest (Llama) and a legacy one (Apache) | CLEARED (read the lower-cased legacy manifest) | held: the v2 manifest, Llama |
| R4b: `Qwen3.5:4b`, v2 only (Apache) | `None` | CLEARED: the manifest Ollama serves |
| R5: a 12-hex-digit name | CLEARED (the named manifest) | held: a digest reference |
| R6: a manifest with no weights layer | CLEARED, `weights=[]` | held |
| R7: stale evidence with an order lacking `ollama`; a dict order | kept; passed unchanged | removed; every route held |
| R8: a store path holding a NUL byte | `ollama_model` raises `ValueError`; the gate holds | the same; documented |
| R9: 5,923 entries naming one 1 MiB child | 99 s | under 0.1 s, the child read once |
| R10: 5,000 absent children | CLEARED, 365,121 characters of uncertainty | held: more than 64 manifests |

### Tests and measurements

| Run | Result |
| --- | --- |
| `tests/unit/test_greg_model_license_gate.py`, 27 tests, on `3358d660`'s `greg/licensing.py` | 27 failed |
| The same file on `4f5ce7e5`'s `greg/licensing.py` | 12 failed: the 11 new tests for the review's findings, and the dangling-v2 test, which now expects a hold. The 15 that pass include two new ones that `4f5ce7e5` already handled: a v2 copy, and a v2 manifest beside a differing legacy one |
| The same file on `2b4b0954` | 27 passed |
| `test_greg_model_license.py`, `test_greg_license_expressions.py`, `test_greg_license_qualification.py`, `test_greg_license_use_context.py`, `test_greg_binary_policy_options.py`, `test_greg_document_text.py`, `tests/integration/test_greg_section_ix_acquisition_scenarios.py` | before and after: 45, 1866, 40, 30, 1 (+1 xfailed), 39 and 4 passed. 2025 passed, 1 xfailed, unchanged |
| The reviewer's `repro.py`, R1 to R10, on `2b4b0954` | as in the table above |
| Mutants: the block for this store and gate rewritten for the new code (51 mutants), and two existing mutants re-pointed at the shared code (`_ollama_blob`; the weights of `_ollama_runs`) | the whole group on `2b4b0954`, 156 mutants: 156 caught, 0 survived or stale, in 52 minutes. The script cannot run one group alone, so the group ran in the worktree through the script's own `_run_one`, one mutant at a time, each mutated file checked byte-identical after. Of the 104 mutants that also ran on `40520bcb`, 61 passed or skipped as many tests before their first failure as they did there, and 43 passed exactly 27 more: the 27 tests of the new file, which runs before the file that catches them. The failing test was compared by that count, not by name. The 52 that did not run on `40520bcb` are the 51 of the rewritten block and the re-pointed digest-check mutant. Those 52, and the re-pointed weights mutant, also ran against the two model-license test files alone, from a scratch copy of `greg/licensing.py`: 53 of 53 caught. |

### The review of `52f5703b`: what Ollama's request parser and JSON decoder read

An independent review compiled Ollama's own `manifest/`, `types/model/` and `internal/modelref/` packages into two
oracles, one on the `v0.40.0` (`0d0720e`) run path and one on `main` (`e9fde36d`), and compared GREG with them over
54 stores: 15 false clears. A false clear is a store GREG clears while some Ollama run path serves a manifest whose
license layers are not the Apache text GREG read, whose weights GREG did not list, or whose config is a relay.

| Finding | `52f5703b` | Now |
| --- | --- | --- |
| F1 (high): Go's `encoding/json` matches a key to a field ignoring case, folds `ſ` (U+017F) to `s` and `K` (U+212A) to `k`, and a repeated key overwrites or merges into the first; GREG read exact keys. 12 stores (`Layers`, `MediaType`, `Digest`, `Manifests`, `Config`, `Remote_Host`, `layerſ`) | CLEARED | held, the key named. Every object the gate reads (manifest, list entry, list child, layer, config, config blob) is held when it carries a key that is not ASCII, two keys equal ignoring case (a repeated key included), or a key equal to one of Ollama's fields ignoring case but spelled otherwise (`_go_fields`) |
| F1, added here: a second `config` without a digest after a relay `config` | CLEARED (Python keeps the last) | held. The oracle shows Go merging the two: both versions serve the relay |
| F2: `<runner>:<digest>` and `sha256:<hex>` request names (`server/model_resolver.go` `digestModelName`). 3 stores | CLEARED (the model `llamacpp`, `sha256` or `mlx`, tagged with the digest) | held for every runner Ollama names (`mlx`, `mlxrunner`, `ggml`, `llamacpp`, `llama.cpp`, `llama-cpp`, `llama_cpp`), in any case (`_ollama_request_form`). A prefix that no blob begins with, which Ollama reads as a model name, is held too |
| F3: a source suffix (`internal/modelref` `ParseRef`): `:cloud`, `:local`, or a tag ending in `-cloud`, any case | `qwen3.5:4b-CLOUD`, `:CLOUD` and `:LOCAL` CLEARED from a local manifest under that tag | held. `qwen-cloud` with no tag is a local model in Ollama and is read |
| F4: 7 of the reviewer's own mutants survived | the safeguards held, untested | 6 have a test and a mutant in the group: a non-ASCII stored name, a digest name tagged `Latest` or under `Library`, `/api/tags` runner case and untyped children, a list entry with a config of its own |

The seventh, "a relay needs a host only", is not added: both versions relay only when `remote_host` and
`remote_model` are both set (`server/routes.go`), so a host-only config runs the local weights GREG reads. Holding it
would be stricter and still safe, so no test forbids it.

**The harness is now a test that needs no Go.** `tests/unit/test_greg_ollama_oracle.py` replays
`tests/fixtures/ollama_oracle/answers.json`: for each of 76 stores (the reviewer's 54, written with the same bytes,
and 22 more for F1 to F4), what both versions serve with no runner and with each runner. Each store is rebuilt by
`scenarios.py` and checked against the fingerprint frozen with it. When GREG clears, every manifest served must be one
GREG assessed, with Apache license layers only, no unlisted weights, no relay config, no cloud proxy, and the
`/api/tags` child GREG reports must be the one Ollama selects. 15 stores must clear. To refreeze:
`sh tests/fixtures/ollama_oracle/build_oracle.sh <dir>` (git, github.com, Go 1.24; it fetches only `manifest/`,
`types/model/` and `internal/modelref/` at the two commits and stubs `envconfig`; since the review of `d1724006`
it compiles Ollama's own `envconfig/` instead), then
`python -B -I tests/fixtures/ollama_oracle/freeze.py <dir>`. The oracle program is the reviewer's, with only its
header comment and the two variant fill-ins changed.

| Run | Result |
| --- | --- |
| The Ollama files the reviewer compiled, against a fresh fetch of `0d0720e` and `e9fde36d` | byte-identical (`manifest/`, `types/model/`, `internal/modelref/`, `server/`) |
| `answers.json` frozen with the rebuilt oracles, with the reviewer's binaries, and frozen twice | identical answers; the two freezes byte-identical |
| `test_greg_model_license_gate.py` (34 tests: the 27 and 7 new) on `3358d660`'s `greg/licensing.py` | 33 failed; the non-ASCII stored-name test passes (3358d660 reads no v2 store) |
| The same on `52f5703b`'s | 3 failed: F1, F2, F3. The 4 F4 tests pass, as tests of safeguards that were there |
| The same on `edb9dd3b` | 34 passed |
| `test_greg_ollama_oracle.py` (77 tests) on `3358d660`'s | 14 failed: 14 of the 15 stores that must clear (it reads no v2 store; `legacy_only` clears) |
| The same on `52f5703b`'s | 27 failed: the reviewer's 15, the 2 cloud names it did not count, and 10 of the 22 new stores |
| The same on `edb9dd3b` | 77 passed |
| The reviewer's `diff_harness.py` on `edb9dd3b`, default and legacy layouts | 54 of 54 match each, 0 false clears |
| The licensing suites on `edb9dd3b` | 45, 1866, 40, 30 (after a throwaway `git init`; 29 + 1 skipped without), 1 (+1 xfailed), 39 and 4 passed |
| Mutants | the whole metabolism group on `edb9dd3b`, 179 mutants (the 156 and 23 for the new guards; the oracle test added to the group's test list), each in its own copy of the repository, docs/evidence included, through the script's own `main()` and `_run_one`, default `TMPDIR`: 179 reported caught, 0 survived or stale. Two were caught only because the mutated file did not parse. One is new here, "a layer's JSON keys are not checked": it removed the loop's only statement. It now leaves `pass`, and re-run alone it is caught by a failing test (1,933 passed before it). The other, "the use verdict mixes terms across alternatives" (`4f995317`, not this round's), replaces the first line of a three-line `return`; it is reported, not changed. The group's 11 test files pass unmutated: 2,205 passed, 1 skipped (no git checkout) |

### The review of `d1724006`: `OLLAMA_MODELS`, and what Go's decoder takes

An independent review of `d1724006` found one false clear (N1), one fall-through (N2) and a note (N3), with an oracle
rebuilt on Ollama's real `envconfig.Var`. Making the frozen test fail a clear of a model Ollama does not find (it
would pull bytes GREG never read) exposed one more fall-through, under the host `ollama.com`.

| Finding | `d1724006` | Now |
| --- | --- | --- |
| N1 (medium): Ollama reads `OLLAMA_MODELS` through `envconfig.Var`, `strings.Trim(strings.TrimSpace(v), "\"'")` (identical in `0d0720e` and `e9fde36d`); a Docker `--env-file` line keeps its quotes. `"<srv>"`, `'<srv>'`, `"<srv> "`, `" <srv>"` with Llama in `<srv>` and Apache in `~/.ollama/models` | CLEARED the home store's Apache manifest (`30e11c14fa`) while Ollama serves `1cf2835061` (Llama) | held (Llama), from the store Ollama serves: Go's `TrimSpace` set (`_GO_SPACE`), then every leading and trailing `"` and `'` (`_ollama_models_env`) |
| N2 (low): `OLLAMA_MODELS` names a store without the model | CLEARED from `~/.ollama/models` or `/usr/share/ollama`; Ollama answers "not found" and a run would pull | not in any store (`None`; the gate holds it, "in no Ollama store"). `envconfig.Models` has no fallback, so neither has GREG. Unset or empty once trimmed (`' "" '`), the home and system stores were still read (until the review of `49aaa812`: HOME's store alone) |
| N3 (note): a manifest with a UTF-8 BOM, or in UTF-16 or UTF-32 | CLEARED (`json.loads(bytes)` detects the encoding); Go: "invalid character" | held: manifests and config blobs are decoded as UTF-8 only (`_go_json`) |
| Found here: a name under the host `ollama.com`, any case | CLEARED from the local entry; `main` never finds a local model asked for under that host (it names them `registry.ollama.ai`) and answers "file does not exist", `v0.40.0` only for an exact spelling | held, with no bytes bound, whatever the store holds. Without a host, or as `registry.ollama.ai/...`, the same store clears |

**The oracle runs Ollama's own `envconfig`.** `build_oracle.sh` fetched `manifest/`, `types/model/` and
`internal/modelref/` and stubbed `envconfig` with a raw `os.Getenv`, so it could not see N1. It now also fetches
`envconfig/` at both commits and compiles it (its non-test file imports only the standard library). Nine stores were
added (85 in all): the four spellings of N1, a value padded and quoted twice that names an Apache store (it must
clear), one empty once trimmed (it must clear, from the home store), a model only in the home store (N2), and a BOM
and a UTF-16 manifest (N3). `scenarios.ENV` gives each one's `OLLAMA_MODELS` spelling, `freeze.py` runs both oracles
under it with `HOME=<dir>`, `answers.json` records it, and the test passes the same environment to GREG with no
`models_dir`. The test also fails a clear when any run answers "file does not exist", or no run serves the model; the
old rule skipped every error and asked for a served run only of the stores that must clear. 17 stores must clear.

Every run below is on `221e1ea7`, whose code and tests the head carries unchanged (the head adds this file and
`g-PR.md`'s text only), unless it names another revision; "on `d1724006`'s" means a lean tree of `221e1ea7`
(`git archive`) with `greg/licensing.py` replaced by `d1724006`'s.

| Run | Result |
| --- | --- |
| `build_oracle.sh` from a fresh fetch of `0d0720e` and `e9fde36d` (Go 1.24.7, linux/amd64) | both oracles built; oracle sha256 `f8d180a8…` (v040) and `4c434f68…` (main), recorded in `answers.json` |
| `answers.json` refrozen | the 76 earlier stores answer byte for byte as before; frozen twice, byte-identical after the provenance block; frozen with the reviewer's `oracle-main-var.bin` in place of the main oracle, the same 85 answers |
| The reviewer's `envrepro.py`, rebuilt main oracle and the reviewer's `oracle-main-var.bin` | on `d1724006`: the four spellings CLEARED `30e11c14fa` while Ollama serves `1cf2835061` (also with the rebuilt v040 oracle); on `221e1ea7`: all four HELD `1cf2835061`, the manifest Ollama serves |
| `test_greg_model_license_gate.py` (38 tests: the 34 and 4 new) on `d1724006`'s | 4 failed: the four new tests (N1, N2, N3, the `ollama.com` host). Two existing tests now ask for `registry.ollama.ai/...` where they asked for `ollama.com/...`, which they cleared and Ollama `main` does not find |
| The same on `221e1ea7` | 38 passed |
| `test_greg_ollama_oracle.py` (86 tests) on `d1724006`'s | 9 failed: the four N1 spellings, the doubly quoted store that must clear, the home-only store, the BOM and UTF-16 manifests, and `r4b_explicit_ollama_com` |
| The same on `221e1ea7` | 86 passed |
| `test_greg_model_license.py` on `d1724006`'s and on `221e1ea7` | 45 passed each |
| The reviewer's `h3.py` and `diff_harness.py` (stub oracles, explicit store), default and legacy layouts | `h3.py` 94 of 94 ok each, 0 false clears; against the reviewer's run its BOM and UTF-16 stores moved from CLEARED to HELD and `r4b_explicit_ollama_com` from CLEARED to HELD. `diff_harness.py` 54 of 54 ok each, 0 false clears, `r4b_explicit_ollama_com` the only verdict changed |
| The licensing suites | 45, 1866, 40, 30 (after a throwaway `git init`; 29 + 1 skipped without), 1 (+1 xfailed), 39 and 4 passed |
| `git merge-tree` with #245 `0ecd091f` | clean, tree `ff98012f`. On it: `test_greg_model_license_route.py` 5, `test_greg_ollama.py` 8, the gate file 38, the oracle test 86, `test_greg_model_license.py` 45 passed |
| Mutants | the whole metabolism group on `221e1ea7`, 187 mutants (the 179 and 8 for the new guards), each in its own copy of a lean tree (docs/evidence left out of the copies) through the script's own `main()` and `_run_one`, 4 workers, default `TMPDIR`: 187 reported caught, 0 survived or stale. 186 are caught by a failing test; the existing "the use verdict mixes terms across alternatives" (`4f995317`) is still caught only by a collection error, as reported before. The 8 new ones are each caught by a failing test. (This said "each fail 1 test"; that was the first failure, which is all the script reports since it runs pytest with `-x`. Run without `-x`, they fail 3, 3, 3, 3, 3, 3, 2 and 1 tests: see [the review of `49aaa812`](#the-review-of-49aaa812-homes-store-alone-and-the-types-go-decodes).) The group's 11 test files pass unmutated: 2218 passed, 1 skipped (no git checkout) |

### The review of `49aaa812`: HOME's store alone, and the types Go decodes

An independent review of `49aaa812` ran both real-`envconfig` oracles beside GREG with the same environment and found
two classes of false clear (F1, F2) and a wrong count in this file (F3).

| Finding | `49aaa812` | Now |
| --- | --- | --- |
| F1 (high): `OLLAMA_MODELS` unset, `HOME`'s store empty or without `.ollama`, an Apache copy in `/usr/share/ollama/.ollama/models` (`usrshare.py`, under a private tmpfs on `/usr/share`) | CLEARED the system store's copy; both oracles answer "file does not exist", so a run would pull | not in any store (`None`; the gate holds it). `envconfig.Models` returns `$HOME/.ollama/models` and nothing else (identical at `0d0720e` and `e9fde36d`), so neither does `_ollama_stores`. The system store is read only as an explicit `models_dir` |
| F1: `HOME` unset or empty, `OLLAMA_MODELS` unset | CLEARED the system store's copy (Python's `Path.home()` reads the password database, or `/` for an empty `HOME`); both oracles panic, `$HOME is not defined` | held (`FOUNDER_REVIEW`, no bytes bound), the reason naming `models_dir`. `HOME` is read raw, as `os.UserHomeDir` reads it |
| F2 (high): NaN, Infinity or -Infinity anywhere in a manifest, list, layer, config or config blob (`nan.py`) | CLEARED (`json.loads` accepts them); Go: "invalid character" | held (`_go_json` refuses the constants) |
| F2: a value Go cannot store in its field's type: a layer's `int64` size of `1e999`, `1e2`, `1.5`, `1.0`, `2**63`, `-2**63 - 1`, `"1"`, `true` or `[1]`; `schemaVersion` `2.0` (`types.py`, `nan.py`) | CLEARED; Go: "cannot unmarshal ... into Go struct field" | held (`_go_value`, over every field of `_GO_MANIFEST_FIELDS`, `_GO_LAYER_FIELDS`, `_GO_CONFIG_FIELDS` and `_GO_DRAFT_FIELDS`: string, int64, struct, slice, `map[string]any` with float64 numbers). The struct types were read at both commits: `manifest/manifest.go` (`Manifest.UnmarshalJSON`), `manifest/layer.go`, `types/model/config.go` (`ConfigV2`, `Draft`; `voices` in `main` only), `types/model/generation.go` (`GenerationDefaults map[string]any`) |
| F2 controls: size `null`, `-1`, `2**63 - 1`, `-2**63`; a lone `\ud800` escape; `1e999` or `1.5` under a key Ollama does not read | cleared | still cleared, as Go decodes them |
| F3: "The 8 new ones each fail 1 test" | the mutant script runs pytest with `-x`, so it reports only the first failure | corrected below with each mutant's count from a run without `-x` |

**F1 trades false holds for no false clears.** A GREG run as a user beside the Linux systemd service (whose `HOME` is
`/usr/share/ollama`) now holds a model only the service's store holds. That is what the user's own Ollama would do:
it would not find the model and would pull it. A caller that gates the service's selection passes
`models_dir="/usr/share/ollama/.ollama/models"`. In this repository nothing else resolves an Ollama store:
`_ollama_stores` has one caller, `ollama_model`; `ollama_model` is called by `admit_model_selection` and the tests;
`admit_model_selection` has no caller outside the tests. `greg/models.py` reads no store. So no caller relied on the
fallback. The mutant script's "a set OLLAMA_MODELS falls back to the home and system stores" still names the
system store, as a mutant.

**The oracle fixture.** 27 stores were added (112 in all; 25 must clear). Seven are F1's: `OLLAMA_MODELS` unset with
`HOME`'s store empty, Apache or Llama (beside an Apache `<dir>/models` that must not be read); `HOME` unset, empty,
or unset under an `OLLAMA_MODELS` of one space; and `HOME` unset under a set `OLLAMA_MODELS`, which must clear. The
system store cannot be written by a fixture, so F1's exact case is the unit test's (`os.scandir` traced: nothing
outside `HOME`'s store is listed) and `usrshare.py`'s. Twenty are F2's manifest cases and controls; the config-blob
types are not in the oracle (it does not decode the config blob) and are unit tests. `scenarios.ENV` takes `None`
for `OLLAMA_MODELS` unset, and the new `scenarios.HOME` gives a `HOME` other than `<dir>` (`None` unset, `""`
empty); `freeze.py` runs both oracles under them, `answers.json` records them, and the test sets the same
environment for GREG. An oracle that panics is recorded by its `panic:` line, since the rest of its stack trace
changes from run to run.

Every run below is on `3ef3495c`, whose code and tests the head carries unchanged (the head adds this text and
`g-PR.md`'s), unless it names another revision; "on `49aaa812`'s" means a lean tree of `3ef3495c` (`git archive`)
with `greg/licensing.py` replaced by `49aaa812`'s.

| Run | Result |
| --- | --- |
| `answers.json` refrozen with the real-`envconfig` oracles whose sha256 the provenance block records (`f8d180a8…` v040, `4c434f68…` main; the reviewer's `rv4/bins`) | the provenance block and the 85 earlier stores byte for byte as before; frozen twice, byte-identical |
| `test_greg_model_license_gate.py` (42: the 38 and 4 new) on `49aaa812`'s / now | 4 failed, 38 passed (the four new tests) / 42 passed |
| `test_greg_ollama_oracle.py` (113) on `49aaa812`'s / now | 14 failed, 99 passed (the 14 F2 stores Go rejects; the F1 stores pass on `49aaa812`'s because this host has no `/usr/share/ollama`) / 113 passed |
| `test_greg_model_license.py` | 45 passed on both |
| The reviewer's `usrshare.py` (`unshare -m`, tmpfs on `/usr/share`) on `49aaa812`'s / now | 4 FALSE CLEARS (HOME's store empty; HOME without `.ollama`; HOME unset; HOME empty), 2 controls right / 0: the first two not found, `HOME` unset and empty HELD, the Llama control HELD, `HOME=/usr/share/ollama` CLEARED as both oracles serve |
| The reviewer's `nan.py` and `types.py` on `49aaa812` / now | 10 false clears of 13 / 0: the 10 HELD, `size 1`, `null`, `-1` and the lone surrogate CLEARED as both oracles serve |
| The reviewer's `envattack.py` | 47 rows, 0 false clears; `HOME` empty and unset HELD (both oracles panic) |
| The reviewer's `h3.py` and `diff_harness.py`, default and legacy layouts | 94 of 94 and 54 of 54 ok each, 0 false clears |
| The licensing suites | 45, 1866, 40, 30 (after a throwaway `git init`; 29 + 1 skipped without), 1 (+1 xfailed), 39 and 4 passed |
| `git merge-tree` with #245 `0ecd091f` | clean, tree `72eb1605`. On it: `test_greg_model_license_route.py` 5, `test_greg_ollama.py` 8, the gate file 42, the oracle test 113, `test_greg_model_license.py` 45 passed |
| Mutants, metabolism group (187 before, 20 added) | the whole group on `3ef3495c`, 207 mutants, each in its own full copy of a lean tree (`git archive`, docs/, tests/evidence/ and cortex/evaluation/ kept), through the script's own `main()` and `_run_one`, 4 workers, default `TMPDIR`: 207 caught, 0 survived or stale; 206 by a failing test, and "the use verdict mixes terms across alternatives" (`4f995317`, not this unit's) still only by a collection error. A first run on `0ac23c58` had 3 survivors: "a manifest-list entry's", "a layer's" and "the config descriptor's JSON keys are not checked". The new recursive check over the whole manifest had made those three `_go_fields` calls redundant; `3ef3495c` removes the calls, and the three mutants keep their names and remove that work from the recursive path instead (without `-x` they fail 4, 15 and 1 tests). The group's 11 test files pass unmutated: 2,249 passed, 1 skipped (no git checkout) |
| F3, the 8 mutants of `d1724006`'s review, on `221e1ea7`, run without `-x` over the group's 11 files | "OLLAMA_MODELS is read raw", "keeps its spaces", "keeps its quotes", "is trimmed of quotes before spaces": 3 failed each (the N1 gate test and the oracle's `env_models_empty_after_trim` and `env_models_quoted_apache`); "a set OLLAMA_MODELS falls back": 3 (the N1 and N2 gate tests, oracle `env_models_home_only`); "a manifest with a BOM or in UTF-16 is decoded": 3 (the N3 gate test, oracle `manifest_utf16` and `manifest_utf8_bom`); "a name under the host ollama.com": 2; "under the host OLLAMA.COM": 1. The same counts on `3ef3495c` |
| The 20 new mutants, run without `-x` | failing tests each: the system store read after HOME's 1, HOME through `Path.home()` 1, an unset HOME read as a relative store 1, the store's hold raising past `ollama_model` 4, NaN and Infinity read 2, no field type-checked 18, a string field taking anything 1, an int field taking any number 10, a bool 2, `2**63` 2, refusing `-2**63` 2, a struct field taking a non-object 1, its own fields unchecked 2, a slice taking a non-array 1, a struct slice item of any value 1, struct slice items unchecked 17, string slice items unchecked 1, a map taking a non-object 1, a map's numbers beyond float64 1, a map's nested values unchecked 1. Re-measured on `6f9b0286` over the group's 11 files: three counts first written from `0ac23c58` (12, 1, 1) are corrected to 18, 2 and 17 |

## Limits

- **Not a legal review.** A text is recognised, not interpreted. A model whose text is a well-known permissive license
  other than Apache-2.0 or MIT (BSD, CC-BY-4.0) is held. Recognising more texts is one entry each, measured the same
  way.
- **Not read:**
  - the weights' own embedded metadata (GGUF `general.license`, `general.base_model.*`);
  - the base model a fine-tune, adapter, merge or quantization was made from;
  - a Hugging Face model card. GREG pulls nothing from Hugging Face today.

  A derivative that declares Apache-2.0 over Llama weights is therefore read as Apache-2.0.
- **Real Llama, Gemma and Qwen texts were not fetched.** The network policy refuses `huggingface.co` and
  `registry.ollama.ai`. Their title lines stand in for them in the tests, and the family names are matched anywhere in
  a text.
- **No real Ollama store was read.** None exists on this body, and Ollama could not be installed. The legacy layout
  (`manifests/<host>/<namespace>/<model>/<tag>`, `blobs/sha256-<hex>`, license media type) follows Ollama's
  `server/modelpath.go` and manifest format as recorded in its source. The 0.40 layout follows Ollama's source at
  `v0.40.0` and `main` `4d22e65` ([below](#ollama-040s-store-and-the-selection-gate)), and the frozen oracle runs
  Ollama's own code at `v0.40.0` and `main` `e9fde36d` over written stores. Neither is tested against a live store.
- **Terms incorporated by reference.** A URL in a copyright notice is set aside as the holder's address, so a
  notice that points to further terms at a URL is still cleared. GREG does not fetch the URL.
- **Not wired into `OllamaRoute`.** `greg/models.py` is pinned by seed `freeze-v12` and owned by the models lane.
  `admit_model_selection` is the hook a caller outside it can use where the selection becomes a route
  (`greg/body.py`, `greg/planner.py`), with no re-seal; nothing calls it yet.
- **What the selection gate does not establish:**
  - **The store read is the one this process's environment names.** `OLLAMA_MODELS`, trimmed as Ollama trims it,
    is the only store read while it is set; otherwise `$HOME/.ollama/models` alone, as `envconfig.Models` reads it.
    With both unset or empty the model is held, since Ollama panics there. The running Ollama server may use
    another store, for example the Linux systemd service, whose `HOME` is `/usr/share/ollama`: a GREG run as a user
    beside that service now holds a model the service has and the user's store lacks ("in no Ollama store"). That
    is a false hold, traded for no false clear: on `49aaa812` GREG also read the service's store, and cleared a
    model the user's own Ollama would pull. A caller that runs the gate for the service passes its store as
    `models_dir`. GREG reads the environment as Python decodes it (UTF-8 here); a value with bytes that are not UTF-8
    is not trimmed of a non-ASCII space Go would not see either. `license_evidence` carries the digest
    `/api/tags` reports: `manifest_sha256` for a plain manifest, and `api_tags_digest` for a list, under each runner
    order. A verifier can compare it with the digest `OllamaRoute` reads. Enforcing their equality at the call
    belongs to `greg/cognition/cortex.py` or `greg/models.py`.
  - **Time of check against time of use.** The gate reads the store when it is called, not at the inference call. A
    re-pull between the two runs once.
  - **A loaded runner.** A model already loaded is served from memory. `main` reuses a loaded runner only while the
    stored v2 link still points to its digest; GREG does not read what is loaded.
  - **Cloud spellings in `OllamaRoute`.** `greg/models.py` refuses only `:cloud` and `-cloud`; `-CLOUD`, `:CLOUD`
    and `:LOCAL` reach Ollama there. `admit_model_selection` holds them, so a caller that runs it is covered.
  - **A hold has no bytes bound to it** when the name or the store is held before a manifest is read
    (`manifest_sha256` is `None`). A future founder clearance must refuse such a hold.
  - **The Ollama version is not read.** GREG reads a manifest only where `v0.40.0` and `main` agree, and holds the
    model where they differ. Other versions are not modelled.
  - **A request that names a runner** (`runner` in Ollama's API) can select a child that the default order does not.
    Every local child is assessed, so no child that could run escapes the gate, but `api_tags_digest` covers only
    the default orders.
  - **Held, not interpreted:** a model held because GREG cannot be sure what Ollama serves carries the verdict
    `FOUNDER_REVIEW`, as an unreadable manifest always has. It does not carry the gate's `UNASSESSED`, which means
    no assessment at all.

## Founder decision

Whether a model held only because its text is unrecognised (BSD, CC-BY-4.0) should wait for the founder, as now, or
whether those texts should be added to the recognised set. Recommended: add each one only with a measured
standard text, as Apache-2.0 and MIT were added. Founder decisions D-LIC-1 and D-LIC-2 are unchanged.
