# Extraction Map: DALEOBANKS to Kernel (Phase 2)

Surveyed 2026-07-19 against `dababiyoda/DALEOBANKS` main (`829c5f2`). Each row is a governance mechanism to extract into a kernel module and import back. Order is by extraction cost ascending.

| DALEOBANKS module | Mechanism | Kernel target | Coupling to remove | Status |
|---|---|---|---|---|
| `services/ledger.py` | Hash-chained decision ledger, kill switch, rate governor | `sdk-python/uniimente_kernel/ledger.py` | `config` import, `logging_utils` | **Extracted in PR #11** |
| `services/raw_vault.py` | Raw evidence preservation with hashes | `sdk-python/uniimente_kernel/raw_vault.py` | `logging_utils`; adds per-record sha256 | **Extracted in PR #12** |
| `services/capability.py` | Capability grants | `sdk-python/uniimente_kernel/capability.py` | ORM to GrantStore protocol; aligned to `contracts/capability-grant.schema.json` | **Extracted in PR #12** |
| `services/prompt_firewall.py` | Prompt-injection defense | `sdk-python/uniimente_kernel/prompt_firewall.py` | constructor-extensible patterns; persona rules stay in organ | **Extracted in PR #13** |
| `services/context_packet.py` | ContextPacket builder | `sdk-python/uniimente_kernel/context_packet.py` | ORM to ContextPacketData; aligned to `contracts/context-packet.schema.json` | **Extracted in PR #13** |
| `services/constitution.py` | Constitution integrity check | `sdk-python/uniimente_kernel/constitution_check.py` | watches all five kernel UCL files; kernel ledger/switch | **Extracted in PR #14; packaged in PR #16** |
| `services/heartbeat.py` | Supervision and automatic disarm | `sdk-python/uniimente_kernel/heartbeat.py` | kernel ledger/switch; behavior identical | **Extracted in PR #14; packaged in PR #16** |
| `services/operator_line.py` | Operator approval queue | `sdk-python/uniimente_kernel/approval_queue.py` | ORM to ApprovalStore; notifier/briefing providers injected; command grammar identical | **Extracted in PR #14; packaged in PR #16** |
| `services/venture_protocol.py` | Signal wire types (packet out, assessment back) | `sdk-python/uniimente_kernel/contracts.py` | mirrored copy in WMI deleted; both import the kernel module; wire formalized as `contracts/venture-signal` + `contracts/signal-assessment` v1.1 | **Unified in PR #17** |
| `services/bridge_security.py` | HMAC signed transport | `sdk-python/uniimente_kernel/transport.py` | scheduled for retirement per `identity/service-identities.yaml` | Phase 5 |

## Adapter principle

Extraction never rewrites organ behavior in the same step. Each module lands in the kernel with identical semantics and an injection point for the organ-specific coupling (example: `KillSwitch(apply=update_config)`). The organ swaps its import, its test suite must stay green, and only then is the local copy deleted.

## Byte-compatibility note

`uniimente_kernel.ledger.DecisionLedger.record()` produces the same canonical entry form as `services/ledger.py` (same fields, same hashing), so existing `data/decision_ledger.jsonl` files verify under the kernel module with no migration.

## Maturation mapping: signal wire to institutional contracts

The signal wire (`venture-signal`, `signal-assessment`) is what organs exchange today. The institutional contracts (`opportunity-packet`, `venture-assessment`) are the mature artifacts produced later in the pipeline. No organ fabricates the institutional fields; they are earned through evaluation and the human gate. The mapping when the venture pipeline matures (Phase 4/6):

| Institutional field | Derived from |
|---|---|
| `observed_failure` | signal `observed_pain` |
| `pain_owner` | signal `customer_segment` |
| `budget_owner` | signal `buyer_type` |
| `governing_bottleneck` | computed by the assessment engine, confirmed at the human gate |
| `cheapest_decisive_test` | signal `smallest_validation_action`, upgraded by the engine |
| `key_risks` | signal `risk_flags` + assessment `reasons` |
| `evidence_refs` | raw-vault `content_hash` values behind signal `evidence` |
| `verdict` | assessment `go_no_go` |
| `adversarial_cases` | engine-generated bull/bear/do_nothing (schema 1.1 committee) |
