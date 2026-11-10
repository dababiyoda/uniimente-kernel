# Provider change review — 2026-11-10

Window: 2026-11-03 17:40 UTC through 2026-11-10 17:40 UTC. Only material changes are recorded. Provider documentation establishes provider claims, not verified UNIIMENTE behavior.

## Decision

**NEEDS_FOUNDER_DECISION.** Add this evidence packet and its machine-readable deliberation to draft PR #105; leave `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` unchanged. Section 7 already covers exact model and tool contracts, leased provider state, canonical receipts, replay and retry safety, credential/data scope, total cost, independent evaluation, incident recovery, and the no-duplicate-runtime constraint. No provider feature is adopted.

## Default-branch exposure

| Repository | Inspected default head | Direct exposure |
|---|---:|---|
| `dababiyoda/uniimente-kernel` | `d64a6c931bb05aba4e3454847b665e73384bbdfa` | Local/loopback model route; no Fable/Mythos 5.2, Anthropic control plane, GPT-6-Cyber, GPT Image, or provider cost-export consumer found. |
| `dababiyoda/DALEOBANKS` | `667439f49442bd898d3655666a389f53114f1412` | Local by default; optional OpenAI `gpt-4o-mini` Chat Completions and `text-embedding-3-small`. Directly exposed only to the broad OpenAI API incidents, not the new models or Costs API. |
| `dababiyoda/WealthMachineIntelligence` | `ec82b8027d987c865dc123215afb53d20916908f` | No direct OpenAI, Anthropic, or Kimi runtime route found. |
| `dababiyoda/PumpStation` | `db6758dfa8621a4f6fb0504c20343e60db5336c1` | No direct OpenAI, Anthropic, or Kimi runtime route found. |

Exact default-branch searches returned no `claude-fable-5-2`, `claude-mythos-5-2`, `prefix_mismatch_behavior`, `computer_toolset_20260801`, Anthropic member sign-out call, organization IP-allowlist integration, `gpt-6-cyber`, `gpt-image-2`, `gpt-image-2.6`, or OpenAI Costs API consumer. Repository inspection cannot establish non-repository account use.

## Material changes and bounded response

### Claude Fable 5.2 and Mythos 5.2 — released 2026-11-09

Anthropic released `claude-fable-5-2` and verification-gated `claude-mythos-5-2` for long-horizon agentic work. Both have a 1M-token context, 128k maximum output, always-on adaptive thinking, standard pricing of $8/MTok input and $40/MTok output, and fast mode at $16/$80. Four migration contracts can break integrations: prefix checks apply to every account; only Fable/Mythos 5.2 can read their thinking blocks; the older `computer_20251124` tool errors in favor of `computer_toolset_20260801`; and a Fable/Mythos 5.2 executor accepts only Fable/Mythos 5.2 as advisor. The models require 30-day retention and are not ZDR-eligible unless Anthropic expressly authorizes it. Official sources: https://platform.claude.com/docs/en/release-notes/overview and https://platform.claude.com/docs/en/models/fable-5-2/migration-guide

- **Canonical authority / one source of truth:** Fable/Mythos reasoning, account links, advisor compatibility, and provider-managed histories remain subordinate artifacts. Canonical system/tool/message prefixes, task identity, grants, receipts, and event history stay in UNIIMENTE.
- **Provider contract / replay / idempotency:** bind every thinking block to provider, exact model, opaque account binding, complete prefix hash, toolset/advisor manifest, platform, speed, and canonical cursor. Editing an earlier prefix returns 400 and identical retry cannot repair it. Switching away may silently drop thinking blocks while the request succeeds; that is a semantic migration, not replay equivalence.
- **Evaluator independence:** neither Fable/Mythos nor its advisor may solely approve its own promotion. Test with frozen tasks and an evaluator outside the candidate route.
- **Credentials / residency:** Mythos requires a verified organization. Both require 30-day retention and lack ordinary ZDR eligibility. No account, verification state, linked account, key, region, or retention setting was inspected.
- **Cost:** always-on thinking, dropped-block recovery, 1M context, long outputs, tool calls, and advisor calls must be measured. Fast mode doubles token rates; `drop_block` can increase output tokens.
- **No duplicate runtime:** Claude Code, Managed Agents, or Agent SDK history management may not become a second canonical conversation, scheduler, evaluator, or retry plane.
- **Next step:** no adapter or canary. Any proposal needs append-only prefix fixtures, model-switch and dropped-block tests, computer-tool/advisor compatibility tests, retention approval, complete cost accounting, independent evaluation, and founder approval.

### Anthropic organization IP allowlists and member sign-out — released 2026-11-05

Anthropic added beta organization-wide IP allowlisting and a beta Admin API operation to sign a Claude Enterprise member out everywhere. The allowlist covers many Console, API, Managed Agents, Admin, Compliance, Claude Code, Cowork, and Remote Tools access paths but not networking from inside Managed Agents or partner-cloud platforms. Changes can take up to 15 minutes. Member sign-out ends sign-in sessions, trusted devices, and organization-issued OAuth tokens, but not API keys, unrelated OAuth tokens, or Claude Code cloud sessions and routines; a token can remain active for up to one hour. Official sources: https://platform.claude.com/docs/en/manage-claude/ip-allowlist and https://platform.claude.com/docs/en/api/http/beta/organization/users/sign_out

- **Authority / one source of truth:** provider allowlists and sign-out state are protective controls and evidence, not UNIIMENTE authorization or proof of complete revocation. Canonical credential inventory and revocation state must record each affected and unaffected credential/session class.
- **Provider contract / replay / idempotency:** allowlist changes have propagation delay and lockout risk. Sign-out is safe to repeat after 503 according to Anthropic, but every request and observed postcondition still needs a canonical operation identity and receipt; 200 does not prove API keys or cloud routines ended.
- **Evaluator independence:** verify access denial, retained sessions, and audit records from a separately controlled path; the same Admin API cannot solely certify full offboarding.
- **Credentials / data residency:** use least-privilege `write:members`; separate allowlist administration from runtime keys; enumerate CI, VPN, proxy, IPv4/IPv6, remote-worker, and partner-cloud paths. No setting or credential was accessed or changed.
- **Cost / no duplicate runtime:** false 403 retries and orphaned cloud routines can create duplicate work or spend. The allowlist does not authorize a provider-side security daemon or second identity plane.
- **Next step:** no account action. A founder-authorized plan must stage read-only inventory, break-glass recovery, propagation/lockout fixtures, explicit uncovered-path mapping, audit reconciliation, and rollback before enabling either control.

### OpenAI GPT-6-Cyber and Daybreak contracts — released 2026-11-05

OpenAI released `gpt-6-cyber` for authorized vulnerability investigation, reproduction in authorized test environments, and fix verification. It requires Daybreak Red plus model approval, a non-default approved project/key, API-source IP allowlisting, and Private Safety Processing when using ZDR. Requests explicitly select `access_programs.cyber: "daybreak_red"` and include a stable pseudonymous `safety_identifier`. The model has a 1.05M context window, supports tools including hosted shell, computer use, apply patch, skills, and MCP, and costs $20/$100 per MTok for short-context input/output, with higher long-context and cache-write rates. `gpt-5.5-cyber-preview` was deprecated the same day and retires 2027-02-01. Official sources: https://developers.openai.com/api/docs/changelog, https://developers.openai.com/api/docs/guides/daybreak, and https://developers.openai.com/api/docs/deprecations

- **Authority / one source of truth:** Daybreak eligibility, reduced-refusal behavior, model access, and a safety identifier do not authorize a security target, exploit, tool, or external effect. Canonical scope, target ownership, consequence policy, receipts, and evidence remain controlling.
- **Provider contract / replay / idempotency:** bind model, resolved alias, access program, project, safety-identifier derivation version, tool manifest, cache tier, and canonical attempt. Access-program errors, approval changes, or model migration are not equivalent retries.
- **Evaluator independence:** the cyber model cannot both perform and solely verify a finding or patch. Require deterministic reproduction plus an independent security reviewer/evaluator.
- **Credentials / residency:** separate approved-project keys; enforce source IPs; validate PSP/ZDR state and region before sending data. A provider program or account approval is not canonical identity.
- **Cost / no duplicate runtime:** long context, cache writes, hosted tools, computer use, security review, and retries can dominate cost. Provider tools remain leased capabilities under one task/runtime.
- **Next step:** no adoption. Any proposal requires target-authorization proofs, isolated sandbox fixtures, pseudonymous identifier rules, least-privilege credentials, retention/residency evidence, per-tool budgets, independent verification, and founder approval.

### OpenAI image model launch and deprecation — 2026-11-04 and 2026-11-10

OpenAI released `gpt-image-2.6-sunburst` and `gpt-image-2.6-flare` with complexity control, markup-guided editing, SVG, and animated GIF output. On November 10, `gpt-image-2` and its `2026-04-21` snapshot were deprecated for removal on 2027-02-10. Image 2.6 pricing is $5/MTok text input, $8 image input, $30 image output; SVG additionally bills an authoring model, and each streamed partial image adds 100 output tokens. Official sources: https://developers.openai.com/api/docs/changelog, https://developers.openai.com/api/docs/guides/image-generation, and https://developers.openai.com/api/docs/deprecations

- **Authority / one source of truth:** generated/edited images, SVGs, GIFs, masks, and markup instructions are artifacts, not canonical evidence or authority. Preserve source assets, transformations, hashes, model, parameters, and receipts.
- **Replay / idempotency:** image generation is not deterministic replay. Replacement models, complexity defaults, streamed partials, or markup edits create new semantic attempts under the original canonical work item.
- **Evaluator independence / credentials / residency:** visual acceptance needs deterministic structural checks or an independent evaluator. Region, retention, source-image permissions, and credential scope require review.
- **Cost / runtime:** measure authoring-model, image-token, partial-image, retry, and storage costs. The image tool may not become a parallel artifact workflow.
- **Next step:** no migration because no affected model is present. Inventory non-repository use before 2027-02-10; if found, compare pinned visual fixtures and retain rollback until independent acceptance.

### OpenAI API and cost-evidence incidents — 2026-11-06 through 2026-11-10

OpenAI reported a major outage across all models and API endpoints on November 8, broad API errors on November 9 affecting Chat Completions, Responses, Agents, Decisions, Embeddings, Images, Batch and other components, and incorrect Costs API export data published November 6–9 before resolution on November 10. Official sources: https://status.openai.com/incidents/01JMYB63BJ47J3SXV6KSCT4D2A/write-up, https://status.openai.com/incidents/01M7193DWYRFWQM5W6E3VZ7TM7, and https://status.openai.com/incidents/01M71W79MAGEXEX93QTVTBYJ4K

- **Direct exposure:** the broad outages directly cover DALEOBANKS' optional Chat Completions and Embeddings routes. No Costs API consumer was found.
- **Authority / one source of truth:** provider recovery and corrected exports are telemetry/evidence, not proof of individual completion or authoritative cost truth. Preserve original usage/cost receipts and later corrections as append-only adjustments.
- **Replay / retry / idempotency:** 502/503, timeout, and broad routing failures leave dispatched attempts ambiguous. Reconcile receipts before retry or failover; keep the original canonical idempotency identity and record every attempt separately.
- **Evaluator / credentials / residency:** use an independent health/canary and pre-approved route only. Incidents do not authorize new credentials, regions, or failover providers.
- **Cost / no duplicate runtime:** incorrect exports can under- or overstate spend. Do not close budgets or invoices from a single provider export; no automatic retry daemon or failover scheduler is authorized.
- **Next step:** existing section 7 incident rules are sufficient. For future direct use, freeze raw exports for November 6–9, append corrected rows with lineage, and require receipt-gated recovery.

### Anthropic and Kimi status incidents — 2026-11-04 through 2026-11-09

Anthropic reported a short Fable 5.1 degradation on November 8. Kimi reported file-service failures, K3 TTFT delays and broad K3 errors on November 4–6, plus three short search-error incidents on November 9. Official sources: https://status.claude.com/ and https://status.moonshot.cn/

- **Impact:** missing files/search results, slow first tokens, model errors, and provider recovery do not establish non-execution or complete evidence.
- **Replay / retry / cost:** retain canonical query/task identity, receipts, partial output, and item/source IDs; reconcile before retry; record each attempt and cost separately.
- **Authority / runtime:** status pages cannot authorize route changes or become evaluators. Failover is limited to pre-approved routes and may not create another scheduler.
- **Next step:** no runtime change because no Anthropic/Kimi adapter exists. Carry these failure cases into any future adapter fixture set.

## Alternatives, dissent, and exactly two strengthening passes

Baseline: local-first default routes, one optional legacy OpenAI surface, no Anthropic/Kimi runtime, and provider-neutral controls in draft section 7.

Alternatives considered: (1) brief only and no repository change; (2) add two dated evidence files; (3) add vendor-specific protocol clauses; (4) adopt/migrate immediately; (5) allow provider-native security, identity, history, tools, and evaluation planes. The strongest competing architecture centralizes these functions in provider services; it is rejected because it duplicates canonical authority, state, credentials, retry, evaluation, cost, and scheduling.

**Pass 1:** evidence-only recording preserves breaking replay/retention/security contracts and direct OpenAI incident exposure without adopting them. Disadvantages: review debt; no live provider verification; mostly prospective features; mutable provider docs; unknown non-repository use. Response: two unique files only; label exposure and evidence tiers; pin dates, URLs, and SHAs; require authorized inventory before migration.

**Pass 2:** attack the design for bureaucracy, one-model self-review, lock-in to provider control planes, hidden long-context/tool cost, false revocation completeness, and blind recovery from corrected billing/status. Strengthening: keep draft status; leave protocol text unchanged; prohibit account action; require explicit uncovered-session and retention mapping; require append-only billing corrections and per-attempt receipts; kill adoption on missing independent evaluation, rollback, residency, or total cost.

**Dissent:** the Adversarial Reviewer prefers brief-only reporting because the new features are absent from default branches and existing section 7 already governs them. That dissent controls scope. The Fable 5.2 breaking cross-model contract, Anthropic consequence-bearing identity controls, GPT-6-Cyber authority/credential contract, and OpenAI direct outage plus incorrect-cost evidence justify only the dated record—no protocol amendment, adapter, provider call, account inspection, migration, or activation.

## Verification, migration, rollback, and kill criteria

- Verification: official provider sources; exact searches on the four listed default heads; deliberation schema validation; Canonical CI on the resulting draft head. No live provider or account test was authorized.
- Migration: none. Future work must pin provider/model/API/platform/region/tool/access-program/retention/speed contracts; map every operation to canonical attempts and receipts; pass deterministic error, dropped-artifact, revocation, outage, and cost-reconciliation fixtures; perform independent evaluation; then receive founder approval for a bounded sandbox.
- Rollback: leave PR #105 unmerged or revert only the 2026-11-10 evidence commits while preserving historical evidence and dissent.
- Kill: any default-branch write or merge; account/credential/production/authority change; provider-owned canonical history, identity, authorization, evidence, evaluation, receipt, retry, cost, scheduler, or runtime; blind retry after ambiguous completion; unapproved target or security effect; incomplete revocation claimed complete; silently dropped reasoning treated as equivalent; unapproved 30-day retention/region; unreconciled cost; or an immaterial recurring repository update.

