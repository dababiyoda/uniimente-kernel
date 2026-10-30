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

- **Where it reads.** It tries the store named by `OLLAMA_MODELS`, then `~/.ollama/models`, then
  `/usr/share/ollama/.ollama/models` (the Linux service user's home). In each it reads the manifest Ollama would
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
this is not where a current Ollama keeps a pulled model. The source read was a clone of `github.com/ollama/ollama` at
`main` `4d22e65` (2026-10-29) and the tags `v0.40.0` (`0d0720e`, 2026-10-06) and `v0.35.1` (`b0c1ca4`):

| What Ollama does | Where in its source | `v0.35.1` | `v0.40.0` and `main` |
| --- | --- | --- | --- |
| The named manifest is written as a blob of its own, `blobs/sha256-<hex>`, and named by a relative link at `manifests-v2/<host>/<namespace>/<model>/<tag>` (a copy on Windows); the legacy name is then removed | `manifest/manifest.go` `writeManifestData`, `linkManifest`; called from `PullModel` in `server/images.go` | no (`manifests/` only) | yes |
| The default registry is filed under `ollama.com` in `manifests-v2`; `registry.ollama.ai` and `ollama.com` are the same host | `manifest/paths.go` `canonicalV2Name`, `isDefaultPublicHost` | — | yes |
| A host's `:` is written `%3A` in `manifests-v2` | `manifest/paths.go` `encodeV2ManifestHost`: `strings.ReplaceAll(host, ":", "%3A")` | — | yes |
| A name resolves to the v2 name when it exists, else to the legacy tree under both spellings of the default registry | `manifest/paths.go` `resolveManifestPath`, `legacyNameCandidates` | — | yes |
| A v2 link is served only when it resolves to the blob of this store its file name names, and the bytes hash to that name | `manifest/manifest.go` `OpenVerifiedManifest` (`v0.40.0`), `openManifestFileLocked` (`main`) | — | yes |
| A name may be a manifest list, `application/vnd.ollama.manifest.list.v2+json`, one child reference per runner; a pull fetches only the child its runner selects, and a child whose blob is not local is never selected | `manifest/manifest.go` `MediaTypeManifestList`, `selectManifestWithPreferences`; `server/images.go` `pullSelectedManifest`; `server/create.go` | — | yes |
| `/api/tags` reports, as a model's digest, the sha256 of the named manifest's bytes (the list's own, for a list) | `server/model_list.go`; `manifest/manifest.go` `parseManifestData` | — | yes |

So every model pulled by Ollama 0.40 or later was unassessed (`None`). A gate that holds an unassessed model would
hold all of them, Apache-licensed ones included. Two smaller defects were found on the way: a manifest nested
100,000 deep made `ollama_model` raise `RecursionError`, and a registry host with a port (`localhost:5000/team/coder`)
was not a name the reader accepted at all.

### What changed (`greg/licensing.py` only)

- **The manifest Ollama serves is the one read.** `_ollama_manifest` resolves a name in Ollama's order: first the v2
  name, then the legacy tree. Each tree is tried under both spellings of the default registry and, as before, in
  lower case.
  - A v2 link is followed only to the blob of this store that its file name names, and only when the bytes hash to
    that name.
  - A v2 name that exists but fails that check holds the model. A legacy file beside it is not read in its place:
    Ollama would not serve the legacy file, and a downgrade anchor can leave one there.
  - A missing or dangling v2 name falls back to the legacy tree, as in Ollama.
- **A manifest list:** every child the store holds is read, and every license layer of every child applies (AND).
  - `manifest_sha256` is the list's own digest, the one `/api/tags` reports. `weights` covers every child read.
  - A child whose blob is not in the store is named in `uncertainty` and not read. Ollama never pulled it here and
    never selects it, so none of its weights can run.
  - A child whose blob is there but does not match its digest holds the model.
  - A child carrying layers or a config of its own holds the model. Ollama would run what that child says, not the
    blob it names, and no Ollama writer produces such a child.
  - A list none of whose children is in the store holds the model.
- **A registry host may carry a port**, as Ollama's names may (`types/model/name.go` `isValidPart`).
- **A manifest too deeply nested to parse holds the model.** It no longer raises.
- **`admit_model_selection(config, models_dir=None)`.** `config` is the selection `models.effective_route_config`
  returns.
  - When its order names `ollama` and the model is cleared, the selection is returned with `license_evidence`:
    `model`, `manifest_sha256`, `weights`, `verdict`, `assessment_digest`, `use_digest`. The last two come from
    `qualify_use` under GREG's use.
  - When the model is held, in no store this process can read, or unreadable, `ollama` leaves the order and
    `ollama_model` leaves the selection. The founder's other routes keep their order. `model_license_hold` records
    `model`, `verdict` (`UNASSESSED` when nothing was read), `reason`, `manifest_sha256` and `assessment_digest`.
  - Stale `license_evidence` from an earlier admission never rides on a hold.
  - Nothing a store holds makes it raise.
  - Any other selection, and `None`, comes back unchanged.
  - It reads the store and nothing else, writes nothing and grants nothing. Nothing calls it yet.

### Tests and measurements

| Run | Result |
| --- | --- |
| `tests/unit/test_greg_model_license_gate.py` (new, 14 tests) on `3358d660`'s `greg/licensing.py` | 14 failed. 10 fail on behaviour: v2 Llama and Apache models, a host with a port and the `ollama.com` legacy spelling are `None`; the out-of-store link test clears the legacy file beside it; the four list tests are `None`; the nested manifest raises `RecursionError`. 4 fail because `admit_model_selection` does not exist. |
| The same file on this change | 14 passed |
| `test_greg_model_license.py`, `test_greg_license_expressions.py`, `test_greg_license_qualification.py`, `test_greg_license_use_context.py`, `test_greg_binary_policy_options.py`, `test_greg_document_text.py`, `tests/integration/test_greg_section_ix_acquisition_scenarios.py` | before and after: 45, 1866, 40, 30, 1 (+1 xfailed), 39 and 4 passed. 2025 passed, 1 xfailed, unchanged |
| The open-source metabolism group's ten test files | 2109 passed |
| 20 mutants added to the open-source metabolism group, and the existing "license blob that does not match its digest" mutant re-pointed at the shared `_ollama_blob` check | the whole group on `031ba4e7`, 125 mutants: 125 caught, 0 survived or stale. The 21 new or re-pointed ones fail in `test_greg_model_license.py` or the new file. The disk had under 250 MB free, too little for the scratch copies `main()` makes, so the group ran in the worktree through the script's own `_run_one`, one mutant at a time, each file checked byte-identical after. A full disk stopped one pass at mutant 58, and the run resumed there. Two pre-existing mutants were caught earlier in that pass than on `40520bcb`. Re-run, both fail where they did before, in `test_greg_license_use_context.py`. Every other pre-existing mutant fails at the same test as on `40520bcb`, allowing for the 14 new tests and one test that is skipped there and passes here. |

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
  `v0.40.0` and `main` `4d22e65` ([below](#ollama-040s-store-and-the-selection-gate)). Neither is tested against a
  live store.
- **Terms incorporated by reference.** A URL in a copyright notice is set aside as the holder's address, so a
  notice that points to further terms at a URL is still cleared. GREG does not fetch the URL.
- **Not wired into `OllamaRoute`.** `greg/models.py` is pinned by seed `freeze-v12` and owned by the models lane.
  `admit_model_selection` is the hook a caller outside it can use where the selection becomes a route
  (`greg/body.py`, `greg/planner.py`), with no re-seal; nothing calls it yet.
- **What the selection gate does not establish:**
  - **The store read is the first that holds the name.** The running Ollama server may use another, for example
    when a service's `OLLAMA_MODELS` or `HOME` differs from the body's. `license_evidence.manifest_sha256` is in the
    form `/api/tags` reports, so a verifier can compare the two. Enforcing their equality at the call belongs to
    `greg/cognition/cortex.py` or `greg/models.py`.
  - **Time of check against time of use.** The gate reads the store when it is called, not at the inference call. A
    re-pull between the two runs once.
  - **A v2 file that is not a link** (Ollama's copy on Windows, or a hard link) is read as the manifest. Ollama's
    further check that it lies inside `manifests-v2` is not made.

## Founder decision

Whether a model held only because its text is unrecognised (BSD, CC-BY-4.0) should wait for the founder, as now, or
whether those texts should be added to the recognised set. Recommended: add each one only with a measured
standard text, as Apache-2.0 and MIT were added. Founder decisions D-LIC-1 and D-LIC-2 are unchanged.
