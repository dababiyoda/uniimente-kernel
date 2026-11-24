# Provider Change Review — 2026-09-29

Status: `NEEDS_FOUNDER_DECISION`  
Scope: official changes observed from 2026-09-23 through 2026-09-29, plus shutdowns effective in that window  
Execution boundary: documentation and review evidence only; no provider, runtime, route, credential, account, billing, production, or authority change

## Decision summary

Update draft PR #105, but do not migrate any provider integration. Three newly material invariants were not explicit in the existing draft:

1. a provider can accept a request after silently dropping model-, conversation-, prefix-, or account-bound reasoning artifacts, so HTTP success is not replay equivalence;
2. a no-output refusal or provider fallback can create separately billed attempts that top-level usage does not fully represent; and
3. a provider transcript can lose messages during an incident, so transcript absence is ambiguous and cannot prove that work or an effect did not occur.

These are directly relevant because current Kernel `main` now contains a merged, Claude-assisted commit with a Claude session reference. The evidence proves collaboration use, not an Anthropic API adapter or production route.

## Official-source findings

### 1. Anthropic — Claude Sonnet 5.5, effective 2026-09-28

Official sources:

- https://platform.claude.com/docs/en/release-notes/overview
- https://platform.claude.com/docs/en/models/sonnet-5-5/overview
- https://platform.claude.com/docs/en/models/sonnet-5-5/whats-new-sonnet-5-5
- https://platform.claude.com/docs/en/build-with-claude/preserved-thinking

What changed:

- `claude-sonnet-5-5` launched with a 1M-token context window, 128K maximum output, and standard pricing of $2/MTok input and $10/MTok output; cache reads are $0.20/MTok, 5-minute cache writes $2.50/MTok, and 1-hour writes $4/MTok.
- Migration from Sonnet 5 has five documented breaking changes: `thinking: disabled` is replaced by `between_tools` at supported effort levels; forced `tool_choice` values `any` and `tool` return 400; thinking is model/conversation bound; older computer-use declarations fail on Claude API and Google Cloud; and some advisor pairings fail.
- Text between tool calls can move into `thinking` blocks, so a UI can become silently quiet unless it handles the new display contract.
- Sonnet 5.5 thinking blocks also stay with the producing account or a linked account. Another account can send the block and receive HTTP success after the API drops it. With the beta binding header the drop appears as `organization_binding_mismatch`; without the header it is silent.

Impact:

- **Canonical authority / one source of truth:** thinking blocks remain provider artifacts, never authority or canonical history. Account linkage cannot become a UNIIMENTE identity grant.
- **Provider contract:** model, account/organization, conversation prefix, effective tools, thinking mode, effort, platform, beta headers, and response display shape must be fixture-bound.
- **Replay / retry / idempotency:** a successful request after a dropped block is a semantic migration, not equivalent replay. Preserve `input_transformations`; stop or route through an explicitly tested migration path. Reuse the canonical attempt and idempotency identity.
- **Evaluator independence:** Sonnet 5.5 cannot certify that its own migrated output is equivalent to the prior reasoning path.
- **Credentials / residency:** account linkage is compatibility metadata, not permission. Do not inspect or record credentials; a live deployment still needs separately authorized residency and account-topology review.
- **Cost:** nominal Sonnet prices are unchanged from Sonnet 5, but recalibrated effort and always-present thinking/progress behavior require a new cost/quality sweep before adoption.
- **No duplicate runtime:** do not let a Claude session, advisor graph, or provider conversation become the institutional task or memory owner.

Review-ready next step: no route change. If adoption is proposed, add deterministic fixtures for all five 400 cases, progress-output shape, model/prefix/account-binding drops, save/restart/resume, and cross-model handoff; evaluate with a non-serving model or deterministic oracle.

### 2. Anthropic — refusal billing and fallback accounting, effective 2026-09-24

Official sources:

- https://platform.claude.com/docs/en/release-notes/overview
- https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback

What changed:

- Refusals before output are now billed for `bio`, `frontier_llm`, and `reasoning_extraction`; other pre-output categories remain unbilled, but all attempts count against rate limits.
- Fallback may run more than one model attempt. Each produced-output attempt and each billed pre-output refusal is charged separately. `usage.iterations` is the per-attempt record; top-level usage describes only the attempt that returned the message.
- Provider sticky routing is best-effort, organization-scoped, and retained for about an hour, so the requested model may or may not run on later turns.

Impact:

- **Canonical authority / one source of truth:** provider fallback routing is telemetry, not authorization or canonical routing policy.
- **Provider contract:** capture every iteration's model, stop reason/category, usage, fallback boundary, credit, serving model, and rate-limit outcome.
- **Replay / retry / idempotency:** HTTP 200 and empty content do not prove zero execution or zero cost. A provider-internal fallback is a group of subordinate attempts under one canonical identity; it cannot independently retry an external effect.
- **Evaluator independence:** the fallback model cannot be the only judge of whether the first refusal was valid or whether the replacement is equivalent.
- **Credentials / residency:** a fallback model or platform must already be approved for the same data class and geography; provider recommendation does not establish eligibility.
- **Cost:** budget for all `usage.iterations`, not only top-level usage. Preserve later credits as append-only adjustments.
- **No duplicate runtime:** sticky routing cannot become an independent scheduler or durable task owner.

Review-ready next step: add offline fixtures before any fallback implementation; no live call or billing-account inspection is authorized.

### 3. Anthropic — Compliance API activity shape, effective 2026-09-24

Official source: https://platform.claude.com/docs/en/release-notes/overview

What changed:

- Local session endpoints are out of beta for Claude for Microsoft 365 sessions.
- Activity Feed records now omit file names, project-document names, and artifact titles, including historical activities. Resolving a name or title from its ID requires a Compliance Access Key with `read:compliance_user_data`.

Impact:

- Existing activity records cannot be treated as self-contained evidence. IDs, timestamps, product surface, and canonical references must remain useful without privileged dereferencing.
- The missing metadata is not authorization to widen Compliance access. Any lookup remains a separate least-privilege, classification, retention, residency, consent, and audit decision.
- No direct exposure was found; no key or session was inspected.

Review-ready next step: preserve as a prospective contract fixture only if a Compliance integration is proposed.

### 4. Anthropic status — Claude API/Code/Cowork incident, 2026-09-29

Official source: https://status.claude.com/

The incident affected Claude API, Claude Code, Claude Cowork, sign-in, new chats, uploads, and other surfaces. Anthropic reported that some messages sent from 14:00 to 14:59 UTC may not have been saved, while service recovered after mitigation.

Impact:

- Provider recovery does not establish that every attempted message was saved or that work did not execute.
- A missing provider conversation entry is an ambiguous completion. Check canonical commit, event, attempt, idempotency, and effect receipts before retrying or recreating work.
- Repository commits and canonical events remain durable evidence; the provider transcript is subordinate evidence.

Review-ready next step: for any work performed in the affected window, reconcile against repository commits and canonical receipts; do not replay consequence-bearing work from transcript absence alone.

### 5. OpenAI — GPT-6 Sol/Luna image-encoder correction, effective 2026-09-25

Official source: https://developers.openai.com/api/docs/changelog

OpenAI corrected an image-encoding bug that degraded image understanding in `gpt-6-sol` and `gpt-6-luna`, including computer-use tasks, and recommends rerunning affected evaluations and workflows.

Impact:

- This is a behavior-baseline change, not a request-schema change. Old and new outputs under the same mutable model ID may differ.
- No default branch contains `gpt-6`, image-input, or relevant computer-use routing, so direct runtime exposure was not found.
- If a stored evaluation or collaboration artifact depended on affected visual behavior, rerun it with captured inputs, observed date, serving model, and independent acceptance criteria; do not overwrite prior evidence.

No repository rule was added for this item because PR #105 already requires mutable-model baselines, captured fixtures, and recovery canaries.

### 6. OpenAI retirements effective in the window

Official source: https://developers.openai.com/api/docs/deprecations

- The Videos API and Sora 2 model family shut down on 2026-09-24.
- `gpt-3.5-turbo-instruct`, `gpt-3.5-turbo-1106`, `babbage-002`, and `davinci-002` shut down on 2026-09-28.

Exact default-branch searches found none of these model or endpoint identifiers. DALEOBANKS uses `gpt-4o-mini` and optional `text-embedding-3-small`; therefore no direct migration is required.

### 7. OpenAI and Kimi status communications

Official sources:

- https://status.openai.com/history
- https://status.moonshot.cn/

OpenAI reported resolved GPT-6 Astra Pro errors on September 24 and Codex issues on September 25. Kimi reported a high file-service request-failure rate from 07:45 to 08:12 CST on September 29 and then resolved it.

These incidents reinforce existing receipt-gated recovery and canary rules. No affected runtime route was found, and no new protocol rule is warranted for them.

## Current default-branch exposure

| Repository | Commit inspected | Direct exposure |
|---|---|---|
| `dababiyoda/uniimente-kernel` | `25ab9b4b5ef940e33a908612f895c9133849fafc` | Latest commit records Claude Opus 5.5 as co-author and links a Claude session: direct collaboration provenance, but no Anthropic API/runtime adapter. No GPT-6/Sora/Kimi runtime token found. |
| `dababiyoda/DALEOBANKS` | `e2f1ebed37407b06ea70cbffb404fd39858e13b5` | `services/llm_adapter.py` uses `gpt-4o-mini`; `services/embeddings.py` optionally uses `text-embedding-3-small` and falls back per call to deterministic hashes. No affected OpenAI model, Anthropic, or Kimi route found. |
| `dababiyoda/WealthMachineIntelligence` | `ec82b8027d987c865dc123215afb53d20916908f` | No direct provider runtime surface found. `CLAUDE.md` is an agent entry point, not an API adapter. |
| `dababiyoda/PumpStation` | `db6758dfa8621a4f6fb0504c20343e60db5336c1` | No direct provider runtime surface found. `CLAUDE.md` is an agent entry point, not an API adapter. |

Search limitation: GitHub code search proves only the indexed current default branches and exact searched tokens. It does not inspect live environment variables, accounts, invoices, contracts, or private deployment configuration; none was authorized or accessed.

## Five-role review

- **Founder-Intent Steward:** retain broad multi-model collaboration, but provider artifacts never become authority or institutional memory.
- **Systems Architect:** map provider-specific drops and fallback iterations into generic canonical artifact-transformation and attempt events.
- **Adversarial Reviewer:** assume HTTP success, empty output, recovery, and visible sessions can all mislead; preserve dissent against weekly policy accumulation.
- **Operator and Maintainer:** require deterministic migration fixtures, serving-model and per-attempt usage receipts, recovery canaries, and receipt-gated retry.
- **Evidence and Welfare Guardian:** keep account binding opaque, avoid privileged Compliance lookups, independently evaluate migrations, and require residency review before live use.

## Exactly two strengthening passes

### Pass 1 — structural inversion

The strongest design is a narrow draft update: bind provider artifacts to opaque account/model/conversation compatibility metadata, classify drops as semantic migrations, and ledger every refusal/fallback iteration separately under one canonical attempt. This strengthens portability and makes duplicate work and hidden cost observable. The counterweight is that metadata capture can expose account topology, provider fields can infect the canonical schema, and the draft can accrete policy.

### Pass 2 — adversarial compounding

The final design stores no credential material, maps vendor fields into generic events while retaining raw payloads, prohibits transcript-loss auto-retry and standalone provider harnesses, and limits future repository edits to a new direct exposure, deadline, or uncovered authority/replay/cost/privacy/runtime invariant. Every Pass-1 downside is dispositioned in `deliberation-provider-change-2026-09-29.json`. No third strengthening pass was performed.

## Dissent

The Adversarial Reviewer objects to continued model-authored protocol accumulation while PR #105 remains undecided. This cycle crosses the stated materiality threshold because current `main` now proves direct Claude-assisted collaboration and official changes expose three previously unstated failure modes. The objection remains unresolved and founder-owned. The next immaterial cycle must be brief-only with no repository change.

## Verification, migration, rollback, and kill criteria

Verification completed for this change:

- official provider pages read and dated;
- all four current default branches inspected by commit;
- exact provider/model searches and affected adapter paths reviewed;
- deliberation validator passed with five distinct roles and exactly two passes.

No runtime migration is authorized. A future provider change must start with offline fixtures in the existing test substrate, then independent evaluation and a separately approved sandbox canary. It must not create a daemon, queue, provider session owner, or second scheduler.

Rollback: leave PR #105 unmerged or revert the 2026-09-29 documentation-only commits while preserving the dated evidence and dissent.

Kill immediately on any default-branch write, merge without founder approval, production/model/credential/account/billing/contract change, provider-owned canonical state, transcript-loss auto-retry, silent artifact-drop acceptance, collapsed fallback-attempt accounting, same-provider sole evaluation, ineligible residency, duplicate effect, or parallel runtime.

## Review-ready next steps

Completed now:

- updated the dedicated draft branch and PR #105 with this evidence;
- added only the three new protocol invariants;
- added a machine-readable deliberation that validates under the collaboration protocol.

Founder decision remains required to merge PR #105, switch models, authorize any live provider fixture/canary, inspect accounts or contracts, or change production routing.
