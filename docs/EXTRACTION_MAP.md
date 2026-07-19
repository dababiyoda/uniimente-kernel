# Extraction Map: DALEOBANKS to Kernel (Phase 2)

Surveyed 2026-07-19 against `dababiyoda/DALEOBANKS` main (`829c5f2`). Each row is a governance mechanism to extract into a kernel module and import back. Order is by extraction cost ascending.

| DALEOBANKS module | Mechanism | Kernel target | Coupling to remove | Status |
|---|---|---|---|---|
| `services/ledger.py` | Hash-chained decision ledger, kill switch, rate governor | `sdk-python/uniimente_kernel/ledger.py` | `config` import, `logging_utils` | **Extracted in PR #11** |
| `services/raw_vault.py` | Raw evidence preservation with hashes | `sdk-python/uniimente_kernel/raw_vault.py` | `logging_utils`; adds per-record sha256 | **Extracted in this PR** |
| `services/capability.py` | Capability grants | `sdk-python/uniimente_kernel/capability.py` | ORM to GrantStore protocol; aligned to `contracts/capability-grant.schema.json` | **Extracted in this PR** |
| `services/prompt_firewall.py` | Prompt-injection defense | `sdk-python/uniimente_kernel/prompt_firewall.py` | persona-specific rules stay in organ | Next |
| `services/context_packet.py` | ContextPacket builder | `sdk-python/uniimente_kernel/context_packet.py` | align to `contracts/context-packet.schema.json` | Planned |
| `services/constitution.py` | Constitution integrity check | `policy/constitution_check.py` | point at kernel `/constitution` hash | Planned |
| `services/heartbeat.py` | Supervision and automatic disarm | `observability/heartbeat.py` | organ-specific intervals to config | Planned |
| `services/operator_line.py` | Operator approval queue | `policy/approval_queue.py` | align states to `workflows/approval-lifecycle.yaml` | Planned |
| `services/venture_protocol.py` | OpportunityPacket / VentureAssessment wire types | `sdk-python/uniimente_kernel/contracts.py` | replace with imports from `/contracts` (Phase 3) | Phase 3 |
| `services/bridge_security.py` | HMAC signed transport | `sdk-python/uniimente_kernel/transport.py` | scheduled for retirement per `identity/service-identities.yaml` | Phase 5 |

## Adapter principle

Extraction never rewrites organ behavior in the same step. Each module lands in the kernel with identical semantics and an injection point for the organ-specific coupling (example: `KillSwitch(apply=update_config)`). The organ swaps its import, its test suite must stay green, and only then is the local copy deleted.

## Byte-compatibility note

`uniimente_kernel.ledger.DecisionLedger.record()` produces the same canonical entry form as `services/ledger.py` (same fields, same hashing), so existing `data/decision_ledger.jsonl` files verify under the kernel module with no migration.
