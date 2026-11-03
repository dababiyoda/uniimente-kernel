# Provider change review — 2026-11-03

Window: 2026-10-27 16:51 UTC through 2026-11-03 16:51 UTC. Only material changes are recorded. Provider documentation establishes provider claims, not verified UNIIMENTE behavior.

## Decision

**NEEDS_FOUNDER_DECISION.** Add this evidence packet and its machine-readable deliberation to draft PR #105; leave `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` unchanged. Section 7 already covers leased provider state, exact contract binding, canonical receipts, replay and retry safety, credentials and data scope, total cost, independent evaluation, and the no-duplicate-runtime constraint. No provider feature is adopted.

## Default-branch exposure

| Repository | Inspected default head | Direct exposure |
|---|---:|---|
| `dababiyoda/uniimente-kernel` | `d64a6c931bb05aba4e3454847b665e73384bbdfa` | Local/loopback model route; no Kimi Admin/Batch, OpenAI Evals, Anthropic connector runtime, or provider-owned scheduler found. |
| `dababiyoda/DALEOBANKS` | `667439f49442bd898d3655666a389f53114f1412` | Optional OpenAI `gpt-4o-mini` Chat Completions and `text-embedding-3-small`; no affected feature found. Default remains local. |
| `dababiyoda/WealthMachineIntelligence` | `ec82b8027d987c865dc123215afb53d20916908f` | No direct OpenAI, Anthropic, or Kimi runtime route found. |
| `dababiyoda/PumpStation` | `db6758dfa8621a4f6fb0504c20343e60db5336c1` | No direct OpenAI, Anthropic, or Kimi runtime route found. |

Exact default-branch searches returned no `MOONSHOT_ADMIN_KEY`, `sk-admin`, `/v1/admin/organizations`, `/v1/batches`, `/v1/evals`, OpenAI Evals, Promptfoo, Kimi K3, Anthropic client, Gmail connector, or Google Calendar connector integration. Repository inspection cannot establish non-repository account use.

## Material changes and bounded response

### OpenAI Evals became read-only — effective 2026-10-31

OpenAI's Evals dashboard and API entered read-only mode on October 31, with shutdown scheduled for November 30, 2026. OpenAI recommends migration to Promptfoo. Official source: https://developers.openai.com/api/docs/deprecations

- **Authority / one source of truth:** provider eval configuration and verdicts remain evidence, never canonical promotion authority. Preserve exported cases, graders, run identifiers, model/API contracts, results, hashes, and provenance in the canonical evidence lineage.
- **Provider contract / replay / idempotency:** new OpenAI-hosted eval runs are no longer available. A replacement run is not replay-equivalent merely because it uses the same prompts; retain stable case IDs and version the runner, grader, model, tool manifest, and sampling contract.
- **Evaluator independence:** neither OpenAI Evals nor Promptfoo may be the sole evaluator of an OpenAI candidate route. Promotion still requires an independent acceptance path.
- **Credentials / residency / cost:** no account, secret, project, retention setting, or contract was inspected. A migration may introduce different secrets, execution locations, retention, and dual-run cost; inventory these before use.
- **No duplicate runtime:** an evaluation runner may measure workflows but may not schedule or execute canonical work.
- **Next step:** no repository adapter change. Before November 30, an authorized human should inventory any non-repository OpenAI Evals use and, if present, export immutable fixtures and compare a replacement on pinned cases. Founder approval is required for adoption.

### OpenAI collaboration-surface incidents — 2026-10-30 and 2026-11-02/03

OpenAI resolved search errors affecting Dots, ChatGPT Work, and some thinking experiences on October 30, and file-upload/read failures in ChatGPT from November 2 into November 3. Official history: https://status.openai.com/history

- **Impact:** search or upload success is not evidence that all expected material was found, saved, or read. Canonical repository blobs, digests, source ranges, and receipts remain the one source of truth.
- **Replay / retry / idempotency:** mark incomplete searches and unread uploads as ambiguous. Re-search or re-upload only with the original canonical evidence identity and deduplicate by content digest; never convert provider recovery into proof that a prior attempt did not complete.
- **Cost / authority / runtime:** record each attempt separately; search and upload surfaces remain subordinate evidence channels, not authority or a second ingestion runtime.
- **Next step:** no code change because no affected integration was found. Apply the existing receipt-gated incident rule to future collaboration use.

### Anthropic Gmail and Google Calendar connector incidents — resolved 2026-10-28

Anthropic reported Gmail connector errors for claude.ai, Claude Code, and Cowork from October 27 23:00 UTC to October 28 05:29 UTC, and Google Calendar list/search errors resolved October 28 18:52 UTC. Official history: https://status.claude.com/

- **Authority / one source of truth:** connector results are observations, not canonical email or calendar state. Missing results must be represented as incomplete evidence.
- **Replay / retry / idempotency:** retain the canonical query, time window, cursor, provider receipt, and item/event identity. Retry the same read and deduplicate by stable provider item identity plus content/version evidence.
- **Evaluator / credentials / residency:** do not let the same connector certify its own completeness. No OAuth grant, mailbox, calendar, tenant, data location, or retention setting was inspected or changed.
- **Cost / no duplicate runtime:** connector retries are subordinate attempts. A Claude connector or Cowork workflow may not become a second polling scheduler.
- **Next step:** no repo change beyond this evidence; no direct integration was found.

### Kimi Admin API beta — announced 2026-11-02

Moonshot made a separate `sk-admin-*` control-plane API available for organization members, invitations, projects, inference keys, billing, usage, and audit logs. It is beta, requires organization verification, supports scoped permissions including a future-expanding `all` scope, applies authorization changes after an approximately 30-second cache, uses cursor pagination, and publishes billing/audit retention and Asia/Shanghai reporting conventions. Official sources: https://platform.kimi.ai/docs/guide/admin-api-overview and https://forum.moonshot.ai/

- **Authority / one source of truth:** Kimi organization roles, projects, keys, spend limits, billing rows, and audit logs cannot create UNIIMENTE authority or become its canonical identity or policy plane. Every mutation, observation, and provider identifier must map to a canonical authorized operation and receipt.
- **Provider contract / retry / idempotency:** admin writes have endpoint-specific semantics; HTTP retry alone is unsafe. Bind method, path, normalized body, organization, actor, expected precondition, canonical operation ID, and resulting receipt. Reconcile an ambiguous write before retry. Bind cursors to the exact filters and stop if filters or organization change.
- **Evaluator independence:** provider audit and billing output is evidence that requires independent reconciliation; the provider cannot solely certify its own access control, spend, or successful revocation.
- **Credentials / data residency:** never reuse an inference key as an admin key. Avoid the future-expanding `all` scope; require least privilege, separate storage and rotation, organization verification, retention/deletion mapping, and explicit review of member, billing, usage, and audit data. Account changes were not authorized or attempted.
- **Cost:** track admin calls, rate-limit/backoff attempts, and every controlled inference-key/project effect. Billing units and time-zone boundaries must be normalized before reconciliation.
- **No duplicate runtime:** no provider-side admin automation, key rotator, webhook executor, or policy engine may become a parallel authority/runtime.
- **Next step:** prohibit adoption from this review. A founder-authorized proposal must begin read-only with pinned scopes, deterministic fixtures, human-gated writes, recovery tests covering the authorization-cache interval, and rollback to disabled credentials and unchanged canonical policy.

### Kimi Batch expanded to K3/K3.1 — October 2026 entry, observed 2026-11-03

Kimi's October changelog now documents Batch API support for `kimi-k3.1-pro` and `kimi-k3` in China and Global. Batch inference is 60% of standard rates, K3/K3.1 incur cache-write fees, cache hits are best effort under concurrent asynchronous processing, jobs are outside real-time concurrency limits, and unfinished jobs expire at their completion window. The source does not state a publication day; this record preserves the observation date. Official sources: https://platform.kimi.ai/docs/platform-changelog and https://platform.kimi.ai/docs/pricing/batch

- **Authority / one source of truth / no duplicate runtime:** the provider queue is a leased execution surface, never a scheduler or canonical job ledger. Each batch and item must map to one canonical task and subordinate attempt.
- **Replay / retry / idempotency:** retain request-line hashes, model/region/contract, batch ID, item ID, state transitions, output/error files, and completion window. Reconcile partial, expired, cancelled, or ambiguous jobs item by item before resubmission; resubmit only missing canonical attempts under the original idempotency identity.
- **Evaluator independence:** evaluate outputs outside the candidate Kimi route with frozen cases and graders.
- **Credentials / residency:** China and Global are not interchangeable. Region, account contract, data path, retention, and key scope require explicit authorization.
- **Cost:** model input/output, cache writes, best-effort cache hits, failed/expired items, downloads, retries, and duplicate submissions must reconcile. The 60% rate is not a total-cost guarantee.
- **Next step:** no adapter or canary because no route exists. If proposed later, use an offline fixture first, then a founder-approved cost-capped sandbox with cancellation, expiry, partial-output, and duplicate-submission tests.

### Kimi latency incidents — 2026-10-28 through 2026-11-02

Kimi reported repeated TTFT and OTPS degradation, including a serious October 31 slowdown and prolonged/repeated November 1 degradation; all listed incidents were resolved. Official history: https://status.moonshot.cn/

- **Impact:** timeout or slow streaming does not prove absence of execution or billing. Preserve provider receipts and distinguish queued, started, partial, completed, expired, and unknown states.
- **Retry / cost / runtime:** retry or fail over only after receipt reconciliation, keep the original canonical idempotency identity, and record each attempt/cost separately. A provider incident does not authorize a new route or scheduler.
- **Next step:** no runtime change because no Kimi route was found; carry the failure cases into any future batch or real-time adapter proposal.

## Alternatives, dissent, and exactly two strengthening passes

Baseline: local-first default routes, one optional legacy OpenAI surface, no Anthropic/Kimi runtime, and provider-neutral rules in draft section 7.

Alternatives considered: (1) do nothing and brief only; (2) add the two dated evidence files; (3) add vendor-specific protocol law; (4) adopt/migrate immediately; (5) allow provider-native control/eval/queue planes. The strongest competing architecture centralizes admin, batch, connectors, and evaluation in provider services; it is rejected because it duplicates canonical authority, state, retries, evidence, cost, and scheduling.

**Pass 1:** the evidence-only update preserves hard effective dates and new control/batch contracts without adoption. Its disadvantages are review debt, no live verification, publication-date uncertainty for Kimi Batch, and unknown non-repository use. Response: two unique files only; label all direct exposure negative; preserve observation versus effective dates; require authorized inventory before migration.

**Pass 2:** attack the remaining design for bureaucracy, self-review, mutable provider docs, hidden control-plane scope, ambiguous async completion, and incomplete cost. Strengthening: keep the PR draft; label five roles as one model's self-review; pin URLs, dates, and repository SHAs; prohibit wildcard admin scope and account action; require per-item receipts and reconciliation; kill adoption on missing cost, residency, rollback, or independent evaluation.

**Dissent:** the Adversarial Reviewer prefers brief-only reporting because no new feature is directly integrated and section 7 already governs the risks. That dissent controls scope. Evidence files are justified only by the Kimi consequence-bearing control plane, the new async batch contract, and the OpenAI Evals effective read-only transition. No protocol text, adapter, fixture, provider call, account inspection, or migration is added.

## Verification, migration, rollback, and kill criteria

- Verification: exact searches on the four listed default heads; official provider sources only; deliberation schema validation; Canonical CI on the resulting draft head. No live provider or account test was authorized.
- Migration: none. Any future migration must pin provider, model, API/version, region, tools, admin scopes, evaluator, retention/residency, cost, and retry semantics; translate all operations into canonical attempts/receipts; pass deterministic failure fixtures and independent evaluation; then receive founder approval for a bounded sandbox.
- Rollback: leave PR #105 unmerged or revert only the two 2026-11-03 evidence commits while preserving historical evidence and dissent.
- Kill: any default-branch write or merge; account/credential/production/authority change; wildcard or unreviewed admin scope; provider-owned canonical identity, policy, evidence, evaluation, receipts, retries, cost, queue, scheduler, or runtime; blind retry after ambiguous completion; duplicate item/effect; unapproved region or data scope; unreconciled cost; non-independent promotion; or an immaterial recurring repository update.

