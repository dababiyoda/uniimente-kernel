# Provider change review — 2026-11-24

Window: 2026-11-17 17:21 UTC through 2026-11-24 17:21 UTC. Only material changes are recorded. Provider documentation establishes provider claims, not verified UNIIMENTE behavior.

## Decision

**NEEDS_FOUNDER_DECISION.** Add this evidence packet and its machine-readable deliberation to draft PR #105; leave `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` unchanged. Existing section 7 already requires exact provider contracts, leased provider state, bound reasoning artifacts, canonical receipts and idempotency, receipt-gated recovery, independent evaluation, bounded credentials/data scope, complete cost accounting, and one canonical runtime. No provider model, feature, account setting, credential, storage destination, route, or authority is adopted.

## Default-branch exposure

| Repository | Inspected default head | Direct exposure |
|---|---:|---|
| `dababiyoda/uniimente-kernel` | `d64a6c931bb05aba4e3454847b665e73384bbdfa` | Local/loopback model route; no GPT-6.2, background Responses completion, GPT-Live, Anthropic EFS, Opus 4.5 runtime, or Kimi provider route found. |
| `dababiyoda/DALEOBANKS` | `667439f49442bd898d3655666a389f53114f1412` | Local by default; optional OpenAI `gpt-4o-mini` Chat Completions and `text-embedding-3-small`. No reviewed new feature is directly used. |
| `dababiyoda/WealthMachineIntelligence` | `ec82b8027d987c865dc123215afb53d20916908f` | No direct OpenAI, Anthropic, or Kimi runtime route found. |
| `dababiyoda/PumpStation` | `db6758dfa8621a4f6fb0504c20343e60db5336c1` | No direct OpenAI, Anthropic, or Kimi runtime route found. |

Exact default-branch searches returned no `gpt-6.2`, `gpt-live`, `background_options`, `claude-opus-4-5`, EFS/external-storage integration, Anthropic API adapter, Moonshot endpoint, or Kimi runtime. Kimi collaboration provenance is historical evidence, not an API route. Repository inspection cannot establish non-repository account use.

## Material changes and bounded response

### OpenAI GPT-6.2 Astra and Sol — released 2026-11-17

OpenAI released `gpt-6.2-astra` and `gpt-6.2-sol` for Responses and Chat Completions. Tool calling requires Responses. GPT-6.2 can drop reasoning items after a mid-conversation prefix edit, model-family downgrade, or end-user/organization change. Migration also changes reasoning-effort, unsupported sampling/logprob parameters, prompt-cache TTL, ZDR multi-turn handling, and regional/tier contracts. Standard short-context prices are $8/$40 per MTok input/output for Astra and $2/$10 for Sol; requests over 272K input tokens raise the full-request input/cache and output rates. Official sources: https://developers.openai.com/api/docs/changelog, https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6.2-astra, https://developers.openai.com/api/docs/guides/keep-prefix-unchanged, and https://developers.openai.com/api/docs/pricing

- **Canonical authority / one source of truth:** model reasoning, encrypted reasoning items, conversation state, cache state, subagents, and provider response IDs remain subordinate artifacts. UNIIMENTE retains canonical task, actor, grant, event, receipt, evidence, and cursor state.
- **Provider contract:** bind provider, exact model/snapshot or observed alias, API, reasoning effort, complete checked-prefix hash, instructions placement, end-user and opaque organization binding, tool-manifest hash, cache TTL, tier, region, and canonical attempt. Chat Completions transport compatibility does not imply tool or reasoning compatibility.
- **Replay / retry / idempotency:** a successful request after reasoning was dropped is a semantic migration, not equivalent replay. Preserve the drop reason and issue a separately evaluated attempt under the original canonical idempotency identity. Prefix edits, model changes, user/organization changes, or omitted prior encrypted reasoning items must stop blind replay.
- **Evaluator independence:** neither GPT-6.2 nor its delegated subagents may solely approve its own promotion. Use frozen tasks, deterministic contract checks, and an evaluator outside the candidate route.
- **Credentials / residency:** ZDR, `store:false`, regional endpoints, Ultrafast, and eligible features have different contracts. Regional processing carries an uplift, and Ultrafast is US-only according to the migration guide. No account eligibility, key, region, or data-control setting was inspected.
- **Cost:** measure reasoning, long-context multipliers, cache reads/writes, tools, subagents, retries, regional uplift, and tier. Nominal model price is not total cost; cache writes and long context can dominate.
- **No duplicate runtime:** Responses sessions, multi-agent delegation, reasoning state, compaction, and tools remain leased adapter capabilities. They may not become a second scheduler, memory, evaluator, receipt ledger, or authority plane.
- **Next step:** no migration. Any proposal needs pinned request/response fixtures; prefix-edit, model-switch, organization/user-switch, tool, ZDR, cache and long-context tests; independent quality/cost evaluation against the local-first baseline; rollback to the existing route; and founder approval.

### OpenAI discounted background completion windows — released 2026-11-17

Responses background mode added `2h` and `8h` completion windows at 30% and 40% below Standard model-token rates for supported models. The provider targets completion within the selected window, may automatically retry eligible capacity errors, uses webhooks or polling for terminal state, and temporarily stores response data even when `store:false` or ZDR is used. New models will not support Flex while that beta winds down. Official sources: https://developers.openai.com/api/docs/changelog and https://developers.openai.com/api/docs/guides/background

- **Authority / one source of truth:** the provider queue, continuation ID, response status, webhook, and temporary store are leased execution state. They do not close canonical work or authorize tools, follow-ups, retries, or deadlines.
- **Provider contract / replay / idempotency:** bind the completion window, response ID, continuation ID, project, model, tool step, webhook event ID/signature, and canonical attempt. Provider-internal capacity retries are distinct subordinate attempts when observable. While queued or in progress, wait on the same response ID; do not resubmit.
- **Evaluator independence:** a completed status proves provider terminal state, not correctness. Retrieve the response, verify canonical postconditions independently, and preserve failed, incomplete, cancelled, and expired results.
- **Credentials / residency:** temporary encrypted storage is still retention and must be approved even under ZDR. Verify project/webhook credentials, signature handling, region, deletion, and access scope before use.
- **Cost:** discounts apply to eligible model-token rates, not necessarily tools, storage, egress, webhooks, polling, follow-up operations, or duplicate work. Record each step and provider retry; compare the discount with delay and operational cost.
- **No duplicate runtime:** the background queue and provider retries cannot become UNIIMENTE's scheduler or recovery plane. Canonical workflow state decides when follow-ups are authorized.
- **Next step:** no adoption. A future canary needs a consequence-inert task, duplicate-webhook and lost-webhook fixtures, cancel/race/timeout/auto-retry tests, temporary-storage approval, total-cost reconciliation, independent acceptance, and rollback to synchronous/local execution.

### OpenAI GPT-Live-1.1 — released 2026-11-19

OpenAI released `gpt-live-1.1`, a full-duplex multilingual voice model that can delegate reasoning and tool work to a Responses backend. WebRTC standby preserves the connection and conversation while pausing inference; client-managed backend work can continue after the voice session closes. Voice is billed at $0.05 per active minute and $0.02 per standby minute, while backend models and tools are billed separately. Official sources: https://developers.openai.com/api/docs/changelog, https://developers.openai.com/api/docs/models/gpt-live-1.1, https://developers.openai.com/api/docs/guides/live-delegation, and https://developers.openai.com/api/docs/pricing

- **Authority / one source of truth:** transcript, Live session, delegation ID, backend response ID, tool call, standby state, and stored/forked session remain subordinate projections. Spoken confirmation cannot create authority or prove an effect.
- **Provider contract / replay / idempotency:** map each delegation and backend operation to the canonical task/attempt and original idempotency identity. A voice reconnect, fork, resumed session, or repeated utterance must reconcile outstanding backend work before resubmission.
- **Evaluator independence:** require transcript/intent confirmation and independent postcondition verification for consequence-bearing results. The same Live/backend pair cannot solely certify that a booking, payment, message, or tool effect completed.
- **Credentials / residency:** keep project keys on a trusted server; treat microphone audio, transcripts, recordings, voice identity, sideband connections, and backend context as separate consent, retention, residency, and access-control surfaces.
- **Cost / runtime:** measure active, silence-before-idle, backend-wait, standby, initialization, backend-model, tool, storage, and reconnect costs. Voice and backend delegation must not form a parallel task runtime.
- **Next step:** no voice route exists. Any proposal needs explicit microphone/recording consent, local transcript and interruption fixtures, reconnect/delegation deduplication, trusted-server isolation, data-control review, cost ceiling, independent acceptance, and founder approval.

### Anthropic Enterprise Frontier Safeguards — released 2026-11-23

Anthropic launched Enterprise Frontier Safeguards (EFS) in beta for eligible organizations. EFS provides ZDR for Messages API requests while placing encrypted Sealed Safety Data—prompts, responses, and model reasoning—in a customer-owned cloud bucket. Anthropic Human Review is disabled and the customer reviews Safety Cases. EFS applies workspace-wide but excludes provider features that store data for their own use, including code-execution containers, Files API uploads, Batch results, and Managed Agents sessions. Anthropic also added `external_storage.failed` and `external_storage.recovered` organization webhooks. Daily checks can be delayed or inconclusive, can miss some IAM failures, and recovery of unwritten data is not guaranteed. EFS has no Anthropic fee, but cloud storage, key operations and network transfer are charged by the cloud provider. Official sources: https://platform.claude.com/docs/en/release-notes/overview, https://platform.claude.com/docs/en/manage-claude/enterprise-frontier-safeguards/overview, https://platform.claude.com/docs/en/manage-claude/enterprise-frontier-safeguards/external-storage-manage?method=api, and https://platform.claude.com/docs/en/manage-claude/organization-webhooks

- **Canonical authority / one source of truth:** a customer-owned bucket, workspace EFS flag, webhook, provider health result, Safety Case, or sealed blob is evidence and custody state—not canonical task truth, authorization, readable audit evidence, or proof of durable retention.
- **Provider contract:** bind workspace, platform, eligible model/API, external-storage ID, cloud account/region, bucket and key configuration version, status/check timestamp, excluded feature set, webhook schema/version, and canonical task/attempt. Workspace-wide activation is a material data contract.
- **Replay / retry / idempotency:** webhooks can be duplicated, missing, delayed, or arrive without the expected predecessor. Deduplicate by event identity, reconcile bucket objects and independent health checks, and never resend model work merely because sealed storage or its telemetry is missing. Requests may continue during a grace period while storage writes fail.
- **Evaluator independence:** Anthropic's daily check and the bucket status cannot solely prove storage completeness; the same unreadable sealed blob cannot independently prove task correctness. Use independent object-arrival, IAM, key, retention and deletion checks plus separate task evaluation.
- **Credentials / residency:** separate workspace/API, cloud IAM, KMS, webhook, transcript, and Safety Case credentials. Customer-owned storage does not cover excluded features and does not by itself prove inference residency. Require data classification, consent, legal terms, key-revocation effects, deletion, recovery and breach procedures.
- **Cost:** include cloud storage, reads/writes, KMS operations, egress, monitoring, Safety Case staffing, incident response and unrecovered-data risk. Zero Anthropic feature price is not zero total cost.
- **No duplicate runtime:** the bucket, Safety Case workflow, webhook consumer and storage-recovery process may not become a second evidence ledger, scheduler, retry plane, or authority system.
- **Next step:** no account/storage action. Any proposal needs founder and privacy/security approval; a complete data-flow and excluded-feature inventory; least-privilege IAM/KMS design; duplicate/missing/out-of-order webhook fixtures; bucket-failure and recovery drills; independent retention/deletion evidence; total-cost baseline; migration/rollback; and kill criteria for missing objects or a second evidence plane.

### Claude Opus 4.5 deprecation — announced 2026-11-23; retirement 2027-01-22

Anthropic deprecated `claude-opus-4-5-20251101` and `claude-opus-4-5` on the Claude API and recommends Opus 5.5. The migration changes thinking, effort, forced tool choice, computer-use toolsets, cross-model thinking replay, token budgeting, cache behavior, image tokens and Priority Tier compatibility. Official sources: https://platform.claude.com/docs/en/release-notes/overview, https://platform.claude.com/docs/en/about-claude/model-deprecations, and https://platform.claude.com/docs/en/models/opus-5-5/migration-guide

- **Impact:** no Anthropic adapter or Opus 4.5 identifier was found. Any non-repository use requires authorized inventory. Replacement is a semantic migration, not retry equivalence; bind exact model/platform/account/prefix/tool contracts, evaluate independently, re-baseline retention/residency and complete cost, and preserve rollback until acceptance.
- **Next step:** no repository migration. An authorized owner should inventory external use before 2027-01-22; if found, freeze fixtures and test every breaking contract before a founder-approved canary.

### Material provider incidents — 2026-11-18 through 2026-11-23

Official status communications reported OpenAI delayed Costs API data, GPT-6 Luna API errors, and GPT-6 ChatGPT conversation errors; Anthropic Google Docs connector failures and elevated errors for Fable/Mythos 5.2 and multiple models; and Kimi API availability failures plus severe Kimi Code K2.8/K3/K3.1/Highspeed request errors. Official sources: https://status.openai.com/history, https://status.claude.com/history, and https://status.moonshot.cn/

- **Direct exposure:** no affected new model, connector, Costs API, Anthropic, or Kimi runtime exists on the four default branches. DALEOBANKS' optional OpenAI models were not named.
- **Authority / one source of truth:** provider recovery, status, conversation history, connector output, and cost dashboards are evidence—not proof of individual completion, absence, or authoritative spend.
- **Replay / retry / idempotency:** errors and latency after dispatch are ambiguous. Retain the original canonical idempotency identity, reconcile receipts/effects before retry or failover, and record each subordinate attempt, partial result and cost separately.
- **Evaluator / credentials / residency:** use an independent health check and only pre-approved routes. Incidents do not authorize new providers, regions, credentials or data scopes.
- **Cost / no duplicate runtime:** delayed costs require append-only correction lineage. No provider recovery poller, auto-retry service or failover scheduler may become a second runtime.
- **Next step:** existing section 7 incident rules are sufficient. Carry these cases into future adapter fixtures; make no runtime change now.

### Kimi platform change threshold

Kimi published no new release, pricing, deprecation or policy update in the review window. Its material activity was limited to the status incidents above. Official sources: https://platform.kimi.ai/docs/platform-changelog and https://status.moonshot.cn/

## Alternatives, dissent, and exactly two strengthening passes

Baseline: local-first default routes; one optional legacy OpenAI surface; no Anthropic/Kimi runtime; and provider-neutral controls in draft section 7.

Alternatives considered: (1) brief only and no repository change; (2) add two dated evidence files; (3) add vendor-specific protocol clauses; (4) migrate to GPT-6.2, background/Live, EFS, or Opus 5.5; (5) let provider reasoning, queues, sessions, customer storage and safety workflows own canonical state. The strongest competing architecture centralizes orchestration and evidence retention in provider services; it is rejected because it duplicates canonical authority, retry, evidence, evaluation, cost and scheduling planes.

**Pass 1:** evidence-only recording preserves the new reasoning-drop, background auto-retry/temporary-storage, voice-delegation, customer-owned ZDR storage and retirement contracts without adopting them. Disadvantages: recurring review debt; no direct feature exposure; no live provider, billing or storage verification; mutable documentation; unknown non-repository use. Response: add two unique files only; label exposure and evidence tiers; pin dates, URLs and SHAs; require separate authorized inventory before any implementation.

**Pass 2:** attack the design for bureaucracy, one-model self-review, provider lock-in, silent reasoning loss, hidden background/voice retries and costs, ZDR overclaiming, unreadable sealed evidence, delayed/missing storage events, and storage recovery that can lose data. Strengthening: keep draft status; make no protocol or runtime change; prohibit account/storage/model action; require exact artifact and storage binding, receipt-gated retry, independent health/evaluation, explicit excluded-feature mapping, complete total cost, local-first comparison, rollback, and kill adoption on a second runtime or unverifiable retention.

**Dissent:** the Adversarial Reviewer prefers brief-only reporting because none of the new features is present on the default branches and existing section 7 already governs the invariants. That dissent controls scope. Breaking GPT-6.2 replay contracts, provider-managed auto-retry/temporary storage, customer-owned ZDR storage failure modes, and a hard Opus retirement justify only dated evidence—no protocol amendment, adapter, fixture, provider call, account/storage inspection, migration, or activation.

## Verification, migration, rollback, and kill criteria

- **Verification:** official provider sources; exact searches on the four listed default heads; all 49 open `main`-target PR file sets inspected for overlap; deliberation schema validation; Canonical CI on the resulting draft head. No live provider call, account, key, storage bucket, invoice, contract or data-control setting was accessed.
- **Migration:** none. Future work must pin every provider/model/API/prefix/user/organization/tier/region/cache/tool/queue/session/storage/IAM/KMS/retention contract; map operations and retries to canonical attempts/receipts; pass deterministic drop, duplicate, delayed, missing, cancellation, restart and recovery fixtures; perform independent evaluation and total-cost/data-control review; then receive founder approval for a bounded canary.
- **Rollback:** leave PR #105 unmerged or revert only the 2026-11-24 evidence commits while preserving historical evidence and dissent.
- **Kill:** any default-branch write or merge; account, credential, production, routing, storage, spending or authority change; dropped reasoning treated as equivalent replay; background or Live resubmission without receipt reconciliation; ZDR/customer-storage claims used as inference-residency or complete-retention proof; provider queue, session, bucket, Safety Case, webhook, evaluator, cost or retry state treated as canonical; a second scheduler/runtime; missing independent evaluation; missing total cost; or an immaterial recurring repository update.

