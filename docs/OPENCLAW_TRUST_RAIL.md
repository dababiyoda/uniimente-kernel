# OpenClaw Trust Rail Integration

## Boundary

Run this integration as an external MCP server. Do not install it as a trusted
in-process OpenClaw plugin: the host boundary should retain its own process,
credentials, policy checks, and audit log.

OpenClaw receives four tools:

1. `execute_bounded_action` selects a pre-registered executor and routes the
   proposal through the existing Consequence Gate.
2. `request_settlement_intent` checks principal-signed authority and creates an
   intent. It cannot submit or commit payment.
3. `verify_outcome_credential` returns proof plus current suspension/revocation.
4. `trust_rail_health` returns configuration posture and integrity counters.

There is deliberately no remote `commit_settlement` tool. A separate controlled
worker or human-authorized service calls `ProofToSettlementRail.commit_settlement`
after commit-time revalidation.

## Composition

```python
from integrations.openclaw import create_server
from trustrail.openclaw import OpenClawTrustBoundary

boundary = OpenClawTrustBoundary(
    consequence_gate=gate,
    rail=rail,
    proposal_factory=build_proposal,
    executors={"sandbox-draft-v1": sandbox_draft_executor},
    allowed_callers={openclaw_agent_passport_id},
    allowed_target_prefixes=("sandbox:outbox/",),
    live_actions_enabled=False,
)

server = create_server(
    boundary,
    authenticated_caller_id=openclaw_agent_passport_id,
)
server.run()
```

`authenticated_caller_id` is host configuration, not a tool argument. Run the
server behind an authenticated transport and bind one server identity to one
OpenClaw passport; never derive it from prompt or request content. The MCP layer
also overwrites the proposal actor with that bound identity.

Install the optional integration dependency with `mcp>=1,<2`. The stable MCP
Python SDK v1 API is used intentionally; v2 was still pre-release when this
module was written.

## First deploy

Start with one OpenClaw passport, one sandbox target prefix, one named executor,
one independently controlled verifier key, one principal authority key, and the
sandbox settlement adapter. Assert `unauthorized_external_effects == 0` and
reconcile every intent before expanding scope. Live actions and live money remain
separate approvals.

## Threat assumptions

Treat the OpenClaw host, agent prompt, inbound content, devices, peer agents, and
settlement callbacks as potentially compromised. A successful agent request is
only a proposal. The Kernel still resolves identity and legal principal, applies
policy, checks the exact capability, creates a commit witness, executes through a
registered adapter, records the outcome, and waits for independent proof.

## Primary references

- [OpenClaw Gateway security](https://docs.openclaw.ai/gateway/security) — the
  Gateway is a single-operator trust domain, not a hostile multi-tenant boundary.
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) —
  v1 is the stable line used by this integration.
- [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final) — authenticate
  and authorize subjects and devices before a session or external effect.
- [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) —
  the credential envelope model; cryptographic verification does not establish
  the truth of an off-chain claim.
- [Ethereum oracle documentation](https://ethereum.org/developers/docs/oracles/) —
  smart contracts require an oracle or equivalent verifier for off-chain facts.
