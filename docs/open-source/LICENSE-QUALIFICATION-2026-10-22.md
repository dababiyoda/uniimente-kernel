# License qualification on Genesis's package route — 2026-10-22

Open-Source Metabolism workstream, increment 1. Session `session_013k41DnwrjzpXL33r3j9BgB`. Base is #196 head `a3fa3795`. Claim: [#96 comment](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6332941620). Authority delta: none.

## Founder intent and effect

- **Directive of 2026-10-22, §5.3:** "Verify the actual license, obligations and commercial suitability". §5.2: "Pay particular attention to copyleft, network-use, branding, redistribution".
- **Directive §6:** the acquisition states "A package legally and technically qualified" and "A capability attached under valid authority" are not interchangeable.
- **Also advanced:** `INTENT-20260930-open-source-first` and `INTENT-20261001-open-source-mechanism-harvest` (#144).
- **Effect:** GREG can depend on mature open-source code without silently acquiring a legal liability. A package whose license GREG cannot clear for its use never attaches without Alfonso's own command, and Alfonso is told why.
- **Not literal:** this is not a legal review and claims none.

## What was found [obs on `a3fa3795`]

- **Supply:** Capability Genesis already acquires open source (`greg/mechanisms.py`, DEPEND mode). It pins version, upstream and file digest, runs the package in a no-network interpreter, and accepts only answers GREG certifies.
- **The defect:** the license is read into the Mechanism Card as a display string, and nothing reads it again. `Genesis._attach` attaches under a founder-signed read-only `auto_attach` whatever that string says, including `UNDECLARED`, `BUSL-1.1`, `AGPL-3.0-only` and `LicenseRef-Proprietary`. The fail-before tests below reproduce this.
- **The string is often not a license expression at all:**
  - protobuf reads `3-Clause BSD License (license text; no SPDX expression)`;
  - scipy and ortools carry only trove classifiers.

## Make / adopt decision

| Route | Considered | Decision |
|---|---|---|
| Existing GREG capability | `mechanisms.license_of` (display string only) | kept; it does not classify |
| Installed mature OSS | **`packaging.licenses`** (PyPA, Apache-2.0 OR BSD-2-Clause; already a dependency of pip and pytest). It canonicalises and validates SPDX expressions against the bundled SPDX list. | **adopted** for parsing |
| Stronger OSS competitor | `license-expression` with the ScanCode LicenseDB (nexB, Apache-2.0). It has categories for more than 2,000 licenses. | not adopted now: a new dependency and a large data set for a gate that fails closed; recorded as the upgrade path if founder-review volume shows the small table is too narrow |
| Other | SPDX license-list-data JSON (OSI/FSF flags), `pip-licenses`, `reuse` | OSI approval is not GREG's question; "may GREG use this as it does?" is. `pip-licenses` and `reuse` are reporters, not gates |
| Residual built by GREG | a fail-closed table mapping identifiers to six obligation classes *for GREG's use*: unmodified, separate no-network process, not redistributed. Also SPDX OR/AND/WITH evaluation and trove/legacy-text fallbacks. | `greg/licensing.py` |

## Mechanism

- **Assessment:** `licensing.assess(dist, deps)` reads, in order, `License-Expression` (PEP 639), then trove classifiers, then the legacy `License` field (exact short names, or an SPDX expression stored there).
  - OR takes the best term, AND the worst, and WITH a linking exception downgrades strong copyleft.
  - Since the review of `a1d2abf` (SPDX-3, SPDX-4, SPDX-5, SPDX-7): classifiers and the License field are read
    beside an expression; restrictive spellings, LicenseRef fields and restrictive families at every version
    count; inclusive "commercial and non-commercial" wording does not. OR elects one whole alternative, so its
    obligations are never mixed with another's. See `docs/evidence/oss-metabolism-201-fixes/LICENSE_EXPRESSIONS.md`.
  - Every `common_mode` dependency that runs in the same interpreter is assessed with the package.
- **Classes:** permissive → CLEARED. Weak or strong copyleft → CLEARED_WITH_OBLIGATIONS; the obligations are stated on the card. Network copyleft, not open source, or unclassified → FOUNDER_REVIEW.
- **Card:** the Mechanism Card carries `license_assessment`, so the founder's CAPABILITY_ATTACH ask carries it too.
- **Attach gate:** `Genesis._attach` adds one condition. A `installed:python:` manifest auto-attaches only when its assessment is cleared. Otherwise the deficit waits with `why = "its license needs your decision before any attach: <reason>"`.
  - The founder's own CAPABILITY_ATTACH still works; the founder's decision is never removed.
  - A card without an assessment is never cleared.

## Capability dividend and evidence

**What GREG can now do that it could not before:** tell a legally cleared open-source mechanism from one that is technically qualified but legally uncleared, and refuse to attach the second on its own. This is the "legally qualified" state of directive §6, executed on the canonical mission path.

`tests/unit/test_greg_license_qualification.py` (39 tests after the review):

- **19 parse and classify cases.** They include AND/OR precedence, a WITH exception, an unparseable expression, an undeclared license, conflicting classifiers, a legacy text field and a copyright-only text.
- **The engines Genesis already uses stay cleared** from their own metadata: networkx, scipy, ortools, and numpy/protobuf as common-mode dependencies.
- **End to end, on a real body and signed mission, with real networkx relicensed in metadata only** (same files and digest):
  - BUSL-1.1, AGPL-3.0-only and LicenseRef-Proprietary are qualified technically but not attached, and the reason is journaled;
  - the founder's attach then closes the mission.
- **Baseline:** the real license is auto-attached and the mission closes.
- **Ablation:** with the gate removed, the BUSL package attaches itself and the mission closes. That is the failure the gate exists to prevent.
- **Fail-before:** 5 of these tests fail on `a3fa3795`'s `genesis.py`/`mechanisms.py` and pass with the change.
- **Non-regression:** the Genesis-related suites (packaging, open-source, linear, cognition, recombine, recovery, negative-control, budgeted selection and the new tests) all pass: 289 passed after the review fixes.
- **Live Mind routing unchanged:** `scripts/mind_status.py` output is byte-identical before and after (4,681 lines). No admitted verdict's code binding moved.
- **Owned-source inventory:** `foundry/owned-source.json` was refreshed with `scripts/refresh_owned_source.py`. The only addition is `greg/licensing.py`, a runtime source with no secrets, readable like `greg/mechanisms.py`.

**Falsifier:** a package that is not cleared reaches `ATTACHED` under `AUTO_ATTACH`. Or a cleared engine (networkx, scipy, ortools) stops auto-attaching.

## Five lenses (single-agent self-review; the independent review is recorded separately)

- **Founder-Intent Steward:** it advances §5.3/§6 without shrinking the destination. No package is banned. Founder attention is spent only where the law is unclear.
- **Systems Architect:** one new module; one condition at the existing attach point. There is no second registry or authority.
- **Adversarial Reviewer:** a package can lie in its metadata. That is a stated limit, not detected. Classes assume GREG's current use; redistributing GREG (for example, packaging a body image with GPL code) changes the obligation, and the card says so.
- **Operator:** no new dependency. The table is about 90 identifiers and fails closed; an unknown license costs one founder decision.
- **Evidence and Welfare Guardian:** upstream authors' terms are respected by construction. The founder sees obligations before any use.

**Pass 1.**
- *Advantage:* the same gate covers every future package GREG acquires. This compounds with the catalogue: each new OSS capability gets legal qualification for free.
- *Reversal:* if AGPL or source-available tools become central, review volume rises. The bound is a founder-amendable `CLEARED_UP_TO` and the ScanCode upgrade path.
- *Disadvantage:* trove classifiers lack versions. It is bounded by mapping a family only when every version shares a class.

**Pass 2.**
- *Attack:* a future attach path that bypasses `_attach`. Mitigation: the independent review checks every `set_state(..., "ATTACHED")` in `genesis.py`.
- *Attack:* system binaries (`sha256sum`, `wc`) and builder-generated code are not license-assessed. That is accepted for now: coreutils are on every body, and builder code is GREG's. It is recorded as a residual below.

**Decision:** EXPERIMENT in draft. Rollback is to revert the `_attach` condition; the card field is inert without it.

## Independent review (separate agent, 2026-10-22, on `73b19fe`)

A separate review agent, which did not write the code, read the diff adversarially. Each finding below now has a regression test that would have passed, wrongly, before its fix.

1. **HIGH. `_attach_dependency` bypassed the gate.** An engine under a construction was re-attached under mission scope after recovery, with no license check. It is now gated like `_attach`.
2. **MEDIUM. Permissive packages verified before this change were blocked for good.** Their cards had no assessment. A card without one is now re-assessed from the installed distribution, and only at the qualified version.
3. **MEDIUM. A multi-line legacy `License` field was read from its first line only.** A multi-line field is now unclassified, and a restrictive phrase in a short field marks it not open source.
4. **MEDIUM. A stricter `License` field beside an expression or classifier was ignored.** It now counts when it classifies stricter or names a restrictive phrase. An unrecognised short name beside a classifier is informational.
5. **Classes. OSL-3.0 (external deployment) and EUPL-1.1/1.2 (online access counts as distribution) are now network copyleft.**
6. **LOW, accepted as a limit.** Only declared `common_mode` dependencies are assessed, not every transitive import.

**A negative found while fixing 3.** A phrase scan over full license texts is unreliable: scipy's field bundles the GPL of its compiled runtime, which says "noncommercially". The scan is limited to short declarations, so a rider inside a full text is not detected; the card's limits say so.

**Sweep of every distribution installed in this environment (123):** 107 CLEARED, 2 CLEARED_WITH_OBLIGATIONS, 14 FOUNDER_REVIEW before the classifier fixes and 2 after (pypdfium2 "BSD-3-Clause, Apache-2.0, dependency licenses"; supervisor "BSD-derived (URL)"). Both are ambiguous declarations; sending them to the founder is fail-closed by design.

## Residual deficits (open, not claimed)

1. Installed system binaries and builder output carry `license not inspected by GREG`.
2. Model-weight licenses (Ollama/Qwen, `docs/OPEN_SOURCE_STACK.md`) are outside this gate. The same assessor can read a model card's SPDX field once a model is acquired through Genesis.
3. A founder-amendable license policy, as a signed setting, instead of the module constant.
4. The ScanCode LicenseDB, if review volume warrants it.
