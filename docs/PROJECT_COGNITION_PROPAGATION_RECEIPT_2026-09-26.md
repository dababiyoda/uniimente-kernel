# Project Cognition Propagation Receipt — 2026-09-26

Canonical source:
- `docs/PROJECT_COGNITION_SOP.md`
- `docs/PROJECT_COGNITION_CONTINUITY.md`
- `docs/PROJECT_SOURCE_CENSUS_2026-09-26.md`
- `docs/intent/INTENT-2026-09-26-REAL-PRODUCT-METABOLISM.json`
- coordination issue #117

## Central Kernel surfaces

| Surface | Status |
|---|---|
| AGENTS.md | UPDATED |
| CLAUDE.md | UPDATED |
| .github/copilot-instructions.md | UPDATED |
| README.md | UPDATED |
| Founder Intent Ledger | UPDATED |
| Project Cognition SOP | INSTALLED |
| Cognition Continuity Addendum | INSTALLED |
| 93-source Project census | INSTALLED |
| PR template | INSTALLED |
| agent implementation issue template | INSTALLED |
| Recursive Collaboration Protocol routing | UPDATED |
| active product PR #114 | COMMENTED |
| predecessor/product substrate PR #113 | COMMENTED |
| Foundry/research PR #115 | COMMENTED |
| coordination issue #117 | CREATED |

## Cross-repository propagation

| Repository | Successful communication | Remaining limitation |
|---|---|---|
| DALEOBANKS | PR #79 steering comment | repo-local branch/file mutation was not accepted in the propagation attempt |
| WealthMachineIntelligence | PR #37 steering comment; cognition branch created | repo-local cognition file write was not accepted |
| RAILSCOUT | PR #5 steering comment | repo-local branch/file mutation was not accepted |
| PumpStation | issue #19; cognition branch + `UNIIMENTE_PROJECT_COGNITION.md` | not merged to default branch |
| RESEARCH-IN | issue #20; cognition branch created | repo-local cognition file write was not accepted |
| gods-eye-view-EGGREGORE-TOOL | role recorded centrally | Issues disabled; branch/file mutation was not accepted |
| build-your-own-x | role recorded centrally; cognition branch created | Issues disabled; repo-local cognition file write was not accepted |

## Epistemic coverage

The source census records **93 Project-backed files visible to the ChatGPT Project source surface at capture time**. It does not claim access to raw conversations or sources that the available Project surface did not expose.

Known Project conversation context is represented in the census/SOP where available, including exported `Branch · ...` source families and the current founder steering.

## Completion semantics

For this propagation operation, "complete" means:
1. every source accessible through the Project source inventory was enumerated;
2. central canonical cognition and continuous-ingestion procedures exist;
3. all writable/high-signal communication surfaces discovered were populated;
4. every cross-repo target was attempted;
5. successes and blocked/unavailable surfaces are recorded rather than hidden;
6. future agents have an SOP for ingesting sources that appear later;
7. no inaccessible source or blocked mutation is falsely represented as completed.

It does **not** mean every repository default branch contains the cognition files, nor that inaccessible raw ChatGPT history was somehow copied into GitHub.

## Follow-up rule

Any future agent with additional access should treat the blocked rows above as explicit synchronization debt. Resolve them, update this receipt, and rerun the anti-context-loss test.


## Verification addendum — second pass

Re-enumeration of the ChatGPT Project source surface returned **93 files, no pagination cursor**. A programmatic comparison of the 93 visible Project file IDs against `docs/PROJECT_SOURCE_CENSUS_2026-09-26.md` found:

- missing Project IDs from census: **0**
- phantom/extra Project IDs in census: **0**

The founder real-product source was reopened and confirmed to contain verbatim excerpts rather than only normalized paraphrase.

Clean retry of repo-local propagation succeeded beyond the earlier connector failures:

- DALEOBANKS: draft PR #80
- WealthMachineIntelligence: draft PR #38
- RAILSCOUT: draft PR #10
- RESEARCH-IN: draft PR #21
- gods-eye-view-EGGREGORE-TOOL: draft PR #1
- build-your-own-x: draft PR #2
- PumpStation: existing cognition branch/file plus issue #19

These draft PRs add only repository-local cognition handoff files; they do not change runtime behavior or authority and are intentionally **not merged** without founder authorization.

### Verbatim-source policy

Do not copy all 93 source bodies wholesale into GitHub merely to claim completeness. The census preserves the complete accessible inventory and IDs. Preserve verbatim founder language when it is necessary to control interpretation, resolve a conflict, or prevent aspiration shrinkage. Preserve other sources by provenance and targeted extraction unless their full body is required for implementation.

This avoids converting unrelated/private/noisy source material into permanent repository content while still making the entire accessible source universe discoverable.
