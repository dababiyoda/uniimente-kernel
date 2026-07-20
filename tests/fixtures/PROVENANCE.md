# Fixture provenance

These fixtures were NOT hand-written. They were produced by executing the sibling
organs' own code in-session on 2026-07-20, then frozen here so the kernel's
integration tests exercise the real wire shapes without importing the sibling
repositories.

- `wire_opportunity_packet.json` — output of
  `services.venture_protocol.packet_to_wire()` over a `db.models.OpportunityPacket`,
  from `dababiyoda/daleobanks` @ `829c5f2810776bef65d6ea108800a3516c9f4c2b`.
- `wire_venture_assessment.json` — output of
  `services.wealthmachine_client.WealthMachineClient._evaluate_mock()` (the
  deterministic scorer that mirrors the WealthMachineIntelligence engine contract,
  including the adversarial committee from `services/adversarial_cases.py`)
  serialized with `assessment_to_wire()`, same commit. The committee module is
  mirrored field-for-field from `dababiyoda/wealthmachineintelligence`
  @ `6549984a22a171f68b268b775f19192aee599609` (`src/services/adversarial.py`).

The scenario content (NEMT broker-dispute evidence) tracks the planned `ivio_nemt`
proving-ground organ in `identity/organ-registry.yaml`.

Regeneration: clone both repos at the commits above and re-run the capture snippet
recorded in the Phase Zero PR description. Changing these files by hand breaks the
"executable evidence" rule in `docs/CANONICAL_EXECUTION_ORDER.md`.
