# Organizational Morphogenesis Failure Model

Status: preregistered design requirements; not runtime evidence.

Every attack must produce a durable detection record. “Kill” means stop or
reconfigure the mission organization without expanding authority. Static
DurableWorkflow or do-not-instantiate is the default degraded form.

| Attack | Detection | Containment | Degraded mode | Recovery | Required evidence | Kill threshold |
|---|---|---|---|---|---|---|
| Coordinator crash | missed heartbeat/lease | fence coordinator identity | static checkpoint order | resume/replace from canonical state | crash, fence, replay receipts | two failed recoveries or ambiguous owner |
| Worker crash | lease heartbeat loss | expire one lease | reduce pool/concurrency | fresh least-authority lease | lease expiry/replacement | task state or authority cannot be reconstructed |
| Worker timeout | timeout event | stop accepting late result | static retry policy | retry idempotently or terminate | timer, attempt, result disposition | retry budget exhausted |
| Duplicate task delivery | idempotency collision | suppress duplicate effect | accept first canonical result | verify receipt and close duplicate | both delivery IDs and one result | any duplicate consequential work |
| Stale task replay | mission/genome/version mismatch | reject and quarantine | current-version tasks only | reconcile source and replay current event | stale payload and rejection | stale event reaches RUNNING |
| Event replay after restart | inbox/event ID collision | deduplicate before handler | checkpointed replay | rebuild inbox/outbox and continue | replay trace and state digest | state differs or consequence repeats |
| Poison task | repeated deterministic failure/schema breach | quarantine task/producer | continue independent tasks | repair input or terminate branch | payload digest, failures, quarantine | message storm or shared-state corruption |
| Worker lies about completion | missing/contradicted proof | keep SUBMITTED, not VERIFIED | independent re-execution | evaluate, replace, preserve dissent | result, evidence and assessment | false result reaches closure |
| Evaluator disagreement | conflicting signed assessments | block acceptance | escalate without suppressing | authorized human/independent tie-break | all assessments and dissent | dissent missing or unilateral override |
| Evaluator capture | correlated identity/provider/outcome pattern | remove captured lease | second independent evaluator | re-evaluate affected results | identity, provider and decision history | required independence cannot be restored |
| Supervisor suppresses dissent | missing required assessment/dissent receipt | block synthesis/closure | direct evidence escalation | restore record and replace coordinator | suppression attempt and recovered dissent | any irreversible loss of dissent |
| Supervisor authority escalation | requested grant exceeds refs | fail closed and quarantine request | static authorized plan | human governance review | request, refs, rejection | any self-issued authority accepted |
| Worker requests excessive capability | lease/genome mismatch | deny capability and isolate worker | minimum-capability worker | issue new bounded lease if justified | request and policy decision | access granted outside lease |
| Workload identity mismatch | SPIFFE/registry/lease mismatch | reject connection/event | verified identities only | rotate/reissue through canonical PKI | handshake/revocation receipts | unverified identity performs task |
| Context leakage | data-classification or tool-policy violation | revoke lease and quarantine output | smaller context/read-only | investigate, rotate credentials, re-run | accessed fields and revocation | prohibited data leaves boundary |
| Budget exhaustion | reservation/usage ceiling hit | deny new leases/calls | static low-cost path or stop | release unused reserve or escalate | reservation and spend ledger | spend exceeds mission ceiling |
| Model provider outage | provider health/failure rate | stop routing to provider | eligible alternate/static path | reassign fresh lease, preserve attempts | provider failure and reassignment | no eligible provider under envelope |
| Split-brain coordinator | duplicate epoch/fencing token | fence all but canonical epoch | static single-owner workflow | reconcile checkpoints before resume | epochs, fences and state digest | two coordinators commit state |
| Task graph cycle | admission-time DAG/cycle check | reject genome/task graph | static acyclic graph | correct via versioned proposal | rejected graph digest | cycle reaches execution |
| Message storm | amplification/rate threshold | backpressure and quarantine source | static routing | drain, diagnose and replay boundedly | rates, source and dropped/quarantined IDs | amplification exceeds frozen ceiling |
| Queue starvation | wait-time/fairness threshold | reserve lane/age priority | static FIFO with safety priority | rebalance authorized capacity | queue age and routing decisions | hard-deadline task starves |
| Priority inversion | high-priority blocked by low-priority resource | bounded inheritance of resource priority, not authority | serialize critical path | release/reorder resource | dependency and scheduling receipts | consequence-critical deadline breached |
| Slow worker | p95 duration/heartbeat drift | stop new leases to worker | smaller tasks/static worker | replace after safe checkpoint | timings and replacement | mission deadline/resource ceiling threatened |
| Malicious worker | invalid proof, policy breach, adversarial pattern | revoke identity/lease; quarantine all output | independent revalidation | rotate secrets and re-run clean | complete forensic lineage | unauthorized effect or evidence corruption |
| Corrupted receipt | digest/signature/schema failure | refuse transition | retain last valid state | recover from canonical ledger/reissue | corrupt and recovered receipt | no trustworthy prior state |
| Missing evidence | required evidence checklist fails | block VERIFIED/CLOSED | request evidence or terminate | produce independent evidence | missing list and response | hard evidence unavailable by deadline |
| Uncertain external effect | request sent but acknowledgement missing | forbid retry | reconciliation state | query canonical external/proof system | request, uncertainty and reconciliation | blind retry attempted |
| Topology thrashing | change frequency/oscillation threshold | freeze current/static genome | static workflow | analyze episodes; new linked deliberation | proposals, triggers and changes | more than one live change or frozen rate exceeded |
| Reconfiguration during active tasks | active-lease/state-transfer check | reject proposal | finish/drain current genome | migrate only after receipts reconcile | affected tasks and rejection/migration proof | active state changed without proof |
| State migration failure | digest/invariant mismatch | roll back new genome | previous known-safe genome | restore checkpoint and reconcile leases | before/after digests and rollback | rollback cannot restore exact state |
| Dissolution with unresolved obligations | closure checklist fails | keep organization draining, no new work | reconciliation-only cell | settle/transfer obligations then dissolve | obligation, lease, credential and release receipts | deadline reached with unowned obligation |
| Founder command superseded mid-mission | signed newer intent/version | freeze admission and external effects | safe checkpoint only | authorized review: continue, amend via new contract, or terminate | old/new intent and disposition | continued work contradicts superseding command |
| Kernel unavailable | health/append/Gate failure | prohibit state/consequence commits | read-only pause or stop | restore canonical Kernel and reconcile | outage and replay evidence | any parallel authority/state store appears |
| Event Spine unavailable | append/ack failure | stop transitions; retain bounded outbox | paused static workflow | restore spine, reconcile outbox/inbox | outage, queued events and replay | task proceeds without canonical event record |

## Hard invariant metrics

- unauthorized external effects = 0;
- authority created by organization = 0;
- evidence/mission lineage completeness = 100%;
- required evaluator suppression = 0;
- unknown external-effect blind retries = 0;
- context-policy violations = 0 for a Verified Durable Mission Closure;
- deliberate interruption count ≥ 1 and duplicate consequential work = 0 for
  the first Verified Durable Mission Closure.

Cross-field enforcement beyond the Phase-1 schemas is deferred to one canonical
semantic validator after the runtime owner is explicitly decided.
