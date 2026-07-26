# Reality Compiler - IVIO v1

The existing mechanism is a deterministic Python compiler over one canonical JSON Schema package. It is the first hard boundary between free-form intent and an exact institutional instruction.

## Defined interface

- reality.ivio.compile_instruction(intent) returns an immutable, integrity-bound CompiledInstruction.
- reality.ivio.bind_integrity(document) adds a deterministic SHA-256 content binding.
- reality.ivio.verify_integrity(document) detects mutation.
- contracts/ivio/v1/schema.json is the normative wire contract.
- scripts/verify_ivio_v1.py is the dependency-free Python preflight.
- scripts/verify_ivio_v1_node.mjs independently checks canonical bytes and digests in Node.

The module compiles only. Policy, approval, capability issuance, commit-time revalidation, execution, credentials, and settlement remain separate interfaces.

## Bounded authority

The compiler has zero external authority. It cannot infer a legal principal, approve its output, issue a grant, call an adapter, mark a case payable-ready, move money, modify policy, or change a reality status. UNIIMENTE is rejected as legal principal. Live irreversible instructions are refused in v1.

## Available dependencies

Runtime uses only the Python standard library. Validation tests use the repository's existing jsonschema and pytest development dependencies. CI actions are pinned to immutable full commit SHAs.

## Security model

The security model is strict input shape, no unknown fields, printable-ASCII object keys, safe integers, no floats, integer minor-unit money, exact data rights, expiring instructions, content hashing, mutation detection, and fail-closed semantic checks. Cryptographic integrity is never represented as proof of underlying truth.

## Failure modes

Known failure modes include cross-language canonicalization drift, consumer schema drift, forged source evidence, stale approval, time-of-check/time-of-use mutation, incorrect policy semantics, verifier rejection, and treating a provider callback as finality. The compiler refuses malformed intent; later layers must still enforce policy, identity, proof, receipt, and reconciliation.

## Acceptance tests

Acceptance tests cover all 15 wire objects, schema validity, deterministic compilation, material mutation, hidden fields, floats, ambiguous authority, overlapping data rights, TTL bounds, live irreversible action, payable-ready requirements, idempotency-key shape, and negative-evidence retention. The full kernel suite remains the merge gate.

## Recovery path

Because the compiler is pure and deterministic, recovery is recompilation from the preserved source intent and policy/Constitution digests. A mismatched result is quarantined; no best-effort repair or silent field insertion is allowed.

## Resource ceiling and operating cost

One compile is CPU- and memory-bounded by the size of a single intent document and uses no network, secret, database, model, or paid API. The resource ceiling for IVIO v1 is one JSON document within the calling service's request-size limit. Operating cost is effectively the host's local serialization and SHA-256 work.

## Legal operator

The legal operator is the named legal principal in the source intent, under Alfonso Lopez's reserved human authority. UNIIMENTE is infrastructure and never the operator.

## Handoff

CHARIO, TGH-CONTROL-RAIL, WealthMachineIntelligence, and DALEOBANKS may consume this schema only after parity tests prove identical bytes, digests, enums, and refusal behavior. No handwritten mirror is an authoritative handoff.

## Replaceable

The Python implementation is replaceable. Any replacement must preserve the ivio.v1 wire contract and pass the same vectors. A canonicalization or semantic change requires a versioned migration, never a silent swap.
