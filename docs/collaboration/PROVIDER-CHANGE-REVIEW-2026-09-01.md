# Provider Change Review — 2026-09-01

- Window: 2026-08-25 through 2026-09-01 UTC
- Scope: official OpenAI, Anthropic/Claude, and Moonshot AI/Kimi release, documentation, deprecation, pricing, policy, and status sources
- Repository exposure: default branches of `uniimente-kernel` (`bcbb1ab4`), `DALEOBANKS` (`ed5e95d7`), `WealthMachineIntelligence` (`ec84b6a2`), and `PumpStation` (`df6a732f`)
- Decision: `RETAIN` the provider-change protocol hardening; make no runtime, routing, model, or credential change

## Material findings

| Provider / date | What changed | Direct UNIIMENTE exposure | Likely impact | Executed next step |
|---|---|---|---|---|
| OpenAI — 2026-08-29 | Mutual TLS and X.509 workload identity federation became generally available for the API. | `DALEOBANKS` uses an API key for Chat Completions and optional embeddings; no WIF or mTLS configuration was found. | No break. This is a future least-privilege and key-reduction option, but changing identity or credentials is a production decision. | Added identity, permission, and residency fields to the required provider-change packet. No credential change. |
| OpenAI — 2026-08-26 | The Assistants API shut down; four transcription models were deprecated for shutdown on 2027-02-26. | Exact searches found no Assistants, Threads, `whisper-1`, or affected transcription-model use. `DALEOBANKS` uses `gpt-4o-mini` Chat Completions and `text-embedding-3-small`. | No current migration is required on the inspected default branches. The shutdown demonstrates that lifecycle checks must precede runtime assumptions. | Recorded the negative exposure result and added deprecation deadlines, last-known-good baselines, and compatibility diffs to the protocol. |
| Anthropic — 2026-08-27 | Current SDKs stopped sending the Files and Skills beta headers by default and return stable shapes; legacy header requests keep beta shapes. Personal and service-account API keys became available. | No Anthropic SDK or API use was found on the four inspected default branches. | Prospective only. A future Claude adapter must pin header and response-shape expectations and bind service identity to least privilege. | Added explicit beta-header, file-shape, identity, and contract-fixture review requirements. |
| Anthropic status — 2026-08-28 and 2026-08-31 | Claude Code/Cowork web sessions failed to start or disconnected during an upstream-cloud incident; Claude Code, Slack, Code Review, and claude.ai later had degraded performance. | UNIIMENTE's durable records show Claude-authored collaboration, even though no Anthropic runtime adapter exists on the inspected default branches. | A collaborator can disconnect after dispatch, leaving completion ambiguous. Blind retry or provider failover can duplicate work or external effects and can split the canonical trail. | Added incident states, receipt-gated retry/failover, provider lineage, circuit-breaking, and recovery-canary rules. |
| Kimi — 2026-08-31 | `kimi-k2.5` and all `moonshot-v1` variants shut down and now return 404. The Files API added `file_` IDs, stopped OCR extraction for images, and auto-renames same-name uploads. | No retired Kimi model or Files API identifier was found. The existing collaboration handoff already identifies Kimi K3. | No current model edit is required. A future adapter could break on file-ID validation, OCR assumptions, or model aliases. | Added exact file/tool/schema diffs and direct-exposure searches to the protocol. |
| Kimi — current documentation published 2026-08-31 | Kimi exposes OpenAI Chat Completions and Responses compatibility plus Anthropic Messages compatibility. Kimi K3 uses provider-specific reasoning and tool semantics. | No Kimi runtime adapter was found. | Transport reuse could be mistaken for semantic equivalence or used to stand up a second agent runtime. That would threaten one-source-of-truth, replay, evaluator independence, and no-duplicate-runtime constraints. | Added the rule that protocol compatibility is transport-only; canonical workflows, identities, leases, receipts, and evidence remain provider-neutral and singular. |

## Repository exposure evidence

- Searches across all four default branches returned no matches for `beta.assistants`, `beta.threads`, `v1/assistants`, `moonshot-v1`, `kimi-k2.5`, `kimi-k3`, `anthropic`, `whisper-1`, or `gpt-4o-transcribe`.
- `DALEOBANKS/services/llm_adapter.py` calls `gpt-4o-mini` through Chat Completions and retries rate limits/timeouts; its output remains a draft and has deterministic fallback.
- `DALEOBANKS/services/embeddings.py` optionally calls `text-embedding-3-small` and falls back to a tagged deterministic hash representation.
- No production credentials, environment state, live requests, or non-default branches were inspected or changed.

## Official sources

- OpenAI: [API changelog](https://developers.openai.com/api/docs/changelog), [deprecations](https://developers.openai.com/api/docs/deprecations), [pricing](https://developers.openai.com/api/docs/pricing)
- Anthropic: [Claude Platform release notes](https://platform.claude.com/docs/en/release-notes/overview), [model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations), [pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Claude status](https://status.claude.com/)
- Kimi: [platform changelog](https://platform.kimi.com/docs/changelog/changelog/changelog), [model list](https://platform.kimi.com/docs/models), [API overview](https://platform.kimi.com/docs/api/overview), [OpenAI compatibility notes](https://platform.kimi.com/docs/guide/migrating-from-openai-to-kimi)

## No-change categories and limits

- No material pricing or provider-policy change effective inside the review window was identified.
- OpenAI incident history and a dedicated Kimi status-history surface were not available through the official documentation routes used in this run; no incident claim is made for those providers.
- Unmerged branches, including draft task-fabric work, were not treated as canonical exposure. Any future implementation must preserve the protected canonical runtime until independently reviewed and authorized.

## Review-ready follow-up

1. Review this docs-only protocol change in the draft PR.
2. Do not migrate a model, SDK, credential, or live route on the evidence found here; the inspected default branches have no direct breaking exposure.
3. At the next material provider change, attach a provider fixture and deterministic replay test to the owning adapter rather than adding orchestration to the kernel.
4. If a live deployment differs from the inspected repository configuration, stop and request a separate, authorized production inventory.
